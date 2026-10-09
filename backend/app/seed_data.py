"""种子数据：造一批可用于开发和演示的文章

用法：
    python -m app.seed_data                     # 追加（已存在则跳过同 slug）
    python -m app.seed_data --reset --force     # 清空文章/标签后重建
    python -m app.seed_data --reset             # 被拒绝（见下方说明）

为什么 --reset 需要 --force：
--reset 会 DELETE 掉 articles / article_tags / tags 三张表的内容，
它曾经是「数据莫名其妙消失」的重点怀疑对象之一。
现在加了一道显式确认，手滑跑不出破坏。
（测试模式下由 run_tests.py 注入 BLOG_TEST_MODE=1，目标本来就是测试库，
不会拦截。）

为什么需要种子数据：
手点后台发 20 篇文章要半小时，而这半小时里你验证不了任何东西——
分页、标签计数、归档分组、搜索，全都需要足够的数据量才看得出问题。
8 篇以下的数据，「分页」这个功能等于没测。
"""

import argparse
import sys

from datetime import timedelta

from sqlalchemy import delete, select

from app.config import settings
from app.database import SessionLocal
from app.models import Article, ArticleTag, Tag, User
from app.utils.markdown import render_markdown, strip_markdown
from app.utils.slug import make_slug_from_title
from app.utils.time import utc_now


def fake_view_count(index: int) -> int:
    """确定性的阅读数

    为什么不用 random.seed() + randint()：
    固定种子看起来确定，实际依赖 CPython 的随机数实现细节。
    「种子 20261009 的第 3 个数是 355」不是语言规范保证的，
    而是当前实现的行为 —— 一旦版本升级或前面多加一次随机调用，
    后续所有数字全部错位，而失败现象是「某个断言莫名其妙红了」。

    这个公式只依赖 index，任何 Python 版本、任何机器结果都一样，
    并且可以手算验证：
        index=0  → (0   + 13) % 397 + 3 =  13 + 3 = 16
        index=1  → (37  + 13) % 397 + 3 =  50 + 3 = 53
        index=10 → (370 + 13) % 397 + 3 = 383 + 3 = 386
        index=11 → (407 + 13) % 397 + 3 =  23 + 3 = 26   （回绕）
    取值范围恒为 3 ~ 399。

    注意这几个注释里的值也被 tests/test_seed_determinism.py 独立核对过。
    初版注释里 index=11 写成 13（中间步骤漏加了 +13），是测试抓出来的 ——
    「可手算」的价值不在于手算一定对，而在于存在一条独立于代码的验证路径。
    """
    return (index * 37 + 13) % 397 + 3


TAGS = [
    ("Vue", "#41b883"),
    ("FastAPI", "#009688"),
    ("SQLite", "#003b57"),
    ("学习笔记", "#1e5cb8"),
    ("踩坑记录", "#c0392b"),
    ("部署", "#8e44ad"),
    ("性能优化", "#d35400"),
    ("工具链", "#16a085"),
]

# 文章清单：标题 + 标签列表。
#
# 标签写成显式列表而不是「第 4 的倍数挂第二个标签」：
# 原来那种规则没有任何语义，纯粹为了凑「一篇文章多标签」的样本，
# 而且依赖 dict 的插入顺序（`list(tag_map.values())[n]`）——
# 顺序一变就指向别的标签，且不会有任何报错。
#
# 显式写出来的收益是「任何人跑一遍都得到同样的东西，并且知道它是什么」，
# 这正是种子数据存在的意义。代价是多标签分布不再均匀，但那本来也不重要。
ARTICLES: list[tuple[str, list[str]]] = [
    ("Vue 3 组合式 API 入门笔记", ["Vue", "学习笔记"]),
    ("ref 与 reactive 到底怎么选", ["Vue"]),
    ("Pinia 的状态设计边界", ["Vue"]),
    ("Vue Router 的 history 模式踩坑", ["Vue", "踩坑记录"]),
    ("FastAPI 依赖注入的三种写法", ["FastAPI", "学习笔记"]),
    ("Pydantic v2 校验器实战", ["FastAPI"]),
    ("为什么我把统一响应体做成装饰器", ["FastAPI"]),
    ("FastAPI 异常处理器的一次重构", ["FastAPI", "踩坑记录"]),
    ("SQLite 的 WAL 模式到底解决了什么", ["SQLite", "学习笔记"]),
    ("外键约束为什么默认是关的", ["SQLite", "踩坑记录"]),
    ("Alembic 迁移的 downgrade 怎么写", ["SQLite"]),
    ("索引建错了比不建还慢", ["SQLite", "性能优化"]),
    ("前端首屏体积从 300KB 压到 57KB", ["性能优化"]),
    ("N+1 查询是怎么悄悄出现的", ["性能优化", "踩坑记录"]),
    ("图片为什么要转 WebP", ["性能优化"]),
    ("3Mbps 带宽下的资源策略", ["部署", "性能优化"]),
    ("4G 内存服务器跑 Docker 的注意事项", ["部署"]),
    ("Nginx 反向代理的常见配置错误", ["部署", "踩坑记录"]),
    ("pnpm 与 npm 的 lockfile 差异", ["工具链"]),
    ("gitignore 漏写一行导致仓库膨胀", ["工具链", "踩坑记录"]),
    ("一次误删数据库的经历", ["踩坑记录"]),
    ("时区问题让我 debug 了一下午", ["踩坑记录"]),
    ("中文 slug 的取舍", ["学习笔记"]),
    ("读源码比读文档慢，但值得", ["学习笔记"]),
]

