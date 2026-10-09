"""标签模式（文档 05 第 3 章）

字段名与文档 05 逐字对应，不允许「顺手改个更顺口的名字」——
前端会照这份契约写代码，改名字等于偷偷改接口。
"""

from pydantic import BaseModel, ConfigDict, Field


class TagOut(BaseModel):
    """标签输出"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    color: str | None = None


class TagWithCount(TagOut):
    """带文章数的标签（标签页列表用）

    article_count 需要 LEFT JOIN 聚合，属于「视图层计算」而不是表字段。
    放在这里而不是 TagOut 里：文章详情返回标签时不需要这个数字，
    为它多做一次聚合查询是浪费。
    """

    article_count: int = 0


class TagCreate(BaseModel):
    """新建标签（后台，M3 使用）"""

    name: str = Field(min_length=1, max_length=32, description="标签名")
    color: str | None = Field(
        default=None,
        max_length=16,
        pattern=r"^#[0-9a-fA-F]{3,8}$",
        description="可选自定义色，形如 #1e5cb8",
    )


class TagUpdate(BaseModel):
    """更新标签（后台，M3 使用）

    所有字段可选：只传要改的字段，未传的保持原值。
    这与 PUT 的语义（整体替换）有出入，但标签只有两个字段，
    整体替换会让前端必须每次回传完整对象，反而更容易出错。
    """

    name: str | None = Field(default=None, min_length=1, max_length=32)
    color: str | None = Field(default=None, max_length=16, pattern=r"^#[0-9a-fA-F]{3,8}$")


class TagUsage(BaseModel):
    """标签的使用情况（删除前的影响预览）

    article_count 包含草稿，published_count 只含已发布。
    两者给出，是因为后台看到的是全部文章，而访客只看到已发布的 ——
    只报一个数字会让作者低估删除的影响范围。
    """

    id: int
    name: str
    slug: str
    article_count: int
    published_count: int


class TagDeleteResult(BaseModel):
    """删除标签的结果"""

    deleted_id: int
    affected_articles: int
