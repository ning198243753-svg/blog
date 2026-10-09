"""slug 工具：把中文标题转成 URL 友好的标识

设计取舍（必须说清楚，否则后面会困惑）：
**中文标题不做拼音转换，而是保留中文并做 URL 编码。**

理由：拼音转换需要引入 pypinyin 之类的库，而且同音字会产生大量冲突
（「实现」和「实践」都是 shixian）。保留中文的 slug 在浏览器里显示为
百分号编码，但可读性对「我自己和面试官」这两类读者没有影响。

代价：中文 slug 更长（一个汉字编码后占 9 个字符），所以数据库里
slug 字段留了 140（title 上限 120 汉字 × 编码膨胀留余量）。

英文/数字则正常处理为小写连字符形式。
"""

import re
import unicodedata

# slug 中允许出现的字符：中文、字母、数字、连字符
_SLUG_KEEP = re.compile(r"[^\w\u4e00-\u9fff-]", re.UNICODE)
_MULTI_DASH = re.compile(r"-{2,}")


def make_slug(text: str, max_length: int = 140) -> str:
    """生成 slug

    >>> make_slug("Hello World")
    'hello-world'
    >>> make_slug("Vue 3 学习笔记")
    'vue-3-学习笔记'
    """
    # NFKC 规范化：把全角字符转成半角（如 ＡＢＣ → ABC），
    # 否则全角空格、全角标点会混进 slug
    text = unicodedata.normalize("NFKC", text).strip().lower()

    # 空白与常见分隔符统一成连字符
    text = re.sub(r"[\s_/\\|·、，。！？；：（）【】《》\"'`]+", "-", text)

    # 去掉不允许的字符
    text = _SLUG_KEEP.sub("", text)

    # 合并连续连字符并去掉首尾连字符
    text = _MULTI_DASH.sub("-", text).strip("-")

    return text[:max_length].strip("-")


def make_slug_from_title(title: str) -> str:
    """从标题生成 slug；若结果为空则给一个兜底值

    兜底是必要的：纯 emoji 或纯标点的标题会产生空 slug，
    空 slug 会让 URL 变成 /posts/ 从而路由到列表页。
    """
    slug = make_slug(title)
    return slug or "post"
