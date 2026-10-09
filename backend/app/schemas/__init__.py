"""模式层（Pydantic）

约定：
- 所有 *Out 类用 from_attributes=True，可以直接由 ORM 对象构造
- 时间字段一律用 str（ISO 8601 带 Z），在服务层用 to_iso_z 转换
  这么做而不是用 datetime：Pydantic 序列化 datetime 会输出
  "2026-10-09T12:00:00"（没有 Z），前端 new Date() 会按**本地时区**解析，
  于是同一篇文章在不同时区显示的时间不同，而且不会报任何错误。
"""

from app.schemas.article import (
    ArchiveGroup,
    ArticleAdminDetail,
    ArticleCreate,
    ArticleDetail,
    ArticleListItem,
    ArticleNeighbor,
    ArticleUpdate,
    SiteConfigOut,
)
from app.schemas.auth import CurrentUser, LoginRequest
from app.schemas.common import PaginatedData, PageMeta, Pagination
from app.schemas.site import SiteConfigUpdate
from app.schemas.tag import (
    TagCreate,
    TagDeleteResult,
    TagOut,
    TagUpdate,
    TagUsage,
    TagWithCount,
)
from app.schemas.upload import UploadResult

__all__ = [
    "ArchiveGroup",
    "ArticleAdminDetail",
    "ArticleCreate",
    "ArticleDetail",
    "ArticleListItem",
    "ArticleNeighbor",
    "ArticleUpdate",
    "CurrentUser",
    "LoginRequest",
    "SiteConfigOut",
    "SiteConfigUpdate",
    "PageMeta",
    "PaginatedData",
    "Pagination",
    "TagCreate",
    "TagDeleteResult",
    "TagOut",
    "TagUpdate",
    "TagUsage",
    "TagWithCount",
    "UploadResult",
]
