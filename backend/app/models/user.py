"""用户模型（《04-数据库设计-v1.0》第 3.4 节）

v1 只有一个管理员账号，没有注册功能（NG-1）。
但用户表不能省：它是 author_id 外键的落点，
将来若真要加作者，数据不需要迁移。
"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    # bcrypt 哈希固定 60 字符，留 128 是给将来换算法（如 argon2）留余量
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    articles = relationship("Article", back_populates="author")

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
