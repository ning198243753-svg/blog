"""安全相关：密码哈希、会话签名（ADR-03）

会话方案说明（《04-数据库设计-v1.0》第 1.3 节）：
不建 sessions 表，也不用进程内内存，而是把「用户 id + 过期时间」
用 SECRET_KEY 签名后放进 Cookie。

代价是服务端无法主动强制下线（没有可作废的会话记录），
收益是每次请求都不用查数据库。
单人博客下这个交换是划算的——需要强制下线时改 SECRET_KEY 即可，
所有已签发的 Cookie 会同时失效。
"""

import base64
import hashlib
import hmac
import json
import time

from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _sign(payload: bytes) -> str:
    signature = hmac.new(settings.secret_key.encode("utf-8"), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def create_session_token(user_id: int) -> str:
    """签发会话令牌：base64(payload).signature"""
    payload = json.dumps(
        {
            "uid": user_id,
            "exp": int(time.time()) + settings.session_expire_days * 86400,
        },
        separators=(",", ":"),
    ).encode("utf-8")

    return f"{_b64encode(payload)}.{_sign(payload)}"


def read_session_token(token: str) -> int | None:
    """校验并解析会话令牌，返回 user_id；无效或过期返回 None

    用 hmac.compare_digest 而不是 ==：字符串比较会在第一个不同的字符处返回，
    攻击者可以据此逐字节猜测签名（时序攻击）。
    """
    if not token or "." not in token:
        return None

    payload_b64, _, signature = token.partition(".")
    try:
        payload = _b64decode(payload_b64)
    except Exception:  # noqa: BLE001 - 任何解码失败都视为无效令牌
        return None

    if not hmac.compare_digest(_sign(payload), signature):
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if int(data.get("exp", 0)) < int(time.time()):
        return None

    uid = data.get("uid")
    return int(uid) if isinstance(uid, int) else None
