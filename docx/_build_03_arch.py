# -*- coding: utf-8 -*-
"""文档 03 · 系统架构设计"""
import sys
sys.path.insert(0, r"E:\project\blog\docx")
from _docbuild import DocBuilder

b = DocBuilder(
    r"E:\project\blog\docx\03-系统架构设计-v1.0.docx",
    "系统架构设计",
    "分层 · 目录 · 部署拓扑 · 关键流程",
    ["个人博客项目　|　阶段二：设计　|　版本 v1.0　|　日期：2026-10-08",
     "本文档承接 ADR（文档 02）的全部决策，描述系统由哪些部分组成、如何协作、如何部署。"],
)

# ============================================================
b.chapter("1", "架构总览")
b.p("判断标准：读完本章能用一句话讲清「一次页面请求经过了哪些环节」，"
    "并且不看代码就能说出每一层负责什么。")

b.h("1.1 全局结构", 2)
b.snippet([
    "┌──────────────────────────────────────────────────────────────┐",
    "│                        用户浏览器                              │",
    "│   访客：Vue SPA（首页 / 文章 / 标签 / 搜索 / 归档 / 关于）      │",
    "│   作者：Vue SPA（登录 / 文章管理 / 编辑器 / 站点设置）          │",
    "└───────────────────────────┬──────────────────────────────────┘",
    "                            │ HTTPS (443)",
    "┌───────────────────────────▼──────────────────────────────────┐",
    "│                        Nginx（反向代理）                       │",
    "│   /              → 静态文件（Vue 构建产物），try_files 回退     │",
    "│   /api/          → 转发到 FastAPI:8000                        │",
    "│   /uploads/      → 静态图片，直出不经过后端                     │",
    "│   TLS 终止、gzip/brotli 压缩、访问日志                          │",
    "└───────────────────────────┬──────────────────────────────────┘",
    "                            │ HTTP (内部网络)",
    "┌───────────────────────────▼──────────────────────────────────┐",
    "│                     FastAPI 应用（Uvicorn）                    │",
    "│   路由层  Routers    接收请求、参数校验、调用服务、组装响应      │",
    "│   服务层  Services   业务逻辑，不感知 HTTP                      │",
    "│   模型层  Models     数据库表映射（SQLAlchemy）                  │",
    "│   模式层  Schemas    请求/响应结构（Pydantic）                   │",
    "└───────────────────────────┬──────────────────────────────────┘",
    "                            │ SQLAlchemy",
    "┌───────────────────────────▼──────────────────────────────────┐",
    "│              SQLite 数据库文件（WAL 模式）                      │",
    "│              /data/blog.db  ← Docker 数据卷持久化               │",
    "└──────────────────────────────────────────────────────────────┘",
], caption="四个组件、一次 TLS 终止、零跨域。这是 ADR-04「前后端同源」带来的直接简化。")

b.h("1.2 分层职责边界", 2)
b.p("**这是最容易做错的地方：分层不是目录分类，是依赖方向规则。**")
b.table(
    ["层次", "职责", "可以做", "绝对不可以做"],
    [["路由层 Routers", "HTTP 入口", "解析参数、调用服务、返回响应、声明鉴权依赖",
      "**写业务逻辑**、**直接查数据库**"],
     ["服务层 Services", "业务逻辑", "编排多步操作、事务控制、调用多个模型", "引入 `Request` / `HTTPException` 等 HTTP 概念"],
     ["模型层 Models", "数据结构映射", "定义字段、关系、索引", "包含业务判断"],
     ["模式层 Schemas", "接口契约", "定义请求与响应的字段、类型、校验规则", "包含业务逻辑"]],
    widths=[2.6, 2.6, 6.4, 5.5], first_col_bold=True)
