"""标签写操作服务层（文档 05 第 3 章）

标签看起来比文章简单，但删除有一个容易忽略的后果：
**删掉一个标签会通过外键 CASCADE 摘掉它在所有文章上的关联。**
文章本身还在，但「这篇文章属于踩坑记录」这个事实消失了，且不可恢复。

所以这个模块的重点不是"怎么删"，而是"删之前让人知道会发生什么"。
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import BizError, ErrorCode
from app.models import Article, ArticleTag, Tag
from app.utils.slug import make_slug


def _normalize_name(name: str) -> str:
    """标签名规范化

    去掉首尾空白，并把内部连续空白压成一个空格。
    「 Vue 」和「Vue」应该是同一个标签，否则用户会造出一堆
    看起来一样、实际不同的标签，而列表页会把它们并排显示。
    """
    return " ".join(name.split())


def _unique_tag_slug(db: Session, name: str, exclude_id: int | None = None) -> str:
    """生成标签 slug

    标签 slug 用 make_slug 而不是 make_slug_from_title：
    后者在结果为空时返回 "post"，对标签来说是个误导性的兜底值。
    这里若为空（纯 emoji 的标签名），用一个稳定的后备方案。
    """
    base = make_slug(name, max_length=40) or "tag"
    stmt = select(Tag.slug).where(Tag.slug.like(f"{base}%"))
    if exclude_id is not None:
        stmt = stmt.where(Tag.id != exclude_id)
    existing = set(db.scalars(stmt).all())

    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
        if n > 1000:
            raise BizError(ErrorCode.TAG_EXISTS, http_status=409)
    return f"{base}-{n}"


def create_tag(db: Session, *, name: str, color: str | None = None) -> int:
    """新建标签，返回 id

    重名直接报错（40003）而不是自动加后缀：
    与文章的 slug 不同，标签名是给人看和给人选的。
    悄悄造出一个「Vue-2」标签，作者下次选标签时会困惑
    「我之前那个 Vue 去哪了」。
    """
    clean = _normalize_name(name)
    if not clean:
        raise BizError(ErrorCode.PARAM_INVALID, message="标签名不能为空", http_status=400)

    exists = db.scalar(select(Tag).where(Tag.name == clean))
    if exists is not None:
        raise BizError(ErrorCode.TAG_EXISTS, http_status=409)

    tag = Tag(
        name=clean,
        slug=_unique_tag_slug(db, clean),
        color=color or None,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag.id


def update_tag(
    db: Session,
    tag_id: int,
    *,
    name: str | None = None,
    color: str | None = None,
) -> int:
    """更新标签（局部更新）

    【slug 不随名字改变】
    与文章同理：改标签名不该让 /tags/vue 这个链接失效。
    而且标签页的链接更容易被分享出去。

    注意 color 用 `is not None` 判断「是否传了」，
    所以 **传 null 无法清空颜色** —— 这是一个刻意的限制，
    因为「传 null」和「不传」在 JSON 里对调用方来说很容易混淆，
    与其猜意图，不如不提供这个能力（v1 也不用颜色，见 ADR-08）。
    """
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise BizError(ErrorCode.NOT_FOUND, http_status=404)

    if name is not None:
        clean = _normalize_name(name)
        if not clean:
            raise BizError(ErrorCode.PARAM_INVALID, message="标签名不能为空", http_status=400)

        # 改名冲突检查：查重时要排除自己，否则「把 A 改成 A」会误报冲突
        conflict = db.scalar(
            select(Tag).where(Tag.name == clean, Tag.id != tag_id)
        )
        if conflict is not None:
            raise BizError(ErrorCode.TAG_EXISTS, http_status=409)
        tag.name = clean

    if color is not None:
        tag.color = color

    db.commit()
    return tag.id


def count_tag_usage(db: Session, tag_id: int) -> dict:
    """统计标签的使用情况（删除前的影响预览）

    返回两个数字：
    - article_count：关联的文章总数（含草稿）
    - published_count：其中已发布的

    为什么要区分：作者在后台看到的是全部文章，
    而访客只能看到已发布的。如果只报一个「已发布 5 篇」，
    作者可能以为删掉没关系，实际上还会影响 3 篇草稿。
    """
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise BizError(ErrorCode.NOT_FOUND, http_status=404)

    total = db.scalar(
        select(func.count()).select_from(ArticleTag).where(ArticleTag.tag_id == tag_id)
    ) or 0

    published = db.scalar(
        select(func.count())
        .select_from(ArticleTag)
        .join(Article, Article.id == ArticleTag.article_id)
        .where(ArticleTag.tag_id == tag_id, Article.status == "published")
    ) or 0

    return {
        "id": tag.id,
        "name": tag.name,
        "slug": tag.slug,
        "article_count": total,
        "published_count": published,
    }


def delete_tag(db: Session, tag_id: int, *, force: bool = False) -> dict:
    """删除标签

    【为什么需要 force】
    删标签会 CASCADE 摘掉它在所有文章上的关联，且不可恢复。
    如果标签还挂在文章上，就要求调用方显式传 force=true ——
    这样「误点删除按钮」不会立刻造成破坏，
    前端也能先弹一个「该标签下还有 5 篇文章，确定删除？」的确认框。

    这个设计的选择依据：**删除的代价不对等**。
    误删一个标签需要重新给每篇文章手动加回来；
    而多一次确认点击的代价几乎为零。

    返回受影响文章数，便于调用方给出反馈。
    """
    usage = count_tag_usage(db, tag_id)

    if usage["article_count"] > 0 and not force:
        raise BizError(
            ErrorCode.STATUS_NOT_ALLOWED,
            message=(
                f"该标签还关联着 {usage['article_count']} 篇文章"
                f"（其中 {usage['published_count']} 篇已发布）。"
                "删除会摘掉这些文章上的该标签，且不可恢复。"
                "确认请重新请求并带上 force=true。"
            ),
            http_status=409,
        )

    tag = db.get(Tag, tag_id)
    db.delete(tag)
    db.commit()

    return {"deleted_id": tag_id, "affected_articles": usage["article_count"]}


def list_tags_for_admin(db: Session) -> list[dict]:
    """后台标签列表：带文章数（含草稿）

    公开接口的 /tags 只数已发布文章（访客视角），
    后台必须数全部 —— 否则会出现「标签显示 0 篇但点进去有草稿」
    这种前后不一致。
    """
    stmt = (
        select(Tag, func.count(ArticleTag.article_id).label("cnt"))
        .outerjoin(ArticleTag, ArticleTag.tag_id == Tag.id)
        .group_by(Tag.id)
        .order_by(func.count(ArticleTag.article_id).desc(), Tag.name.asc())
    )
    return [
        {
            "id": tag.id,
            "name": tag.name,
            "slug": tag.slug,
            "color": tag.color,
            "article_count": cnt,
        }
        for tag, cnt in db.execute(stmt).all()
    ]
