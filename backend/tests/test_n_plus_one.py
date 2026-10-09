"""N+1 查询守卫：断言查询次数不随数据量增长

为什么需要这个测试文件：
N+1 的失败方式是「功能完全正常，只是慢」。8 个标签时是 9 次查询，
毫秒级，完全感觉不到；50 个标签时是 51 次。它不会报错、不会崩溃、
不会有任何一个功能测试失败 —— 只能靠数 SQL 语句条数来发现。

所以这里用 SQLAlchemy 的 before_cursor_execute 事件统计查询次数，
造两组不同规模的数据，断言查询次数**相同**。
不依赖绝对条数（那会随实现微调而失效），只依赖「不随规模增长」这个性质。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database import Base  # noqa: E402
from app.models import Article, ArticleTag, Tag, User  # noqa: E402
from app.services import (  # noqa: E402
    list_all_tags,
    list_archive,
    list_articles,
)
from app.utils.time import utc_now  # noqa: E402


class QueryCounter:
    """统计一段代码执行的 SQL 条数"""

    def __init__(self, engine):
        self.engine = engine
        self.count = 0

    def __enter__(self):
        def _before(conn, cursor, statement, parameters, context, executemany):
            self.count += 1

        self._handler = _before
        event.listen(self.engine, "before_cursor_execute", _before)
        return self

    def __exit__(self, *exc):
        event.remove(self.engine, "before_cursor_execute", self._handler)
        return False


def make_session():
    """内存库：每个测试用独立数据库，互不干扰

    这个文件从一开始就用内存库，所以那次「开发库被清空」的事故
    完全没有影响到它 —— 这是「测试自带数据」这个原则的直接收益，
    也是这次把接口测试也改成独立测试库的理由。
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def seed(db, tag_count: int, articles_per_tag: int):
    """造数据：tag_count 个标签，每个标签下 articles_per_tag 篇已发布文章"""
    user = User(username="tester", password_hash="x")
    db.add(user)
    db.flush()

    now = utc_now()
    for t in range(tag_count):
        tag = Tag(name=f"标签{t}", slug=f"tag-{t}")
        db.add(tag)
        db.flush()

        for a in range(articles_per_tag):
            article = Article(
                title=f"文章{t}-{a}",
                slug=f"post-{t}-{a}",
                summary="摘要",
                content_md="# 标题\n正文",
                content_html="<h1>标题</h1><p>正文</p>",
                status="published",
                author_id=user.id,
                published_at=now,
            )
            db.add(article)
            db.flush()
            db.add(ArticleTag(article_id=article.id, tag_id=tag.id))
    db.commit()


def measure(fn, db, engine):
    with QueryCounter(engine) as counter:
        result = fn(db)
    return counter.count, result


def main() -> int:
    failed = []

    def check(name, ok, detail=""):
        print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")
        if not ok:
            failed.append(name)

    print("=" * 62)
    print("N+1 查询守卫")
    print("=" * 62)

    # ---- 小规模：3 个标签 × 2 篇 ----
    engine_s, Session_s = make_session()
    db_s = Session_s()
    seed(db_s, tag_count=3, articles_per_tag=2)
    small_tags, small_tag_data = measure(list_all_tags, db_s, engine_s)
    small_list, _ = measure(lambda d: list_articles(d, page=1, page_size=50), db_s, engine_s)
    small_archive, _ = measure(list_archive, db_s, engine_s)
    db_s.close()
    engine_s.dispose()

    # ---- 大规模：12 个标签 × 2 篇（标签数是 4 倍）----
    engine_l, Session_l = make_session()
    db_l = Session_l()
    seed(db_l, tag_count=12, articles_per_tag=2)
    large_tags, large_tag_data = measure(list_all_tags, db_l, engine_l)
    large_list, _ = measure(lambda d: list_articles(d, page=1, page_size=50), db_l, engine_l)
    large_archive, _ = measure(list_archive, db_l, engine_l)
    db_l.close()
    engine_l.dispose()

    print()
    print(f"{'查询':<22}{'3 个标签':<12}{'12 个标签':<12}结论")
    print("-" * 62)
    print(f"{'标签列表':<20}{small_tags:<12}{large_tags:<12}{'恒定 ✅' if small_tags == large_tags else '随规模增长 ❌'}")
    print(f"{'文章列表':<20}{small_list:<12}{large_list:<12}{'恒定 ✅' if small_list == large_list else '随规模增长 ❌'}")
    print(f"{'归档':<22}{small_archive:<12}{large_archive:<12}{'恒定 ✅' if small_archive == large_archive else '随规模增长 ❌'}")
    print()

    check("标签列表查询数不随标签数增长", small_tags == large_tags, f"{small_tags} → {large_tags}")
    check("文章列表查询数不随文章数增长", small_list == large_list, f"{small_list} → {large_list}")
    check("归档查询数不随文章数增长", small_archive == large_archive, f"{small_archive} → {large_archive}")

    # ---- 数据正确性：count 不能把草稿算进去 ----
    engine_d, Session_d = make_session()
    db_d = Session_d()
    seed(db_d, tag_count=2, articles_per_tag=1)
    # 再给第一个标签加一篇草稿
    user = db_d.query(User).first()
    tag0 = db_d.query(Tag).filter(Tag.slug == "tag-0").first()
    draft = Article(
        title="草稿",
        slug="draft-post",
        summary="x",
        content_md="x",
        content_html="x",
        status="draft",
        author_id=user.id,
    )
    db_d.add(draft)
    db_d.flush()
    db_d.add(ArticleTag(article_id=draft.id, tag_id=tag0.id))
    db_d.commit()

    tag_data = {t["slug"]: t["article_count"] for t in list_all_tags(db_d)}
    check("草稿不计入标签文章数", tag_data["tag-0"] == 1, f"tag-0 = {tag_data['tag-0']}（期望 1）")

    # 真的造一个「没有任何文章」的标签，验证它计数为 0 而不是消失
    empty_tag = Tag(name="空标签", slug="empty-tag")
    db_d.add(empty_tag)
    db_d.commit()
    tag_data = {t["slug"]: t["article_count"] for t in list_all_tags(db_d)}
    check(
        "无文章标签计数为 0 且仍在列表中",
        tag_data.get("empty-tag") == 0,
        f"empty-tag = {tag_data.get('empty-tag')}（期望 0）",
    )
    check("空标签没有被列表漏掉", "empty-tag" in tag_data, f"共 {len(tag_data)} 个标签")

    # ---- 草稿不出现在公开列表 ----
    items = list_articles(db_d, page=1, page_size=50)["items"]
    check("草稿不出现在公开列表", all(i["slug"] != "draft-post" for i in items), f"共 {len(items)} 篇")

    # ---- 详情页对草稿返回 404 ----
    from app.core.errors import BizError
    from app.services import get_article_by_slug

    try:
        get_article_by_slug(db_d, "draft-post", count_view=False)
        check("草稿详情抛 404", False, "没有抛异常")
    except BizError as exc:
        check("草稿详情抛 404", exc.http_status == 404, f"http_status={exc.http_status}")

    db_d.close()
    engine_d.dispose()

    print()
    print("=" * 62)
    print("FAILED:", failed if failed else "none")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
