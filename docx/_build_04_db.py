# -*- coding: utf-8 -*-
"""文档 04 · 数据库设计"""
import sys
sys.path.insert(0, r"E:\project\blog\docx")
from _docbuild import DocBuilder

b = DocBuilder(
    r"E:\project\blog\docx\04-数据库设计-v1.0.docx",
    "数据库设计",
    "实体 · 表结构 · 迁移策略",
    ["个人博客项目　|　阶段二：设计　|　版本 v1.0　|　日期：2026-10-08",
     "数据库：SQLite（WAL 模式）+ SQLAlchemy 2.x + Alembic。本文档是建表与迁移的唯一依据。"],
)

# ============================================================
b.chapter("1", "设计说明")
b.p("判断标准：本章的表结构能否**直接变成可执行的建表语句**，且不需要任何口头补充。")

b.h("1.1 为什么只有 4 张表", 2)
b.table(["表", "存什么", "不存什么"],
        [["`articles`", "文章本体：标题、slug、Markdown 原文、渲染后的 HTML、状态、时间", "标签名（存关联表）"],
         ["`tags`", "标签：名称、slug、颜色", "文章数（实时统计，不冗余存储）"],
         ["`article_tags`", "文章与标签的多对多关联", "—"],
         ["`users`", "管理员账号", "会话数据（见 1.3）"],
         ["`site_config`", "站点配置（标题、副标题、备案号等）", "敏感配置（走 `.env`）"]],
        widths=[3.0, 8.0, 6.1], first_col_bold=True)
b.callout("刻意不做的表：",
          "**不建 `comments`（评论，非目标 NG-3）、不建 `sessions`（会话，见 1.3）、"
          "不建 `categories`（分类，与标签职责重叠）。**"
          "表少是好事——每张表都意味着迁移、备份和一致性成本。", kind="ok")

b.h("1.2 主键与标识的选择", 2)
b.table(["项", "选择", "理由"],
        [["主键", "`INTEGER PRIMARY KEY AUTOINCREMENT`", "SQLite 中自增整数主键即 rowid，查询最快且占用最小"],
         ["对外标识", "`slug`（文章与标签）", "URL 友好；阶段一 FR-09 已要求（见 ADR-07）"],
         ["slug 唯一性", "`UNIQUE` 约束 + 后端自动去重", "冲突时自动追加 `-2`、`-3`，不让用户看到报错"],
         ["不外露自增 ID", "公开接口只返回 slug", "避免通过 ID 推测文章总量"]],
        widths=[2.6, 5.4, 9.1], first_col_bold=True)

b.h("1.3 关于「会话」的说明（ADR-03 的落点）", 2)
b.p("ADR-03 选择了「HttpOnly Cookie + 服务端会话」。**服务端会话存放方式有三种，本项目选最简单的一种：**")
b.table(["方案", "做法", "本项目是否采用"],
        [["签名 Cookie（无服务端存储）", "用户信息签名后放进 Cookie 本身", "**✅ 采用**"],
         ["数据库会话表", "会话记录写入 `sessions` 表", "❌ 增加一张表和一次查询"],
         ["内存会话", "存在进程内存里", "❌ 重启即失效，多 worker 不共享"]],
        widths=[4.4, 6.4, 6.3])
b.callout("采用「签名 Cookie」的具体做法：",
          "Cookie 内容 = 用户 ID + 过期时间，用 `SECRET_KEY` 做 HMAC 签名。"
          "服务端只需验签，**不需要查库、不需要 `sessions` 表**。"
          "注销时让 Cookie 立即过期即可（牺牲了「服务端强制踢下线」的能力，"
          "**单管理员场景下这个能力没有意义**）。", kind="info")

