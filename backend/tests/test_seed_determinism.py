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

# 【这一段的断言是修正过的，说明原因】
#
# 最初的写法是：断言「库里的 view_count 恒等于公式值」。
# 它第一次能过，随后就长期失败 —— 原因不是公式错了，而是这个断言
# 建立在一个错误前提上：**view_count 是运行时状态，不是种子数据。**
#
# 每次打开一篇文章详情，后端都会 view_count += 1。
# 只要有人访问过站点，这个值就不再等于 seed 时写入的初值。
# 于是这个「测试」实际上在断言「没人访问过这个站点」——
# 它跟代码正确性无关，只会制造假失败。
#
# 现在的断言改成验证**真正成立的性质**：
#   库里每一篇文章的阅读数 >= 公式给它的初值
# 因为阅读数只增不减，所以「当前值不小于初值」是恒成立的。
# 它仍然能抓住「种子数据写错了初值」这类错误
# （比如把初值写成 0，或公式被改成负数），
# 但不会因为正常访问而误报。

conn = sqlite3.connect(DB)
rows = conn.execute("SELECT slug, view_count FROM articles WHERE status='published'").fetchall()
db_map = {slug: count for slug, count in rows}
conn.close()

from app.utils.slug import make_slug_from_title  # noqa: E402

missing = []
below_initial = []
for index, (title, _tags) in enumerate(ARTICLES):
    slug = make_slug_from_title(title)
    initial = fake_view_count(index)
    actual = db_map.get(slug)
    if actual is None:
        missing.append(slug)
    elif actual < initial:
        # 只增不减：当前值小于初值说明种子数据或计数逻辑被改坏了
        below_initial.append((slug, initial, actual))

check("公式覆盖的每篇文章都在库中", not missing,
      f"{len(missing)} 篇缺失" + (f"：{missing[:3]}" if missing else ""))

check("每篇文章的阅读数不低于公式初值（只增不减）", not below_initial,
      f"{len(below_initial)} 处异常" + (f"：{below_initial[:3]}" if below_initial else ""))

# 反过来说明「为什么不能断言相等」：把当前值与初值的差值打印出来，
# 让读的人直接看到「访问确实增加了它」。
grew = sum(1 for i, (title, _t) in enumerate(ARTICLES)
           if (v := db_map.get(make_slug_from_title(title))) is not None
           and v > fake_view_count(i))
check("阅读数确实会因访问而增长（证明它是运行时状态）", grew > 0,
      f"{grew} 篇的阅读数高于种子初值 —— 这正是不能断言相等的原因")

print()
print("=" * 60)
print("FAILED:", failed if failed else "none")
sys.exit(1 if failed else 0)
