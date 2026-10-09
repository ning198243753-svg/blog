"""服务层

分层规则（文档 03 第 2.3 节）：
- 路由层：只为「谁可以访问」而分组（public / auth / admin），不按业务领域分
- 服务层：全部业务逻辑与数据库访问都在这里
- 模型层：只描述表结构，不含业务判断
- 模式层：只描述输入输出形状

服务层禁止导入 fastapi 的 Request / HTTPException ——
它应当能被单元测试直接调用，不需要启动 HTTP 服务。
出错统一抛 BizError，由 main.py 的异常处理器翻译成 HTTP 响应。
"""

from app.services.article_service import (
    get_article_by_slug,
    get_article_for_admin,
    list_all_tags,
    list_archive,
    list_articles,
    to_detail,
    to_list_item,
)
from app.services.auth_service import authenticate, to_current_user
from app.services.site_service import get_articles_per_page, get_site_config

__all__ = [
    "authenticate",
    "get_article_by_slug",
    "get_article_for_admin",
    "get_articles_per_page",
    "get_site_config",
    "list_all_tags",
    "list_archive",
    "list_articles",
    "to_current_user",
    "to_detail",
    "to_list_item",
]