b.h("1.4 SQLite 专项设置（必须执行）", 2)
b.snippet([
    "# 每个连接建立时都要执行（在 SQLAlchemy 的 connect 事件里挂载）",
    "PRAGMA journal_mode = WAL;      # 写前日志：读写可并发",
    "PRAGMA synchronous = NORMAL;    # WAL 下的推荐值，兼顾安全与速度",
    "PRAGMA foreign_keys = ON;       # SQLite 默认关闭外键约束，必须手动开启",
    "PRAGMA busy_timeout = 5000;     # 写锁被占用时等待 5 秒而不是立即报错",
], caption="前两条对应风险 R-1（并发写入受限）；第三条极易漏——不开的话外键约束形同虚设。")
b.callout("`foreign_keys = ON` 是最容易漏掉的一条：",
          "**SQLite 默认不强制外键约束**，即使建表时写了 `FOREIGN KEY`。"
          "不显式开启，删除一篇文章后，`article_tags` 里会留下指向不存在文章的垃圾行，"
          "而且**不会报任何错误**。", kind="warn")

# ============================================================
b.chapter("2", "实体关系")
b.snippet([
    "        ┌──────────────┐              ┌──────────────┐",
    "        │    users     │              │     tags     │",
    "        │──────────────│              │──────────────│",
    "        │ id (PK)      │              │ id (PK)      │",
    "        │ username  U  │              │ name      U  │",
    "        │ password_hash│              │ slug      U  │",
    "        │ created_at   │              │ color        │",
    "        └──────────────┘              └───────┬──────┘",
    "                                              │",
    "          articles.author_id ──┐              │ 1",
    "                               │              │",
    "        ┌──────────────┐       │      ┌───────▼──────────┐",
    "        │   articles   │       │      │  article_tags    │",
    "        │──────────────│       │      │──────────────────│",
    "        │ id (PK)      │◀──────┼──────│ article_id (FK)  │",
    "        │ title        │      1│  N   │ tag_id (FK)      │",
    "        │ slug      U  │       └──────│ (复合主键)        │",
    "        │ summary      │              └──────────────────┘",
    "        │ content_md   │                      ▲",
    "        │ content_html │                      │ N",
    "        │ status       │                      │",
    "        │ published_at │              一篇文章可有多个标签",
    "        │ created_at   │              一个标签可属于多篇文章",
    "        │ updated_at   │",
    "        └──────────────┘",
    "",
    "        ┌──────────────┐",
    "        │ site_config  │   （单行表，用 key-value 灵活扩展）",
    "        │──────────────│",
    "        │ key (PK)     │",
    "        │ value        │",
    "        └──────────────┘",
], caption="4 张业务表 + 1 张单行配置表。article_tags 用复合主键防止重复关联。")

b.p("**三条关系说明：**")
b.bullets([
    "**users → articles（1:N）**：现阶段只有 1 个管理员，但保留外键是为了将来若要多作者不必改表结构。",
    "**articles ↔ tags（M:N）**：通过 `article_tags` 中间表实现，用复合主键 `(article_id, tag_id)` 天然防止重复。",
    "**site_config 单行表**：用 key-value 结构而非固定列，将来加一个配置项**不需要改表结构**。",
])

# ============================================================
b.chapter("3", "表结构定义")
b.p("以下为逻辑结构定义。实现阶段由 SQLAlchemy 模型生成，再由 Alembic 产出迁移脚本。")

b.h("3.1 articles（文章）", 2)
b.table(["字段", "类型", "约束", "说明"],
        [["`id`", "INTEGER", "PK, AUTOINCREMENT", "主键"],
         ["`title`", "VARCHAR(120)", "NOT NULL", "文章标题"],
         ["`slug`", "VARCHAR(140)", "NOT NULL, UNIQUE", "URL 标识，由标题生成，冲突时自动追加序号"],
         ["`summary`", "VARCHAR(300)", "NULL", "摘要；为空时自动截取正文前 150 字"],
         ["`content_md`", "TEXT", "NOT NULL", "Markdown 原文 —— **必须保留，它是内容的事实来源**"],
         ["`content_html`", "TEXT", "NOT NULL", "渲染后的 HTML，已做 XSS 过滤（ADR-06）"],
         ["`status`", "VARCHAR(16)", "NOT NULL, DEFAULT 'draft'", "`draft`（草稿）/ `published`（已发布）"],
         ["`author_id`", "INTEGER", "FK → users.id", "作者"],
         ["`view_count`", "INTEGER", "NOT NULL, DEFAULT 0", "阅读数（简单累加，不做去重）"],
         ["`published_at`", "DATETIME", "NULL", "首次发布时间；草稿为 NULL"],
         ["`created_at`", "DATETIME", "NOT NULL", "创建时间（UTC）"],
         ["`updated_at`", "DATETIME", "NOT NULL", "更新时间（UTC），每次修改自动刷新"]],
        widths=[2.4, 2.6, 4.2, 8.0], first_col_bold=True)
