"""后台接口（需要登录）

路由层只做三件事：接参数、调服务、包成统一响应体。
所有后台接口都在函数签名里声明 `user: User = Depends(get_current_user)` ——
这是「默认公开、要保护就显式声明」的方向，比中间件白名单安全。

【为什么全文放在一个文件而不是按领域拆】
文档 03 第 2.3 节：路由按「访问身份」分组，不按业务领域。
后台接口的共同点是「都要登录」，拆成 admin_articles.py / admin_tags.py
只会让路由注册变复杂，而保护级别完全相同，拆开没有收益。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.errors import ApiResponse, ok
from app.database import get_db
from app.models import User
from app.schemas import (
    ArticleAdminDetail,
    ArticleCreate,
    ArticleListItem,
    ArticleUpdate,
    PaginatedData,
    SiteConfigOut,
    SiteConfigUpdate,
    TagCreate,
    TagDeleteResult,
    TagUpdate,
    TagUsage,
    TagWithCount,
)
from app.services import get_article_for_admin, get_site_config, to_list_item
from app.services.article_admin_service import (
    create_article,
    delete_article,
    list_articles_for_admin,
    update_article,
)
from app.services.site_admin_service import update_site_config
from app.services.tag_admin_service import (
    count_tag_usage,
    create_tag,
    delete_tag,
    list_tags_for_admin,
    update_tag,
)

router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------------------------------------------
# 文章管理（文档 05 第 4 章）
# ------------------------------------------------------------------


@router.get("/articles", response_model=ApiResponse[PaginatedData[ArticleListItem]])
def admin_list_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    status: str | None = Query(None, pattern=r"^(draft|published)$"),
    q: str | None = Query(None, max_length=50),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """后台文章列表（含草稿）

    status 参数是可选的：不传返回全部（草稿 + 已发布），
    传 draft / published 则只看其中一种。
    后台需要「全部」这个视图 —— 否则作者无法一眼看到自己有多少草稿。
    """
    data = list_articles_for_admin(db, page=page, page_size=page_size, status=status, q=q)
    data["items"] = [to_list_item(item) for item in data["items"]]
    return ok(data)


@router.get("/articles/{article_id}", response_model=ApiResponse[ArticleAdminDetail])
def admin_get_article(
    article_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """后台文章详情：额外返回 content_md

    编辑必须拿到 Markdown 原文，否则无法在编辑器里继续修改。
    content_html 也一起返回 —— 编辑器通常要提供「预览」，
    用它比自己在前端渲染一份更一致。

    注意这里**按 id 而不是 slug** 查询：
    后台处理的是「数据库里的第几行」，slug 是可变的展示标识；
    而且草稿也有 slug，用 slug 查询会让「草稿的 slug 泄漏」
    变成一个可枚举的接口。
    """
    return ok(get_article_for_admin(db, article_id))


@router.post("/articles", response_model=ApiResponse[dict])
def admin_create_article(
    payload: ArticleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    """新建文章

    返回 {id} 而不是完整对象：前端拿到 id 后跳转到编辑页，
    跳转会再拉一次完整详情 —— 少一次组装，也避免
    「返回的对象和随后 GET 到的对象不一致」这种困惑。
    """
    article_id = create_article(
        db,
        title=payload.title,
        content_md=payload.content_md,
        author_id=user.id,
        slug=payload.slug,
        summary=payload.summary,
        status=payload.status,
        tag_ids=payload.tag_ids,
    )
    return ok({"id": article_id}, message="创建成功")


@router.put("/articles/{article_id}", response_model=ApiResponse[dict])
def admin_update_article(
    article_id: int,
    payload: ArticleUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """更新文章（局部更新）

    payload.model_dump(exclude_unset=True) 而不是直接取字段：
    这是「传了才改」能正确工作的前提。
    如果不加 exclude_unset，Pydantic 会把没传的字段填成默认值 None，
    于是「只改标题」的请求会把正文清空 —— 这是最难发现的一类 bug。
    """
    fields = payload.model_dump(exclude_unset=True)
    update_article(db, article_id, **fields)
    return ok({"id": article_id}, message="更新成功")


@router.delete("/articles/{article_id}", response_model=ApiResponse[None])
def admin_delete_article(
    article_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """删除文章（物理删除，不可恢复）

    关联的 article_tags 行由外键 ON DELETE CASCADE 清理。
    """
    delete_article(db, article_id)
    return ok(None, message="删除成功")


# ------------------------------------------------------------------
# 标签管理（文档 05 第 3 章）
# ------------------------------------------------------------------


@router.get("/tags", response_model=ApiResponse[list[TagWithCount]])
def admin_list_tags(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """后台标签列表：文章数含草稿

    与公开的 GET /api/tags 的差别只在计数口径上：
    公开接口只数已发布（访客视角），后台数全部。
    否则会出现「标签显示 0 篇但点进去有草稿」的前后不一致。
    """
    return ok(list_tags_for_admin(db))


@router.post("/tags", response_model=ApiResponse[dict])
def admin_create_tag(
    payload: TagCreate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """新建标签

    重名返回 40003 而不是自动加后缀 ——
    标签名是给人选用的，悄悄造出「Vue-2」会让作者困惑。
    """
    tag_id = create_tag(db, name=payload.name, color=payload.color)
    return ok({"id": tag_id}, message="创建成功")


@router.get("/tags/{tag_id}/usage", response_model=ApiResponse[TagUsage])
def admin_tag_usage(
    tag_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """查询标签被多少篇文章使用（删除前的影响预览）

    前端在弹出删除确认框之前调用它，好把「会影响 5 篇文章」
    这句提示写具体。只有一个数字，比「确定要删除吗」有用得多。
    """
    return ok(count_tag_usage(db, tag_id))


@router.put("/tags/{tag_id}", response_model=ApiResponse[dict])
def admin_update_tag(
    tag_id: int,
    payload: TagUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """更新标签（局部更新）

    slug 不随名字变化：改标签名不该让 /tags/vue 这个链接失效。
    """
    fields = payload.model_dump(exclude_unset=True)
    update_tag(db, tag_id, **fields)
    return ok({"id": tag_id}, message="更新成功")


@router.delete("/tags/{tag_id}", response_model=ApiResponse[TagDeleteResult])
def admin_delete_tag(
    tag_id: int,
    force: bool = Query(False, description="标签还挂在文章上时必须传 true"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """删除标签

    【为什么默认拒绝】
    删标签会通过外键 CASCADE 摘掉它在所有文章上的关联，且不可恢复。
    若标签还挂在文章上，默认返回 409 并要求显式 force=true ——
    这样「误点删除按钮」不会立刻造成破坏。

    依据是**删除的代价不对等**：误删标签要逐篇手动加回来，
    而多一次确认点击的成本几乎为零。
    """
    result = delete_tag(db, tag_id, force=force)
    return ok(result, message="删除成功")


# ------------------------------------------------------------------
# 站点配置（文档 05 第 5 章）
# ------------------------------------------------------------------


@router.get("/site", response_model=ApiResponse[SiteConfigOut])
def admin_get_site_config(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """读取站点配置（后台）

    与公开的 GET /api/site 返回同样的结构。
    单独准备一个后台版本，是为了将来后台需要多看到一些
    「不对外展示」的配置项时有地方放，而不必改动公开接口。
    """
    return ok({"values": get_site_config(db)})


@router.put("/site", response_model=ApiResponse[SiteConfigOut])
def admin_update_site_config(
    payload: SiteConfigUpdate,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
) -> dict:
    """更新站点配置（局部更新：只写传了的键）

    返回更新后的完整配置 —— 前端可直接用它刷新界面，
    少一次 GET，也避免「写成功但读到的还是旧值」这种困惑。

    未知键会被拒绝（400），原因见 site_admin_service 里的说明：
    静默接受拼错的键会变成「改了配置但页面没变」这类难查的问题。
    """
    values = update_site_config(db, payload.values)
    return ok({"values": values}, message="保存成功")
