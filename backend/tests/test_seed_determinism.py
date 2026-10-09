"""验证种子数据的阅读数是确定性公式算出来的

这个脚本做两件事：
1. 手算核对公式（任何人不用跑代码就能验证这几个值）
2. 核对数据库里的实际值是否与公式一致

为什么要单独验证一个"造数据的公式"：
因为它现在已经进入了"可被断言"的范围 —— 有人可能在测试里写
`assert view_count == 16`。如果公式和实际存库的值不一致，
那条测试会在最难排查的地方失败。
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.seed_data import ARTICLES, fake_view_count  # noqa: E402

DB = r"E:\project\blog\backend\data\db\blog.db"

failed = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    if not ok:
        failed.append(name)


print("=" * 60)
print("1. 公式手算核对")
print("=" * 60)
# 这几个值是**人工独立算出来**的，不是从公式抄来的。
#
# 这正是这个测试的意义所在：如果期望值写成 fake_view_count(11)，
# 那测试只是把公式复述了一遍，公式错了它也照样通过。
# 手写死值才能形成「独立验证」。
#
# 曾经真的抓到过错误：初版把 index=11 写成 13，
# 实际是 (11*37+13) % 397 + 3 = 420 % 397 + 3 = 23 + 3 = 26。
# 算错的原因是在中间步骤漏加了公式里的 +13。
EXPECTED = {0: 16, 1: 53, 2: 90, 10: 386, 11: 26}
for index, expected in EXPECTED.items():
    actual = fake_view_count(index)
    check(f"index={index} → {expected}", actual == expected, f"实际 {actual}")

print()
print("=" * 60)
print("2. 取值范围")
print("=" * 60)
values = [fake_view_count(i) for i in range(200)]
check("最小值 >= 3", min(values) >= 3, f"min={min(values)}")
check("最大值 <= 399", max(values) <= 399, f"max={max(values)}")
check("不是常数（看起来像真实数据）", len(set(values)) > 100, f"{len(set(values))} 个不同值")

print()
print("=" * 60)
print("3. 与数据库实际值一致")
print("=" * 60)
conn = sqlite3.connect(DB)
rows = conn.execute("SELECT slug, view_count FROM articles WHERE status='published'").fetchall()
db_map = {slug: count for slug, count in rows}
conn.close()

from app.utils.slug import make_slug_from_title  # noqa: E402

mismatch = []
for index, (title, _tags) in enumerate(ARTICLES):
    slug = make_slug_from_title(title)
    expected = fake_view_count(index)
    actual = db_map.get(slug)
    if actual != expected:
        mismatch.append((slug, expected, actual))

check("每篇文章的阅读数与公式一致", not mismatch, f"{len(mismatch)} 处不符" + (f"：{mismatch[:3]}" if mismatch else ""))

print()
print("=" * 60)
print("FAILED:", failed if failed else "none")
sys.exit(1 if failed else 0)
