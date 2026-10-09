"""初始化脚本：python -m app.init_db

做两件事，都必须幂等（重复执行不报错、不产生重复数据）：
1. 写入预置站点配置（已存在的键不覆盖，避免把线上改过的配置重置）
2. 创建管理员账号（已存在则跳过，不重置密码）

**绝不调用 Base.metadata.create_all()**：表结构由 Alembic 迁移负责。
两者混用的后果是：迁移历史与实际表结构脱节，
新环境执行迁移会失败，而老环境又不缺表，问题只在部署时才暴露。
"""

import sys

from sqlalchemy import select

from app.config import settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import SiteConfig, User

# 预置站点配置（《04-数据库设计-v1.0》第 4.2 节）
DEFAULT_SITE_CONFIG: dict[str, str] = {
    "site_title": "moon 的学习笔记",
    "site_subtitle": "记录 · 整理 · 复现",
    "author_name": "moon",
    "author_intro": "正在学习 Vue 3 / FastAPI / SQLite 的开发者。",
    "footer_text": "",
    "icp_number": "",
    "github_url": "https://github.com/ning198243753-svg",
    "articles_per_page": "10",
}


def init_site_config(db) -> int:
    created = 0
    for key, value in DEFAULT_SITE_CONFIG.items():
        exists = db.execute(select(SiteConfig).where(SiteConfig.key == key)).scalar_one_or_none()
        if exists is None:
            db.add(SiteConfig(key=key, value=value))
            created += 1
    return created


def init_admin(db) -> bool:
    username = settings.admin_username
    exists = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if exists is not None:
        return False

    if not settings.admin_password:
        print("[跳过] 未设置 ADMIN_PASSWORD，未创建管理员账号。")
        print("       密码只从 .env 读取，不接受命令行参数——")
        print("       命令行参数会留在 shell 历史和进程列表里。")
        return False

    db.add(User(username=username, password_hash=hash_password(settings.admin_password)))
    return True


def main() -> int:
    print(f"数据库：{settings.database_url}")

    db = SessionLocal()
    try:
        site_count = init_site_config(db)
        admin_created = init_admin(db)
        db.commit()
    except Exception as exc:  # noqa: BLE001 - 初始化脚本要给出可读的失败原因
        db.rollback()
        print(f"[失败] {exc}")
        return 1
    finally:
        db.close()

    print(f"[完成] 新增站点配置 {site_count} 项，管理员账号{'已创建' if admin_created else '已存在或跳过'}。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
