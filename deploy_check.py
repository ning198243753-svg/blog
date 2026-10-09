"""检查部署配置之间的**一致性**

【为什么需要这个检查】
Docker 配置最典型的故障不是「语法错」——那些启动时就会报错，
一眼能看出来。真正麻烦的是**多处配置之间的约定不一致**：

  应用写 /data/db/blog.db，卷挂在 /data/db      → 看起来对
  但 compose 里环境变量写的是相对路径 ./data/db  → 实际写到容器可写层

这种问题在启动时不报错、健康检查也能通过，
只有等到「容器重建后数据全没了」才会暴露 ——
而那时你已经在上面存了几周的文章。

所以这里把「必须一致的约定」逐条自动比对。
运行方式：python deploy_check.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

problems: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def note(msg: str) -> None:
    notes.append(msg)


def read(rel: str) -> str:
    path = ROOT / rel
    if not path.exists():
        fail(f"缺少文件：{rel}")
        return ""
    return path.read_text(encoding="utf-8")


def read_lines(rel: str) -> str:
    """读取文件但去掉注释行

    【为什么需要这个】
    检查配置时如果用纯字符串搜索，注释里提到的内容会被误判成实际配置。
    这里就踩过一次：修正注释里写了「之前是 pnpm@latest，改成 corepack enable」，
    结果检查继续报「仍在用 pnpm@latest」—— 报的是注释。

    这类误判的危害不只是「烦」：一旦你开始习惯性地忽略某条检查，
    它真正报警时你也会忽略。
    """
    text = read(rel)
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        # 跳过各类注释
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        kept.append(line)
    return "\n".join(kept)


compose = read("docker-compose.yml")
compose_code = read_lines("docker-compose.yml")
backend_dockerfile = read("backend/Dockerfile")
backend_dockerfile_code = read_lines("backend/Dockerfile")
frontend_dockerfile = read("frontend/Dockerfile")
frontend_dockerfile_code = read_lines("frontend/Dockerfile")
nginx_conf = read("nginx/nginx.conf")
nginx_conf_code = read_lines("nginx/nginx.conf")
deploy = read("deploy.sh")
deploy_code = read_lines("deploy.sh")
env_example = read("backend/.env.example")

print("=" * 66)
print("部署配置一致性检查")
print("=" * 66)

# --------------------------------------------------------------------
print("\n--- 1. 数据路径：应用写的路径 = 卷挂载的路径 ---")
# --------------------------------------------------------------------

# compose 里 backend 的 DATABASE_URL
m = re.search(r"DATABASE_URL:\s*(\S+)", compose_code)
compose_db_url = m.group(1) if m else None
print(f"  compose 的 DATABASE_URL = {compose_db_url}")

if compose_db_url:
    # sqlite:////data/db/blog.db → 容器内路径 /data/db/blog.db
    # 【为什么要 4 个斜杠】SQLAlchemy 的格式是 sqlite://<host><path>，
    # 绝对路径需要空 host + 绝对路径 = sqlite:////data/...
    # 写成 3 个斜杠（sqlite:///data/db）会被当成相对路径 data/db。
    if not compose_db_url.startswith("sqlite:////"):
        fail(
            f"compose 的 DATABASE_URL 不是绝对路径：{compose_db_url}\n"
            "     期望 sqlite:////data/db/blog.db（4 个斜杠 = 空 host + 绝对路径）\n"
            "     3 个斜杠会被当成相对路径，数据会写进容器可写层，重建即丢失。"
        )
    else:
        db_path = "/" + compose_db_url[len("sqlite:////"):]
        print(f"  解析出的容器内路径 = {db_path}")

        # 卷挂载点
        if "blog_data:/data" in compose:
            print("  卷挂载 = blog_data:/data")
            if not db_path.startswith("/data/"):
                fail(f"数据库路径 {db_path} 不在卷挂载点 /data 之下")
            else:
                note(f"数据库 {db_path} 位于持久卷内")
        else:
            fail("compose 里找不到 blog_data:/data 卷挂载")

# UPLOAD_DIR
m = re.search(r"UPLOAD_DIR:\s*(\S+)", compose_code)
print(f"  compose 的 UPLOAD_DIR = {m.group(1) if m else '(未设置)'}")
if not m:
    fail("compose 未设置 UPLOAD_DIR，应用会用默认值（相对路径），图片会写进容器可写层")
elif not m.group(1).startswith("/data/"):
    fail(f"UPLOAD_DIR={m.group(1)} 不在卷内，图片会在容器重建后丢失")
else:
    note("上传目录位于持久卷内")

# --------------------------------------------------------------------
print("\n--- 2. Nginx 读图片的路径 = 卷挂载点 ---")
# --------------------------------------------------------------------

# nginx.conf 里的 alias
aliases = re.findall(r"alias\s+(\S+);", nginx_conf_code)
print(f"  nginx.conf 里的 alias: {aliases}")

for a in aliases:
    if not a.startswith("/data/"):
        fail(f"alias {a} 不在 /data 之下")
    elif "blog_data:/data" not in compose:
        fail(f"alias {a} 依赖 /data，但 compose 里没有挂载 blog_data:/data")
    else:
        note(f"alias {a} 与卷挂载一致")

# nginx 容器是否挂了 data 卷
if re.search(r"blog_data:/data:ro", compose_code):
    print("  nginx 已挂载 blog_data:/data:ro")
    # 只读是对的：Nginx 只需要读图片
    note("Nginx 以只读方式挂载数据卷（正确：它不需要写）")
else:
    fail("nginx 未挂载 blog_data 卷，/uploads/ 会返回 404")

# --------------------------------------------------------------------
print("\n--- 3. 前端产物：构建服务输出的位置 = Nginx 读取的位置 ---")
# --------------------------------------------------------------------

if "frontend_dist:/export" in compose_code:
    note("构建服务把产物导出到 frontend_dist 卷的 /export")
else:
    fail("构建服务未挂载 frontend_dist:/export")

if "frontend_dist:/usr/share/nginx/html:ro" in compose_code:
    note("Nginx 从 frontend_dist 卷读取静态文件（只读）")
else:
    fail("Nginx 未挂载 frontend_dist 到 /usr/share/nginx/html")

# 构建命令是否真的复制了文件
if "cp -r /dist/. /export/" in compose_code:
    note("构建命令会把 dist 内容复制进共享卷")
else:
    fail("构建服务没有把产物复制进共享卷（只构建不导出，Nginx 会读到空目录）")

# --------------------------------------------------------------------
print("\n--- 4. 上传体积上限：Nginx ≥ 应用 ---")
# --------------------------------------------------------------------

# Nginx 的 client_max_body_size
cms = re.findall(r"client_max_body_size\s+(\d+)([mk]);", nginx_conf_code, re.IGNORECASE)
nginx_limits = [int(n) * (1024 if u.lower() == "k" else 1024 * 1024) for n, u in cms]
print(f"  nginx 的 client_max_body_size: {cms}")

# 应用的上限
app_limit_mb = None
m = re.search(r"UPLOAD_MAX_SIZE_MB=(\d+)", env_example)
if m:
    app_limit_mb = int(m.group(1))
    print(f"  应用的 upload_max_size_mb = {app_limit_mb}（来自 .env.example）")

if nginx_limits and app_limit_mb:
    app_bytes = app_limit_mb * 1024 * 1024
    max_nginx = max(nginx_limits)
    if max_nginx < app_bytes:
        fail(
            f"Nginx 上限（{max_nginx // 1024 // 1024}MB）小于应用上限（{app_limit_mb}MB）。\n"
            "     后果：较大的图片会被 Nginx 直接返回 413，请求到不了 FastAPI，\n"
            "     应用层精心写的 40005 错误码永远不会出现，用户看到的是空白页或通用错误。"
        )
    else:
        note(
            f"Nginx 上限 {max_nginx // 1024 // 1024}MB ≥ 应用上限 {app_limit_mb}MB（正确：Nginx 要留出 multipart 包装余量）"
        )

# --------------------------------------------------------------------
print("\n--- 5. Cookie 安全标记 ---")
# --------------------------------------------------------------------

if re.search(r'COOKIE_SECURE:\s*"true"', compose_code):
    note("compose 强制 COOKIE_SECURE=true（生产走 HTTPS，正确）")
elif re.search(r"COOKIE_SECURE:\s*\"?false", compose):
    fail(
        "compose 把 COOKIE_SECURE 设成了 false。\n"
        "     后果：会话 Cookie 没有 Secure 标记，任何 http 请求都会明文带上它。\n"
        "     本项目用签名 Cookie 存会话（ADR-03），泄露即等于账号被盗。"
    )
else:
    fail("compose 未显式设置 COOKIE_SECURE，会沿用 .env 的值（本地开发用的 false）")

# --------------------------------------------------------------------
print("\n--- 6. 后端端口是否意外暴露 ---")
# --------------------------------------------------------------------

# 找 backend 服务块
backend_block = re.search(r"\n  backend:\n(.*?)(?=\n  \w+:\n|\nvolumes:)", compose_code, re.DOTALL)
if backend_block:
    body = backend_block.group(1)
    if re.search(r"^\s+ports:", body, re.MULTILINE):
        fail(
            "backend 服务暴露了 ports。\n"
            "     后果一：绕过 Nginx 的 HTTPS，用户可能通过 http 访问\n"
            "     后果二：Dockerfile 里 --forwarded-allow-ips \"*\" 变成漏洞 ——\n"
            "             任何人可伪造 X-Forwarded-For 冒充任意 IP"
        )
    else:
        note("backend 未暴露端口（只在内网被 nginx 访问，正确）")
else:
    fail("无法解析 compose 里的 backend 服务块")

# --------------------------------------------------------------------
print("\n--- 7. Nginx 的关键 location ---")
# --------------------------------------------------------------------

checks = [
    (r"try_files\s+\$uri\s+\$uri/\s+/index\.html", "SPA 回退（history 模式必需，ADR-07）"),
    (r"location\s+/api/", "/api 转发到后端"),
    (r"proxy_pass\s+http://blog_backend", "proxy_pass 指向 upstream"),
    (r"upstream\s+blog_backend", "upstream 定义"),
    (r"server\s+backend:8000", "upstream 指向 compose 服务名 backend"),
    (r"location\s+~?\*?\s*/uploads/", "/uploads 由 Nginx 直接返回（ADR-02）"),
    (r"location\s+=?\s*/assets/", "/assets 长期缓存"),
    (r"location\s+=\s*/index\.html", "index.html 不缓存"),
    (r"gzip\s+on", "开启 gzip"),
    (r"listen\s+443\s+ssl", "HTTPS 监听"),
    (r"return\s+301\s+https://", "HTTP 跳转 HTTPS"),
]

for pattern, desc in checks:
    if re.search(pattern, nginx_conf_code):
        note(f"配置包含：{desc}")
    else:
        fail(f"nginx.conf 缺少：{desc}（模式 {pattern}）")

# index.html 的 no-cache 是否真的在那一段
if re.search(r"location\s+=\s*/index\.html\s*\{[^}]*no-cache", nginx_conf_code, re.DOTALL):
    note("index.html 确实设置了 no-cache")
else:
    fail("index.html 的 location 里没有 no-cache（部署新版本后用户会看到旧页面）")

# --------------------------------------------------------------------
print("\n--- 8. 多阶段构建是否真的丢弃了构建依赖 ---")
# --------------------------------------------------------------------

if "FROM python:3.12-slim AS base" in backend_dockerfile_code:
    note("后端基础镜像 python:3.12-slim")
if "USER appuser" in backend_dockerfile_code:
    note("后端以非 root 用户运行")
else:
    fail("后端容器以 root 运行（一旦应用被攻破，攻击者直接拿到容器内 root）")

if "AS builder" in frontend_dockerfile_code and "AS dist" in frontend_dockerfile_code:
    note("前端用多阶段构建，node_modules 不会进入产物阶段")
else:
    fail("前端缺少多阶段构建，产物阶段可能包含 node_modules（几百 MB）")

# 前端构建是否用 frozen-lockfile
if "--frozen-lockfile" in frontend_dockerfile_code:
    note("前端用 --frozen-lockfile（保证容器内装的依赖与本地一致）")
else:
    fail(
        "前端未使用 --frozen-lockfile。\n"
        "     后果：容器里可能装上锁文件之外的新版本依赖 ——\n"
        "     即生产跑着一个从未被测试过的组合。"
    )

# package.json 是否声明 packageManager（与 Dockerfile 的 corepack 配合）
pkg = read("frontend/package.json")
if '"packageManager"' in pkg:
    m = re.search(r'"packageManager":\s*"([^"]+)"', pkg)
    note(f"package.json 声明了 packageManager = {m.group(1) if m else '?'}")
else:
    fail(
        "package.json 未声明 packageManager。\n"
        "     后果：Dockerfile 里的 corepack 会装上不确定的版本，\n"
        "     今天构建和三个月后构建可能用不同的 pnpm，行为不一致。"
    )

# Dockerfile 里是否还写着 @latest
if "pnpm@latest" in frontend_dockerfile_code:
    fail(
        "Dockerfile 里仍写着 pnpm@latest。\n"
        "     构建不可复现：同样的代码在不同时间构建出的依赖树可能不同。\n"
        "     应该改用 package.json 的 packageManager 字段。"
    )

# --------------------------------------------------------------------
print("\n--- 9. .dockerignore 是否排除了数据与密钥 ---")
# --------------------------------------------------------------------

for rel, musts in [
    ("backend/.dockerignore", ["data/", ".env", ".venv/"]),
    ("frontend/.dockerignore", ["node_modules/", "dist/"]),
]:
    content = read(rel)
    if not content:
        continue
    for must in musts:
        if must in content:
            note(f"{rel} 排除了 {must}")
        else:
            fail(
                f"{rel} 未排除 {must}\n"
                "     后果：这些内容会被打进构建上下文，构建变慢，\n"
                "     数据或密钥可能进入镜像层（镜像层不可变，删不干净）。"
            )

# --------------------------------------------------------------------
print("\n--- 10. 部署脚本的基本健壮性 ---")
# --------------------------------------------------------------------

if "set -euo pipefail" in deploy_code:
    note("deploy.sh 用了 set -euo pipefail（命令失败会中止）")
else:
    fail(
        "deploy.sh 未用 set -euo pipefail。\n"
        "     后果：构建失败后脚本会继续执行，最后用旧镜像启动 ——\n"
        "     你以为部署成功了，实际跑的还是上个版本。"
    )

if "__DOMAIN__" in nginx_conf_code:
    note("nginx.conf 保留了 __DOMAIN__ 占位符（部署脚本会检查并拒绝未替换的情况）")
    if "__DOMAIN__" in deploy_code:
        note("deploy.sh 会检查域名是否已替换")
    else:
        fail("deploy.sh 未检查域名占位符，可能带着 __DOMAIN__ 启动 Nginx")
else:
    note("nginx.conf 中的域名已替换（本地已配置过）")

# 换行符检查
for rel in ["deploy.sh", "backend/Dockerfile", "frontend/Dockerfile", "nginx/nginx.conf", "docker-compose.yml"]:
    path = ROOT / rel
    if path.exists():
        raw = path.read_bytes()
        if b"\r\n" in raw:
            fail(
                f"{rel} 含 CRLF 行尾。\n"
                "     shell 脚本会报 `syntax error near unexpected token`（且不提行尾）；\n"
                "     Dockerfile 的续行符会失效；\n"
                "     .env 的每个值会多一个不可见字符。\n"
                "     检查 .gitattributes 是否生效。"
            )
        else:
            note(f"{rel} 是 LF 行尾")

# --------------------------------------------------------------------

print()
print("=" * 66)
print(f"检查通过 {len(notes)} 项")
if problems:
    print(f"\n发现 {len(problems)} 个问题：\n")
    for i, p in enumerate(problems, 1):
        print(f"  {i}. {p}")
    print()
    sys.exit(1)

print("没有发现问题。")
print()
print("【注意】这些检查只能证明「配置之间自洽」，")
print("不能证明「容器能跑起来」—— 那需要在有 Docker 的机器上验证。")
print("=" * 66)
