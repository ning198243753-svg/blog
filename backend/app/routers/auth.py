"""鉴权接口（文档 05 第 3 章，3 个）

按「访问身份」分组：这里处理身份，admin.py 处理已登录后的操作。
"""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import get_current_user
from app.core.errors import ApiResponse, ok
from app.core.security import create_session_token
from app.database import get_db
from app.models import User
from app.schemas.auth import CurrentUser, LoginRequest
from app.services import authenticate, to_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[CurrentUser])
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    """登录：校验密码并签发会话 Cookie（ADR-03）

    Cookie 的三个关键属性：
    - httponly=True：JavaScript 读不到，XSS 拿不到会话
    - samesite="lax"：跨站请求不发送 Cookie，防 CSRF
    - secure：由配置决定。生产 HTTPS 必须为 True；
      开发环境是 http，设成 True 浏览器会直接丢弃这个 Cookie，
      表现为「登录成功但立刻又变成未登录」。
    """
    user = authenticate(db, payload.username, payload.password)

    token = create_session_token(user.id)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_expire_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )

    return ok(to_current_user(user), message="登录成功")


@router.post("/logout", response_model=ApiResponse[None])
def logout(response: Response) -> dict:
    """登出：让 Cookie 立即过期

    不需要登录态就能调用 —— 设计上更安全：
    如果要求登录，那么「令牌已过期时点登出」会返回 401，
    用户会卡在「退不出去」的状态。

    这里用 delete_cookie 而非 set_cookie(max_age=0)：
    前者会同时输出正确的 expires 与 max-age，兼容性更好。
    path 必须与设置时一致，否则删不掉 —— 这是很常见的坑。
    """
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return ok(None, message="已退出登录")


@router.get("/me", response_model=ApiResponse[CurrentUser])
def me(user: User = Depends(get_current_user)) -> dict:
    """获取当前登录用户

    前端刷新页面后用它恢复登录态（Pinia 是内存状态，刷新即丢失）。
    文档 06 第 4.2 节的路由守卫第 1 步依赖这个接口。

    未登录时由 get_current_user 抛 401，前端拦截器据此跳转登录页。
    """
    return ok(to_current_user(user))
