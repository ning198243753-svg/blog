"""站点配置写操作（文档 05 第 5 章）

只做一件事：把前端提交的键值对写进 site_config 表。

【为什么必须有白名单】
site_config 是一张 key-value 表，任何人都能往里塞任意键。
不限制的话，一个拼错的键（author_nmae）会安安静静地写进去 ——
页面读的是 author_name，于是「改了配置但页面没变」，
而数据库里确实多了一行，排查时会非常困惑。

所以只接受 DEFAULTS 里已声明的键。新增配置项必须先加到 DEFAULTS。
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BizError, ErrorCode
from app.models import SiteConfig
from app.services.site_service import DEFAULTS

# 值的长度上限。site_config.value 是 TEXT，本身不限长，
# 但作者不会需要一万字的站点标题 —— 加上限是为了防止
# 误粘贴一大段内容进去（那种数据很难清理，因为它在每一页都输出）。
MAX_VALUE_LENGTH = 2000

# 这些键的值必须是数字，且要落在合理区间
NUMERIC_RULES: dict[str, tuple[int, int]] = {
    # 每页文章数：0 会导致除零，过大让分页失去意义
    "articles_per_page": (1, 50),
}


def update_site_config(db: Session, values: dict[str, str]) -> dict[str, str]:
    """更新站点配置（局部更新：只写传了的键）

    返回更新后的完整配置，便于前端直接用来刷新界面 ——
    少一次 GET 请求，也避免「写成功但读到的还是旧值」这种困惑。
    """
    if not values:
        raise BizError(ErrorCode.PARAM_INVALID, message="没有需要更新的配置项", http_status=400)

    # ---- 白名单校验 ----
    unknown = [k for k in values if k not in DEFAULTS]
    if unknown:
        raise BizError(
            ErrorCode.PARAM_INVALID,
            message=(
                f"不认识的配置项：{unknown}。"
                f"可用配置项：{sorted(DEFAULTS)}"
            ),
            http_status=400,
        )

    # ---- 值校验 ----
    for key, raw in values.items():
        if not isinstance(raw, str):
            raise BizError(
                ErrorCode.PARAM_INVALID,
                message=f"配置项 {key} 的值必须是字符串",
                http_status=400,
            )
        if len(raw) > MAX_VALUE_LENGTH:
            raise BizError(
                ErrorCode.PARAM_INVALID,
                message=f"配置项 {key} 的值过长（上限 {MAX_VALUE_LENGTH} 字符）",
                http_status=400,
            )

        if key in NUMERIC_RULES:
            low, high = NUMERIC_RULES[key]
            try:
                number = int(raw)
            except (TypeError, ValueError):
                raise BizError(
                    ErrorCode.PARAM_INVALID,
                    message=f"配置项 {key} 必须是数字",
                    http_status=400,
                ) from None
            if not (low <= number <= high):
                raise BizError(
                    ErrorCode.PARAM_INVALID,
                    message=f"配置项 {key} 必须在 {low} 到 {high} 之间",
                    http_status=400,
                )

    # ---- 写入 ----
    # 逐条 upsert：存在则改值，不存在则插入。
    # 用「先查出所有存在的键，再决定 insert 还是 update」而不是
    # 一条条 db.get()：配置项很少，一次查完更省往返。
    keys = list(values)
    existing = {
        row.key: row
        for row in db.scalars(select(SiteConfig).where(SiteConfig.key.in_(keys))).all()
    }

    for key in keys:
        if key in existing:
            existing[key].value = values[key]
        else:
            db.add(SiteConfig(key=key, value=values[key]))

    db.commit()

    # 返回完整配置（含默认值），而不是只返回改动的那几个键
    from app.services.site_service import get_site_config

    return get_site_config(db)
