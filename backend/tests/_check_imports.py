"""找出未使用的导入与明显的代码问题（开发期检查工具）

为什么不用 ruff：项目 venv 里没装，而为了一个检查装一个 linter
对学习期项目来说收益不明。这个脚本用标准库 ast 做最基本的检查 ——
它发现的正是最容易出现的疏漏：**重构后忘了删的导入**。

这类问题的危害不在于多占内存，而在于「读者以为它被用到了」，
下次改动时会因为「import 还在，应该有关系」而判断失误。
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

problems: list[str] = []


def check_file(path: Path) -> None:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        problems.append(f"{path.relative_to(ROOT)}:{exc.lineno} 语法错误：{exc.msg}")
        return

    imported: dict[str, int] = {}
    lines = source.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = (alias.asname or alias.name).split(".")[0]
                imported[name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                name = alias.asname or alias.name
                imported[name] = node.lineno

    if not imported:
        return

    # 带 noqa 标记的行跳过。
    #
    # 这不是为了"让检查通过"，而是这类导入确实有正当用途：
    # 例如 alembic/env.py 的 `import app.models  # noqa: F401` ——
    # 它靠「被导入时把模型注册到 Base.metadata」产生副作用，
    # 名字本身永远不被引用，但删掉它迁移就会看不到任何表。
    # 检查工具无法识别这种意图，所以尊重显式标注。
    noqa_lines = {
        i + 1 for i, line in enumerate(lines) if "noqa" in line.lower()
    }

    # 收集文件里出现的所有名字（不只是 Name 节点，
    # 因为导入也可能被用在类型注解字符串、装饰器、
    # __all__ 列表里）
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            # 字符串形式的类型注解、__all__ 里的条目
            used.add(node.value)
            # "list[Foo]" 这种注解要拆开看
            for token in node.value.replace("[", " ").replace("]", " ").replace(
                ",", " "
            ).split():
                used.add(token)

    for name, lineno in imported.items():
        if lineno in noqa_lines:
            continue
        if name not in used and name != "annotations":
            problems.append(
                f"{path.relative_to(ROOT)}:{lineno} 未使用的导入：{name}"
            )


files = sorted(
    p for p in ROOT.rglob("*.py")
    if ".venv" not in p.parts and "__pycache__" not in p.parts
)

print(f"检查了 {len(files)} 个 Python 文件")
print()

for path in files:
    check_file(path)

if problems:
    print(f"发现 {len(problems)} 个问题：")
    for p in problems:
        print(f"  {p}")
    sys.exit(1)

print("[OK] 没有发现未使用的导入或语法错误")
