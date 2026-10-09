"""文章写操作服务层（文档 05 第 4 章）

M1/M2 的服务层是只读的，这一层开始有写操作，因此责任更重：
写错了不容易发现，删除更不可逆。

本模块集中处理四件事：
1. slug 的唯一性（含中文标题生成）
2. 摘要的自动生成
3. Markdown → HTML 的渲染时机
4. 状态切换时 published_at 的维护
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import BizError, ErrorCode
from app.models import Article, Tag
from app.utils.markdown import render_markdown, strip_markdown
from app.utils.slug import make_slug_from_title


def _now() -> datetime:
    """当前 UTC 时间（naive）

    数据库里存的是 naive UTC（文档 04 约定），
    所以这里必须去掉 tzinfo，否则 SQLite 存进去的字符串会带 +00:00，
    读出来再被当成本地时间 —— 就是那个「差 8 小时」的问题。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _unique_slug(db: Session, base_slug: str, exclude_id: int | None = None) -> str:
    """生成不与现有文章冲突的 slug

    冲突时依次尝试 base、base-2、base-3 …
    为什么从 -2 开始而不是 -1：`-1` 容易被误读成「第一版」，
    而 `-2` 明确表示「第二个同名」。

    为什么不用随机后缀：可读性差，且同一标题重建两次会得到不同 URL，
    不利于「我知道这篇文章的地址」这种使用方式。

    exclude_id 用于更新场景：更新时文章自身的 slug 不算冲突。
    """
    stmt = select(Article.slug).where(Article.slug.like(f"{base_slug}%"))
    if exclude_id is not None:
        stmt = stmt.where(Article.id != exclude_id)
    existing = set(db.scalars(stmt).all())

    if base_slug not in existing:
        return base_slug

    n = 2
    while f"{base_slug}-{n}" in existing:
        n += 1
        # 理论上不会发生，但无限循环比多三行代码危险得多
        if n > 1000:
            raise BizError(ErrorCode.SLUG_CONFLICT, http_status=409)
    return f"{base_slug}-{n}"


def _resolve_tags(db: Session, tag_ids: list[int]) -> list[Tag]:
    """按 id 取标签，任何一个不存在都报错

    为什么不静默忽略不存在的 id：那会让前端以为标签保存成功了，
    而实际上少了一个 —— 这种「部分成功」最难排查。
    """
    if not tag_ids:
        return []

    # 去重：前端可能传入重复 id，直接关联会产生重复关联行
    unique_ids = list(dict.fromkeys(tag_ids))
    tags = db.scalars(select(Tag).where(Tag.id.in_(unique_ids))).all()

    if len(tags) != len(unique_ids):
        found = {t.id for t in tags}
        missing = [i for i in unique_ids if i not in found]
        raise BizError(
            ErrorCode.PARAM_INVALID,
            message=f"标签不存在：{missing}",
            http_status=400,
        )
    return list(tags)


def _apply_status(article: Article, status: str, is_new: bool) -> None:
    """维护 status 与 published_at 的一致性

    规则（文档 05）：
    - 改为 published 且此前没有发布时间 → 记录当前时间
    - 改为 draft → **保留** published_at 不清空

    第二条是有意的：如果清空，那么「发布 → 转草稿 → 再发布」
    会让文章跳到列表最前面，虽然内容没变。保留原时间更符合直觉。
    """
    article.status = status
    if status == "published" and article.published_at is None:
        article.published_at = _now()


def create_article(
    db: Session,
    *,
    title: str,
    content_md: str,
    author_id: int,
    slug: str | None = None,
    summary: str | None = None,
    status: str = "draft",
    tag_ids: list[int] | None = None,
) -> int:
    """新建文章，返回新文章 id

    返回 id 而不是 ORM 对象：路由层马上要靠它做第二次查询
    （带 tags 的详情），返回对象会让「这个对象是否已过期」变得含糊。
    """
    title = title.strip()
    if not title:
        raise BizError(ErrorCode.PARAM_INVALID, message="标题不能为空", http_status=400)

    # slug：用户指定则直接用（但仍要去重），否则从标题生成
    base_slug = (slug or "").strip() or make_slug_from_title(title)
    final_slug = _unique_slug(db, base_slug)

    # 摘要：没填就从正文提取。存的是纯文本，不是 Markdown ——
    # 列表页直接显示它，留 Markdown 标记会显示成 "## 标题" 这样的字面量。
    final_summary = (summary or "").strip() or strip_markdown(content_md, 300)

    article = Article(
        title=title,
        slug=final_slug,
        summary=final_summary or None,
        content_md=content_md,
        # 【关键】渲染发生在写入时，不是读取时（ADR-06）。
        # 好处：读接口零渲染开销；代价：改渲染规则后需要重刷历史数据。
        content_html=render_markdown(content_md),
        author_id=author_id,
        view_count=0,
    )
    _apply_status(article, status, is_new=True)
    article.tags = _resolve_tags(db, tag_ids or [])

    db.add(article)
    db.commit()
    db.refresh(article)
    return article.id


