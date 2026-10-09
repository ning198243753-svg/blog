"""Markdown 渲染与 XSS 过滤测试

这个文件覆盖两类断言：
1. 功能正确性 —— 代码块、表格、行内代码必须渲染出预期结构
2. 安全性 —— 常见 XSS 载荷必须被拦住

第 1 类曾经真的失败过：使用 commonmark 预设时围栏代码块被渲染成单行
<code>，换行与语言标记全部丢失。所以这里对结构做精确断言，
而不是只断言"输出非空"。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.markdown import render_markdown, strip_markdown  # noqa: E402


def check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"[{'PASS' if condition else 'FAIL'}] {name}  {detail}")
    return condition


def test_code_block() -> list[str]:
    """围栏代码块必须生成 <pre><code class="language-xxx">"""
    failed = []
    html = render_markdown("```python\nprint(1)\nprint(2)\n```")

    if not check("代码块生成 <pre>", "<pre>" in html, html.replace("\n", " ")[:80]):
        failed.append("code_pre")
    if not check("语言标记写入 class", "language-python" in html, html[:80]):
        failed.append("code_lang")
    if not check("换行被保留", "print(1)\nprint(2)" in html, ""):
        failed.append("code_newline")
    if not check("代码块未被压成单行 <code>", html.count("<code") == 1 and "<p>" not in html, ""):
        failed.append("code_single_line")

    # 缩进式代码块也要支持
    html2 = render_markdown("前文\n\n    indented code\n")
    if not check("缩进代码块生成 <pre>", "<pre>" in html2, html2.replace("\n", " ")[:60]):
        failed.append("indent_code")
    return failed


def test_inline_code() -> list[str]:
    failed = []
    html = render_markdown("使用 `pip install` 安装")
    if not check("行内代码生成 <code>", "<code>pip install</code>" in html, html.replace("\n", " ")[:70]):
        failed.append("inline_code")
    return failed


def test_table() -> list[str]:
    failed = []
    html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |")
    for token in ["<table>", "<thead>", "<th>a</th>", "<td>1</td>"]:
        if not check(f"表格包含 {token}", token in html, ""):
            failed.append(f"table_{token}")
    return failed


def test_basic_formatting() -> list[str]:
    failed = []
    cases = [
        ("# 标题", "<h1>标题</h1>", "h1"),
        ("**粗体**", "<strong>粗体</strong>", "strong"),
        ("*斜体*", "<em>斜体</em>", "em"),
        ("> 引用", "<blockquote>", "blockquote"),
        ("- 项目", "<li>项目</li>", "li"),
        ("~~删除~~", "<s>删除</s>", "strikethrough"),
    ]
    for src, expect, label in cases:
        html = render_markdown(src)
        if not check(f"渲染 {label}", expect in html, html.replace("\n", " ")[:60]):
            failed.append(f"fmt_{label}")
    return failed


def _real_tags(html: str) -> set[str]:
    """用 HTML 解析器列出输出里**真实存在的标签**

    为什么必须用解析器、不能用字符串查找：
    `&lt;script&gt;` 这串文本里既有 "script" 也有尖括号，但它是一个
    **文本节点**，浏览器不会执行它。只有解析器知道哪个 `<` 是标签的开始。

    早期版本用 raw.replace("&lt;","<") 手动"解码"再查找子串，
    结果把安全的转义文本误判成危险标签 —— 测试自己报了假警报。
    凡是需要判断「这是标签还是文本」的地方，都必须交给解析器。
    """
    from html.parser import HTMLParser

    class Collector(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.tags: set[str] = set()

        def handle_starttag(self, tag: str, attrs) -> None:
            self.tags.add(tag.lower())

        def handle_startendtag(self, tag: str, attrs) -> None:
            self.tags.add(tag.lower())

    parser = Collector()
    parser.feed(html)
    parser.close()
    return parser.tags


def _real_attrs(html: str, tag: str, attr: str) -> list[str]:
    """解析出指定标签上指定属性的**真实取值**

    用于判断 href/src 这类属性，理由同 _real_tags：
    字符串查找分不清「这是属性值」还是「这是正文里的文字」。
    """
    from html.parser import HTMLParser

    class Collector(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=False)
            self.values: list[str] = []

        def handle_starttag(self, t: str, attrs) -> None:
            if t.lower() == tag:
                for name, value in attrs:
                    if name.lower() == attr and value is not None:
                        self.values.append(value)

        def handle_startendtag(self, t: str, attrs) -> None:
            self.handle_starttag(t, attrs)

    parser = Collector()
    parser.feed(html)
    parser.close()
    return parser.values


# 白名单外的标签：一旦以真实标签形式出现就是漏洞
FORBIDDEN_TAGS = {
    "script", "iframe", "object", "embed", "style", "form", "input",
    "base", "link", "meta", "svg", "math", "applet", "frame", "frameset",
}


def test_xss() -> list[str]:
    """安全测试：判据是「输出里不允许出现白名单外的真实标签」"""
    failed = []
    payloads = [
        ("<script>alert(1)</script>", "script 标签"),
        ("javascript:alert(1)", "裸 javascript 协议"),
        ("[x](javascript:alert(1))", "js 协议链接"),
        ("[x](data:text/html,<script>alert(1)</script>)", "data 协议链接"),
        ("<img src=x onerror=alert(1)>", "img onerror"),
        ("<iframe src='https://evil.com'></iframe>", "iframe"),
        ("<svg onload=alert(1)></svg>", "svg onload"),
        ("<a href='#' onclick='alert(1)'>x</a>", "onclick 事件属性"),
        ("<style>body{display:none}</style>", "style 标签"),
        ("<form action='//evil.com'><input name=p></form>", "表单"),
        ("<object data='evil.swf'></object>", "object 标签"),
        ("<base href='//evil.com/'>", "base 标签"),
    ]
    for payload, label in payloads:
        html = render_markdown(payload)
        tags = _real_tags(html)
        bad_tags = sorted(tags & FORBIDDEN_TAGS)

        # 事件属性：只有在**真实标签**上才算漏洞
        bad_attrs = []
        if "onerror" in html.lower() and "img" in tags:
            bad_attrs.append("onerror")
        if "onclick" in html.lower() and "a" in tags:
            bad_attrs.append("onclick")

        bad = bad_tags + bad_attrs
        if not check(f"拦截 {label}", not bad, f"残留: {bad}" if bad else ""):
            failed.append(f"xss_{label}")

    # 危险协议：必须检查**真实 href 属性**，不能在整个 HTML 里找 "javascript:"
    #
    # 原因：markdown-it 对 `[x](javascript:alert(1))` 会生成一个带
    # data-* 记录的 <a>，或者干脆不生成链接；而即使链接被过滤掉，
    # 转义后的文本里仍然会出现 "javascript:" 这几个字母 —— 那是文本不是协议。
    # 只有解析出真实属性再判断，结论才可靠。
    html = render_markdown("[x](javascript:alert(1))")
    hrefs = _real_attrs(html, "a", "href")
    bad_proto = [h for h in hrefs if h.strip().lower().startswith(("javascript:", "data:"))]
    if not check("链接未生成危险协议", not bad_proto, f"hrefs={hrefs}"):
        failed.append("xss_proto_js")

    # 正常外链必须仍然可用 —— 否则"拦住危险协议"可能是因为链接功能整个坏了
    ok_html = render_markdown("[链接](https://example.com)")
    if not check(
        "安全外链仍可生成",
        _real_attrs(ok_html, "a", "href") == ["https://example.com"],
        str(_real_attrs(ok_html, "a", "href")),
    ):
        failed.append("xss_safe_link")
    return failed


def test_whitelist_actually_used() -> list[str]:
    """确认白名单生效：合法的 Markdown 结构不被误删

    这个测试和 XSS 测试是一对：
    只测"危险标签被拦住"是不够的 —— 把白名单设成空集也能让那些测试全过，
    但博客的排版会全部失效。必须同时验证"该保留的保住了"。
    """
    failed = []
    html = render_markdown(
        "# 标题\n\n正文 **粗** *斜* `代码`\n\n> 引用\n\n- 列表\n\n"
        "```python\nprint(1)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n[链接](https://example.com)\n"
    )
    tags = _real_tags(html)
    for tag in ["h1", "p", "strong", "em", "code", "pre", "blockquote",
                "ul", "li", "table", "thead", "tbody", "tr", "th", "td", "a"]:
        if not check(f"保留标签 {tag}", tag in tags, ""):
            failed.append(f"keep_{tag}")

    if not check("外链 href 保留", 'href="https://example.com"' in html, ""):
        failed.append("keep_href")
    return failed


def test_xss_escaped_not_stripped() -> list[str]:
    """确认危险标签是「被转义成文本」而不是「被静默删除」

    两者都安全，但表现不同：转义后正文里能看到 `&lt;script&gt;` 这段文字，
    删除则会让内容凭空消失。我们选择转义——读者能看出原文写了什么，
    比内容莫名消失更容易排查。
    """
    failed = []
    html = render_markdown("<script>alert(1)</script>")
    if not check("危险标签被转义为文本", "&lt;script&gt;" in html, html.replace("\n", " ")[:70]):
        failed.append("escape_not_strip")
    if not check("源码文字仍可见", "alert(1)" in html, ""):
        failed.append("content_kept")
    return failed


def test_strip_markdown() -> list[str]:
    failed = []
    plain = strip_markdown("# 标题\n\n这是**加粗**和`代码`的正文。")
    if not check("摘要去掉标记符号", "#" not in plain and "**" not in plain and "`" not in plain, plain):
        failed.append("strip_marks")
    if not check("摘要保留文字", "标题" in plain and "加粗" in plain, plain):
        failed.append("strip_text")

    long_text = "字" * 500
    truncated = strip_markdown(long_text, max_length=300)
    if not check("摘要超长被截断", len(truncated) <= 301 and truncated.endswith("…"), f"len={len(truncated)}"):
        failed.append("strip_truncate")
    return failed


def main() -> int:
    print("=" * 60)
    print("Markdown 渲染与 XSS 过滤测试")
    print("=" * 60)

    all_failed: list[str] = []
    for name, fn in [
        ("代码块", test_code_block),
        ("行内代码", test_inline_code),
        ("表格", test_table),
        ("基础格式", test_basic_formatting),
        ("XSS 防护", test_xss),
        ("白名单未误删", test_whitelist_actually_used),
        ("转义而非删除", test_xss_escaped_not_stripped),
        ("摘要提取", test_strip_markdown),
    ]:
        print(f"\n--- {name} ---")
        all_failed.extend(fn())

    print()
    print("=" * 60)
    print("FAILED:", all_failed if all_failed else "none")
    return 1 if all_failed else 0


if __name__ == "__main__":
    sys.exit(main())
