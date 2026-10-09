"""通用模式：分页与统一响应体的 Pydantic 定义

这些是所有接口共用的形状，放在 common.py 里，
避免每个业务模块各写一份「看起来差不多」的分页结构。
"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Pagination(BaseModel):
    """分页参数

    上限 50 不是随便定的：SQLite 在单条查询返回大量行时会明显变慢，
    而且 3Mbps 带宽下返回 100 条带 summary 的记录约 60KB，
    首屏还没渲染完用户就开始滚动加载下一批了。
    """

    page: int = Field(default=1, ge=1, description="页码，从 1 开始")
    page_size: int = Field(default=10, ge=1, le=50, description="每页条数，最大 50")


class PageMeta(BaseModel):
    """分页元信息

    为什么同时给 total 和 pages：
    前端页码控件需要 pages 来画按钮，而「共 N 篇」的文案需要 total。
    只给其中一个，前端就得自己算，而算错的代价是页码显示错误。
    """

    total: int = Field(description="符合条件的总条数")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页条数")
    pages: int = Field(description="总页数")


class PaginatedData(BaseModel, Generic[T]):
    """分页数据体（放在 ApiResponse.data 里）"""

    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int
