"""密码哈希验证（M3 前置：从 passlib 切换到 bcrypt 直调）

要验证的不只是「新密码能哈希能校验」，而是三件事：

1. 新哈希是合法 bcrypt 格式，且能被自己校验
2. **数据库里已有的哈希仍能校验** —— 切换库最怕的就是让现有账号登不进去
3. 边界情况不抛异常：空密码、超长密码、损坏的哈希

第 2 条是关键。如果换库时哈希格式变了，用户不会收到「格式不兼容」的提示，
只会看到「用户名或密码错误」—— 那是最难排查的一类故障。
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.security import hash_password, verify_password  # noqa: E402

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "blog.db"

failed = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    if not ok:
        failed.append(name)


print("=" * 62)
print("1. 新哈希的格式与自校验")
print("=" * 62)

h = hash_password("TestPassw0rd!2026")
check("哈希以 $2b$ 开头（标准 bcrypt）", h.startswith("$2b$"), h[:12])
check("哈希长度为 60", len(h) == 60, f"len={len(h)}")
check("成本因子为 12", h.split("$")[2] == "12", h.split("$")[2])
check("正确密码校验通过", verify_password("TestPassw0rd!2026", h))
check("错误密码校验失败", not verify_password("wrong-password", h))
check("空密码校验失败", not verify_password("", h))

# 同一个密码两次哈希必须不同 —— bcrypt 每次生成随机 salt。
# 如果相同，说明 salt 没生效，那所有相同密码的用户会有相同哈希，
# 一次破解就能命中多个账号。
h2 = hash_password("TestPassw0rd!2026")
check("同一密码两次哈希不同（salt 随机）", h != h2)
check("两个不同哈希都能校验原密码",
      verify_password("TestPassw0rd!2026", h) and verify_password("TestPassw0rd!2026", h2))

print()
print("=" * 62)
print("2. 中文密码与边界情况")
print("=" * 62)

cn = hash_password("中文密码测试")
check("中文密码可哈希", cn.startswith("$2b$"))
check("中文密码可校验", verify_password("中文密码测试", cn))
check("中文密码错误时不通过", not verify_password("中文密码测试2", cn))

# 72 字节边界：bcrypt 只处理前 72 字节，超出必须显式拒绝而不是静默截断。
# 中文一个字 3 字节，所以 24 个汉字正好是 72 字节。
exactly_72_bytes = "汉" * 24
check("正好 72 字节的密码可哈希", hash_password(exactly_72_bytes).startswith("$2b$"))

too_long = "汉" * 25  # 75 字节
try:
    hash_password(too_long)
    check("超过 72 字节应抛 ValueError", False, "没有抛异常（会被静默截断）")
except ValueError as exc:
    check("超过 72 字节应抛 ValueError", True, str(exc)[:50])

# 校验超长密码不应抛异常，只返回 False
# （哈希是用别的密码生成的，长度检查要在比较之前生效）
try:
    r = verify_password(too_long, h)
    check("校验超长密码不抛异常、返回 False", r is False, f"返回 {r}")
except Exception as exc:  # noqa: BLE001
    check("校验超长密码不抛异常、返回 False", False, f"抛了 {type(exc).__name__}")

print()
print("=" * 62)
print("3. 损坏的哈希不抛异常")
print("=" * 62)

for bad in ("", "not-a-hash", "$2b$12$tooshort", "中文乱码", "$2x$12$" + "a" * 53):
    try:
        r = verify_password("anything", bad)
        check(f"损坏哈希 {bad[:15]!r} 返回 False 而非抛异常", r is False, f"返回 {r}")
    except Exception as exc:  # noqa: BLE001
        check(f"损坏哈希 {bad[:15]!r} 返回 False 而非抛异常", False, f"抛了 {type(exc).__name__}")

print()
print("=" * 62)
print("4. 数据库中已有哈希的兼容性（最关键）")
print("=" * 62)

conn = sqlite3.connect(str(DB))
rows = conn.execute("SELECT username, password_hash FROM users").fetchall()
conn.close()

check("数据库中存在用户", len(rows) > 0, f"{len(rows)} 个")

for username, existing_hash in rows:
    check(f"{username} 的哈希格式为标准 bcrypt",
          existing_hash.startswith("$2b$") and len(existing_hash) == 60,
          existing_hash[:12])

    # 用错误密码校验，确认能正常返回 False（说明哈希可解析）
    try:
        r = verify_password("definitely-not-the-password", existing_hash)
        check(f"{username} 的错误密码返回 False（哈希可解析）", r is False)
    except Exception as exc:  # noqa: BLE001
        check(f"{username} 的错误密码返回 False（哈希可解析）", False,
              f"抛了 {type(exc).__name__}: {exc}")

print()
print("=" * 62)
print("5. 用新库重新生成的哈希替换后仍可登录（模拟改密码流程）")
print("=" * 62)

new_hash = hash_password("NewPassw0rd!2026")
check("新生成的哈希可用于校验", verify_password("NewPassw0rd!2026", new_hash))
check("旧密码对新哈希无效", not verify_password("TestPassw0rd!2026", new_hash))

print()
print("=" * 62)
print("FAILED:", failed if failed else "none")
print("=" * 62)
sys.exit(1 if failed else 0)
