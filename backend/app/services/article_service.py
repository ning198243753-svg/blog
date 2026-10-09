"""文章服务层（文档 03 第 2.3 节分层规则的落地）

本层职责：
- 所有数据库查询与写入都在这里
- 组装输出（把 ORM 对象转成模式层能直接用的 dict）
- 业务规则判断（如「草稿对外不可见」）

本层禁止：
- 导入 fastapi 的 Request / HTTPException
- 直接构造 HTTP 响应
出错时抛 BizError，由 main.py 的异常处理器统一转换。
"""

from math import ceil

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BizError, ErrorCode
from app.models import Article, ArticleTag, Tag
from app.schemas.article import ArticleDetail, ArticleListItem
from app.schemas.tag import TagOut
from app.utils.time import to_iso_z


def _to_item(article: Article) -> dict:
    """ORM 对象 → 列表项字典

    时间在这里转成 ISO 8601 带 Z 的字符串。
    不要在模式层用 datetime 类型自动序列化 —— 那样会丢掉 Z 后缀，
    前端按本地时区解析，时间会整体偏移。
    """
    return {
        "id": article.id,
        "title": article.title,
        "slug": article.slug,
        "summary": article.summary,
        "status": article.status,
        "view_count": article.view_count,
        "published_at": to_iso_z(article.published_at),
        "created_at": to_iso_z(article.created_at),
        "updated_at": to_iso_z(article.updated_at),
        "tags": [TagOut.model_validate(t).model_dump() for t in article.tags],
    }


def _published_query():
    """已发布文章的基础查询

    抽成函数而不是到处复制 where(status == "published")：
    将来若增加「定时发布」等状态，只需要改这一处。

    用 selectinload 预加载标签，避免 N+1：
    列表 10 篇若每篇都单独查一次标签，就是 11 次查询。
    """
    return (
        select(Article)
        .where(Article.status == "published")
        .options(selectinload(Article.tags))
    )