b.callout("为什么必须守这条规则：",
          "如果路由层直接写 `db.query(...)`，那么「同一条业务规则」会在多个接口里各写一遍。"
          "改一次需求要改 N 处，且必然漏掉一处。**服务层存在的唯一价值，就是让业务规则只有一份。**",
          kind="warn")

b.h("1.3 约束检查", 2)
b.table(["约束（来自阶段一第 9 章）", "本架构如何满足"],
        [["3Mbps 带宽", "静态文件与图片由 Nginx 直出并压缩；后端只传 JSON；首屏 JS ≤ 150KB（NFR-14）"],
         ["4G 内存", "SQLite 无独立进程；Uvicorn 固定 2 个 worker；合计约 2.1GB，余量约 1.9GB"],
         ["单机部署", "无任何分布式组件；所有服务由一份 Compose 文件管理"],
         ["峰值并发 ≤ 5", "不引入连接池调优、不引入缓存中间件、不做读写分离"],
         ["必须能重建环境", "镜像 + Compose + `.env.example` + 迁移脚本 = 可完整复现（SM-04）"]],
        widths=[4.6, 12.5])

# ============================================================
b.chapter("2", "后端结构设计")
b.h("2.1 目录结构", 2)
b.snippet([
    "backend/",
    "├── app/",
    "│   ├── main.py              # 应用入口：创建 app、挂载路由、注册中间件与异常处理",
    "│   ├── config.py            # 配置读取（pydantic-settings）",
    "│   ├── database.py          # 引擎、会话工厂、get_db 依赖",
    "│   ├── models/              # 模型层：SQLAlchemy 表定义",
    "│   │   ├── __init__.py",
    "│   │   ├── article.py       # 文章",
    "│   │   ├── tag.py           # 标签 + 文章标签关联",
    "│   │   ├── user.py          # 管理员账号",
    "│   │   └── site.py          # 站点配置",
    "│   ├── schemas/             # 模式层：Pydantic 请求/响应结构",
    "│   │   ├── common.py        # 统一响应体、分页结构",
    "│   │   ├── article.py",
    "│   │   ├── tag.py",
    "│   │   └── auth.py",
    "│   ├── services/            # 服务层：业务逻辑（唯一允许写业务规则的地方）",
    "│   │   ├── article_service.py",
    "│   │   ├── tag_service.py",
    "│   │   ├── auth_service.py",
    "│   │   ├── upload_service.py",
    "│   │   └── markdown_service.py   # Markdown 渲染 + XSS 过滤（ADR-06）",
    "│   ├── routers/             # 路由层：HTTP 入口",
    "│   │   ├── public.py        # 公开接口（访客可访问）",
    "│   │   ├── admin.py         # 后台接口（需登录）",
    "│   │   └── auth.py          # 登录 / 注销 / 当前用户",
    "│   ├── core/",
    "│   │   ├── security.py      # 密码哈希、会话校验依赖",
    "│   │   ├── errors.py        # 业务错误码枚举 + 统一异常处理",
    "│   │   └── logging.py       # 日志配置",
    "│   └── utils/",
    "│       ├── slug.py          # 标题转 slug",
    "│       └── image.py         # 图片压缩与格式转换（ADR-02 的前提）",
    "├── alembic/                 # 数据库迁移脚本",
    "│   └── versions/",
    "├── tests/",
    "│   ├── conftest.py          # 测试夹具（临时数据库、测试客户端）",
    "│   ├── test_articles.py",
    "│   ├── test_auth.py",
    "│   └── test_markdown.py",
    "├── alembic.ini",
    "├── requirements.txt",
    "├── .env.example",
    "└── Dockerfile",
], caption="分层的物理体现：目录名即层次名，一眼能看出一个新文件该放哪。")

b.h("2.2 依赖注入与请求生命周期", 2)
b.p("FastAPI 的依赖注入（Dependency Injection）是理解本项目的关键机制，它负责把"
    "「数据库会话」「当前用户」「分页参数」等横切关注点注入到接口函数里。")
