"""统一的查询时间处理

数据库里所有时间都按 UTC 存（文档 04 第 6.1 节），
API 返回 ISO 8601 且带 Z 后缀，前端按本地时区显示。

为什么要统一：只要有一处存了本地时间，跨时区或跨夏令时就必然出现
「有的文章时间差 8 小时」，而且这种错很难被发现——它看起来只是数据错了。
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """当前 UTC 时间（不带 tzinfo，与 SQLite 的 DATETIME 存储方式一致）

    SQLite 没有原生时区类型，存 aware datetime 会连同偏移一起写成字符串，
    读取时又拿不到 tzinfo，反而容易混乱。统一存 naive UTC 最省心。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_iso_z(dt: datetime | None) -> str | None:
    """转成带 Z 的 ISO 8601 字符串（供 API 返回）

    >>> to_iso_z(datetime(2026, 10, 9, 12, 0, 0))
    '2026-10-09T12:00:00Z'
    """
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
