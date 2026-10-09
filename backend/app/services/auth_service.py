"""鉴权服务层（文档 05 第 3 章）

本层禁止导入 fastapi 的 Request / Response —— 那是 HTTP 细节，
属于路由层。这里只处理「用户名密码对不对」这类业务判断。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BizError, ErrorCode
from app.core.security import verify_password
from app.models import User
from app.utils.time import to_iso_z


def authenticate(db: Session, username: str, password: str) -> User:
    """校验用户名与密码

    【这里有两个刻意的设计】

    1. 用户名不存在与密码错误返回**同一个**错误码（40101）。
       如果分开返回，这个接口就变成了「用户名枚举器」：
       攻击者可以逐个试出哪些账号存在，再针对性爆破密码。
       文档 05 也明确要求统一提示「用户名或密码错误」。

    2. 用户名不存在时**不做**任何 hash 计算，直接返回。
       这带来一个理论上的时序差异（存在的账号会慢约 250ms）。
       常见做法是「用户不存在时也做一次假 hash」来抹平差异，
       但那会让暴力破解时的服务端开销翻倍 —— 而一个单人博客的
       登录接口本来就不该暴露在公网爆破之下（M5 会加 Nginx 限流）。
       这里选择简单直接，并把权衡写清楚。
    """
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise BizError(ErrorCode.BAD_CREDENTIALS, http_status=401)

    # verify_password 内部已处理畸形哈希与超长密码，不会抛异常
    if not verify_password(password, user.password_hash):
        raise BizError(ErrorCode.BAD_CREDENTIALS, http_status=401)

    return user


def to_current_user(user: User) -> dict:
    """ORM 对象 → 当前用户字典

    手工挑字段而不是 model_validate(user)：
    后者依赖响应模型来过滤，一旦有人给响应模型加上 password_hash
    就会直接泄漏。手工挑字段的默认方向是安全的。
    """
    return {
        "id": user.id,
        "username": user.username,
        "created_at": to_iso_z(user.created_at),
    }
