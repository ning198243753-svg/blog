"""站点配置服务（文档 04 第 3.5 节 / 文档 05 第 2.7 节）"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SiteConfig

# 配置文件里没有的值用这些兜底。
# 不兜底的话，新环境首次启动（还没跑 init_db）时前端会拿到空字符串，
# 页面标题变成空白 —— 而且 init_db 是独立步骤，很容易被漏掉。
DEFAULTS: dict[str, str] = {
    "site_title": "moon 的学习笔记",
    "site_subtitle": "记录 · 整理 · 复现",
    "author_name": "moon",
    "author_intro": "",
    "footer_text": "",
    "icp_number": "",
    "github_url": "",
    "articles_per_page": "10",
}


def get_site_config(db: Session) -> dict[str, str]:
    """读取全部站点配置

    返回合并后的字典（数据库值覆盖默认值）。
    不返回「数据库里有什么就返回什么」：那样前端必须自己处理缺失项，
    而每个组件各处理一次就是 N 处重复逻辑。
    """
    rows = db.execute(select(SiteConfig)).scalars().all()
    values = dict(DEFAULTS)
    for row in rows:
        values[row.key] = row.value
    return values


def get_articles_per_page(db: Session) -> int:
    """读取每页文章数

    单独抽出来是因为它要转成 int：site_config 是 key-value 表，
    所有值都是字符串。转换失败时退回 10 而不是抛异常 ——
    一个配错的数字不该让整个列表页打不开。
    """
    raw = get_site_config(db).get("articles_per_page", "10")
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 10
    # 越界值同样退回默认：0 会导致除零，过大则让分页失去意义
    return value if 1 <= value <= 50 else 10
