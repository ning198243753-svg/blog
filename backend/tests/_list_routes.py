"""列出全部路由，用于确认注册是否完整（开发期工具，非测试）"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402

rows = []
for r in app.routes:
    methods = getattr(r, "methods", None)
    if not methods:
        continue
    keep = sorted(methods - {"HEAD", "OPTIONS"})
    rows.append((",".join(keep), r.path))

for methods, path in sorted(rows, key=lambda x: x[1]):
    print(f"{methods:8} {path}")

print()
print(f"共 {len(rows)} 条路由")
