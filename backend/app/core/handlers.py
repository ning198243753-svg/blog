"""统一 404 处理

不写这段的话，访问一个不存在的接口会返回 FastAPI 默认的
{"detail": "Not Found"} —— 形状与全站统一响应体不一致，
前端的拦截器拆包逻辑会在这个分支上失效。

所以「不存在」也必须是 {code, message, data} 的形状。
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors import ERROR_MESSAGES, ErrorCode


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        # 404 用统一的 40400；其它（如 405）暂时沿用 HTTP 状态码 ×100，
        # 它们在本项目里不是正常业务路径，不会进入前端的错误分支
        code = ErrorCode.NOT_FOUND if exc.status_code == 404 else exc.status_code * 100
        message = ERROR_MESSAGES.get(code, str(exc.detail))
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": code, "message": message, "data": None},
        )
