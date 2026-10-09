"""M3 鉴权接口端到端验证（3 个接口）

走真实 HTTP + 真实 Cookie，不用 httpx 的 TestClient —— 
理由与 M1 相同：TestClient 会绕过 uvicorn 的 Cookie 处理，
而本次要验证的恰恰是 Cookie 有没有被正确设置和清除。
"""

import json
import os
import sys
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402

BASE = "http://127.0.0.1:8000/api"
failed = []
passed = 0

COOKIE_NAME = settings.session_cookie_name


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
    else:
        failed.append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def make_opener(with_cookies: bool = True):
    """构造一个会携带 Cookie 的 opener"""
    if with_cookies:
        jar = CookieJar()
        return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar
    return urllib.request.build_opener(), None


def call(opener, method: str, path: str, body: dict | None = None):
    """返回 (状态码, 响应体, 原始 headers)"""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with opener.open(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8")), resp.headers
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw), exc.headers
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw}, exc.headers


print("=" * 64)
print("M3 鉴权接口验证")
print("=" * 64)

password = settings.admin_password or os.environ.get("ADMIN_PASSWORD", "")
username = settings.admin_username

if not password:
    print("[跳过] ADMIN_PASSWORD 未设置，无法测试登录")
    sys.exit(0)

# ---------- 1. 未登录状态 ----------
print("\n--- 未登录 ---")
opener, _ = make_opener()
status, body, _h = call(opener, "GET", "/auth/me")
check("未登录访问 /auth/me 返回 401", status == 401, f"status={status}")
check("业务码为 40100", body.get("code") == 40100, f"code={body.get('code')}")
check("401 也带统一响应体", all(k in body for k in ("code", "message", "data")))

# ---------- 2. 错误密码 ----------
print("\n--- 登录失败 ---")
opener, jar = make_opener()
status, body, _h = call(opener, "POST", "/auth/login", {"username": username, "password": "wrong-password"})
check("错误密码返回 401", status == 401, f"status={status}")
check("业务码为 40101", body.get("code") == 40101, f"code={body.get('code')}")

# 用户名不存在时必须是同一个错误码 —— 否则就是用户名枚举器
status2, body2, _h = call(
    opener, "POST", "/auth/login", {"username": "no-such-user-xyz", "password": "whatever"}
)
check("用户名不存在返回同一错误码（不可枚举用户名）",
      body2.get("code") == body.get("code") == 40101,
      f"不存在={body2.get('code')} 密码错={body.get('code')}")
check("两种失败的提示语完全相同",
      body2.get("message") == body.get("message"),
      f"{body2.get('message')!r} vs {body.get('message')!r}")

cookies_after_fail = [c for c in jar] if jar else []
check("登录失败不下发 Cookie", len(cookies_after_fail) == 0,
      f"{len(cookies_after_fail)} 个 cookie")

# ---------- 3. 正确登录 ----------
print("\n--- 登录成功 ---")
opener, jar = make_opener()
status, body, headers = call(opener, "POST", "/auth/login", {"username": username, "password": password})
check("正确密码返回 200", status == 200, f"status={status}")
check("业务码为 0", body.get("code") == 0, f"code={body.get('code')}")
check("返回用户名", body["data"]["username"] == username, body["data"].get("username"))
check("响应中不含 password_hash", "password_hash" not in json.dumps(body),
      f"字段={sorted(body['data'].keys())}")

# Cookie 属性 —— 这几条是安全性的关键
set_cookie = headers.get("Set-Cookie", "")
check(f"下发了 {COOKIE_NAME} Cookie", COOKIE_NAME in set_cookie, set_cookie[:60])
check("Cookie 带 HttpOnly（JS 读不到）", "HttpOnly" in set_cookie)
check("Cookie 带 SameSite=Lax（防 CSRF）", "samesite=lax" in set_cookie.lower())
check("Cookie 带 Max-Age（会过期）", "max-age" in set_cookie.lower())
check("Cookie 的 Path=/", "path=/" in set_cookie.lower())

jar_cookies = [c for c in jar]
check("Cookie 已存入客户端 jar", len(jar_cookies) == 1, f"{len(jar_cookies)} 个")

