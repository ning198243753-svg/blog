# -*- coding: utf-8 -*-
"""文档 05 · 接口设计（API 契约）"""
import sys
sys.path.insert(0, r"E:\project\blog\docx")
from _docbuild import DocBuilder

b = DocBuilder(
    r"E:\project\blog\docx\05-接口设计-v1.0.docx",
    "接口设计",
    "API 契约 · 错误码 · 鉴权约定",
    ["个人博客项目　|　阶段二：设计　|　版本 v1.0　|　日期：2026-10-08",
     "本文档是实现阶段的施工图：后端照它写，前端照它调。接口未定义完就开始写代码是返工的头号原因。"],
)

# ============================================================
b.chapter("1", "通用约定")
b.h("1.1 基础规则", 2)
b.table(["项", "约定"],
        [["接口前缀", "`/api`（ADR-04 前后端同源）"],
         ["数据格式", "请求与响应均为 JSON（文件上传除外）"],
         ["字符编码", "UTF-8"],
         ["时间格式", "ISO 8601 带时区，如 `2026-10-08T14:32:01Z`；**统一存 UTC**"],
         ["字段命名", "`snake_case`（与 Python 一致，前端 camelCase 转换由 Axios 拦截器可选处理）"],
         ["分页参数", "`page`（从 1 开始）、`page_size`（默认 10，最大 50）"]],
        widths=[2.6, 14.5], first_col_bold=True)

b.h("1.2 统一响应体（ADR-09）", 2)
b.snippet([
    "// 成功",
    '{ "code": 0, "message": "ok", "data": { ... } }',
    "",
    "// 业务错误",
    '{ "code": 40001, "message": "标题已存在", "data": null }',
    "",
    "// 分页数据结构（放在 data 内）",
    '{',
    '  "code": 0,',
    '  "message": "ok",',
    '  "data": {',
    '    "items": [ ... ],',
    '    "total": 42,',
    '    "page": 1,',
    '    "page_size": 10,',
    '    "pages": 5',
    '  }',
    '}',
], caption="`code = 0` 表示成功。HTTP 状态码仍按其原生语义返回（200/201/400/401/404/500）。")
b.callout("为什么 code 和 HTTP 状态码都要：",
          "HTTP 状态码表达「这类请求成功还是失败」，业务码表达「具体是哪一种失败」。"
          "**前端拦截器只看 `code`，不需要解析 HTTP 状态码**——"
          "这样加新错误类型时前端不用改代码。", kind="info")

b.h("1.3 HTTP 方法语义", 2)
b.table(["方法", "语义", "幂等", "本项目用例"],
        [["GET", "读取，不改变服务端状态", "是", "列表、详情、配置"],
         ["POST", "创建新资源", "否", "新建文章、新建标签、登录"],
         ["PUT", "整体更新已有资源", "是", "编辑文章"],
         ["PATCH", "部分更新", "否", "仅更新状态（发布/下架）"],
         ["DELETE", "删除资源", "是", "删除文章、删除标签"]],
        widths=[1.8, 5.4, 1.6, 8.3], first_col_bold=True)

b.h("1.4 鉴权约定（ADR-03）", 2)
b.table(["项", "约定"],
        [["方式", "Cookie 中的签名会话（`session`），**服务端不建会话表**（见文档 04 第 1.3 节）"],
         ["Cookie 属性", "`HttpOnly`（防 JS 读取）+ `Secure`（仅 HTTPS）+ `SameSite=Lax`（防 CSRF）"],
         ["有效期", "默认 7 天，由 `SESSION_EXPIRE_DAYS` 配置"],
         ["需要登录的接口", "`/api/admin/*` 全部需要；`/api/auth/me` 用于查询登录状态"],
         ["未登录响应", "HTTP 401，`code = 40100`"],
         ["前端处理", "Axios 响应拦截器捕获 401 → 清除登录状态 → 跳转登录页"]],
        widths=[3.0, 14.1], first_col_bold=True)
