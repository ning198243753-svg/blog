"""标签与文章-标签关联（《04-数据库设计-v1.0》第 3.2、3.3 节）

这里有一个容易漏的点：
article_tags 用复合主键 (article_id, tag_id)，它天然支持「按文章查标签」，
但**不支持「按标签查文章」**——因为 tag_id 不是索引最左列。
而标签页的核心查询恰好是按标签查文章，所以必须为 tag_id 单独建索引。
这个疏漏在数据量小时不会暴露，等文章多了才表现为标签页变慢。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    # 可选自定义色；为空时前端统一用灰底标签（ADR-08 的克制用色）
    color: Mapped[str | None] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    articles = relationship("Article", secondary="article_tags", back_populates="tags")

    def __repr__(self) -> str:
        return f"<Tag id={self.id} name={self.name!r}>"


class ArticleTag(Base):
    __tablename__ = "article_tags"

    article_id: Mapped[int] = mapped_column(
        ForeignKey("articles.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )

    __table_args__ = (
        # 复合主键无法加速按 tag_id 的查询，必须单独建索引
        Index("idx_article_tags_tag", "tag_id"),
    )
