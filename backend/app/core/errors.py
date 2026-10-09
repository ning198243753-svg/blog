"""统一响应体与错误码（ADR-09 / 《05-接口设计-v1.0》第 1.2、1.5 节）

响应体固定为 {code, message, data}，code 为 0 表示成功。
业务错误码与 HTTP 状态码是两套东西：HTTP 状态码说「这次请求本身的结果」，
业务错误码说「业务上发生了什么」。
"""

from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None


def ok(data: Any = None, message: str = "ok") -> dict:
    return {"code": 0, "message": message, "data": data}


class ErrorCode:
    """业务错误码表（文档 05 第 1.5 节）

    新增错误码必须先加进这里再使用，避免出现只在某个分支里硬编码的数字。
    """

    SUCCESS = 0

    # 40000 段：请求参数与业务规则
    PARAM_INVALID = 40000
    TITLE_EXISTS = 40001
    SLUG_CONFLICT = 40002
    TAG_EXISTS = 40003
    IMAGE_FORMAT_UNSUPPORTED = 40004
    IMAGE_TOO_LARGE = 40005
    STATUS_NOT_ALLOWED = 40006

    # 40100 段：身份
    UNAUTHORIZED = 40100
    BAD_CREDENTIALS = 40101

    # 40300 段：权限（预留）
    FORBIDDEN = 40300

    # 40400 段：资源
    NOT_FOUND = 40400

    # 42200 段：框架层校验
    VALIDATION_FAILED = 42200

    # 42900 段：限流
    TOO_MANY_REQUESTS = 42900

    # 50000 段：服务端
    INTERNAL_ERROR = 50000


# 业务错误码 → 默认提示语。
# 40101 刻意不区分「用户名不存在」与「密码错误」，
# 否则会变成一个可以枚举用户名的接口。
ERROR_MESSAGES = {
    ErrorCode.PARAM_INVALID: "参数错误",
    ErrorCode.TITLE_EXISTS: "标题已存在",
    ErrorCode.SLUG_CONFLICT: "该链接标识已被占用",
    ErrorCode.TAG_EXISTS: "标签已存在",
    ErrorCode.IMAGE_FORMAT_UNSUPPORTED: "图片格式不支持",
    ErrorCode.IMAGE_TOO_LARGE: "图片体积超出限制",
    ErrorCode.STATUS_NOT_ALLOWED: "当前状态不允许该操作",
    ErrorCode.UNAUTHORIZED: "未登录或登录已过期",
    ErrorCode.BAD_CREDENTIALS: "用户名或密码错误",
    ErrorCode.FORBIDDEN: "没有权限执行该操作",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.VALIDATION_FAILED: "请求参数校验失败",
    ErrorCode.TOO_MANY_REQUESTS: "操作过于频繁，请稍后再试",
    ErrorCode.INTERNAL_ERROR: "服务器内部错误",
}


class BizError(Exception):
    """业务异常

    由路由层抛出，由 main.py 里的异常处理器统一转成 ApiResponse，
    这样路由函数里不需要写 try/except 和手工拼响应体。
    """

    def __init__(self, code: int, message: str | None = None, http_status: int = 200):
        self.code = code
        self.message = message or ERROR_MESSAGES.get(code, "未知错误")
        self.http_status = http_status
        super().__init__(self.message)
