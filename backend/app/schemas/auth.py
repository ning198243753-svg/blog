"""鉴权模式（文档 05 第 3 章）"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """登录请求

    这里刻意**不**对 username/password 加 min_length 之类的校验：
    加了之后，「用户名太短」会返回 422 参数校验失败，
    而「用户名不存在」返回 401 —— 两者不同的响应
    会让攻击者能区分「格式不对」和「账号不存在」。

    统一在服务层用同一个错误码拒绝即可。
    """

    username: str = Field(max_length=64)
    password: str = Field(max_length=128)


class CurrentUser(BaseModel):
    """当前登录用户（GET /api/auth/me）

    只返回 id、username、created_at。
    **绝不返回 password_hash** —— 哪怕前端不显示，
    响应体也会出现在浏览器网络面板和任何中间层日志里。
    """

    id: int
    username: str
    created_at: str
