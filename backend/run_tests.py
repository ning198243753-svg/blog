"""一键跑完全部测试

用法：
    python run_tests.py                      # 只跑不依赖 HTTP 服务的测试
    python run_tests.py --with-api           # 额外启动后端并跑接口端到端测试
    python run_tests.py --with-api --keep-db # 保留测试库，便于事后排查

数据库隔离（重要）：
接口测试需要一个真实的 HTTP 服务，因此需要一个真实的文件数据库。
但它**绝不能是开发库** —— 曾经发生过一次真实事故：跑完一轮测试后，
开发库里的 26 篇文章和 1 个管理员全部消失，而测试报的是
「列表为空 / total=0」，看起来像代码坏了。

所以这里做了三件事：
1. 接口测试在独立的 blog_test.db 上跑，通过环境变量覆盖 DATABASE_URL
2. 启动前断言目标库不是开发库，是则直接拒绝运行
3. 每次跑完删除测试库，保证下次是从干净状态开始

另外：测试列表里刻意不含任何 `_` 开头的辅助脚本 ——
那些是「检查/排查」用的，不属于测试套件，混在一起会让
「跑测试」这件事变得既会读也会写，边界不清。
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PY = ROOT / ".venv" / "Scripts" / "python.exe"
PYTHON = str(VENV_PY) if VENV_PY.exists() else sys.executable

DEV_DB = (ROOT / "data" / "db" / "blog.db").resolve()
TEST_DB = (ROOT / "data" / "db" / "blog_test.db").resolve()
TEST_DB_WAL = Path(str(TEST_DB) + "-wal")
TEST_DB_SHM = Path(str(TEST_DB) + "-shm")

# 不依赖 HTTP 服务的测试
OFFLINE_TESTS = [
    ("Markdown 渲染与 XSS 防护", "tests/test_markdown.py"),
    ("数据库 PRAGMA 与外键约束", "tests/test_foreign_keys.py"),
    ("N+1 查询守卫", "tests/test_n_plus_one.py"),
    ("种子数据确定性", "tests/test_seed_determinism.py"),
    ("密码哈希与边界情况", "tests/test_password.py"),
    ("登录流程与会话令牌", "tests/test_login_flow.py"),
]

ONLINE_TESTS = [
    ("鉴权接口（登录/登出/当前用户）", "tests/test_auth_e2e.py"),
    ("文章 CRUD 与权限边界", "tests/test_article_crud.py"),
    ("标签与站点配置", "tests/test_tag_site_crud.py"),
    ("图片上传与压缩", "tests/test_upload.py"),
    ("公开接口端到端验证", "tests/test_api_e2e.py"),
]


def base_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    if extra:
        env.update(extra)
    return env


def run_one(label: str, script: str, env: dict[str, str]) -> bool:
    print()
    print("=" * 66)
    print(f">> {label}   ({script})")
    print("=" * 66)

    proc = subprocess.run(
        [PYTHON, str(ROOT / script)],
        cwd=str(ROOT),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    # 通过时只打印末尾几行（中间细节是噪音），失败时打印全部输出便于定位
    ok = proc.returncode == 0
    lines = (proc.stdout or "").rstrip().splitlines()
    if ok:
        for line in lines[-6:]:
            print(line)
    else:
        print(proc.stdout)
        if proc.stderr:
            print("--- stderr ---")
            print(proc.stderr)
        if proc.returncode == 2:
            print("(退出码 2 表示被「拒绝操作开发库」的保护拦下)")

    print(f"\n{'[OK] 通过' if ok else '[FAIL] 失败'}：{label}")
    return ok


def clean_test_db() -> None:
    for path in (TEST_DB, TEST_DB_WAL, TEST_DB_SHM):
        if path.exists():
            path.unlink()


def wait_for_server(url: str, timeout: float = 30.0) -> bool:
    """轮询等服务就绪

    不用固定 sleep：机器快就白等，机器慢又等不够，
    而「等不够」的表现是接口测试集体失败，看起来像代码坏了。
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2):
                return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="一键跑测试")
    parser.add_argument("--with-api", action="store_true", help="启动后端并跑接口端到端测试")
    parser.add_argument("--keep-db", action="store_true", help="跑完后保留测试库")
    args = parser.parse_args()

    # ---- 安全断言：测试库绝不能是开发库 ----
    if TEST_DB == DEV_DB:
        print("[拒绝运行] 测试库路径与开发库相同，这会导致测试破坏开发数据。")
        return 2

    print("后端测试套件")
    print(f"Python  : {PYTHON}")
    print(f"开发库  : {DEV_DB}   <- 测试绝不读写这个文件")
    if args.with_api:
        print(f"测试库  : {TEST_DB}")

    results: list[tuple[str, bool]] = []
    env = base_env()

    for label, script in OFFLINE_TESTS:
        results.append((label, run_one(label, script, env)))

    server = None
    if args.with_api:
        print()
        print("=" * 66)
        print(">> 准备独立的测试数据库")
        print("=" * 66)

        clean_test_db()
        # 测试库的管理员密码。接口测试要用它登录（test_auth_e2e.py、
        # test_article_crud.py 都会真的走登录流程），所以这个值必须与
        # 建库时用的一致 —— 两处写死不同值会导致「测试全部 401」，
        # 而报错看起来像鉴权代码坏了。这里只定义一次，两处共用。
        test_admin_password = os.environ.get("ADMIN_PASSWORD", "TestPassw0rd!2026")
        test_env = base_env({
            "DATABASE_URL": f"sqlite:///{TEST_DB.as_posix()}",
            "BLOG_TEST_MODE": "1",
            "ADMIN_PASSWORD": test_admin_password,
            "DEBUG": "false",
            # 测试库走 http，Cookie 的 secure 必须为 false，
            # 否则浏览器/客户端会直接丢弃这个 Cookie，
            # 表现为「登录成功但下一次请求仍是未登录」。
            "COOKIE_SECURE": "false",
        })

        # 建表 + 造数据，全部作用在测试库上
        for step, cmd in (
            ("初始化数据库结构", [PYTHON, "-m", "alembic", "upgrade", "head"]),
            ("创建管理员", [PYTHON, "-m", "app.init_db"]),
            ("生成种子数据", [PYTHON, "-m", "app.seed_data", "--reset", "--force"]),
        ):
            proc = subprocess.run(
                cmd, cwd=str(ROOT), env=test_env,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            status = "[OK]" if proc.returncode == 0 else "[FAIL]"
            print(f"  {status} {step}")
            if proc.returncode != 0:
                print(proc.stdout)
                print(proc.stderr)
                return 1

        print()
        print("=" * 66)
        print(">> 启动后端服务（127.0.0.1:8000，指向测试库）")
        print("=" * 66)

        server = subprocess.Popen(
            [PYTHON, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=str(ROOT), env=test_env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

        if wait_for_server("http://127.0.0.1:8000/api/health"):
            print("服务已就绪")
            for label, script in ONLINE_TESTS:
                results.append((label, run_one(label, script, test_env)))
        else:
            print("[FAIL] 服务在 30 秒内没有就绪，跳过接口测试")
            results.append(("接口端到端验证", False))

    if server is not None:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        time.sleep(0.5)

    if args.with_api:
        if args.keep_db:
            print(f"\n测试库已保留：{TEST_DB}")
        else:
            clean_test_db()
            print("\n测试库已清理")

    print()
    print("=" * 66)
    print("汇总")
    print("=" * 66)
    for label, ok in results:
        print(f"  {'[OK]  ' if ok else '[FAIL]'}  {label}")

    failed = [label for label, ok in results if not ok]
    print()
    if failed:
        print(f"失败 {len(failed)} 项：")
        for label in failed:
            print(f"  - {label}")
    else:
        print(f"全部通过（{len(results)} 项）")

    if not args.with_api:
        print()
        print("提示：加 --with-api 可同时跑接口端到端测试（使用独立测试库）")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