b.p("**路由划分（对应后端 `routers/` 的三个文件）：**")
b.table(["前缀", "文件", "是否需要登录", "说明"],
        [["`/api/auth/*`", "`auth.py`", "混合", "登录、注销、查询当前用户"],
         ["`/api/*`", "`public.py`", "否", "访客可访问的只读接口"],
         ["`/api/admin/*`", "`admin.py`", "**是**", "后台管理接口，全部需登录"]],
        widths=[3.0, 2.6, 2.8, 8.7], first_col_bold=True)
b.callout("把 `admin` 做成 URL 前缀的好处：",
          "鉴权可以**按路由组批量生效**，而不是逐个接口记得加 `Depends(get_current_user)`。"
          "**漏加一个就是未授权访问漏洞**——这类漏洞靠人自觉是防不住的，靠结构才防得住。",
          kind="warn")

b.h("1.5 错误码表", 2)
b.table(["code", "HTTP", "含义", "触发场景"],
        [["`0`", "200/201", "成功", "—"],
         ["`40000`", "400", "请求参数错误", "参数缺失、格式不正确"],
         ["`40001`", "400", "标题已存在", "存在同名文章"],
         ["`40002`", "400", "slug 冲突且无法自动处理", "极少见，自动加序号失败时"],
         ["`40003`", "400", "标签已存在", "新建标签时重名"],
         ["`40004`", "400", "图片格式不支持", "非 jpg/png/webp/gif"],
         ["`40005`", "400", "图片体积超限", "超过 `UPLOAD_MAX_SIZE_MB`"],
         ["`40006`", "400", "文章状态不允许此操作", "例如把草稿直接下架"],
         ["`40100`", "401", "未登录或会话已过期", "无 Cookie 或签名校验失败"],
         ["`40101`", "401", "用户名或密码错误", "登录失败（**不区分是哪个错**，防用户名探测）"],
         ["`40300`", "403", "无权限", "预留，当前单管理员场景用不到"],
         ["`40400`", "404", "资源不存在", "文章或标签不存在"],
         ["`42200`", "422", "字段校验失败", "Pydantic 校验不通过（长度、类型等）"],
         ["`42900`", "429", "请求过于频繁", "登录失败次数过多（**建议实现**）"],
         ["`50000`", "500", "服务器内部错误", "未捕获异常（**不外露堆栈信息**）"]],
        widths=[2.2, 2.0, 4.4, 8.5], first_col_bold=True)
b.callout("`40101` 那一条为什么这样设计：",
          "登录失败时**不告诉用户是用户名错还是密码错**。"
          "如果分开提示，攻击者可以先用任意密码试探出哪些用户名存在。"
          "**这是零成本的安全改进，只需把两条错误信息合成一条。**", kind="warn")

# ============================================================
b.chapter("2", "公开接口（无需登录）")
b.p("共 8 个接口。全部为只读，对应后端的 `routers/public.py`。")

b.h("2.1 获取文章列表", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/articles`"],
         ["用途", "首页列表、标签页、归档页、搜索结果共用"],
         ["查询参数", "`page`（默认 1）、`page_size`（默认 10）、`tag`（标签 slug，可选）、\n"
          "`q`（搜索关键词，可选）、`year`（归档年份，可选）"],
         ["返回", "分页结构，`items` 中为**列表项字段**（不含正文）"],
         ["服务需求", "FR-05 文章列表、FR-06 分页、FR-08 标签筛选、FR-10 搜索"]],
        widths=[2.6, 14.5], first_col_bold=True)
b.snippet([
    "GET /api/articles?page=1&page_size=10&tag=vue",
    "",
    '{',
    '  "code": 0, "message": "ok",',
    '  "data": {',
    '    "items": [',
    '      {',
    '        "slug": "vue-router-guards",',
    '        "title": "Vue Router 的三种守卫",',
    '        "summary": "守卫的作用是在路由跳转前后插入逻辑……",',
    '        "tags": [{"name": "Vue", "slug": "vue", "color": "#41B883"}],',
    '        "published_at": "2026-10-01T09:00:00Z",',
    '        "view_count": 42',
    '      }',
    '    ],',
    '    "total": 42, "page": 1, "page_size": 10, "pages": 5',
    '  }',
    '}',
], caption="列表项刻意不含 `content_html`——列表页只需要摘要，传正文会白白浪费 3Mbps 带宽。")

b.h("2.2 获取文章详情", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/articles/{slug}`"],
         ["返回", "文章全部字段，含 `content_html`（已渲染、已过滤）"],
         ["404", "`code = 40400`"],
         ["副作用", "**阅读数 +1**（每次请求都加，不做去重）"],
         ["服务需求", "FR-07 文章详情"]],
        widths=[2.6, 14.5], first_col_bold=True)