b.callout("`content_md` 与 `content_html` 为什么都存：",
          "**`content_md` 是事实来源，`content_html` 是派生产物。**"
          "只存 HTML 会导致原文丢失、无法重新渲染、无法迁移到其他系统；"
          "只存 Markdown 则每次读取都要渲染一次，浪费 CPU。"
          "**冗余这一个字段，换来的是可迁移性和读取性能。**", kind="info")

b.h("3.2 tags（标签）", 2)
b.table(["字段", "类型", "约束", "说明"],
        [["`id`", "INTEGER", "PK, AUTOINCREMENT", "主键"],
         ["`name`", "VARCHAR(32)", "NOT NULL, UNIQUE", "标签名，如 `Vue`"],
         ["`slug`", "VARCHAR(40)", "NOT NULL, UNIQUE", "URL 标识；中文标签也要有 slug"],
         ["`color`", "VARCHAR(16)", "NULL", "标签颜色（十六进制），为空时用主题色"],
         ["`created_at`", "DATETIME", "NOT NULL", "创建时间（UTC）"]],
        widths=[2.4, 2.6, 4.2, 8.0], first_col_bold=True)

b.h("3.3 article_tags（文章标签关联）", 2)
b.table(["字段", "类型", "约束", "说明"],
        [["`article_id`", "INTEGER", "PK(联合), FK → articles.id, ON DELETE CASCADE", "文章"],
         ["`tag_id`", "INTEGER", "PK(联合), FK → tags.id, ON DELETE CASCADE", "标签"]],
        widths=[2.4, 3.4, 7.4, 4.0], first_col_bold=True)
b.p("**两个设计要点：**")
b.bullets([
    "**复合主键 `(article_id, tag_id)`**：天然防止同一篇文章重复关联同一标签，不需要额外的唯一索引。",
    "**`ON DELETE CASCADE`**：删除文章时关联行自动清理。**但前提是已执行 `PRAGMA foreign_keys = ON`**（见 1.4）。",
])

b.h("3.4 users（管理员）", 2)
b.table(["字段", "类型", "约束", "说明"],
        [["`id`", "INTEGER", "PK, AUTOINCREMENT", "主键"],
         ["`username`", "VARCHAR(32)", "NOT NULL, UNIQUE", "用户名"],
         ["`password_hash`", "VARCHAR(128)", "NOT NULL", "**密码哈希，绝不存明文**"],
         ["`created_at`", "DATETIME", "NOT NULL", "创建时间（UTC）"]],
        widths=[2.4, 2.8, 4.0, 7.9], first_col_bold=True)
b.callout("密码哈希用什么：",
          "使用 **bcrypt**（经 `passlib` 调用），**不要用 MD5 / SHA1 / 裸 SHA256** —— "
          "这些算法速度太快，用显卡每秒可尝试数十亿次，等于没有保护。"
          "bcrypt 的设计目标就是「慢」，单次验证约 100ms，暴力破解成本由此变得不可接受。",
          kind="warn")

