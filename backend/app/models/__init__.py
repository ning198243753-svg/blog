"""ORM 模型包

导入所有模型是必要的：Alembic 自动生成迁移时需要它们全部注册到 Base.metadata，
否则新表不会被识别为「新增」。
"""

from app.models.article import Article
from app.models.tag import ArticleTag, Tag
from app.models.user import User
from app.models.site_config import SiteConfig

__all__ = ["Article", "Tag", "ArticleTag", "User", "SiteConfig"]
