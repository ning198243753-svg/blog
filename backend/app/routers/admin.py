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
)
from app.services import get_article_for_admin, to_list_item
from app.services.article_admin_service import (
    create_article,
    delete_article,
    list_articles_for_admin,
    update_article,
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
