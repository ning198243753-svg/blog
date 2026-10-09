"""FastAPI 应用入口

职责只有三件：创建应用、注册中间件、注册路由。
任何业务逻辑都不应该出现在这里。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.errors import BizError, ErrorCode, ERROR_MESSAGES
from app.core.handlers import register_error_handlers
from app.core.logging import register_access_log, setup_logging
from app.routers import public

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时做的事：目前只有确保上传目录存在。
    # 建表不在这里做 —— 必须由 Alembic 迁移完成（文档 04 第 5 章），
    # 用 Base.metadata.create_all() 会让迁移历史与实际表结构脱节。
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="个人博客 API",
    version="0.1.0",
    description="Vue 3 + FastAPI + SQLite 个人博客项目（阶段三 M0 骨架）",
    # 生产环境（settings.debug=False）关闭交互式文档，
    # 避免把全部接口结构暴露给外部
    docs_url="/docs" if settings.debug else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings.debug else None,
    lifespan=lifespan,
)

register_access_log(app)
register_error_handlers(app)


@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError) -> JSONResponse:
    """业务异常统一转成响应体，路由里因此不需要写 try/except"""
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic 参数校验失败 → 业务错误码 42200

    不直接透出 Pydantic 的原始错误结构：那是框架细节，
    前端不应该被迫理解它的形状。
    """
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:]) or "参数"
    detail = first.get("msg", "")
    return JSONResponse(
        status_code=422,
        content={
            "code": ErrorCode.VALIDATION_FAILED,
            "message": ERROR_MESSAGES[ErrorCode.VALIDATION_FAILED] + f"：{field} {detail}",
            "data": None,
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """兜底：绝不让原始堆栈直接返回给客户端

    堆栈可能包含文件路径、SQL 语句等内部信息。
    """
    return JSONResponse(
        status_code=500,
        content={
            "code": ErrorCode.INTERNAL_ERROR,
            "message": ERROR_MESSAGES[ErrorCode.INTERNAL_ERROR],
            "data": None,
        },
    )


# 所有接口统一挂在 /api 前缀下（ADR-04 同源，无 CORS）
app.include_router(public.router, prefix="/api")
