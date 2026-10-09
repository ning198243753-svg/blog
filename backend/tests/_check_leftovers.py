"""检查 M4 测试是否在开发库留下残留数据

M2 的回归测试在访问一篇标题为 "M4 验证文章 ..." 的文章，
说明 M4 测试的清理没有生效，或者有别的测试留下了数据。
"""

import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parent.parent / "data" / "db" / "blog.db"
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row

print(f"开发库：{db}")
print()

print("=== 所有文章（标题 + 状态 + slug）===")
rows = con.execute(
    "SELECT id, title, slug, status, published_at FROM articles ORDER BY id"
).fetchall()
for r in rows:
    flag = ""
    if "M4" in r["title"] or "验证" in r["title"]:
        flag = "   <<< 测试残留！"
    print(f"  #{r['id']:<3} [{r['status']:<9}] {r['title'][:44]:<46}{flag}")

print()
print(f"总计 {len(rows)} 篇")
print()

print("=== 疑似测试残留 ===")
suspects = [r for r in rows if "M4" in r["title"] or "验证文章" in r["title"]]
if suspects:
    for r in suspects:
        print(f"  #{r['id']} {r['title']}  status={r['status']}")
else:
    print("  无")

print()
print("=== 标签里是否有测试残留 ===")
for r in con.execute("SELECT id, name, slug FROM tags ORDER BY id").fetchall():
    flag = "   <<< 测试残留！" if "M4" in r["name"] else ""
    print(f"  #{r['id']:<3} {r['name']}{flag}")

print()
print("=== site_config 的站标题 ===")
for r in con.execute(
    "SELECT key, value FROM site_config WHERE key IN ('site_title','site_subtitle')"
).fetchall():
    print(f"  {r['key']} = {r['value']}")

con.close()
