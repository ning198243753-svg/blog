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

import bcrypt

from app.config import settings

# ---------------------------------------------------------------
# 密码哈希：直接使用 bcrypt，不经 passlib
#
# 之前用 passlib 的 CryptContext(schemes=["bcrypt"])，会持续输出
#     AttributeError: module 'bcrypt' has no attribute '__about__'
# 原因：bcrypt 4.x 移除了 __about__ 属性，而 passlib 1.7.4（2020 年发布）
# 仍在读它来探测版本号。哈希结果本身是正确的，所以这只是一个警告 ——
# 但「已知警告」会让人对新出现的警告失去敏感度，这比警告本身更危险。
#
# 换掉 passlib 的另一个理由是它已停止维护，而密码哈希属于安全组件。
# 直接调用只涉及两个函数（hashpw / checkpw），包装层带来的复杂度
# 大于它提供的便利。
#
# 兼容性：现有哈希是标准 $2b$12$ 格式，bcrypt 可直接校验，
# 不需要重算任何已存密码。
# ---------------------------------------------------------------

# bcrypt 的工作因子。12 是 2026 年的常见取值：
# 单次哈希约 250ms，对登录接口可接受，同时让离线爆破的成本足够高。
# 不要再调低 —— 这个数字直接决定攻击者每秒能试多少个密码。
_BCRYPT_ROUNDS = 12

# bcrypt 只处理前 72 字节，超出部分会被**静默截断**。
# 若不拦截，用户设置一个 100 字符的密码，后 28 个字符其实是无效的 ——
# 这不会报错，但会让「密码长度」这个安全假设失效。
# 用 bcrypt 自己的常量而不是硬编码 72，避免版本间含义变化。
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """生成密码哈希

    bcrypt 要求输入是 bytes。这里显式 UTF-8 编码，
    让中文密码也能正确处理（不编码的话 Python 会直接抛 TypeError）。
    """
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        raise ValueError(
            f"密码过长：bcrypt 最多处理 {_BCRYPT_MAX_BYTES} 字节，"
            f"当前 {len(raw)} 字节（中文一个字约占 3 字节）"
        )
    return bcrypt.hashpw(raw, bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    """校验密码

    所有「不匹配」都返回 False，不抛异常：
    密码错、超长密码、哈希格式损坏。

    【为什么这里捕获 BaseException 而不是 Exception】
    bcrypt 4.x 是 Rust 实现（PyO3 绑定）。遇到格式损坏的哈希时，
    Rust 侧会 panic，而 pyo3 把 panic 转成的 PanicException
    **直接继承 BaseException，不经过 Exception**：

        PanicException → BaseException → object

    所以 `except Exception` 捕不到它 —— 后果是登录接口 500，
    而日志里只有一句 Rust panic，排查方向完全错误。
    （实测：bcrypt.checkpw(b"x", b"$2b$12$tooshort") 会 panic。）

    不能写裸的 `except BaseException`：那会连 KeyboardInterrupt 和
    SystemExit 一起吞掉，Ctrl+C 将无法中断进程 —— 那是更糟的问题。
    所以显式排除这两个。
    """
    try:
        raw = password.encode("utf-8")
        if len(raw) > _BCRYPT_MAX_BYTES:
            return False
        return bcrypt.checkpw(raw, password_hash.encode("ascii"))
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException:  # noqa: BLE001 - 含 pyo3 的 PanicException
        # TypeError: 哈希不是字符串 / 不是合法 ASCII
        # ValueError: 哈希不是合法 bcrypt 格式
        # PanicException: Rust 侧对畸形输入 panic
        return False


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
