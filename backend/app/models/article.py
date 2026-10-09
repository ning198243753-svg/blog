"""文章模型（《04-数据库设计-v1.0》第 3.1 节）

字段与类型必须与设计文档逐项一致，不允许「顺手多加点东西」。
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    summary: Mapped[str | None] = mapped_column(String(300))

    # Markdown 原文是唯一事实来源；HTML 是渲染产物，可随时重新生成。
    # 两者都必须保留：只存 HTML 就无法再次编辑，只存 Markdown 则每次阅读都要重新渲染。
    content_md: Mapped[str] = mapped_column(Text, nullable=False)
    content_html: Mapped[str] = mapped_column(Text, nullable=False)

    # draft | published
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")

    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    # 草稿的 published_at 为 NULL —— 用它区分「未发布」比单看 status 更可靠
    published_at: Mapped[datetime | None] = mapped_column(DateTime)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    author = relationship("User", back_populates="articles")
    tags = relationship("Tag", secondary="article_tags", back_populates="articles")

    __table_args__ = (
        # 列表页默认按发布时间倒序 + 只取已发布，这个复合索引直接服务该查询
        Index("idx_articles_status_published", "status", "published_at"),
        Index("idx_articles_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Article id={self.id} slug={self.slug!r} status={self.status}>"
