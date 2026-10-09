#!/usr/bin/env bash
# ============================================================
# 部署脚本
#
# 【这个脚本的设计原则】
# 每一步都要能自证结果。部署最怕的不是失败，而是
# 「看起来成功了但实际没生效」—— 那时你会去排查应用代码，
# 而问题其实在部署环节。
#
# 所以这里的每一段都在关键节点做**验证**：
# 构建后检查产物存在、启动后检查健康检查通过、
# 部署后检查页面真的能访问。
#
# 【用法】
#   ./deploy.sh init      首次部署（含建库、建管理员）
#   ./deploy.sh update    更新代码后重新部署
#   ./deploy.sh rollback  回滚到上一个版本
#   ./deploy.sh status    查看当前状态
#   ./deploy.sh backup    备份数据库与上传文件
#
# 【前置条件】
# 服务器上已装 Docker 与 Docker Compose 插件，
# 且当前目录是仓库根目录，且 backend/.env 已按 .env.example 配好。
# ============================================================

set -euo pipefail

# 【为什么用 set -euo pipefail】
# -e：任何命令失败立即中止。不加的话，构建失败后脚本会继续
#     往下走，最后用旧镜像启动 —— 你以为部署成功了，
#     实际跑的还是上个版本。
# -u：引用未定义变量时报错。拼错变量名会立刻暴露，
#     而不是变成空字符串继续执行。
# -o pipefail：管道中任何一段失败都算失败。
#     否则 `cmd | tail` 里 cmd 失败会被 tail 的成功掩盖。

cd "$(dirname "$0")"

# ---- 配置 ----
DOMAIN="${DOMAIN:-}"
# 【为什么 COMPOSE 是数组而不是字符串】
# 最初写的是 COMPOSE="docker compose"，然后到处写 "${COMPOSE[@]}" up。
# 那样在 `"${COMPOSE[@]}" up` 这种位置能工作（shell 会把展开结果按空格
# 再切一次词），但一放进 $(...) 或引号里就会变成
# 「找不到名为 'docker compose' 的命令」——
# 因为那时整个字符串被当成一个命令名。
#
# 数组形式 "${COMPOSE[@]}" 在任何位置都正确，
# 而且参数里的空格或特殊字符不会被错误切分。
COMPOSE=(docker compose)
BACKUP_DIR="./backups"
# 保留多少个备份。磁盘有限，不限制的话备份会撑满磁盘 ——
# 而磁盘满的表现是「应用突然写不了数据库」，很难联想到备份。
KEEP_BACKUPS=10