b.snippet([
    '{',
    '  "code": 0, "message": "ok",',
    '  "data": {',
    '    "slug": "vue-router-guards",',
    '    "title": "Vue Router 的三种守卫",',
    '    "summary": "守卫的作用是……",',
    '    "content_html": "<h2>什么是守卫</h2><p>……</p>",',
    '    "tags": [{"name": "Vue", "slug": "vue", "color": "#41B883"}],',
    '    "published_at": "2026-10-01T09:00:00Z",',
    '    "updated_at": "2026-10-03T11:20:00Z",',
    '    "view_count": 43',
    '  }',
    '}',
], caption="前端用 v-html 插入 content_html。该字段必须已在后端完成 XSS 过滤（ADR-06）。")
b.callout("草稿不能通过这个接口访问：",
          "若文章 `status = draft`，公开接口必须返回 **404 而不是 403**。"
          "返回 403 等于告诉外人「这里有一篇未发布的文章」。", kind="warn")

b.h("2.3 获取标签列表", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/tags`"],
         ["返回", "全部标签 + 各自的已发布文章数（按文章数倒序）"],
         ["是否分页", "**否**——标签总量在 50 个以内，一次返回"],
         ["服务需求", "FR-08 标签筛选"]],
        widths=[2.6, 14.5], first_col_bold=True)
b.snippet([
    '{ "code": 0, "message": "ok", "data": [',
    '  {"name": "Vue", "slug": "vue", "color": "#41B883", "count": 12},',
    '  {"name": "FastAPI", "slug": "fastapi", "color": null, "count": 8}',
    '] }',
])

b.h("2.4 获取归档", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/archive`"],
         ["返回", "按年份分组的文章（含月份与数量）"],
         ["服务需求", "FR-09 归档页"]],
        widths=[2.6, 14.5], first_col_bold=True)
b.snippet([
    '{ "code": 0, "message": "ok", "data": [',
    '  {"year": 2026, "count": 30, "articles": [',
    '    {"slug": "sqlite-wal", "title": "SQLite 为什么要开 WAL", "published_at": "…"}',
    '  ]}',
    '] }',
])

b.h("2.5 获取站点配置", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/site`"],
         ["返回", "站点标题、副标题、作者、页脚、备案号、GitHub 链接等**公开**配置"],
         ["不返回", "任何敏感项（邮箱、密钥等）"],
         ["调用时机", "**应用启动时调用一次**，存入 Pinia，供全局使用（ADR-05）"]],
        widths=[2.6, 14.5], first_col_bold=True)

b.h("2.6 获取关于页内容", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/about`"],
         ["返回", "`{ \"content_html\": \"...\" }`（来自 `site_config.author_intro`，同样经 Markdown 渲染与过滤）"],
         ["服务需求", "FR-04 关于页"]],
        widths=[2.6, 14.5], first_col_bold=True)

b.h("2.7 图片访问", 2)
b.table(["项", "内容"],
        [["路径", "`GET /uploads/{filename}`"],
         ["处理方", "**Nginx 直接返回，不经过 FastAPI**（ADR-02）"],
         ["缓存", "`Cache-Control: public, max-age=2592000`（30 天）"],
         ["约束", "只允许特定扩展名，禁止目录穿越（如 `../`）"]],
        widths=[2.6, 14.5], first_col_bold=True)

b.h("2.8 健康检查", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/health`"],
         ["返回", "`{ \"code\": 0, \"data\": { \"status\": \"ok\", \"db\": \"ok\" } }`"],
         ["用途", "**部署验证**（SM-04）：确认容器起来且数据库可读"],
         ["注意", "数据库不可读时返回 500，便于脚本判断"]],
        widths=[2.6, 14.5], first_col_bold=True)

