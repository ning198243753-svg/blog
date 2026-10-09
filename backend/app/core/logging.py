"""日志配置（《03-系统架构设计-v1.0》第 6.2 节）

日志格式固定为：
    时间 | 级别 | 请求方法 | 路径 | 状态码 | 耗时(ms) | 错误信息

为什么要统一格式：出问题时用 grep 就能筛出所有 5xx，
不需要在五花八门的输出里人工辨认。
"""

import logging
import sys
import time

from fastapi import FastAPI, Request

from app.config import settings


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def register_access_log(app: FastAPI) -> None:
    """访问日志中间件

    用中间件而不是在每个路由里打日志：路由层不应该关心日志，
    这是横切关注点。
    """
    logger = logging.getLogger("blog.access")

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        start = time.perf_counter()
        error_message = "-"

        try:
            response = await call_next(request)
        except Exception as exc:  # noqa: BLE001 - 这里就是要兜住所有异常再抛出
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(
                "%s | %s | %s | 500 | %.1f | %s",
                request.method,
                request.url.path,
                500,
                elapsed,
                exc,
            )
            raise

        elapsed = (time.perf_counter() - start) * 1000
        status = response.status_code
        message = (
            f"{request.method} | {request.url.path} | {status} | "
            f"{elapsed:.1f}ms | {error_message}"
        )
        if status >= 500:
            logger.error(message)
        elif status >= 400:
            logger.warning(message)
        else:
            logger.info(message)
        return response
