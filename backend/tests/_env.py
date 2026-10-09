"""测试环境的数据库隔离

解决的问题（来自一次真实事故）：
测试脚本原本直接对着开发库 backend/data/db/blog.db 跑。
某次运行之后，库里的 26 篇文章和 1 个管理员全部消失，
而所有测试的报错都是「列表为空」「total=0」——
看起来像代码坏了，实际是数据没了。排查花了很久。

根因没有最终定位（强杀 uvicorn 已被实验排除），但暴露的设计缺陷是明确的：
**测试依赖一个手工维护、随时可能被破坏、且不属于测试管辖的共享状态。**

这个模块提供两层保护：

1. 单元测试用内存库（create_test_engine），各自独立、跑完即消失
2. 接口测试用独立的文件库（TEST_DB_PATH），开发库永不被碰

另外提供 assert_not_dev_db()，让任何脚本在误连开发库时直接拒绝运行 ——
「防呆」比「文档里写一句注意事项」可靠得多。
"""

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEV_DB_PATH = (BACKEND_DIR / "data" / "db" / "blog.db").resolve()
TEST_DB_PATH = (BACKEND_DIR / "data" / "db" / "blog_test.db").resolve()


def is_test_mode() -> bool:
    """当前进程是否处于测试模式（由 run_tests.py 注入环境变量）"""
    return os.environ.get("BLOG_TEST_MODE") == "1"


def assert_not_dev_db(script_name: str) -> None:
    """拒绝在「非测试模式」下对开发库执行可能写入的操作

    只在测试模式（BLOG_TEST_MODE=1）或数据库被显式指向测试库时放行。
    这样即使有人后来往测试脚本里加了删除逻辑，也删不到开发数据。
    """
    from app.database import resolve_sqlite_path
    from app.config import settings

    target = resolve_sqlite_path(settings.database_url)

    if target is None:
        return  # 内存库或非 sqlite，不受影响

    if target == TEST_DB_PATH:
        return

    if target == DEV_DB_PATH and not is_test_mode():
        print(
            f"[拒绝执行] {script_name} 正准备写入开发数据库：\n"
            f"  {target}\n"
            "这个保护是为了避免测试数据与开发数据互相覆盖。\n"
            "如需在开发库上造数据，请直接运行 python -m app.seed_data 并加上 --force。",
            file=sys.stderr,
        )
        sys.exit(2)


def create_test_engine():
    """内存库引擎：每个测试文件独立一份，跑完自动消失

    注意不修改全局的 app.database.engine —— 那只会在测试之间
    互相影响，且掩盖「测试到底连了哪个库」这件事。
    """
    from sqlalchemy import create_engine, event
    from sqlalchemy.pool import StaticPool

    # StaticPool + 单连接：内存库的生命周期跟随连接，
    # 用默认连接池会得到「不同连接看到不同内存库」的诡异结果
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine
