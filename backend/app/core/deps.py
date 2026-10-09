"""鉴权依赖（文档 05 第 3 章）

这是 M3 所有后台接口的基础。设计要点如下。

【为什么不放在 routers/ 里】
依赖不是路由 —— 它会被 auth.py 和 admin.py 同时使用。
放在 core/ 下，两个 router 都 import 它，方向是单向的。

【为什么依赖注入而不是中间件】
中间件会对**所有**请求生效，包括公开接口和 /docs。
那样就得在中间件里维护一张"哪些路径需要登录"的白名单，
而白名单会随路由增加而漏更新 —— 漏了就是未授权访问。
用依赖是"哪个接口需要就在哪个函数上声明"，默认为公开，
需要显式添加才是受保护的，这个默认方向是安全的。

【会话方案】
Cookie 里存的是「user id + 过期时间」的 HMAC 签名串（ADR-03），
每次请求验签即可，不查库、不查 sessions 表。
代价是无法主动强制下线 —— 需要时改 SECRET_KEY，所有 Cookie 同时失效。
"""

from fastapi import Cookie, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.errors import BizError, ErrorCode
from app.core.security import read_session_token
from app.database import get_db
from app.models import User


def get_current_user(
    db: Session = Depends(get_db),
    # Cookie 名从配置读。参数名必须与 Cookie 名一致，
    # 所以这里用 alias 把「配置里的变量名」和「Cookie 的实际名字」解耦 ——
    # 否则一旦有人改了 session_cookie_name，这个函数会静默拿不到值。
    session: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> User:
    """要求登录：未登录或令牌失效时抛 401

    http_status=401 而不是 200：文档 05 规定鉴权失败返回 HTTP 401，
    前端 Axios 拦截器靠这个状态码触发跳转登录页。
    业务码 40100 与 HTTP 401 同时给出，两者含义不同（见 core/errors.py）。
    """
    if not session:
        raise BizError(ErrorCode.UNAUTHORIZED, http_status=401)

    user_id = read_session_token(session)
    if user_id is None:
        # 令牌无效、被篡改、或已过期 —— 对调用方是同一件事：重新登录
        raise BizError(ErrorCode.UNAUTHORIZED, http_status=401)

    user = db.get(User, user_id)
    if user is None:
        # 令牌签名有效但用户已被删除（例如重建了数据库）。
        # 这种情况不返回 401，而是当作未登录 —— 否则前端会陷入
        # 「有令牌但一直 401」的循环。
        raise BizError(ErrorCode.UNAUTHORIZED, http_status=401)

    return user


def get_current_user_optional(
    db: Session = Depends(get_db),
    session: str | None = Cookie(default=None, alias=settings.session_cookie_name),
) -> User | None:
    """可选登录：未登录返回 None 而不是抛异常

    给「登录后显示额外内容、未登录也能看」的接口用。
    M3 暂时没有这样的接口，但保留它可以让将来新增这类接口时
    不需要改动鉴权层。
    """
    if not session:
        return None
    user_id = read_session_token(session)
    if user_id is None:
        return None
    return db.get(User, user_id)
