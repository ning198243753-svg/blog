"""Alembic 环境配置

关键点：target_metadata 必须指向 Base.metadata，
并且 app.models 必须被 import —— 否则迁移脚本不会"看见"任何表，
autogenerate 会生成一个空迁移。
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base

# 导入所有模型，让它们注册到 Base.metadata
import app.models  # noqa: F401

config = context.config

# 用运行时配置覆盖 alembic.ini 里的空 URL
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连接数据库"""
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # SQLite 不支持大部分 ALTER，必须开批处理模式
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # 批处理模式：SQLite 改列时采用「建新表→拷数据→换名」，
            # 不开这个选项，任何 ALTER COLUMN 都会失败
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
