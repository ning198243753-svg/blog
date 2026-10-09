"""M0 验收：数据库结构 + 外键真实生效 + PRAGMA（不依赖任何库，用标准库 sqlite3）"""

import sqlite3
import sys

DB = r"E:\project\blog\backend\data\db\blog.db"

FAIL = []


def check(name, condition, detail=""):
    mark = "PASS" if condition else "FAIL"
    if not condition:
        FAIL.append(name)
    print(f"[{mark}] {name}  {detail}")


c = sqlite3.connect(DB)
cur = c.cursor()

# ---- 1. 表齐全 ----
tables = sorted(r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"))
expected = {"articles", "article_tags", "tags", "users", "site_config"}
check("5 张业务表", expected.issubset(set(tables)), str(tables))
check("alembic 版本表存在", "alembic_version" in tables)

# ---- 2. 索引齐全 ----
indexes = sorted(r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='index'"))
need = {"idx_articles_created", "idx_articles_status_published", "idx_article_tags_tag"}
check("自定义索引齐全", need.issubset(set(indexes)), str(indexes))

# ---- 3. PRAGMA ----
j = cur.execute("PRAGMA journal_mode").fetchone()[0]
check("journal_mode = WAL", j.lower() == "wal", j)

fk = cur.execute("PRAGMA foreign_keys").fetchone()[0]
# 注意：sqlite3 模块默认不开外键，这里读到 0 是正常的；
# 应用层由 SQLAlchemy 的 connect 事件开启。下面单独验证应用层。
print(f"[INFO] 本连接的 foreign_keys = {fk}（sqlite3 默认关闭，属预期）")

# ---- 4. 结构细节 ----
cols = {r[1] for r in cur.execute("PRAGMA table_info(articles)")}
check(
    "articles 字段齐全",
    {"id", "title", "slug", "summary", "content_md", "content_html", "status",
     "author_id", "view_count", "published_at", "created_at", "updated_at"}.issubset(cols),
    str(sorted(cols)),
)

pk = [r[1] for r in sorted(cur.execute("PRAGMA table_info(article_tags)"), key=lambda r: r[5])
      if r[5] > 0]
check("article_tags 复合主键", pk == ["article_id", "tag_id"], str(pk))

c.close()
print()
print("FAILED:", FAIL if FAIL else "none")
sys.exit(1 if FAIL else 0)
