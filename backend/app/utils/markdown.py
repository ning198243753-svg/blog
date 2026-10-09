"""Markdown 渲染与 XSS 过滤

这条链路是 ADR-06 的落地，顺序不能变：
    Markdown → HTML → **白名单过滤** → 存库 → 前端 v-html

为什么过滤必须放在「渲染后」而不是「渲染前」：
过滤 Markdown 源码是没用的——攻击者可以写 Markdown 里合法但会生成
危险 HTML 的结构。只有拿到最终 HTML 再按标签/属性白名单过一遍，
才能保证存进 content_html 的字符串是安全的。

为什么必须用白名单而不是黑名单：
黑名单要穷举所有危险写法（<script>、onerror、javascript:、data:、
SVG 内嵌脚本……），漏一个就失效。白名单反过来：不在名单里的一律删掉，
漏掉的风险是「某个正常标签被误删」，表现为排版异常而不是安全漏洞。
"""

import bleach
import markdown_it

# ---- 白名单 ----
# 允许的标签：Markdown 常见产物 + 代码高亮需要的结构
ALLOWED_TAGS = [
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "del", "s", "sup", "sub",
    "ul", "ol", "li",
    "blockquote",
    "pre", "code",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
    "div", "span",
]

# 允许的属性：只留真正需要的
ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "img": ["src", "alt", "title"],
    # 代码高亮库会把语言写在 class 上（language-python）
    "code": ["class"],
    "pre": ["class"],
    "div": ["class"],
    "span": ["class"],
    "th": ["align"],
    "td": ["align"],
}

# 允许的协议：不允许 javascript: 与 data:
ALLOWED_PROTOCOLS = ["http", "https", "mailto"]


def _build_markdown() -> markdown_it.MarkdownIt:
    """构建 Markdown 解析器

    预设必须用 gfm-like，不能用 commonmark。
    原因是 CommonMark 规范里**没有**围栏代码块（```）、表格、删除线、
    自动链接——这些全部是 GitHub Flavored Markdown 的扩展。
    用 commonmark 预设的后果：代码块被渲染成单行 <code>，换行丢失、
    语言标记失效、CSS 中所有 pre 样式失效。

    用 gfm-like 而不是「commonmark + 手动 enable 扩展」：
    手动列举必然会漏（本项目就漏了 fence），而漏掉的表现是静默的渲染错误，
    不会报任何异常。
    """
    return markdown_it.MarkdownIt(
        "gfm-like",
        {
            # 源码里的原始 HTML 一律转义成文本（第一道防线）
            "html": False,
            "typographer": False,
        },
    )


_md = _build_markdown()


def render_markdown(text: str) -> str:
    """Markdown → 安全 HTML

    两个开关都必须在位：
    - markdown_it 的 html=False：源码里的原始 HTML 标签被转义成文本
    - bleach.clean 白名单：最终 HTML 再过一遍，双保险

    只靠其中一个是不够的：html=False 只处理 Markdown 解析阶段，
    而 bleach 只处理解析后的结果；两层都开，任何一层出问题都还有另一层。
    """
    if not text:
        return ""

    raw_html = _md.render(text)

    return bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,  # 不在白名单的标签直接删掉标签本身，保留内部文本
    )


def strip_markdown(text: str, max_length: int = 300) -> str:
    """提取纯文本摘要：去掉所有 Markdown 标记

    用于「作者没填摘要时自动生成」，以及全文搜索的匹配文本。
    """
    if not text:
        return ""

    plain = _md.render(text)
    plain = bleach.clean(plain, tags=[], strip=True)
    # 连续空白压成一个空格
    plain = " ".join(plain.split())

    if len(plain) <= max_length:
        return plain
    return plain[:max_length].rstrip() + "…"
