"""M0 验收（最关键的一项）：验证外键约束**真实生效**

为什么不能只检查代码里写了 `PRAGMA foreign_keys=ON`：
那条语句完全可以被写进代码却因为执行时机不对而不起作用
（比如只在启动时对一条连接执行，而不是每条新连接）。
唯一可靠的验证方式是**真的插一条脏数据，看它报不报错**。

同时也验证反向情况：删掉一篇文章，关联的 article_tags 行应被级联删除。
"""

import sys

from sqlalchemy import text

from app.database import SessionLocal, engine


def main() -> int:
    results = []

    def check(name, condition, detail=""):
        results.append((name, condition))
        print(f"[{'PASS' if condition else 'FAIL'}] {name}  {detail}")

    # ---- 1. 连接级 PRAGMA：确认 SQLAlchemy 连接上外键是开的 ----
    with engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        jm = conn.execute(text("PRAGMA journal_mode")).scalar()
        bt = conn.execute(text("PRAGMA busy_timeout")).scalar()
    check("PRAGMA foreign_keys 已开启", fk == 1, f"= {fk}")
    check("PRAGMA journal_mode = WAL", str(jm).lower() == "wal", f"= {jm}")
    check("PRAGMA busy_timeout 已设置", bt == 5000, f"= {bt}")

    # ---- 2. 池中第二条连接也必须是开的 ----
    # 这是最容易失败的一项：如果 PRAGMA 只在启动时执行一次，
    # 第一条连接是开的，第二条就退回默认值了。
    conn_a = engine.raw_connection()
    conn_b = engine.raw_connection()
    try:
        fk_a = conn_a.cursor().execute("PRAGMA foreign_keys").fetchone()[0]
        fk_b = conn_b.cursor().execute("PRAGMA foreign_keys").fetchone()[0]
    finally:
        conn_a.close()
        conn_b.close()
    check("连接池中每条连接都开启外键", fk_a == 1 and fk_b == 1, f"conn1={fk_a} conn2={fk_b}")

    # ---- 3. 脏数据测试：插入指向不存在文章的关联行 ----
    db = SessionLocal()
    try:
        raised = False
        detail = ""
        try:
            db.execute(
                text(
                    "INSERT INTO article_tags (article_id, tag_id) "
                    "VALUES (999999, 999999)"
                )
            )
            db.commit()
        except Exception as exc:  # noqa: BLE001 - 这里就是要捕获数据库异常
            raised = True
            detail = type(exc).__name__ + ": " + str(exc).split("\n")[0][:90]
            db.rollback()
        check("插入不存在的关联被拒绝", raised, detail)

        # ---- 4. 级联删除测试 ----
        db.execute(text("DELETE FROM article_tags"))
        db.execute(text("DELETE FROM articles"))
        db.execute(text("DELETE FROM tags"))
        db.execute(text("DELETE FROM users"))
        db.commit()

        db.execute(
            text(
                "INSERT INTO users (id, username, password_hash) "
                "VALUES (1, 'tmp_user', 'x')"
            )
        )
        db.execute(
            text(
                "INSERT INTO articles (id, title, slug, content_md, content_html, status, author_id) "
                "VALUES (1, 'tmp', 'tmp', 'md', 'html', 'draft', 1)"
            )
        )
        db.execute(text("INSERT INTO tags (id, name, slug) VALUES (1, 'tmp_tag', 'tmp-tag')"))
        db.execute(text("INSERT INTO article_tags (article_id, tag_id) VALUES (1, 1)"))
        db.commit()

        before = db.execute(text("SELECT COUNT(*) FROM article_tags")).scalar()
        db.execute(text("DELETE FROM articles WHERE id = 1"))
        db.commit()
        after = db.execute(text("SELECT COUNT(*) FROM article_tags")).scalar()
        check("删除文章级联清理关联表", before == 1 and after == 0, f"before={before} after={after}")

        # 清理测试数据
        db.execute(text("DELETE FROM tags"))
        db.execute(text("DELETE FROM users"))
        db.commit()
    finally:
        db.close()

    failed = [n for n, ok in results if not ok]
    print()
    print("FAILED:", failed if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