b.h("3.5 site_config（站点配置）", 2)
b.table(["字段", "类型", "约束", "说明"],
        [["`key`", "VARCHAR(64)", "PK", "配置项名"],
         ["`value`", "TEXT", "NOT NULL", "配置值（统一按字符串存储，读取时转换）"]],
        widths=[2.4, 2.8, 4.0, 7.9], first_col_bold=True)
b.p("**预置配置项：**")
b.table(["key", "用途", "示例值"],
        [["`site_title`", "站点标题", "`moon 的学习笔记`"],
         ["`site_subtitle`", "站点副标题", "`记录 · 整理 · 复现`"],
         ["`author_name`", "作者名", "`moon`"],
         ["`author_intro`", "关于页自我介绍", "（Markdown 文本）"],
         ["`footer_text`", "页脚文字", "`© 2026 moon`"],
         ["`icp_number`", "备案号（若需备案）", "`京ICP备xxxxxxxx号`"],
         ["`github_url`", "GitHub 链接", "`https://github.com/...`"],
         ["`articles_per_page`", "列表每页条数", "`10`"]],
        widths=[4.0, 6.0, 7.1], first_col_bold=True)
b.callout("为什么用 key-value 而不是固定列：",
          "如果做成固定列（`site_title`、`site_subtitle` 各占一列），"
          "**每加一个配置项都要写一次数据库迁移**。"
          "key-value 结构下，加配置只是插一行数据。"
          "**代价是失去了类型约束**（值都是字符串），但配置项数量少、改动频率高，这个取舍是划算的。",
          kind="info")

# ============================================================
b.chapter("4", "索引策略")
b.p("索引不是越多越好——**每个索引都会拖慢写入，并占用磁盘**。本项目只建必要的索引。")
b.table(["索引", "字段", "为什么需要", "支撑的查询"],
        [["`idx_articles_slug`", "`articles.slug` (唯一)", "URL 查询走这里", "按 slug 读文章"],
         ["`idx_articles_status_published`", "`articles(status, published_at DESC)`", "列表页按状态过滤并倒序排列",
          "首页列表、归档页"],
         ["`idx_articles_created`", "`articles(created_at DESC)`", "按时间倒序", "归档页、后台列表"],
         ["`idx_tags_slug`", "`tags.slug` (唯一)", "标签页 URL 查询", "按 slug 读标签"],
         ["`idx_article_tags_tag`", "`article_tags(tag_id)`", "**反向查询**", "按标签查文章列表"]],
        widths=[3.8, 4.2, 4.4, 4.7])
b.callout("最后一条容易被漏掉：",
          "`article_tags` 的复合主键是 `(article_id, tag_id)`，它天然支持「按文章查标签」，"
          "但**不支持「按标签查文章」**——因为 tag_id 不是索引的最左列。"
          "而标签页的核心查询正好是后者。**所以必须为 `tag_id` 单独建一个索引。**",
          kind="warn")
b.p("**明确不建的索引：**")
b.bullets([
    "`articles.title` —— 不做标题模糊搜索（搜索走 `LIKE` 全表扫描，文章量小可接受）",
    "`articles.view_count` —— 不按阅读数排序",
    "`site_config.value` —— 只有几行数据，全表扫描更快",
])

# ============================================================
b.chapter("5", "迁移策略")
b.h("5.1 工具与规则", 2)
b.table(["项", "规定"],
        [["工具", "Alembic（ADR 已在阶段一确定为必需项）"],
         ["**禁止行为**", "**禁止手工修改 `.db` 文件或手工执行 `ALTER TABLE`**"],
         ["每次变更", "必须生成一个迁移脚本，纳入版本控制"],
         ["命名", "`alembic revision -m \"add_view_count_to_articles\"`（动词开头，描述清楚）"],
         ["上线顺序", "先备份数据库 → 执行迁移 → 重启应用"],
         ["回滚", "每个迁移脚本必须能 `downgrade`，不允许只写一半"]],
        widths=[3.0, 14.1])