# ---- 输出辅助 ----
RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[0;33m'; NC=$'\033[0m'
info()  { echo "${GREEN}[信息]${NC} $*"; }
warn()  { echo "${YELLOW}[注意]${NC} $*"; }
error() { echo "${RED}[错误]${NC} $*" >&2; }
die()   { error "$*"; exit 1; }

step() {
  echo
  echo "=============================================================="
  echo ">> $*"
  echo "=============================================================="
}

# ---- 前置检查 ----
check_prerequisites() {
  step "检查前置条件"

  command -v docker >/dev/null 2>&1 || die "未找到 docker。请先安装 Docker。"
  info "docker 已安装：$(docker --version)"

  # 【为什么要专门检查 compose 插件】
  # 老教程里用的是独立的 docker-compose 命令（带连字符），
  # 而新版 Docker 用的是插件形式（docker compose，带空格）。
  # 两者不通用，混用会报「unknown command」。
  "${COMPOSE[@]}" version >/dev/null 2>&1 || die "未找到 docker compose 插件。需要 Docker 20.10+ 或单独安装 compose 插件。"
  info "compose 已安装：$("${COMPOSE[@]}" version --short 2>/dev/null || echo 'ok')"

  [ -f "./docker-compose.yml" ] || die "未找到 docker-compose.yml，请在仓库根目录运行本脚本。"
  [ -f "./backend/.env" ] || die "未找到 backend/.env。请先复制 .env.example 并填写 SECRET_KEY 与 ADMIN_PASSWORD。"
  [ -f "./nginx/nginx.conf" ] || die "未找到 nginx/nginx.conf。"

  # 【检查 .env 里的占位值是否被替换】
  # 忘了改 SECRET_KEY 的后果很严重：任何人都能用这个
  # 公开在 .env.example 里的值伪造登录 Cookie。
  if grep -q "change-me-generate-with-secrets-token-urlsafe-48" ./backend/.env; then
    die "backend/.env 里的 SECRET_KEY 仍是示例值。任何人都能用它伪造登录 Cookie。
     生成方式：python3 -c \"import secrets; print(secrets.token_urlsafe(48))\""
  fi

  if ! grep -qE '^ADMIN_PASSWORD=.+' ./backend/.env; then
    die "backend/.env 里未设置 ADMIN_PASSWORD。"
  fi

  # 域名：nginx.conf 里的占位符必须被替换
  if ! grep -q "__DOMAIN__" ./nginx/nginx.conf; then
    info "nginx.conf 中的域名已替换"
  else
    die "nginx/nginx.conf 里仍有 __DOMAIN__ 占位符。
     请把两处 __DOMAIN__ 替换为你的真实域名，并确保：
       - 该域名的 A 记录已指向本服务器 IP
       - 且证书文件已存在（首次部署见 docs 中的证书申请步骤）"
  fi

  # 【.env 的权限检查】
  # 它含 SECRET_KEY 与管理员密码。
  perms=$(stat -c '%a' ./backend/.env 2>/dev/null || stat -f '%Lp' ./backend/.env 2>/dev/null || echo "")
  if [ -n "$perms" ] && [ "$perms" != "600" ]; then
    warn "backend/.env 权限是 $perms，建议改为 600：chmod 600 backend/.env"
  fi

  info "前置检查通过"
}

# ---- 备份 ----
do_backup() {
  step "备份数据库与上传文件"

  mkdir -p "$BACKUP_DIR"
  local stamp
  stamp=$(date +%Y%m%d-%H%M%S)
  local target="$BACKUP_DIR/$stamp"
  mkdir -p "$target"

  # 【为什么必须通过容器来做备份，而不是直接拷文件】
  # SQLite 开了 WAL 模式（见 ADR），数据分散在 .db、.db-wal、.db-shm
  # 三个文件里。在应用运行时直接 cp 这三个文件，可能拿到
  # 「主库是旧的、WAL 是新的」这种不一致的组合 ——
  # 恢复到这种备份上，数据会缺一部分且难以察觉。
  #
  # VACUUM INTO 让 SQLite 自己生成一份一致的单文件快照，
  # 它会在事务边界上操作，不受并发写入影响。
  if "${COMPOSE[@]}" ps --status running --quiet backend 2>/dev/null | grep -q .; then
    info "后端正在运行，用 SQLite 的 VACUUM INTO 生成一致快照"
    "${COMPOSE[@]}" exec -T backend python -c "
import sqlite3, os, sys
src = '/data/db/blog.db'
dst = '/data/db/backup-snapshot.db'
if os.path.exists(dst):
    os.remove(dst)
con = sqlite3.connect(src)
con.execute(f\"VACUUM INTO '{dst}'\")
con.close()
print('快照大小:', os.path.getsize(dst), '字节')
" || die "生成数据库快照失败"

    # 把快照从容器里取出来
    local cid
    cid=$("${COMPOSE[@]}" ps -q backend)
    docker cp "$cid:/data/db/backup-snapshot.db" "$target/blog.db" || die "导出快照失败"
    "${COMPOSE[@]}" exec -T backend rm -f /data/db/backup-snapshot.db || true
  else
    # 后端没运行：这时没有并发写入，直接拷三个文件是安全的
    warn "后端未运行，直接复制数据库文件"
    for f in blog.db blog.db-wal blog.db-shm; do
      if [ -f "backend/data/db/$f" ]; then
        cp "backend/data/db/$f" "$target/"
      fi
    done
  fi

  # 上传的图片
  if [ -d "./backend/data/uploads" ]; then
    info "备份上传的图片"
    tar -czf "$target/uploads.tar.gz" -C ./backend/data uploads 2>/dev/null || warn "uploads 备份失败（可能目录为空）"
  fi

  # 【记录当前的代码版本】
  # 回滚时需要知道「回到哪一个 commit」。
  # 只备份数据而不记录版本，恢复出来的可能是
  # 「新版本的数据 + 旧版本的代码」这种错配组合。
  if command -v git >/dev/null 2>&1 && [ -d .git ]; then
    git rev-parse HEAD > "$target/commit.txt" 2>/dev/null || true
    git log -1 --pretty=format:'%H %ad %s' --date=short > "$target/commit-info.txt" 2>/dev/null || true
  fi

  info "备份完成：$target"
  du -sh "$target" 2>/dev/null || true

  # 清理旧备份
  local count
  count=$(find "$BACKUP_DIR" -maxdepth 1 -mindepth 1 -type d | wc -l)
  if [ "$count" -gt "$KEEP_BACKUPS" ]; then
    info "清理旧备份（保留最近 $KEEP_BACKUPS 个）"
    find "$BACKUP_DIR" -maxdepth 1 -mindepth 1 -type d | sort | head -n -"$KEEP_BACKUPS" | xargs rm -rf
  fi
}

# ---- 构建 ----
do_build() {
  step "构建镜像"

  info "构建后端镜像（多阶段，最终镜像不含构建工具）"
  # 【为什么要 --pull】
  # 拉取基础镜像的最新版本。不加的话会用本机缓存的旧版本，
  # 而基础镜像里的安全更新就拿不到了。
  "${COMPOSE[@]}" build --pull backend || die "后端镜像构建失败"

  info "构建前端产物（这一步在 4G 内存机器上约占 1-2 分钟）"
  # 【为什么用 run --rm 而不是 up】
  # 这个服务做完就退出，不需要常驻。
  # --rm 用完即删，避免留下一堆已退出的容器。
  "${COMPOSE[@]}" --profile build run --rm frontend-build || die "前端构建失败"

  # 【验证产物真的出来了】
  # 不验证的话，构建失败可能只在日志里，而后续步骤
  # 依然会成功启动 Nginx —— 结果是部署了一个空白站点。
  info "验证前端产物"
  local count
  count=$("${COMPOSE[@]}" run --rm --entrypoint sh nginx -c 'ls /usr/share/nginx/html 2>/dev/null | wc -l' 2>/dev/null || echo 0)
  if [ "${count:-0}" -lt 2 ]; then
    die "前端产物为空或缺少文件（只有 $count 个条目）。
     预期至少有 index.html 与 assets 目录。
     请检查上面 frontend-build 的输出。"
  fi
  info "前端产物已就位（$count 个顶层条目）"

  info "构建完成"
}

# ---- 启动 ----
do_up() {
  step "启动服务"

  info "启动 nginx（backend 由后续步骤启动）"
  "${COMPOSE[@]}" up -d nginx

  info "启动 backend"
  "${COMPOSE[@]}" up -d backend

  info "等待后端健康检查通过（最多 60 秒）"
  local waited=0
  while [ $waited -lt 60 ]; do
    # 【为什么要看 health 而不是「容器在不在运行」】
    # 容器启动成功不等于应用能提供服务。
    # 应用可能在启动过程中崩溃（比如迁移失败），
    # 而 docker 会因为 restart 策略不断重启它 ——
    # 只看「是否运行」会看到一个永远在重启的容器。
    local health
    health=$("${COMPOSE[@]}" ps --format json backend 2>/dev/null | grep -o '"Health":"[^"]*"' | cut -d'"' -f4 || echo "")
    if [ "$health" = "healthy" ]; then
      info "后端健康检查通过"
      return 0
    fi
    sleep 3
    waited=$((waited + 3))
    printf "."
  done

  echo
  error "后端在 60 秒内未通过健康检查。当前状态："
  "${COMPOSE[@]}" ps
  echo
  error "后端最近日志："
  "${COMPOSE[@]}" logs --tail=50 backend
  die "启动失败。请根据上面的日志排查。"
}

# ---- 首次初始化 ----
do_init() {
  step "首次初始化"

  do_build
  do_up

  info "建表与迁移"
  "${COMPOSE[@]}" exec -T backend python -m alembic upgrade head || die "数据库迁移失败"

  info "初始化站点配置与管理员账号"
  # 【为什么要显式调用而不是让应用启动时自动做】
  # 隐式的初始化很难排查：应用启动失败时，
  # 你分不清是「表没建」还是「代码有问题」。
  # 显式调用会在失败时立刻给出清晰的报错。
  "${COMPOSE[@]}" exec -T backend python -m app.init_db || die "初始化失败"

  info "完成。接下来："
  echo "  1. 确认 DNS 已指向本机：  dig +short \$DOMAIN"
  echo "  2. 申请证书（见 docs/部署文档 的证书章节）"
  echo "  3. 重启 nginx 加载证书："
  echo "     ${COMPOSE[*]} restart nginx"
  echo "  4. 访问 https://\$DOMAIN 确认"
}

# ---- 更新 ----
do_update() {
  step "更新部署"

  do_backup

  # 【记录当前版本，供回滚使用】
  if [ -d .git ]; then
    git rev-parse HEAD > "$BACKUP_DIR/.last-deployed" 2>/dev/null || true
  fi

  do_build

  info "应用数据库迁移"
  # 【为什么迁移要在重启应用之前】
  # 新代码可能依赖新表结构。先迁移再启动新代码，
  # 顺序反了会出现「新代码查一个还不存在的表」。
  # 反过来（旧代码 + 新结构）通常也能容忍，
  # 所以这个顺序对短时间的滚动更新更安全。
  "${COMPOSE[@]}" exec -T backend python -m alembic upgrade head || die "数据库迁移失败"

  info "重启服务"
  do_up

  do_verify

  info "更新完成"
}

# ---- 验证 ----
do_verify() {
  step "验证部署结果"

  local failed=0

  # 1. 容器状态
  info "容器状态："
  "${COMPOSE[@]}" ps

  # 2. 健康检查接口
  # 【为什么验证的是「通过 Nginx 的完整链路」而不是直连后端】
  # 直连后端能通，不代表用户能访问 ——
  # Nginx 配置错误（比如 location 写错）时，
  # 后端一切正常而站点是坏的。
  info "验证 HTTP 链路（经 Nginx）"
  local http_code
  http_code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1/api/health" || echo "000")
  if [ "$http_code" = "200" ]; then
    info "  /api/health 返回 200"
  else
    error "  /api/health 返回 $http_code（预期 200）"
    failed=1
  fi

  # 3. 首页静态文件
  http_code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1/" || echo "000")
  if [ "$http_code" = "200" ] || [ "$http_code" = "301" ]; then
    info "  首页返回 $http_code"
  else
    error "  首页返回 $http_code"
    failed=1
  fi

  # 4. SPA 回退（history 模式的关键）
  http_code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1/some/deep/route" || echo "000")
  if [ "$http_code" = "200" ] || [ "$http_code" = "301" ]; then
    info "  SPA 回退正常（深层路由返回 $http_code）"
  else
    error "  SPA 回退失效：/some/deep/route 返回 $http_code。"
    error "  检查 nginx.conf 里的 try_files \$uri \$uri/ /index.html;"
    failed=1
  fi

  # 5. 如果域名已知，验证 HTTPS
  if [ -n "$DOMAIN" ]; then
    info "验证 HTTPS"
    http_code=$(curl -s -o /dev/null -w '%{http_code}' "https://$DOMAIN/api/health" || echo "000")
    if [ "$http_code" = "200" ]; then
      info "  https://$DOMAIN/api/health 返回 200"
    else
      error "  https://$DOMAIN/api/health 返回 $http_code"
      error "  检查：DNS 是否已生效、证书是否已申请、nginx 是否已重启"
      failed=1
    fi
  else
    warn "未设置 DOMAIN 环境变量，跳过 HTTPS 验证。"
    warn "用法：DOMAIN=你的域名 ./deploy.sh verify"
  fi

  if [ $failed -ne 0 ]; then
    die "验证未通过。请根据上面的错误排查，不要认为部署已成功。"
  fi

  info "全部验证通过"
}

# ---- 回滚 ----
do_rollback() {
  step "回滚"

  if [ ! -f "$BACKUP_DIR/.last-deployed" ]; then
    die "找不到上一个版本的记录（$BACKUP_DIR/.last-deployed）。
     回滚需要知道回到哪个 commit，无法自动完成。
     请手动操作：
       git log --oneline          # 找到要回到的版本
       git checkout <commit>
       ./deploy.sh update"
  fi

  local target
  target=$(cat "$BACKUP_DIR/.last-deployed")
  warn "将从当前版本回滚到：$target"
  echo
  read -r -p "确认回滚？这会重建镜像并重启服务 (yes/no): " confirm
  if [ "$confirm" != "yes" ]; then
    info "已取消"
    return 0
  fi

  # 【回滚前先备份当前状态】
  # 回滚本身也可能因为别的原因失败，那时你会希望
  # 至少还有一份「回滚前」的数据。
  do_backup

  if [ -d .git ]; then
    git stash push -m "rollback-$(date +%s)" 2>/dev/null || warn "没有未提交的改动"
    git checkout "$target" || die "切换到 $target 失败。请先处理未提交的改动。"
  fi

  do_build

  # 【回滚时的迁移要特别小心】
  # 如果新版本包含数据库迁移，旧代码可能不认识新的表结构。
  # 这里**不自动 downgrade** —— 降级迁移可能丢数据，
  # 而且很多迁移的 downgrade 写得并不严谨。
  warn "注意：数据库迁移不会自动回退。"
  warn "如果新版本包含结构变更，旧代码可能与当前结构不兼容。"
  warn "需要回退迁移时请手工执行："
  warn "  ${COMPOSE[*]} exec backend python -m alembic downgrade -1"

  do_up
  do_verify

  info "回滚完成。如需恢复数据，用备份目录里的文件（见 docs）。"
}

# ---- 状态 ----
do_status() {
  step "当前状态"

  # 【为什么 status 也要检查 docker 是否存在】
  # 最初这里直接调 "${COMPOSE[@]}" ps，结果在没装 docker 的机器上
  # 只打印一行 `docker: command not found` —— 那是 shell 的原始报错，
  # 既不说清楚是什么问题，也不说该怎么办。
  #
  # status 的用途正是「出问题时先看一眼」，所以它自己更不能
  # 用一句看不懂的报错把人挡住。
  if ! command -v docker >/dev/null 2>&1; then
    error "未找到 docker。"
    echo
    info "在没有 Docker 的机器上仍然可以看到这些信息："
    echo
    info "项目文件："
    ls -la "$BACKUP_DIR" 2>/dev/null | head -6 || echo "  （没有备份目录）"
    echo
    info "磁盘占用："
    df -h . 2>/dev/null | tail -1 || true
    echo
    warn "容器状态需要 Docker。请在本机或服务器上运行本命令。"
    return 0
  fi

  "${COMPOSE[@]}" ps
  echo
  info "磁盘占用："
  df -h / | tail -1
  echo
  if command -v du >/dev/null 2>&1; then
    info "数据卷占用："
    docker system df 2>/dev/null || true
  fi
  echo
  info "最近的备份："
  ls -lt "$BACKUP_DIR" 2>/dev/null | head -6 || echo "  （还没有备份）"
}

# ---- 入口 ----
case "${1:-}" in
  init)     check_prerequisites; do_init ;;
  update)   check_prerequisites; do_update ;;
  build)    check_prerequisites; do_build ;;
  up)       check_prerequisites; do_up ;;
  verify)   check_prerequisites; do_verify ;;
  rollback) check_prerequisites; do_rollback ;;
  backup)   check_prerequisites; do_backup ;;
  status)   do_status ;;
  *)
    cat <<EOF
用法：./deploy.sh <命令>

  init       首次部署（构建 + 启动 + 建库 + 建管理员）
  update     更新代码后重新部署（自动备份 + 迁移 + 验证）
  build      只构建镜像，不启动
  up         只启动服务
  verify     验证部署结果（容器状态 + HTTP 链路 + SPA 回退）
  rollback   回滚到上一次 update 前的版本
  backup     备份数据库与上传文件
  status     查看当前状态与磁盘占用

环境变量：
  DOMAIN=example.com    用于 HTTPS 验证，例如：
                        DOMAIN=blog.example.com ./deploy.sh verify
EOF
    exit 1
    ;;
esac
