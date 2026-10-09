"""公开接口（访客可访问，无需登录）

路由层只做三件事：接参数、调服务、包成统一响应体。
这里不允许出现任何 SQL 或业务判断 —— 一旦出现，测试就必须启动 HTTP 服务，
而且同一段逻辑在后台接口里会被复制第二遍。

路由按「访问身份」而不是「业务领域」分组（文档 03 第 2.3 节）：
将来若某篇文章同时需要给访客和后台用，差别也只是挂在哪个 router 上。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.errors import ApiResponse, ok
from app.database import get_db
from app.schemas import (
    ArchiveGroup,
    ArticleDetail,
    ArticleListItem,
    PaginatedData,
    SiteConfigOut,
    TagWithCount,
)
from app.services import (
    get_article_by_slug,
    get_articles_per_page,
    get_site_config,
    list_all_tags,
    list_archive,
    list_articles,
)

router = APIRouter(tags=["public"])


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    """健康检查：真的查一次库

    只返回字面量 "ok" 的接口在部署验证时等于没有 ——
    进程活着但数据库挂了，它照样返回 ok。
    """
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:  # noqa: BLE001 - 健康检查要吞掉异常并如实上报
        db_status = "error"
    return ok({"status": "ok", "db": db_status})


@router.get("/articles", response_model=ApiResponse[PaginatedData[ArticleListItem]])
def get_articles(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=0, ge=0, le=50, description="传 0 表示使用站点配置的每页条数"),
    tag: str | None = Query(default=None, description="按标签 slug 过滤"),
    q: str | None = Query(default=None, description="搜索标题与摘要"),
    db: Session = Depends(get_db),
) -> dict:
    """文章列表（文档 05 第 2.1 节）"""
    # page_size 传 0 表示「用站点配置里的值」。
    # 为什么不在前端直接写死 10：配置项在后台可改，
    # 前端写死就与后台设置脱节了。
    effective_size = page_size or get_articles_per_page(db)
    data = list_articles(db, page=page, page_size=effective_size, tag_slug=tag, q=q)
    return ok(data)


@router.get("/articles/{slug}", response_model=ApiResponse[ArticleDetail])
def get_article(slug: str, db: Session = Depends(get_db)) -> dict:
    """文章详情（文档 05 第 2.2 节）

    草稿返回 404 而不是 403：403 相当于确认「这里有一篇你看不到的文章」。
    """
    return ok(get_article_by_slug(db, slug))


@router.get("/tags", response_model=ApiResponse[list[TagWithCount]])
def get_tags(db: Session = Depends(get_db)) -> dict:
    """标签列表，带已发布文章数"""
    return ok(list_all_tags(db))


@router.get("/tags/{slug}", response_model=ApiResponse[PaginatedData[ArticleListItem]])
def get_articles_by_tag(
    slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=0, ge=0, le=50),
    db: Session = Depends(get_db),
) -> dict:
    """某个标签下的文章列表（文档 05 第 2.4 节）"""
    effective_size = page_size or get_articles_per_page(db)
    return ok(list_articles(db, page=page, page_size=effective_size, tag_slug=slug))


@router.get("/archive", response_model=ApiResponse[list[ArchiveGroup]])
def get_archive(db: Session = Depends(get_db)) -> dict:
    """归档：按年月分组（文档 05 第 2.6 节）"""
    return ok(list_archive(db))


@router.get("/search", response_model=ApiResponse[PaginatedData[ArticleListItem]])
def search(
    q: str = Query(min_length=1, max_length=50, description="关键词"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=0, ge=0, le=50),
    db: Session = Depends(get_db),
) -> dict:
    """搜索（文档 05 第 2.5 节）

    搜索范围是标题 + 摘要，不含正文。理由见 article_service.list_articles：
    LIKE '%关键词%' 无法走索引，搜 TEXT 正文会让每次搜索都全表扫描。
    """
    effective_size = page_size or get_articles_per_page(db)
    return ok(list_articles(db, page=page, page_size=effective_size, q=q))


@router.get("/site", response_model=ApiResponse[SiteConfigOut])
def get_site(db: Session = Depends(get_db)) -> dict:
    """站点配置（文档 05 第 2.7 节）"""
    return ok({"values": get_site_config(db)})