b.callout("为什么迁移是硬要求：",
          "SQLite 的 `ALTER TABLE` 能力很弱（改列类型、删列都要重建整张表）。"
          "**手工改表在 SQLite 上极易造成数据丢失，而且没有记录可查。**"
          "Alembic 会帮你生成「建新表 → 拷数据 → 删旧表 → 改名」的完整步骤。",
          kind="warn")

b.h("5.2 迁移脚本示例", 2)
b.snippet([
    "# alembic/versions/xxxx_add_view_count_to_articles.py",
    "",
    "def upgrade() -> None:",
    "    op.add_column('articles',",
    "        sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'))",
    "",
    "def downgrade() -> None:",
    "    op.drop_column('articles', 'view_count')",
], caption="注意 server_default='0'：已有行必须有值，否则 NOT NULL 会失败。")

b.h("5.3 备份与恢复（ADR-02 与 SQLite 的红利）", 2)
b.table(["项", "做法", "频率"],
        [["备份命令", "`sqlite3 /data/db/blog.db \".backup /backup/blog-$(date +%F).db\"`", "每日"],
         ["保留策略", "保留最近 14 份，更早的自动清理", "—"],
         ["异地留存", "下载到本地或推送至网盘（**不留在同一台服务器**）", "每周"],
         ["恢复步骤", "停容器 → 用备份文件替换 `.db` → 删除 `-wal`/`-shm` 残留 → 启动", "演练一次"],
         ["验证", "恢复后访问首页与一篇文章，确认内容完整", "每次演练"]],
        widths=[2.6, 11.4, 3.1], first_col_bold=True)
b.callout("相比 MySQL 方案简化了什么：",
          "MySQL 需要 `mysqldump` 导出、恢复时要先建库再导入、还要处理用户权限。"
          "**SQLite 的备份是复制一个文件，恢复是替换一个文件。**"
          "这正是阶段一 A2 决策带来的实际收益。", kind="ok")
b.callout("但有一个坑必须注意：",
          "**备份文件不能和数据库放在同一个目录**。"
          "如果哪天误删了整个数据目录，备份会跟着一起没。"
          "备份必须写到另一个路径，并定期取到服务器之外。", kind="warn")

# ============================================================
b.chapter("6", "种子数据与初始化")
b.p("首次部署时数据库是空的，需要初始化脚本创建管理员与默认配置。")
b.snippet([
    "# 执行一次即可：python -m app.init_db",
    "1. 创建所有表（由 Alembic 完成，不调用 create_all）",
    "2. 从 .env 读取 ADMIN_USERNAME / ADMIN_PASSWORD",
    "3. 若无同名用户 → 用 bcrypt 哈希密码后插入 users 表",
    "4. 写入 site_config 的默认配置项（已存在则跳过）",
    "5. 输出：'初始化完成，请用 xxx 登录并立即修改密码'",
], caption="幂等设计：重复执行不会报错、不会覆盖已有数据。")
b.callout("初始化脚本的密码来源：",
          "密码从 `.env` 读取，**不写在脚本里、不写进文档、不提交仓库**。"
          "首次登录后应立即修改，并把 `.env` 里的初始密码清空。", kind="warn")

# ============================================================
b.chapter("7", "完成标准")
b.table(["#", "检查项", "结论"],
        [["1", "表结构可直接生成建表语句", "✅ 见第 3 章，字段含类型、约束、说明"],
         ["2", "每张表都有存在理由，无冗余表", "✅ 4 张业务表 + 1 张配置表"],
         ["3", "关系与级联行为明确", "✅ 见第 2 章与 3.3"],
         ["4", "索引有明确支撑的查询", "✅ 见第 4 章，含「不建什么」"],
         ["5", "迁移策略明确且可回滚", "✅ 见第 5 章"],
         ["6", "备份与恢复有具体命令", "✅ 见 5.3，含恢复演练要求"],
         ["7", "SQLite 专项设置已列出", "✅ 见 1.4（含最易漏的 `foreign_keys`）"]],
        widths=[1.0, 6.4, 9.7], first_col_bold=True)

b.save()
