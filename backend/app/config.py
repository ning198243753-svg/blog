"""配置（ADR-10：.env + pydantic-settings）

.env 不进仓库，.env.example 进仓库。所有配置项都必须有默认值或在此声明，
不允许在代码里散落 os.getenv —— 那样无法一眼看清项目依赖哪些配置。
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录（本文件位于 backend/app/config.py）
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 应用 ----
    app_name: str = "blog"
    debug: bool = False
    log_level: str = "INFO"
    # 站点对外地址，用于拼接绝对链接（RSS 等）
    site_url: str = "http://localhost:5173"

    # ---- 数据库 ----
    # 开发环境用相对路径；生产环境在 .env 里覆盖为 sqlite:////data/db/blog.db
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'db' / 'blog.db').as_posix()}"

    # ---- 会话（ADR-03：HttpOnly Cookie + 签名 Cookie）----
    # 生产环境必须用 python -c "import secrets; print(secrets.token_urlsafe(48))" 生成
    secret_key: str = "dev-only-insecure-key-change-me"
    session_cookie_name: str = "blog_session"
    session_expire_days: int = 7
    # 生产环境（HTTPS）必须为 True，否则 Cookie 会在明文连接中传输
    cookie_secure: bool = False

    # ---- 管理员账号（初始化脚本使用）----
    admin_username: str = "admin"
    admin_password: str = ""

    # ---- 上传（文档 05 第 4.7 节）----
    upload_dir: Path = BASE_DIR / "data" / "uploads"
    upload_max_size_mb: int = 2
    # 图片宽度超过该值则等比缩小，避免手机原图直接入库
    upload_max_width: int = 1600


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
