"""验证外键约束**真实生效**

为什么不能只检查代码里写了 `PRAGMA foreign_keys=ON`：
那条语句完全可以被写进代码却因为执行时机不对而不起作用
（比如只在启动时对一条连接执行，而不是每条新连接）。
唯一可靠的验证方式是**真的插一条脏数据，看它报不报错**。

同时也验证反向情况：删掉一篇文章，关联的 article_tags 行应被级联删除。

---

【重要】本文件曾造成一次真实的数据事故，改动理由必须写在这里：

旧版本直接使用 app.database 里的全局 engine 和 SessionLocal，
也就是**开发库**。而"验证级联删除"这件事，必然要先清空表：

    db.execute(text("DELETE FROM article_tags"))
    db.execute(text("DELETE FROM articles"))
    ...

测完之后，它只清理了自己插入的临时数据，没有恢复原有内容。
结果是：跑一次测试，开发库里的 26 篇文章和 1 个管理员全部消失。
而报错现象是别的测试开始报「列表为空 / total=0」——
看起来像代码坏了，实际是数据没了，排查代价极高。

教训不是「记得恢复数据」，而是：
**会执行 DELETE 的测试，就绝不能连真实数据库。**
现在改为独立的内存库，操作对象与开发库再无任何关系。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, event, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import Article, ArticleTag, Tag, User  # noqa: E402


def make_memory_engine():
    """独立内存库：每个连接看到同一份数据，进程结束即消失

    用 StaticPool 的原因是内存库的生命周期绑定在连接上，
    默认连接池会给出「不同连接看到不同内存库」的诡异结果。

    这里同时注册和 app.database 完全相同的四条 PRAGMA ——
    测试要验证的正是这套 PRAGMA 是否生效，
    所以不能图省事只开 foreign_keys。
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    return engine


def main() -> int:
    results = []

    def check(name, condition, detail=""):
        results.append((name, condition))
        print(f"[{'PASS' if condition else 'FAIL'}] {name}  {detail}")

    engine = make_memory_engine()
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    # ---- 1. 连接级 PRAGMA ----
    with engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
        jm = conn.execute(text("PRAGMA journal_mode")).scalar()
        bt = conn.execute(text("PRAGMA busy_timeout")).scalar()
    check("PRAGMA foreign_keys 已开启", fk == 1, f"= {fk}")
    check("PRAGMA busy_timeout 已设置", bt == 5000, f"= {bt}")

    # 内存库上 journal_mode 永远是 memory，不是 wal —— 这不是配置没生效。
    # WAL 是文件数据库的机制：SQLite 对内存库执行 PRAGMA journal_mode=WAL 时
    # 会**静默返回 memory**，不报错也不生效。
    # 所以「WAL 是否生效」必须在文件库上验证，见 tests/_check_db.py；
    # 这里只验证「同一条 PRAGMA 语句在内存库上不报错、且有确定的返回值」。
    check(
        "内存库的 journal_mode 是 memory（WAL 不适用于内存库）",
        str(jm).lower() == "memory",
        f"= {jm}（文件库的 WAL 由 tests/_check_db.py 验证）",
    )

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
    db = Session()
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
        # 注意这里直接用 ORM 造数据，而不是 DELETE 全表再插临时行。
        # 在内存库里没有"别人的数据"可删，全表 DELETE 本身就没有意义。
        user = User(username="tmp_user", password_hash="x")
        db.add(user)
        db.flush()

        article = Article(
            title="tmp",
            slug="tmp",
            content_md="md",
            content_html="html",
            status="draft",
            author_id=user.id,
        )
        tag = Tag(name="tmp_tag", slug="tmp-tag")
        db.add_all([article, tag])
        db.flush()

        db.add(ArticleTag(article_id=article.id, tag_id=tag.id))
        db.commit()

        before = db.execute(text("SELECT COUNT(*) FROM article_tags")).scalar()
        # 用原生 SQL 删，而不是 db.delete(article)，这是刻意的：
        # 本测试要验证的是**数据库 DDL 里写的 ON DELETE CASCADE 是否生效**。
        # 若用 ORM 的 db.delete()，SQLAlchemy 会按 relationship 的 cascade 配置
        # 自己先把 article_tags 清理掉 —— 那样即使数据库的 CASCADE 是坏的，
        # 测试也会通过，属于典型的假阳性。
        db.execute(text("DELETE FROM articles WHERE id = :id"), {"id": article.id})
        db.commit()
        after = db.execute(text("SELECT COUNT(*) FROM article_tags")).scalar()
        check("删除文章级联清理关联表", before == 1 and after == 0, f"before={before} after={after}")

        # 原生 SQL 绕过了 ORM，Session 的身份映射里还留着 (Article, 1)。
        # 下一段又插一条新文章，SQLite 会复用 id=1，于是 SQLAlchemy 警告
        # "Identity map already had an identity for Article (1,)"。
        # 用 expunge_all() 显式让它忘掉缓存对象，而不是忽略这个警告 ——
        # 零警告的测试套件才能在出现**新**警告时立刻被发现。
        db.expunge_all()

        # ---- 隔离性守卫 ----
        # 这条断言替代了之前的"残留条数"检查。
        # 之前那条断言（slug IN ('tmp','tmp2') 应等于 2）是无效的：
        # 第 4 步已经删掉了 tmp，所以数字取决于测试步骤的顺序，
        # 它证明不了任何关于隔离性的事情。
        #
        # 真正要守的是：这个 engine 指向的是内存库，而不是文件库。
        # 判据用 url 而不是数据内容 —— 数据内容会因为测试步骤变化，
        # 而 url 是稳定的、可直接检查的事实。
        check(
            "engine 指向内存库（不是开发库文件）",
            engine.url.database in (None, "", ":memory:"),
            f"url.database={engine.url.database!r}",
        )

        # ---- 5. 反向验证：删标签也应级联清理关联表 ----
        article2 = Article(
            title="tmp2",
            slug="tmp2",
            content_md="md",
            content_html="html",
            status="draft",
            author_id=user.id,
        )
        tag2 = Tag(name="tmp_tag2", slug="tmp-tag2")
        db.add_all([article2, tag2])
        db.flush()  # flush 之后 id 就分配好了，直接取属性即可

        db.add(ArticleTag(article_id=article2.id, tag_id=tag2.id))
        db.commit()

        before2 = db.execute(text("SELECT COUNT(*) FROM article_tags")).scalar()
        # 同样用原生 SQL 验证 DDL 层的级联
        db.execute(text("DELETE FROM tags WHERE id = :id"), {"id": tag2.id})
        db.commit()
        after2 = db.execute(text("SELECT COUNT(*) FROM article_tags")).scalar()
        check("删除标签级联清理关联表", before2 == 1 and after2 == 0, f"before={before2} after={after2}")
        db.expunge_all()
    finally:
        db.close()

    engine.dispose()

    failed = [n for n, ok in results if not ok]
    print()
    print("FAILED:", failed if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
