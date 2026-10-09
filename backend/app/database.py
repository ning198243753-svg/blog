"""数据库连接与会话（SQLAlchemy 2.x）

本文档最关键的部分是 _set_sqlite_pragma：
SQLite 默认**不强制外键约束**，即使建表时写了 FOREIGN KEY。
不开启的话，删掉一篇文章后 article_tags 会留下指向不存在文章的垃圾行，
而且不会报任何错误。

详见《04-数据库设计-v1.0》第 1.4 节。
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# SQLite 需要关闭同线程检查，FastAPI 的依赖注入会在不同线程中复用连接
connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    # 打印 SQL 便于学习期观察 ORM 生成了什么语句（DEBUG 时开启）
    echo=settings.debug,
)


@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """每条新连接都要执行，不是启动时执行一次。

    连接池会新建连接，如果只在启动时设置，新连接会退回 SQLite 的默认行为。
    """
    if not settings.database_url.startswith("sqlite"):
        return

    cursor = dbapi_connection.cursor()
    # WAL：读写可以并发，避免读操作阻塞写操作
    cursor.execute("PRAGMA journal_mode=WAL")
    # NORMAL：WAL 模式下的推荐值，兼顾安全与性能
    cursor.execute("PRAGMA synchronous=NORMAL")
    # 关键项：SQLite 默认不强制外键，必须每条连接显式开启
    cursor.execute("PRAGMA foreign_keys=ON")
    # 写锁等待 5 秒再报 database is locked，而不是立刻失败
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类（SQLAlchemy 2.x 风格）"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖注入用的会话工厂。

    用 yield 而不是 return：请求结束后一定要关闭会话，
    否则连接会一直占着，最终出现 database is locked。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