# ---------- 4. 带 Cookie 访问 ----------
print("\n--- 已登录 ---")
status, body, _h = call(opener, "GET", "/auth/me")
check("已登录访问 /auth/me 返回 200", status == 200, f"status={status}")
check("返回正确的用户", body["data"]["username"] == username, str(body["data"]))
check("created_at 带 Z 后缀", str(body["data"]["created_at"]).endswith("Z"),
      body["data"].get("created_at"))

# ---------- 5. 伪造与篡改 ----------
print("\n--- 令牌安全 ---")


def call_with_cookie(method: str, path: str, cookie_value: str):
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("Cookie", f"{COOKIE_NAME}={cookie_value}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except json.JSONDecodeError:
            return exc.code, {}


real_token = jar_cookies[0].value

status, body = call_with_cookie("GET", "/auth/me", "garbage-token")
check("随机字符串被拒绝", status == 401, f"status={status}")

status, body = call_with_cookie("GET", "/auth/me", real_token[:-4] + "AAAA")
check("篡改签名被拒绝", status == 401, f"status={status}")

# 改 payload 但保留签名 —— 签名校验必须能发现
parts = real_token.split(".")
if len(parts) == 2:
    import base64

    padded = parts[0] + "=" * (-len(parts[0]) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    payload["uid"] = 999999
    tampered = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    status, body = call_with_cookie("GET", "/auth/me", f"{tampered}.{parts[1]}")
    check("篡改 payload（改 uid）被拒绝", status == 401, f"status={status}")

# 空 Cookie
status, body = call_with_cookie("GET", "/auth/me", "")
check("空 Cookie 被拒绝", status == 401, f"status={status}")

# ---------- 6. 登出 ----------
print("\n--- 登出 ---")
status, body, headers = call(opener, "POST", "/auth/logout")
check("登出返回 200", status == 200, f"status={status}")
check("登出业务码为 0", body.get("code") == 0, f"code={body.get('code')}")

set_cookie = headers.get("Set-Cookie", "")
check("登出时清除了 Cookie",
      COOKIE_NAME in set_cookie and ("max-age=0" in set_cookie.lower() or "expires" in set_cookie.lower()),
      set_cookie[:70])

# 登出后携带旧令牌仍应被拒绝？—— 注意：签名方案下旧令牌在过期前依然有效！
# 这是「无 sessions 表」这个决策的已知代价（ADR-03），下面显式验证并记录。
status, body = call_with_cookie("GET", "/auth/me", real_token)
still_valid = status == 200
check("登出后旧令牌在服务端仍然有效（ADR-03 的已知代价）", still_valid,
      "这是签名 Cookie 方案的固有取舍：没有可作废的会话记录，"
      "浏览器侧已清除 Cookie，但令牌本身要等到过期才失效")

# 新 opener（新 jar）模拟浏览器已清除 Cookie
opener2, jar2 = make_opener()
status, body, _h = call(opener2, "GET", "/auth/me")
check("新会话（无 Cookie）访问 /auth/me 返回 401", status == 401, f"status={status}")

# 未登录也能登出 —— 避免「令牌已过期时退不出去」
opener3, _ = make_opener()
status, body, _h = call(opener3, "POST", "/auth/logout")
check("未登录调用登出不报错（幂等）", status == 200, f"status={status}")

# ---------- 7. 参数校验 ----------
print("\n--- 参数校验 ---")
opener4, _ = make_opener()
status, body, _h = call(opener4, "POST", "/auth/login", {"username": username})
check("缺少 password 返回 422", status == 422, f"status={status}")
check("422 业务码为 42200", body.get("code") == 42200, f"code={body.get('code')}")

status, body, _h = call(opener4, "POST", "/auth/login", {"username": "x" * 100, "password": "y"})
check("超长用户名被拒（422）", status == 422, f"status={status}")

print()
print("=" * 64)
print(f"通过 {passed} 项，失败 {len(failed)} 项")
if failed:
    print("失败清单：")
    for name in failed:
        print(f"  - {name}")
print("=" * 64)

sys.exit(1 if failed else 0)