b.snippet([
    "# app/database.py",
    "def get_db():",
    "    db = SessionLocal()",
    "    try:",
    "        yield db          # 请求处理完毕后回到这里，执行关闭",
    "    finally:",
    "        db.close()",
    "",
    "# app/core/security.py",
    "def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:",
    "    # 从 Cookie 读取会话标识并校验；失败则抛 401",
    "    ...",
    "",
    "# app/routers/admin.py",
    "@router.post(\"/articles\")",
    "def create_article(",
    "    payload: ArticleCreate,              # 请求体自动校验",
    "    db: Session = Depends(get_db),       # 数据库会话",
    "    user: User = Depends(get_current_user),   # 未登录时自动返回 401",
    "):",
    "    return article_service.create(db, payload, user)",
], caption="接口函数只声明「我需要什么」，不关心「怎么来的」。鉴权因此只需一个 Depends 即可全站生效。")

b.h("2.3 分层调用规则", 2)
b.table(["调用方向", "允许", "说明"],
        [["路由层 → 服务层", "✅", "唯一的标准路径"],
         ["路由层 → 模型层", "❌", "路由不应直接查库，必须经服务层"],
         ["服务层 → 模型层", "✅", "业务逻辑操作数据的正常路径"],
         ["服务层 → 服务层", "✅", "允许，但避免循环依赖"],
         ["模型层 → 任何层", "❌", "模型只描述数据结构"],
         ["路由层 → 模式层", "✅", "用于声明请求/响应类型"]],
        widths=[4.4, 1.6, 11.1])

# ============================================================
b.chapter("3", "前端结构设计")
b.h("3.1 目录结构", 2)
b.snippet([
    "frontend/",
    "├── src/",
    "│   ├── main.ts              # 应用入口：创建 app、挂载 Pinia 与路由",
    "│   ├── App.vue              # 根组件：全局布局（页头 / 内容区 / 页脚）",
    "│   ├── router/",
    "│   │   └── index.ts         # 路由表 + 路由守卫（登录校验）",
    "│   ├── stores/              # Pinia（ADR-05）：只放跨页面共享的状态",
    "│   │   ├── auth.ts          # 登录状态、当前用户",
    "│   │   └── site.ts          # 站点配置（标题、副标题、备案号等）",
    "│   ├── api/                 # 接口调用层",
    "│   │   ├── client.ts        # Axios 实例 + 请求/响应拦截器（ADR-09）",
    "│   │   ├── articles.ts",
    "│   │   ├── tags.ts",
    "│   │   └── auth.ts",
    "│   ├── views/               # 页面组件（与路由一一对应）",
    "│   │   ├── public/          # 访客页面 —— 首屏必须懒加载",
    "│   │   │   ├── HomeView.vue",
    "│   │   │   ├── ArticleView.vue",
    "│   │   │   ├── TagView.vue",
    "│   │   │   ├── ArchiveView.vue",
    "│   │   │   ├── SearchView.vue",
    "│   │   │   ├── AboutView.vue",
    "│   │   │   └── NotFoundView.vue",
    "│   │   └── admin/           # 后台页面 —— 必须懒加载（NFR-14）",
    "│   │       ├── LoginView.vue",
    "│   │       ├── ArticleListView.vue",
    "│   │       ├── ArticleEditView.vue",
    "│   │       └── SettingsView.vue",
    "│   ├── components/          # 可复用组件",
    "│   │   ├── common/          # 通用：分页器、空状态、加载骨架",
    "│   │   ├── article/         # 文章相关：卡片、正文渲染、目录",
    "│   │   └── layout/          # 布局：页头、页脚、侧栏",
    "│   ├── composables/         # 组合式函数：可复用的状态逻辑",
    "│   │   ├── usePagination.ts",
    "│   │   └── useArticleList.ts",
    "│   ├── styles/",
    "│   │   ├── variables.css    # 设计令牌（CSS 变量，为暗色模式预留 —— ADR-08）",
    "│   │   ├── base.css         # 全局重置与基础排版",
    "│   │   └── markdown.css     # 正文样式（作用于 v-html 内容）",
    "│   ├── types/               # TypeScript 类型定义（对应后端 Schemas）",
    "│   └── assets/              # 少量构建期资源（字体、图标）",
    "├── public/                  # 原样复制的静态资源（favicon 等）",
    "├── index.html",
    "├── vite.config.ts           # 含 /api 代理配置（ADR-04 同源开发）",
    "└── package.json",
], caption="views 按 public / admin 分区，是为了让「哪些代码该进访客首屏」一眼可辨。")