# ============================================================
b.chapter("3", "鉴权接口")
b.h("3.1 登录", 2)
b.table(["项", "内容"],
        [["方法与路径", "`POST /api/auth/login`"],
         ["请求体", "`{ \"username\": \"admin\", \"password\": \"******\" }`"],
         ["成功响应", "HTTP 200，`Set-Cookie: session=...; HttpOnly; Secure; SameSite=Lax`"],
         ["失败响应", "HTTP 401，`code = 40101`（**不区分用户名或密码错误**）"],
         ["限流建议", "同一 IP 连续失败 5 次后返回 `42900`（见错误码表）"]],
        widths=[2.6, 14.5], first_col_bold=True)
b.snippet([
    '// 请求',
    '{ "username": "admin", "password": "my-password" }',
    '',
    '// 响应（成功）',
    'HTTP/1.1 200 OK',
    'Set-Cookie: session=eyJ1aWQiOjEsImV4cCI6MTc2MH0.abc123; HttpOnly; Secure; SameSite=Lax; Path=/',
    '{ "code": 0, "message": "ok", "data": {"username": "admin"} }',
])

b.h("3.2 注销", 2)
b.table(["项", "内容"],
        [["方法与路径", "`POST /api/auth/logout`"],
         ["行为", "返回 `Set-Cookie` 将 session 置空并立即过期"],
         ["幂等性", "未登录时调用也返回成功，不报错"]],
        widths=[2.6, 14.5], first_col_bold=True)

b.h("3.3 查询当前登录用户", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/auth/me`"],
         ["用途", "**前端刷新页面后恢复登录状态**（Pinia 是内存状态，刷新即丢失）"],
         ["已登录", "`{ \"code\": 0, \"data\": {\"username\": \"admin\"} }`"],
         ["未登录", "HTTP 401，`code = 40100`"]],
        widths=[2.6, 14.5], first_col_bold=True)
b.callout("这个接口看似多余，实际必需：",
          "Pinia 的状态存在内存里，**用户一刷新页面就没了**。"
          "没有这个接口，用户每次刷新后台都会被踢回登录页。"
          "正确做法：路由守卫在首次进入需登录页面时调用一次 `/api/auth/me` 来恢复状态。",
          kind="info")

# ============================================================
b.chapter("4", "后台接口（需要登录）")
b.p("共 10 个接口，全部位于 `/api/admin/*`，由路由组统一挂载鉴权依赖。")

b.h("4.1 获取文章列表（含草稿）", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/admin/articles`"],
         ["与公开接口的差异", "**包含草稿**，且返回 Markdown 原文用于编辑"],
         ["查询参数", "`page`、`page_size`、`status`（`draft` / `published` / 全部）"]],
        widths=[3.4, 13.7], first_col_bold=True)

b.h("4.2 获取单篇文章（用于编辑）", 2)
b.table(["项", "内容"],
        [["方法与路径", "`GET /api/admin/articles/{id}`"],
         ["说明", "返回 `content_md`（原文），而不是渲染后的 HTML"],
         ["为什么用 id 而不是 slug", "**允许在编辑时修改 slug**，用 slug 定位会导致改了就找不到"]],
        widths=[3.4, 13.7], first_col_bold=True)

b.h("4.3 新建文章", 2)
b.table(["项", "内容"],
        [["方法与路径", "`POST /api/admin/articles`"],
         ["请求体", "`{ \"title\", \"content_md\", \"summary\"?, \"tags\"?: [\"vue\"], \"status\": \"draft\" }`"],
         ["服务端行为", "生成 slug → Markdown 渲染 + XSS 过滤 → 写文章 → 关联标签（**同一事务**）"],
         ["成功响应", "HTTP 201，`{ \"code\": 0, \"data\": {\"id\": 1, \"slug\": \"vue-router-guards\"} }`"]],
        widths=[3.4, 13.7], first_col_bold=True)

b.h("4.4 更新文章", 2)
b.table(["项", "内容"],
        [["方法与路径", "`PUT /api/admin/articles/{id}`"],
         ["请求体", "同新建，字段可省略（省略即不改）"],
         ["服务端行为", "**内容变化时重新渲染 HTML**；标题变化时**保持原 slug 不变**（避免旧链接失效）"],
         ["tags 字段语义", "**传了就整体替换**，不传则保持不变"]],
        widths=[3.4, 13.7], first_col_bold=True)
