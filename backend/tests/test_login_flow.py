"""验证切换到 bcrypt 直调后，真实账号仍能登录

前一个测试（test_password.py）用的是自己造的哈希。
这里用**数据库里那个真实的管理员账号**走完整流程：
从 .env 读 ADMIN_PASSWORD → 用它的哈希 → 执行登录接口 → 拿 Cookie。
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.core.security import create_session_token, read_session_token, verify_password  # noqa: E402

DB = Path(__file__).resolve().parent.parent / "data" / "db" / "blog.db"
failed = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")
    if not ok:
        failed.append(name)


print("=" * 62)
print("1. 配置里的管理员密码")
print("=" * 62)
print(f"admin_username = {settings.admin_username}")
print(f"admin_password = {'(已设置，长度 ' + str(len(settings.admin_password)) + ')' if settings.admin_password else '(空！)'}")

check("ADMIN_PASSWORD 已配置", bool(settings.admin_password))

print()
print("=" * 62)
print("2. 用配置里的密码校验数据库中的哈希")
print("=" * 62)

conn = sqlite3.connect(str(DB))
row = conn.execute(
    "SELECT username, password_hash FROM users WHERE username = ?",
    (settings.admin_username,),
).fetchone()
conn.close()

check("数据库中存在该管理员", row is not None)

if row:
    username, stored_hash = row
    ok = verify_password(settings.admin_password, stored_hash)
    check("配置密码与库中哈希匹配（可登录）", ok,
          "如果不匹配说明 .env 里的密码与库不一致" if not ok else "")

    wrong = verify_password("definitely-wrong-password", stored_hash)
    check("错误密码被拒绝", wrong is False)

    # 大小写敏感：bcrypt 是大小写敏感的，不能像某些系统那样忽略大小写
    if settings.admin_password:
        swapped = settings.admin_password.swapcase()
        if swapped != settings.admin_password:
            check("密码大小写敏感",
                  verify_password(swapped, stored_hash) is False)

print()
print("=" * 62)
print("3. 会话令牌（登录后签发的 Cookie 内容）")
print("=" * 62)

token = create_session_token(1)
check("能签发令牌", bool(token) and "." in token, token[:40] + "...")

check("能解析回 user_id", read_session_token(token) == 1)

check("篡改签名后失效", read_session_token(token[:-4] + "AAAA") is None)
check("篡改内容后失效", read_session_token("AAAA." + token.split(".")[1]) is None)
check("空令牌返回 None", read_session_token("") is None)
check("无点号令牌返回 None", read_session_token("nodothere") is None)

# 过期令牌：手工构造一个 exp 在过去的 payload
# 这三个导入放在这里是因为只有本段用到；
# base64 不需要 —— 编码由 security 模块的 _b64encode 负责，
# 直接调它比自己再实现一遍更不容易出错。
import json  # noqa: E402
import time  # noqa: E402

from app.core.security import _b64encode, _sign  # noqa: E402

past = json.dumps({"uid": 1, "exp": int(time.time()) - 100}, separators=(",", ":")).encode()
expired_token = f"{_b64encode(past)}.{_sign(past)}"
check("过期令牌被拒绝", read_session_token(expired_token) is None)

print()
print("=" * 62)
print("FAILED:", failed if failed else "none")
print("=" * 62)
sys.exit(1 if failed else 0)