b.h("3.2 数据流方向", 2)
b.snippet([
    "组件 (views / components)",
    "   │  调用 composables（复用逻辑）",
    "   ▼",
    "组合式函数 (composables)",
    "   │  调用 api 层",
    "   ▼",
    "接口层 (api/*.ts)",
    "   │  Axios 实例 → 拦截器统一处理错误与响应包装",
    "   ▼",
    "后端 /api/*",
    "",
    "跨页面共享的状态（登录、站点配置）例外：直接读写 Pinia store",
], caption="单向数据流。禁止在组件里直接 import axios 发请求，否则拦截器与错误处理会被绕过。")

b.h("3.3 状态放置规则（ADR-05 的落地）", 2)
b.table(["数据类型", "放哪里", "判断依据"],
        [["登录状态、当前用户", "Pinia", "多个不相邻组件都需要，且跨页面生存"],
         ["站点配置", "Pinia", "几乎每个页面都要用"],
         ["文章列表、文章详情", "组件内", "只有当前页面用；放全局反而造成状态同步问题"],
         ["表单输入", "组件内", "生命周期与页面一致"],
         ["加载 / 错误状态", "组件内", "属于单次请求的局部状态"],
         ["分页页码", "URL 查询参数", "**必须进 URL**——否则刷新丢失、无法分享链接"]],
        widths=[3.8, 3.0, 10.3])
b.callout("最后一条值得强调：",
          "分页页码放在 URL 查询参数（如 `?page=2`）而不是组件状态里。"
          "这不仅让刷新不丢失，也让浏览器前进/后退正常工作——"
          "**这是最容易被忽略、用户体验影响却最明显的细节之一。**", kind="info")

# ============================================================
b.chapter("4", "部署架构")
b.h("4.1 容器划分", 2)
b.table(["容器", "镜像", "职责", "对外端口", "内存预算"],
        [["nginx", "nginx:alpine", "TLS 终止、静态文件、反向代理、gzip", "80 / 443", "≤ 80 MB"],
         ["backend", "自建（python:3.12-slim）", "FastAPI 应用（Uvicorn 2 worker）", "仅内网 8000", "300–500 MB"],
         ["certbot", "certbot/certbot", "证书申请与自动续期", "无", "临时进程"]],
        widths=[2.0, 4.2, 5.4, 2.4, 3.1], first_col_bold=True)
b.callout("注意这里只有两个常驻进程：",
          "SQLite 不是容器，它是被 backend 进程打开的一个文件。"
          "**这是 ADR-02 与阶段一 A2 决策带来的最直接简化**——"
          "不需要数据库容器、不需要连接配置、不需要单独的内存预算。", kind="ok")

b.h("4.2 数据卷与持久化", 2)
b.table(["卷", "宿主机路径", "容器内路径", "内容", "备份要求"],
        [["db_data", "./data/db", "/data/db", "`blog.db` 及 WAL 文件", "**每日备份**"],
         ["uploads", "./data/uploads", "/app/uploads", "上传的图片", "每周备份"],
         ["certs", "./data/certs", "/etc/letsencrypt", "TLS 证书", "可不备份，可重新签发"],
         ["nginx_logs", "./data/logs", "/var/log/nginx", "访问与错误日志", "按需"]],
        widths=[2.2, 3.8, 3.6, 4.0, 3.5])
