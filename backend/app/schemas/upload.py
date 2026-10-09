"""图片上传模式（文档 05 第 4.7 节）"""

from pydantic import BaseModel


class UploadResult(BaseModel):
    """上传结果

    url 是前端唯一必需的字段（直接放进 <img src>）。
    其余字段是诊断信息：让调用方能确认「压缩真的生效了」——
    没有这些数字的话，压缩失效（比如漏了缩放）不会有任何提示，
    只会表现为「博客变慢」。

    source_* 前缀的字段是原图信息，upload 后可以用来对比。
    """

    url: str
    filename: str
    width: int
    height: int
    size: int
    format: str

    # 原图信息（便于验证压缩效果）
    source_format: str
    source_size: int
    source_width: int
    source_height: int

    # 动图信息：frames > 1 表示这是动图，已保留动画
    animated: bool
    frames: int
