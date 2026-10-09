"""站点配置模型（《04-数据库设计-v1.0》第 3.5 节）

用 key-value 而不是一行多列，原因：
站点配置项会随需求增加（加一个字段就要改表结构 + 写迁移），
而 key-value 加配置项只是多一行数据。

代价是失去了类型约束——所有值都是字符串，
取值方必须自己做类型转换（articles_per_page 要 int()）。
这个代价在只有十来个配置项时完全可以接受。
"""

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SiteConfig(Base):
    __tablename__ = "site_config"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False, default="")

    def __repr__(self) -> str:
        return f"<SiteConfig {self.key}={self.value!r}>"