b.callout("备份顺序有讲究：",
          "SQLite 开启 WAL 后，数据分散在 `blog.db`、`blog.db-wal`、`blog.db-shm` 三个文件里。"
          "**直接复制 `blog.db` 可能丢失尚未合并的数据。**"
          "正确做法是使用 `sqlite3 blog.db \".backup backup.db\"` 命令，它会生成一致快照。",
          kind="warn")

b.h("4.3 请求路径", 2)
b.table(["请求", "经过的环节", "是否经过后端"],
        [["`GET /`（首页）", "Nginx → 返回 index.html", "❌"],
         ["`GET /assets/*.js`", "Nginx → 返回静态文件（gzip）", "❌"],
         ["`GET /uploads/xxx.webp`", "Nginx → 返回图片（长缓存）", "❌"],
         ["`GET /api/articles`", "Nginx → FastAPI → SQLite → JSON", "✅"],
         ["`POST /api/admin/articles`", "Nginx → FastAPI（校验会话）→ SQLite", "✅"],
         ["`GET /posts/vue-router`", "Nginx 找不到文件 → `try_files` 回退到 index.html → 前端路由接管", "❌"]],
        widths=[4.4, 9.0, 3.7])
b.callout("最后一行是 ADR-07 的落点：",
          "**这是部署后最容易出现的故障**——直接访问文章链接或按 F5 会 404。"
          "配置 `try_files $uri $uri/ /index.html;` 即可解决。", kind="warn")

b.h("4.4 Docker Compose 结构（示意）", 2)
b.snippet([
    "services:",
    "  backend:",
    "    build: ./backend",
    "    restart: unless-stopped",
    "    env_file: .env",
    "    volumes:",
    "      - ./data/db:/data/db",
    "      - ./data/uploads:/app/uploads",
    "    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2",
    "",
    "  nginx:",
    "    image: nginx:alpine",
    "    restart: unless-stopped",
    "    ports: [\"80:80\", \"443:443\"]",
    "    volumes:",
    "      - ./frontend/dist:/var/www/blog:ro      # 前端构建产物",
    "      - ./data/uploads:/var/www/uploads:ro",
    "      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro",
    "      - ./data/certs:/etc/letsencrypt:ro",
    "    depends_on: [backend]",
], caption="两个服务、四个卷。没有数据库服务——这正是选 SQLite 的收益。")

b.h("4.5 前端构建位置（重要）", 2)
b.callout("绝不在服务器上构建前端：",
          "`npm run build` 实测常占用 1GB 以上内存。在 4G 服务器上执行，极可能触发 OOM "
          "并连带影响正在运行的容器。**正确做法：本地构建出 `dist/`，再上传到服务器。**"
          "这也是阶段一「不在服务器上构建」约束的具体落点。", kind="warn")

# ============================================================
b.chapter("5", "关键流程时序")
b.p("以下三条流程覆盖了系统 90% 的行为。**实现阶段遇到不确定的地方，先回到这里对齐。**")

b.h("5.1 流程 A：访客阅读一篇文章", 2)
b.snippet([
    "浏览器                Nginx              FastAPI            SQLite",
    "  │                     │                   │                  │",
    "  │ GET /posts/vue-router│                   │                  │",
    "  ├────────────────────▶│                   │                  │",
    "  │                     │ 文件不存在         │                  │",
    "  │◀──── index.html ────┤ (try_files 回退)   │                  │",
    "  │                     │                   │                  │",
    "  │ 解析 HTML、请求 JS/CSS                   │                  │",
    "  ├────────────────────▶│                   │                  │",
    "  │◀─── 静态文件(gzip) ──┤                   │                  │",
    "  │                     │                   │                  │",
    "  │ JS 执行，前端路由匹配到文章页             │                  │",
    "  │ GET /api/articles/vue-router            │                  │",
    "  ├────────────────────▶├──────────────────▶│                  │",
    "  │                     │                   │ SELECT ...       │",
    "  │                     │                   ├─────────────────▶│",
    "  │                     │                   │◀──── 文章行 ──────┤",
    "  │◀──── JSON(含渲染好的 HTML) ──────────────┤                  │",
    "  │ v-html 插入正文，图片按需懒加载            │                  │",
], caption="注意：正文的 HTML 已在入库时渲染完成，这里读出来直接用，前端不需要 Markdown 解析库（ADR-06 的收益）。")