def update_article(
    db: Session,
    article_id: int,
    *,
    title: str | None = None,
    summary: str | None = None,
    content_md: str | None = None,
    status: str | None = None,
    tag_ids: list[int] | None = None,
) -> int:
    """更新文章（局部更新：只改传了的字段）

    为什么用「None 表示不改」而不是 PUT 的整体替换：
    文档 05 的 PUT 语义是局部更新。整体替换要求前端每次提交
    都带上全部字段 —— 任何一次遗漏都会把字段清空。

    【slug 刻意不可修改】
    文档 05 规定 PUT 保持原 slug。已发布的链接一旦失效，
    个人博客通常没有做重定向，读者会直接碰到 404。

    返回 id，理由同 create_article。
    """
    article = db.get(Article, article_id)
    if article is None:
        raise BizError(ErrorCode.NOT_FOUND, http_status=404)

    if title is not None:
        stripped = title.strip()
        if not stripped:
            raise BizError(ErrorCode.PARAM_INVALID, message="标题不能为空", http_status=400)
        article.title = stripped

    if content_md is not None:
        article.content_md = content_md
        # Markdown 改了就必须重渲染。忘了这一步的表现是
        # 「编辑后页面还是旧内容」，而数据库里 content_md 已经是新的 ——
        # 一个很容易查错方向的问题。
        article.content_html = render_markdown(content_md)

    if summary is not None:
        article.summary = summary.strip() or None

    if tag_ids is not None:
        # 传了才整体替换；没传保持不动。
        # 这个区分很重要：传 [] 表示「清空标签」，不传表示「不改标签」。
        article.tags = _resolve_tags(db, tag_ids)

    if status is not None:
        _apply_status(article, status, is_new=False)

    # 摘要兜底：正文更新后若仍没有摘要，重新生成一次
    if not article.summary and article.content_md:
        article.summary = strip_markdown(article.content_md, 300) or None

    db.commit()
    return article.id


def delete_article(db: Session, article_id: int) -> None:
    """删除文章

    article_tags 的关联行由数据库的 ON DELETE CASCADE 自动清理
    （见 models/article.py 的关联表定义），这里不需要手工删。

    【为什么不做软删除】
    表里有 status，理论上可以加一个 'deleted' 状态。
    但那会让每一个查询都必须带上 "AND status != 'deleted'"，
    漏一处就会让已删文章重新出现 —— 而漏掉的地方不会有任何提示。
    单人博客的删除需求很低频，真删掉、想恢复时从备份找回更简单。
    （M5 会加数据库定时备份，删除因此不是不可挽回的。）

    不存在的 id 直接报 404，而不是静默成功：
    静默成功会让「删错了 id」这类 bug 无处暴露。
    """
    article = db.get(Article, article_id)
    if article is None:
        raise BizError(ErrorCode.NOT_FOUND, http_status=404)

    db.delete(article)
    db.commit()


def list_articles_for_admin(
    db: Session,
    *,
    page: int = 1,
    page_size: int = 10,
    status: str | None = None,
    q: str | None = None,
) -> dict:
    """后台文章列表：**包含草稿**（文档 05 第 4.1 节）

    与公开列表的关键差别：
    - 不限制 status（默认全给），可按 status 过滤
    - 排序按 created_at 倒序：后台关心「我最近编辑了什么」，
      而草稿没有 published_at，按它排序会让草稿全部排到末尾或开头。

    仍然不返回 content_html：后台列表是表格视图，用不到正文。
    一页 10 篇 × 20KB 的 HTML 是 200KB，纯粹浪费带宽。
    """
    stmt = select(Article).options(selectinload(Article.tags))

    if status:
        stmt = stmt.where(Article.status == status)

    if q:
        keyword = f"%{q.strip()}%"
        stmt = stmt.where(Article.title.like(keyword) | Article.summary.like(keyword))

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = (
        stmt.order_by(Article.created_at.desc(), Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    articles = db.scalars(stmt).unique().all()

    from math import ceil

    from app.schemas.article import ArticleListItem
    from app.services.article_service import _to_item

    return {
        "items": [_to_item(a) for a in articles],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if total else 0,
    }


__all__ = [
    "ArticleListItem",
    "create_article",
    "delete_article",
    "list_articles_for_admin",
    "update_article",
]