# 草稿：用来验证「草稿对外不可见」。
# 草稿同样挂标签——原版本草稿不挂标签，导致「草稿是否被计入标签文章数」
# 这件事在真实数据里根本验证不到，只能靠单元测试手工造数据。
DRAFTS: list[tuple[str, list[str]]] = [
    ("草稿：还没写完的思考 一", ["学习笔记"]),
    ("草稿：还没写完的思考 二", ["踩坑记录", "部署"]),
]

BODY_TEMPLATE = """## 背景

这篇文章记录我在 {topic} 上的实践与思考。

## 核心内容

先看一段代码：

```python
def example(topic: str) -> dict:
    return {{"topic": topic, "ok": True}}
```

几个关键点：

1. 先把问题复现出来
2. 再确认根因，不要急着改代码
3. 最后补一条测试，防止它回来

## 对比

| 方案 | 优点 | 代价 |
|---|---|---|
| 方案 A | 实现简单 | 后期难扩展 |
| 方案 B | 结构清晰 | 前期投入大 |

## 小结

> 能复现的问题才是问题，不能复现的只是现象。

对 {topic} 这个话题，我的结论是：**先让它跑起来，再让它跑得对，最后才让它跑得快。**
"""


def seed(reset: bool = False) -> int:
    db = SessionLocal()
    try:
        admin = db.scalars(select(User).order_by(User.id)).first()
        if admin is None:
            print("[失败] 没有管理员账号，请先执行：python -m app.init_db")
            return 1

        if reset:
            db.execute(delete(ArticleTag))
            db.execute(delete(Article))
            db.execute(delete(Tag))
            db.commit()
            print("[重置] 已清空文章与标签")

        # ---- 标签 ----
        tag_map: dict[str, Tag] = {}
        for name, color in TAGS:
            existing = db.scalars(select(Tag).where(Tag.name == name)).one_or_none()
            if existing is None:
                existing = Tag(name=name, slug=make_slug_from_title(name), color=color)
                db.add(existing)
                db.flush()
            tag_map[name] = existing

        # ---- 文章 ----
        now = utc_now()
        created = 0
        skipped = 0

        for index, (title, tag_names) in enumerate(ARTICLES):
            slug = make_slug_from_title(title)
            if db.scalars(select(Article).where(Article.slug == slug)).one_or_none():
                skipped += 1
                continue

            md = BODY_TEMPLATE.format(topic=title)
            # 发布时间依次往前推，让归档页产生多个年月分组
            days_ago = index * 9
            published = (now - timedelta(days=days_ago)).replace(microsecond=0)

            article = Article(
                title=title,
                slug=slug,
                summary=strip_markdown(md, max_length=120),
                content_md=md,
                content_html=render_markdown(md),
                status="published",
                author_id=admin.id,
                view_count=fake_view_count(index),
                published_at=published,
                created_at=published,
                updated_at=published,
            )
            db.add(article)
            db.flush()

            for tag_name in tag_names:
                db.add(ArticleTag(article_id=article.id, tag_id=tag_map[tag_name].id))

            created += 1

        # 草稿：同样挂标签，这样「草稿是否被计入标签文章数」
        # 在真实数据里也能验证，而不只依赖单元测试手工造的数据。
        for index, (title, tag_names) in enumerate(DRAFTS):
            slug = make_slug_from_title(title)
            if db.scalars(select(Article).where(Article.slug == slug)).one_or_none():
                skipped += 1
                continue

            md = BODY_TEMPLATE.format(topic=title)
            draft = Article(
                title=title,
                slug=slug,
                summary="草稿，未发布",
                content_md=md,
                content_html=render_markdown(md),
                status="draft",
                author_id=admin.id,
                view_count=0,
            )
            db.add(draft)
            db.flush()

            for tag_name in tag_names:
                db.add(ArticleTag(article_id=draft.id, tag_id=tag_map[tag_name].id))

            created += 1

        db.commit()
        total = len(ARTICLES) + len(DRAFTS)
        print(
            f"[完成] 新增 {created} 篇（共 {total} 篇，"
            f"含草稿 {len(DRAFTS)} 篇），跳过已存在 {skipped} 篇，标签 {len(tag_map)} 个"
        )
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[失败] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="生成种子数据")
    parser.add_argument("--reset", action="store_true", help="清空文章与标签后重建")
    parser.add_argument(
        "--force",
        action="store_true",
        help="确认对开发库执行 --reset（不加此参数时，非测试模式下的 --reset 会被拒绝）",
    )
    args = parser.parse_args()

    # --reset 会删除数据。加上一道确认，避免「手滑跑了一下测试库/开发库」。
    # 测试模式下（run_tests.py 注入 BLOG_TEST_MODE=1）目标本来就是测试库，无需确认。
    if args.reset:
        from app.database import resolve_sqlite_path
        from tests._env import DEV_DB_PATH, TEST_DB_PATH, is_test_mode

        target = resolve_sqlite_path(settings.database_url)
        if target == DEV_DB_PATH and not is_test_mode() and not args.force:
            print("[拒绝执行] --reset 会清空开发数据库里的文章与标签：")
            print(f"  {target}")
            print("确认要这么做，请加 --force 再运行一次。")
            return 2
        if target is not None and target not in (DEV_DB_PATH, TEST_DB_PATH):
            print(f"[注意] 目标是自定义数据库：{target}")

    return seed(reset=args.reset)


if __name__ == "__main__":
    sys.exit(main())