b.callout("改标题不改 slug —— 这是有意为之：",
          "如果标题一改 slug 就跟着变，那么**任何外部链接、浏览器书签、你自己发过的链接全部失效**。"
          "正确做法是 slug 在首次创建时生成后固定。"
          "**若确实需要修改，必须提供单独的「修改链接」操作，并让用户明确知道后果。**",
          kind="warn")

b.h("4.5 发布 / 下架文章", 2)
b.table(["项", "内容"],
        [["方法与路径", "`PATCH /api/admin/articles/{id}/status`"],
         ["请求体", "`{ \"status\": \"published\" }`"],
         ["服务端行为", "首次发布时写入 `published_at`；重新下架不改该值"]],
        widths=[3.4, 13.7], first_col_bold=True)

b.h("4.6 删除文章", 2)
b.table(["项", "内容"],
        [["方法与路径", "`DELETE /api/admin/articles/{id}`"],
         ["行为", "**物理删除**，关联的 `article_tags` 由 `ON DELETE CASCADE` 自动清理"],
         ["确认", "前端必须二次确认（见文档 06 交互规范）"]],
        widths=[3.4, 13.7], first_col_bold=True)
b.callout("为什么不做「软删除」：",
          "软删除（`is_deleted` 标记）适合「误删后有客服帮你恢复」的场景。"
          "**本项目有每日备份，从备份恢复比维护软删除状态简单得多**——"
          "软删除会让**每一个查询**都必须记得加 `WHERE is_deleted = 0`，漏一个就出 bug。",
          kind="info")

b.h("4.7 上传图片", 2)
b.table(["项", "内容"],
        [["方法与路径", "`POST /api/admin/upload`"],
         ["请求", "`multipart/form-data`，字段名 `file`"],
         ["允许格式", "jpg / jpeg / png / webp / gif"],
         ["体积上限", "`UPLOAD_MAX_SIZE_MB`（默认 2MB）"],
         ["**服务端必做处理**", "① 校验真实格式（不能只看扩展名）；"
          "② **超过 1600px 的图片等比缩放**；③ **转为 WebP**；"
          "④ 文件名用随机串（不用原始名，防止路径注入与重名）"],
         ["成功响应", "`{ \"code\": 0, \"data\": { \"url\": \"/uploads/a3f9c2.webp\" } }`"]],
        widths=[3.4, 13.7], first_col_bold=True)
b.callout("这里的「必做处理」是 ADR-02 的前提：",
          "选了本地存储，就等于把图片流量全部压在自己的带宽上。"
          "**不做压缩，一个 2MB 的原图在 3Mbps 下需要 5 秒以上才能显示——博客会变得不可用。**"
          "压缩不是优化项，是这条决策能否成立的先决条件。", kind="warn")

b.h("4.8 标签管理（增 / 改 / 删）", 2)
b.table(["方法与路径", "用途", "说明"],
        [["`GET /api/admin/tags`", "标签列表（含草稿文章数）", "—"],
         ["`POST /api/admin/tags`", "新建标签", "`{ \"name\", \"slug\"?, \"color\"? }`，slug 缺省时由 name 生成"],
         ["`PUT /api/admin/tags/{id}`", "重命名标签", "**slug 同步更新**（标签改名的代价远小于文章）"],
         ["`DELETE /api/admin/tags/{id}`", "删除标签", "**仅解除关联，不删除文章**"]],
        widths=[5.0, 4.2, 7.9], first_col_bold=True)
b.callout("删除标签的语义必须明确：",
          "**删除标签只删标签本身和它的关联关系，文章一律保留。**"
          "如果实现成「连带删除文章」，一次误操作会毁掉大量内容。"
          "前端确认框文案也必须写清这一点。", kind="warn")

b.h("4.9 站点配置", 2)
b.table(["方法与路径", "用途"],
        [["`GET /api/admin/site`", "读取全部配置（含不公开的项）"],
         ["`PUT /api/admin/site`", "批量更新，请求体为 `{ \"key\": \"value\", ... }`"]],
        widths=[5.0, 12.1], first_col_bold=True)