b.h("5.2 流程 B：作者发布一篇文章", 2)
b.snippet([
    "浏览器(后台)          Nginx              FastAPI            SQLite",
    "  │                     │                   │                  │",
    "  │ POST /api/admin/articles                │                  │",
    "  │  body: {title, content_md, tags}        │                  │",
    "  ├────────────────────▶├──────────────────▶│                  │",
    "  │                     │        Cookie 校验会话 → 得到 user     │",
    "  │                     │                   │                  │",
    "  │                     │        1. 校验标题唯一、slug 唯一       │",
    "  │                     │        2. Markdown → HTML（含 XSS 过滤）│",
    "  │                     │        3. 写入文章 + 标签关联（事务）    │",
    "  │                     │                   ├─────────────────▶│",
    "  │                     │                   │◀──── 新文章 id ───┤",
    "  │◀──── {code:0, data:{id, slug}} ─────────┤                  │",
    "  │                     │                   │                  │",
    "  │ 跳转到文章预览页      │                   │                  │",
], caption="第 2 步的 XSS 过滤不可省略（ADR-06）。渲染后的 HTML 会以 v-html 插入，是唯一的注入入口。")

b.h("5.3 流程 C：登录与鉴权", 2)
b.snippet([
    "浏览器                Nginx              FastAPI            SQLite",
    "  │                     │                   │                  │",
    "  │ POST /api/auth/login│                   │                  │",
    "  │  {username, password}                   │                  │",
    "  ├────────────────────▶├──────────────────▶│                  │",
    "  │                     │                   │ 查用户、校验哈希   │",
    "  │                     │                   ├─────────────────▶│",
    "  │                     │                   │◀──── 用户行 ──────┤",
    "  │                     │        生成会话标识，写入会话存储         │",
    "  │◀── Set-Cookie: session=...; HttpOnly; Secure; SameSite=Lax ─┤",
    "  │                     │                   │                  │",
    "  │ ── 之后每个请求浏览器自动携带该 Cookie ──                   │",
    "  │                     │                   │                  │",
    "  │ 路由守卫检查登录状态 ──▶ 未登录则跳转登录页                   │",
], caption="同源（ADR-04）下 Cookie 自动携带，无需任何 CORS 配置。")

# ============================================================
b.chapter("6", "横切关注点")
b.h("6.1 统一错误处理（ADR-09 的落地）", 2)
b.snippet([
    "# app/core/errors.py",
    "class BizError(Exception):",
    "    def __init__(self, code: int, message: str, http_status: int = 400):",
    "        self.code = code",
    "        self.message = message",
    "        self.http_status = http_status",
    "",
    "# app/main.py 中注册全局处理器",
    "@app.exception_handler(BizError)",
    "async def biz_error_handler(request, exc):",
    "    return JSONResponse(",
    "        status_code=exc.http_status,",
    "        content={\"code\": exc.code, \"message\": exc.message, \"data\": None},",
    "    )",
], caption="服务层抛 BizError，路由层不写 try/except。错误码定义见文档 05。")
b.p("**校验失败**（Pydantic 抛出的 422）也要统一成同一格式，否则前端拦截器要处理两种结构：")
b.snippet([
    '{ "code": 42200, "message": "标题长度必须在 1–120 之间", "data": null }',
])

