"""分层验证：bleach 白名单到底有没有在做事？

做法：对同一批危险载荷，分别用「开启 bleach」和「关闭 bleach」渲染，
比较结果差异。如果两者完全相同，说明 bleach 是多余的。

这不是正式测试，是一次性的验证脚本 —— 结论会写进注释和文档，
脚本本身保留下来以便将来换库时重跑。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import bleach  # noqa: E402
import markdown_it  # noqa: E402

from app.utils.markdown import ALLOWED_ATTRIBUTES, ALLOWED_PROTOCOLS, ALLOWED_TAGS  # noqa: E402

md = markdown_it.MarkdownIt("gfm-like", {"html": False, "typographer": False})

PAYLOADS = [
    ("<script>alert(1)</script>", "script 标签"),
    ("[x](javascript:alert(1))", "js 协议链接"),
    ("<img src=x onerror=alert(1)>", "img onerror"),
    ("![x](javascript:alert(1))", "图片 js 协议"),
    ("[x](data:text/html,<script>alert(1)</script>)", "data 协议"),
    ("<iframe src='//evil.com'></iframe>", "iframe"),
    ("[正常链接](https://example.com)", "安全外链"),
    ("```python\nprint(1)\n```", "代码块"),
]

print(f"{'载荷':<24} {'仅 markdown_it':<44} {'再加 bleach':<44} 是否不同")
print("-" * 130)

diff_count = 0
for payload, label in PAYLOADS:
    layer1 = md.render(payload).replace("\n", " ").strip()
    layer2 = bleach.clean(
        layer1,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True,
    ).replace("\n", " ").strip()

    different = layer1 != layer2
    if different:
        diff_count += 1
    print(f"{label:<24} {layer1[:42]:<44} {layer2[:42]:<44} {'是' if different else '否'}")

print()
print(f"两层的差异数量：{diff_count} / {len(PAYLOADS)}")
print()
if diff_count == 0:
    print("结论：bleach 没有改变任何输出 —— 它在这个配置下是多余的。")
else:
    print("结论：bleach 确实改变了输出，需要逐条判断这些改变是「增强安全」还是「破坏功能」。")