b.h("4.10 修改登录密码", 2)
b.table(["项", "内容"],
        [["方法与路径", "`PUT /api/auth/password`"],
         ["请求体", "`{ \"old_password\", \"new_password\" }`"],
         ["要求", "新密码长度 ≥ 8；**修改成功后旧会话立即失效，需重新登录**"]],
        widths=[3.4, 13.7], first_col_bold=True)

# ============================================================
b.chapter("5", "接口与需求的对应")
b.p("**这一节是验证线的起点**：阶段三写测试时，按本表逐条确认每条需求都有接口承载。")
b.table(["需求", "内容", "承载接口"],
        [["FR-05", "首页文章列表", "`GET /api/articles`"],
         ["FR-06", "分页", "`GET /api/articles`（`page` / `page_size`）"],
         ["FR-07", "文章详情", "`GET /api/articles/{slug}`"],
         ["FR-08", "标签筛选", "`GET /api/articles?tag=`、`GET /api/tags`"],
         ["FR-09", "归档与友好链接", "`GET /api/archive`、slug 机制"],
         ["FR-10", "站内搜索", "`GET /api/articles?q=`"],
         ["FR-04", "关于页", "`GET /api/about`"],
         ["FR-11~15", "后台文章管理", "`/api/admin/articles/*`"],
         ["FR-16", "图片上传", "`POST /api/admin/upload`"],
         ["FR-17", "标签管理", "`/api/admin/tags/*`"],
         ["FR-18", "站点配置", "`/api/admin/site`"],
         ["FR-19", "登录鉴权", "`/api/auth/*`"],
         ["FR-22", "title / description（修订后）", "由前端路由守卫动态设置，无需接口"]],
        widths=[1.8, 5.2, 10.1], first_col_bold=True)
b.callout("最后一行值得注意：",
          "FR-22 修订后**不再需要后端接口**——因为纯 SPA 下页面标题由前端在路由切换时设置。"
          "**接口少一个，就少一份测试与维护成本。**", kind="ok")

# ============================================================
b.chapter("6", "前端的接口调用组织（ADR-09 落地）")
b.snippet([
    "// src/api/client.ts —— 全站唯一的 Axios 实例",
    "const client = axios.create({ baseURL: '/api', timeout: 15000 })",
    "",
    "// 响应拦截器：统一拆包与错误处理",
    "client.interceptors.response.use(",
    "  (res) => {",
    "    const { code, message, data } = res.data",
    "    if (code !== 0) return Promise.reject(new BizError(code, message))",
    "    return data            // 组件拿到的直接是 data，不用层层 .data",
    "  },",
    "  (err) => {",
    "    if (err.response?.status === 401) {",
    "      authStore.clear()     // 清登录态",
    "      router.push('/admin/login')",
    "    }",
    "    return Promise.reject(err)",
    "  }",
    ")",
], caption="拦截器让 401 处理只写一次。禁止在组件里直接 import axios，否则会绕过这里。")
b.callout("`return data` 这个细节的价值：",
          "把 `{code, message, data}` 在拦截器里拆开，组件里写 `const list = await getArticles()` 就直接拿到数组，"
          "而不是 `res.data.data.items`。**省掉的是每一处调用点的认知负担。**", kind="info")

# ============================================================
b.chapter("7", "完成标准")
b.table(["#", "检查项", "结论"],
        [["1", "每个接口都有明确的请求与响应示例", "✅ 见第 2–4 章"],
         ["2", "错误码表覆盖全部已知失败场景", "✅ 15 个错误码，见 1.5"],
         ["3", "鉴权范围明确，无「漏加」空间", "✅ `/api/admin/*` 路由组统一挂载，见 1.4"],
         ["4", "每条功能需求都有接口承载", "✅ 见第 5 章对照表"],
         ["5", "前端调用方式已规定，不会各写各的", "✅ 见第 6 章"],
         ["6", "关键安全点已标注", "✅ 草稿返回 404、登录错误不区分、XSS 过滤、上传格式校验"],
         ["7", "接口数量与实际需求匹配，无多余接口", "✅ 公开 8 个 + 鉴权 3 个 + 后台 10 个 = 21 个"]],
        widths=[1.0, 6.4, 9.7], first_col_bold=True)

b.save()
