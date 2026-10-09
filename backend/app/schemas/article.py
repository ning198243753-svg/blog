"""文章模式（文档 05 第 2 章）

这里有一个刻意的设计：列表项（ArticleListItem）和详情（ArticleDetail）
是两个不同的类，而不是一个类加可选字段。

理由是「列表接口绝不能返回 content_html」：
一页 10 篇、每篇 HTML 20KB，一次响应就是 200KB。
在 3Mbps 带宽下约 5 秒才能传完（NFR-14 的首屏预算是 150KB gzip）。
用两个类而不是一个类加 exclude，是因为「不返回」必须是类型层面的事实——
只要字段存在于响应模型里，某次改动就可能把它带出去。
"""

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.tag import TagOut


class ArticleListItem(BaseModel):
    """列表项：只含摘要级字段

    注意这里**没有** content_html / content_md。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    slug: str
    summary: str | None = None
    status: str
    view_count: int
    published_at: str | None = None
    created_at: str
    updated_at: str
    tags: list[TagOut] = Field(default_factory=list)


class ArticleDetail(ArticleListItem):
    """详情：在列表项基础上增加正文 HTML

    不返回 content_md：那是编辑用的原始文本，
    访客页面用不到，返回它只是白白增加体积。
    后台编辑接口会单独返回 content_md（见 ArticleAdminDetail）。
    """

    content_html: str


class ArticleAdminDetail(ArticleDetail):
    """后台详情：额外返回 Markdown 原文（M3 使用）

    编辑时必须拿到原文，否则无法在编辑器里继续修改。
    """

    content_md: str


class ArticleCreate(BaseModel):
    """新建文章（后台，M3 使用）"""

    title: str = Field(min_length=1, max_length=120)
    slug: str | None = Field(
        default=None,
        max_length=140,
        description="留空则按标题自动生成",
    )
    summary: str | None = Field(default=None, max_length=300, description="留空则自动提取正文前 300 字")
    content_md: str = Field(min_length=1)
    # draft | published
    status: str = Field(default="draft", pattern=r"^(draft|published)$")
    tag_ids: list[int] = Field(default_factory=list, description="标签 id 列表")


class ArticleUpdate(BaseModel):
    """更新文章（后台，M3 使用）

    slug 刻意不在这里：文档 05 规定 PUT 保持原 slug 不变。
    允许改 slug 会让已发布的链接失效，而个人博客通常没有做重定向。
    """

    title: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, max_length=300)
    content_md: str | None = None
    status: str | None = Field(default=None, pattern=r"^(draft|published)$")
    tag_ids: list[int] | None = Field(default=None, description="传了则整体替换标签")


class ArchiveGroup(BaseModel):
    """归档页的一个月分组（文档 05 第 2.6 节）"""

    year: int
    month: int
    count: int
    articles: list[ArticleListItem]


class SiteConfigOut(BaseModel):
    """站点配置输出（文档 05 第 2.7 节）

    用 dict 而不是固定字段：配置项本来就会增加，
    每加一项都要改响应模型的话，这个「可扩展的表」就失去意义了。
    """

    values: dict[str, str]