def list_articles(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    tag_slug: str | None = None,
    q: str | None = None,
) -> dict:
    """文章列表（文档 05 第 2.1 节）

    返回 {items, total, page, page_size, pages}
    """
    stmt = _published_query()

    if tag_slug:
        # 通过关联表过滤。这里用子查询而不是 JOIN：
        # JOIN 会产生重复行（一篇文章带多个标签时），需要额外 DISTINCT，
        # 而 DISTINCT 与分页的 LIMIT 组合容易算错总数。
        stmt = stmt.where(
            Article.id.in_(
                select(ArticleTag.article_id)
                .join(Tag, Tag.id == ArticleTag.tag_id)
                .where(Tag.slug == tag_slug)
            )
        )

    if q:
        keyword = f"%{q.strip()}%"
        # 搜索范围：标题 + 摘要。
        # 刻意不搜正文：content_html 是 TEXT 且体积大，
        # LIKE '%关键词%' 无法走索引，搜正文会让每次搜索都全表扫描。
        stmt = stmt.where(or_(Article.title.like(keyword), Article.summary.like(keyword)))

    # 总数：用同一组 where 条件，避免「列表和总数对不上」
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    # 排序：发布时间倒序。published_at 理论上非空（已发布的都该有值），
    # 但用 coalesce 兜底，避免历史数据为 NULL 时排序结果不稳定。
    stmt = (
        stmt.order_by(func.coalesce(Article.published_at, Article.created_at).desc(), Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    articles = db.scalars(stmt).unique().all()

    return {
        "items": [_to_item(a) for a in articles],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


def _neighbors(db: Session, article: Article) -> dict:
    """查询上一篇 / 下一篇（文档 06 表格 8）

    方向定义（这是容易搞混的地方，明确写下来）：
    - prev = 比当前文章**更早**发布的那一篇（时间上在它前面）
    - next = 比当前文章**更晚**发布的那一篇（时间上在它后面）

    为什么方向这么定：读者读完后想接着读的是「更新的内容」，
    按时间倒序的博客里，「下一篇」指更新的一篇才符合直觉。

    排序键必须与列表接口完全一致（coalesce(published_at, created_at) + id），
    否则会出现「列表里的顺序」和「详情页的上下篇」对不上的情况 ——
    尤其是在同一天发布了多篇文章时，只按时间比较会拿到不确定的结果。
    """
    order_key = func.coalesce(Article.published_at, Article.created_at)
    current_key = article.published_at or article.created_at

    def one(stmt):
        row = db.scalars(stmt.limit(1)).unique().one_or_none()
        if row is None:
            return None
        return {"title": row.title, "slug": row.slug}

    # 更早：排序键 < 当前，取最接近的一个（即倒序里的第一条）
    prev = one(
        _published_query()
        .where(
            (order_key < current_key)
            | ((order_key == current_key) & (Article.id < article.id))
        )
        .order_by(order_key.desc(), Article.id.desc())
    )

    # 更晚：排序键 > 当前，取最接近的一个（即正序里的第一条）
    next_ = one(
        _published_query()
        .where(
            (order_key > current_key)
            | ((order_key == current_key) & (Article.id > article.id))
        )
        .order_by(order_key.asc(), Article.id.asc())
    )

    return {"prev": prev, "next": next_}


def get_article_by_slug(db: Session, slug: str, *, count_view: bool = True) -> dict:
    """文章详情（文档 05 第 2.2 节）

    草稿对外返回 404 而不是 403 —— 403 等于告诉对方「这里有一篇文章，
    只是你没权限看」，那本身就是信息泄漏。
    """
    stmt = (
        select(Article)
        .where(Article.slug == slug)
        .options(selectinload(Article.tags))
    )
    article = db.scalars(stmt).unique().one_or_none()

    if article is None or article.status != "published":
        raise BizError(ErrorCode.NOT_FOUND, http_status=404)

    if count_view:
        # 阅读数用「读时累加」。这会让 GET 请求产生写操作，
        # 严格来说不符合 HTTP 语义（GET 应当是幂等的），
        # 但文档 05 明确要求该行为，且它是唯一的高频写路径。
        article.view_count = (article.view_count or 0) + 1
        db.commit()
        db.refresh(article)

    data = _to_item(article)
    data["content_html"] = article.content_html

    # 上下篇：只多两条 LIMIT 1 查询，各自走 idx_articles_status_published 索引。
    # 不做成一次 OR 查询 —— 那需要在一个结果集里区分「更早的」和「更晚的」，
    # 反而要取回全部相邻行再在内存里挑，得不偿失。
    data.update(_neighbors(db, article))
    return data


def list_archive(db: Session) -> list[dict]:
    """归档：按年月分组（文档 05 第 2.6 节）

    一次查出全部已发布文章，在内存里分组。
    为什么不按年月分别查：那会产生 N+1 次查询（每个年月一次），
    而归档页本来就要展示全部文章，一次取完反而更快。
    """
    stmt = _published_query().order_by(
        func.coalesce(Article.published_at, Article.created_at).desc(), Article.id.desc()
    )
    articles = db.scalars(stmt).unique().all()

    groups: dict[tuple[int, int], list] = {}
    for article in articles:
        # 归档用 published_at，没有则退回 created_at，
        # 否则草稿改发布后会出现「没有年月」的文章
        moment = article.published_at or article.created_at
        key = (moment.year, moment.month)
        groups.setdefault(key, []).append(_to_item(article))

    return [
        {
            "year": year,
            "month": month,
            "count": len(items),
            "articles": items,
        }
        for (year, month), items in sorted(groups.items(), reverse=True)
    ]


def list_all_tags(db: Session) -> list[dict]:
    """标签列表，带每个标签下的已发布文章数（文档 05 第 2.3 节）

    一条 SQL 算完，不在 Python 里循环查库。

    关键点：COUNT 里必须写 **Article.id**，不能写 ArticleTag.article_id。
    outerjoin 之后，草稿文章对应的 Article 行是 NULL，但它的关联行仍然存在；
    COUNT(article_tags.article_id) 数的是「关联行数」，会把草稿也算进去；
    COUNT(articles.id) 数的是「真正匹配到的文章」，NULL 不计入。
    早期版本写错了这一点，然后用「循环里再查一遍」来补救 ——
    那是用 N+1 掩盖 JOIN 条件错误，标签一多就会暴露成几十次查询。
    """
    stmt = (
        select(Tag, func.count(Article.id).label("article_count"))
        .outerjoin(ArticleTag, ArticleTag.tag_id == Tag.id)
        .outerjoin(
            Article,
            (Article.id == ArticleTag.article_id) & (Article.status == "published"),
        )
        .group_by(Tag.id)
        # 文章多的标签排前面；数量相同时按名称，保证排序稳定
        .order_by(func.count(Article.id).desc(), Tag.name.asc())
    )

    return [
        {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "color": tag.color,
            "article_count": count,
        }
        for tag, count in db.execute(stmt).all()
    ]


def get_article_for_admin(db: Session, article_id: int) -> dict:
    """后台文章详情：额外带 content_md（M3 使用）"""
    stmt = (
        select(Article)
        .where(Article.id == article_id)
        .options(selectinload(Article.tags))
    )
    article = db.scalars(stmt).unique().one_or_none()
    if article is None:
        raise BizError(ErrorCode.NOT_FOUND, http_status=404)

    data = _to_item(article)
    data["content_html"] = article.content_html
    data["content_md"] = article.content_md
    return data


def to_detail(data: dict) -> ArticleDetail:
    """把服务层 dict 转成响应模型，做一次字段白名单校验

    这一步的价值：如果服务层不小心多塞了字段（比如 content_md），
    Pydantic 会因为响应模型里没有该字段而丢弃它 —— 多一道防线。
    """
    return ArticleDetail.model_validate(data)


def to_list_item(data: dict) -> ArticleListItem:
    return ArticleListItem.model_validate(data)
