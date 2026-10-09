"""复现实验：强杀 uvicorn 之后数据库还剩什么

【这是排查工具，不是测试。文件名以 _ 开头，不会进 run_tests.py 的测试列表。】

为什么留着它：
数据消失事故排查期间，第一个被怀疑的原因是「强杀进程导致 WAL 未合并」。
本脚本用可观察、分步的方式否证了这个假设 ——
强杀、WAL 恢复、重新打开之后，26 篇文章和 1 个用户始终都在，
数据一次都没丢过。

真正的凶手是 tests/test_foreign_keys.py 里那句 DELETE FROM articles
（它直接连开发库，且不恢复数据），已在那个文件里修复并注明。

保留这个脚本的价值：
M5 部署阶段会涉及「容器重启 / 进程被 kill 时 SQLite 数据是否安全」，
这个脚本提供了一个现成的验证手段，不用重写。

用法：
    python tests/_reproduce_kill.py
"""

import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "db" / "blog.db"
PY = str(ROOT / ".venv" / "Scripts" / "python.exe")


def file_state(label: str) -> None:
    print(f"\n--- {label} ---")
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(DB) + suffix)
        size = path.stat().st_size if path.exists() else None
        print(f"  {path.name:<16} {'不存在' if size is None else f'{size} 字节'}")
    try:
        conn = sqlite3.connect(str(DB))
        articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        print(f"  文章数 {articles}，用户数 {users}")
    except Exception as exc:  # noqa: BLE001
        print(f"  读取失败：{exc}")


def run_seed() -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        [PY, "-m", "app.seed_data", "--reset"],
        cwd=str(ROOT), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    last = (proc.stdout or "").strip().splitlines()[-1] if proc.stdout else "(无输出)"
    print(f"  seed: {last}")


def main() -> int:
    print("=" * 62)
    print("复现实验：强杀 uvicorn 后的数据状态")
    print("=" * 62)

    file_state("0. 实验开始前")

    print("\n[1] 重建数据")
    run_seed()
    file_state("1. seed 之后（未启动服务）")

    print("\n[2] 启动 uvicorn")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    server = subprocess.Popen(
        [PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=str(ROOT), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    ready = False
    for _ in range(40):
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/api/health", timeout=2):
                ready = True
                break
        except (urllib.error.URLError, OSError):
            time.sleep(0.4)

    if not ready:
        print("  服务未就绪，实验中止")
        server.kill()
        return 1
    print("  服务已就绪")
    file_state("2. 服务已启动（尚无写入）")

    print("\n[3] 制造写入：连续读同一篇文章 5 次（每次都会 view_count + 1）")
    conn = sqlite3.connect(str(DB))
    slug = conn.execute(
        "SELECT slug FROM articles WHERE status='published' ORDER BY id LIMIT 1"
    ).fetchone()[0]
    conn.close()
    print(f"  目标文章：{slug}")

    for i in range(1, 6):
        url = "http://127.0.0.1:8000/api/articles/" + urllib.request.quote(slug)
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                body = resp.read().decode("utf-8")
            import json

            count = json.loads(body)["data"]["view_count"]
            print(f"  第 {i} 次：view_count = {count}")
        except Exception as exc:  # noqa: BLE001
            print(f"  第 {i} 次失败：{exc}")
    file_state("3. 写入之后（WAL 应当变大）")

    print("\n[4] 强杀进程（Stop-Process -Force，等价于 job_kill）")
    server.kill()
    server.wait(timeout=10)
    time.sleep(2)
    print("  已强杀")
    file_state("4. 强杀之后")

    print("\n[5] 新建连接再读一次（这会触发 WAL 恢复）")
    file_state("5. 重新读取之后")

    print()
    print("=" * 62)
    print("结论")
    print("=" * 62)
    print("对比「3. 写入之后」与「5. 重新读取之后」的文章数即可判断数据是否丢失。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
