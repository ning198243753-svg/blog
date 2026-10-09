"""数据核对：开发期快速查看库里有什么

注意 SQL 字符串的写法：f-string 里嵌引号在 Python 3.12 之前不允许
引号复用，所以这里把 SQL 全部提到变量里，避免在 f-string 里转义引号。
"""

import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else r"E:\project\blog\backend\data\db\blog.db"
c = sqlite3.connect(DB)


def q(sql: str) -> int:
    return c.execute(sql).fetchone()[0]


SQL_ALL = "SELECT COUNT(*) FROM articles"
SQL_PUB = "SELECT COUNT(*) FROM articles WHERE status='published'"
SQL_DRAFT = "SELECT COUNT(*) FROM articles WHERE status='draft'"
SQL_TAGS = "SELECT COUNT(*) FROM tags"
SQL_LINKS = "SELECT COUNT(*) FROM article_tags"
SQL_GROUPS = (
    "SELECT COUNT(DISTINCT strftime('%Y-%m', published_at)) "
    "FROM articles WHERE status='published'"
)
SQL_USERS = "SELECT COUNT(*) FROM users"
SQL_CONFIG = "SELECT COUNT(*) FROM site_config"

print("=" * 46)
print("数据库概况")
print("=" * 46)
print(f"{'文章总数':<14}{q(SQL_ALL)}")
print(f"{'已发布':<15}{q(SQL_PUB)}")
print(f"{'草稿':<16}{q(SQL_DRAFT)}")
print(f"{'标签数':<15}{q(SQL_TAGS)}")
print(f"{'关联行':<16}{q(SQL_LINKS)}")
print(f"{'归档分组':<14}{q(SQL_GROUPS)}")
print(f"{'用户数':<15}{q(SQL_USERS)}")
print(f"{'站点配置':<14}{q(SQL_CONFIG)}")

print()
print("=" * 46)
print("各标签文章数（应只统计已发布）")
print("=" * 46)
for name, count in c.execute(
    """
    SELECT t.name, COUNT(a.id)
    FROM tags t
    LEFT JOIN article_tags at ON at.tag_id = t.id
    LEFT JOIN articles a ON a.id = at.article_id AND a.status = 'published'
    GROUP BY t.id
    ORDER BY COUNT(a.id) DESC, t.name
    """
).fetchall():
    print(f"  {name:<12} {count}")

print()
print("=" * 46)
print("归档分组明细")
print("=" * 46)
for ym, count in c.execute(
    """
    SELECT strftime('%Y-%m', published_at) AS ym, COUNT(*)
    FROM articles WHERE status = 'published'
    GROUP BY ym ORDER BY ym DESC
    """
).fetchall():
    print(f"  {ym}  {count} 篇")

c.close()
