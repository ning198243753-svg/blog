# ============================================================
# 后端镜像
#
# 【为什么用多阶段构建】
# 最终镜像里只有运行需要的东西。构建期用到的编译器、
# 头文件、pip 缓存全部留在前一阶段被丢弃 ——
# 3Mbps 带宽下镜像每小 10MB 都是省下来的传输时间。
#
# 【为什么基础镜像选 slim 而不是 alpine】
# alpine 用 musl libc，而 bcrypt 与 Pillow 都是带 C 扩展的包，
# musl 下需要现场编译（要装 gcc、rust 工具链），
# 结果是构建更慢、镜像未必更小，还多一类「本地能跑、容器里报错」的风险。
# slim 是 Debian 系，有预编译 wheel，pip install 直接拿二进制。
# ============================================================

FROM python:3.12-slim AS base

# 【为什么必须设这两个】
# PYTHONDONTWRITEBYTECODE：容器里 .pyc 没有复用价值（镜像层是只读的），
#   写了只是白白增加层大小。
# PYTHONUNBUFFERED：不设的话 Python 会缓冲 stdout，
#   而容器日志正是靠 stdout —— 结果是 `docker logs` 看不到实时日志，
#   排查问题时会以为「服务没打日志」，实际只是被缓冲住了。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# ---- 依赖层：单独一层，利用 Docker 层缓存 ----
# 【为什么先 COPY requirements.txt 再装依赖】
# Docker 按层缓存，只有这一层的内容变化才会重新执行 pip install。
# 如果写成 COPY . . 之后再 pip install，那么每次改一行 Python 代码
# 都会让依赖层失效并重装全部依赖 —— 在 3Mbps 的机器上这很要命。
COPY requirements.txt ./

# 【为什么预先装好所有依赖而不是分开】
# 一次装完，减少层数。--no-cache-dir 见上面的 PIP_NO_CACHE_DIR。
RUN pip install --no-cache-dir -r requirements.txt

# ---- 应用代码 ----
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# 【为什么不把 tests/ 拷进镜像】
# 生产容器里跑测试套件没有意义，而那些脚本里有
# 「清空全部表」这类破坏性操作（早期 test_foreign_keys.py 就干过）。
# 让它们不存在于生产环境里，是最简单也最可靠的防护。
#
# 需要跑测试时在本地跑，或用单独的测试镜像。

# 数据目录（数据库 / 上传图片 / 日志）。
# 这个目录在 compose 里会被卷覆盖，这里建出来只是为了
# 「不带卷直接 docker run」时也有地方可写。
RUN mkdir -p /data/db /data/uploads /data/logs

# 【为什么不用 root 跑应用】
# 容器逃逸需要先拿到容器内的权限。以 root 运行意味着
# 一旦应用被攻破（比如某个依赖有 RCE），攻击者直接拿到
# 容器内 root —— 离逃逸只差一个内核漏洞。
# 这里建一个普通用户，代价是数据目录要改属主。
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app /data
USER appuser

EXPOSE 8000

# 健康检查交给 compose 的 healthcheck 定义（见 docker-compose.yml），
# 这里不重复，避免两处不一致时不知道该信哪个。

# 【关于 --proxy-headers 与 --forwarded-allow-ips】
#
# --proxy-headers 让 uvicorn 信任 X-Forwarded-For / X-Forwarded-Proto，
# 这样应用里看到的客户端 IP 和协议才是真实的（而不是 Nginx 容器的 IP 和 http）。
#
# --forwarded-allow-ips "*" 表示「信任任何来源的转发头」。
# 这在这里是安全的，前提是：**后端容器不对公网暴露端口**
# （docker-compose.yml 里 backend 没有 ports 映射，只在内网被 nginx 访问）。
#
# 如果哪天给 backend 加了 "ports: 8000:8000"，这个配置就会立刻变成漏洞：
# 任何人直连 8000 并伪造 X-Forwarded-For 就能冒充任意 IP ——
# 限流、审计日志、封禁全部失效。
# 加端口映射时必须同时把这里改成 Nginx 容器的内网地址。
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
