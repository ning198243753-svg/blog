"""公开接口：无需登录（文档 05 第 2 章）

路由层只做三件事：接参数、调服务、返回统一响应体。
禁止在这里写业务逻辑，也禁止直接用 db 做查询——
这是《03-系统架构设计-v1.0》第 2.3 节定下的分层规则。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import ok
from app.database import get_db

router = APIRouter(tags=["public"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """健康检查（文档 05 第 2.8 节）

    不只返回 status=ok，还要真实查一次数据库。
    只返回字面量 ok 的健康检查没有意义——进程活着但数据库挂了，
    它照样返回 ok，部署验证就失去了作用。
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001 - 健康检查要能报告任何数据库异常
        db_status = "error"

    return ok({"status": "ok", "db": db_status})
