"""站点配置写模式（文档 05 第 5 章）"""

from pydantic import BaseModel, Field


class SiteConfigUpdate(BaseModel):
    """更新站点配置

    用 dict[str, str] 而不是固定字段：配置项本来就会增加，
    每加一项都要改请求模型的话，这张「可扩展的表」就没有意义了。

    真正的白名单校验在服务层（site_admin_service.update_site_config），
    那里有一份 DEFAULTS 作为唯一事实来源 ——
    在这里再写一遍键名，两处就会不同步。
    """

    values: dict[str, str] = Field(
        description="要更新的配置项，形如 {\"site_title\": \"我的博客\"}",
        min_length=1,
    )