b.h("6.2 日志规范", 2)
b.table(["级别", "使用场景", "示例"],
        [["DEBUG", "开发排查，生产默认关闭", "SQL 语句、请求耗时明细"],
         ["INFO", "正常的关键事件", "启动完成、登录成功、文章发布、备份完成"],
         ["WARNING", "可恢复的异常", "登录失败、slug 重复自动追加序号、图片压缩失败改用原图"],
         ["ERROR", "需要人工介入", "数据库写入失败、图片保存失败、未捕获异常"]],
        widths=[2.0, 4.6, 10.5], first_col_bold=True)
b.p("日志字段固定为：`时间 | 级别 | 请求方法 | 路径 | 状态码 | 耗时(ms) | 错误信息`。"
    "**固定字段的意义**：出问题时可以直接用命令行过滤，不需要肉眼找。")
b.snippet([
    "2026-10-08 14:32:01 | INFO  | POST /api/admin/articles | 201 | 87ms | -",
    "2026-10-08 14:35:12 | WARN  | POST /api/auth/login     | 401 | 12ms | 密码错误",
    "2026-10-08 15:01:44 | ERROR | GET  /api/articles      | 500 | 210ms | database is locked",
], caption="按固定格式输出的日志示例。最后一行是 SQLite 并发写入的典型告警，对应风险 R-1。")

b.h("6.3 环境与配置", 2)
b.table(["变量", "用途", "示例值", "是否必填"],
        [["`DATABASE_URL`", "数据库连接串", "`sqlite:////data/db/blog.db`", "是"],
         ["`SECRET_KEY`", "会话签名密钥", "随机 64 位字符串", "是"],
         ["`ADMIN_USERNAME`", "初始管理员用户名", "`admin`", "是"],
         ["`ADMIN_PASSWORD`", "初始管理员密码", "仅初始化脚本使用", "是"],
         ["`SESSION_EXPIRE_DAYS`", "会话有效期（天）", "`7`", "否（有默认值）"],
         ["`UPLOAD_MAX_SIZE_MB`", "单张图片体积上限", "`2`", "否"],
         ["`SITE_URL`", "站点地址", "`https://blog.com`", "是"],
         ["`LOG_LEVEL`", "日志级别", "`INFO`", "否"]],
        widths=[4.2, 4.2, 5.4, 3.3])
b.callout("`SECRET_KEY` 必须随机生成：",
          "用 `python -c \"import secrets; print(secrets.token_urlsafe(48))\"` 生成。"
          "**不要用示例值或常用词**——它决定了会话 Cookie 能否被伪造。", kind="warn")

b.h("6.4 时间与时区", 2)
b.table(["项", "规定"],
        [["数据库存储", "统一存 UTC 时间"],
         ["接口返回", "ISO 8601 格式，带时区标识（如 `2026-10-08T14:32:01Z`）"],
         ["前端显示", "转为浏览器本地时区"],
         ["原因", "**若存本地时间，服务器换时区或迁移后历史数据会全部错乱**"]],
        widths=[3.0, 14.1])

b.h("6.5 本架构的约束检查", 2)
b.table(["检查项", "结论"],
        [["一次请求的完整路径能讲清", "✅ 见 5.1 / 5.2 / 5.3"],
         ["每层职责无重叠", "✅ 见 1.2 与 2.3 的调用规则"],
         ["每个目录职责明确", "✅ 见 2.1 / 3.1"],
         ["4G 内存可承载", "✅ 两个常驻进程，预算合计约 2.1GB"],
         ["不依赖任何第二台机器", "✅ 单机两个容器"],
         ["环境可完整重建", "✅ 镜像 + Compose + `.env.example` + 迁移脚本"],
         ["不引入并发场景用不上的复杂度", "✅ 无消息队列、无缓存中间件、无读写分离"]],
        widths=[5.4, 11.7], first_col_bold=True)

b.save()
