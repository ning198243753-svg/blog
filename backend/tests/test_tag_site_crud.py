"""M3 标签与站点配置端到端验证（7 个接口）

会执行 DELETE，因此必须跑在测试库上（assert_not_dev_db 保护）。

本文件重点验证删除标签的「破坏性」是否被正确拦下 ——
这是 M3 里唯一一个「一个请求可能影响多篇其它数据」的操作。
"""

import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests._env import TEST_DB_PATH, assert_not_dev_db  # noqa: E402

assert_not_dev_db("test_tag_site_crud.py")

from app.config import settings  # noqa: E402

BASE = "http://127.0.0.1:8000/api"
failed = []
passed = 0

jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
    else:
        failed.append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def quote_path(path: str) -> str:
    """先分离查询串，再对路径逐段编码（见 test_article_crud.py 的详细说明）"""
    path_only, sep, query = path.partition("?")
    parts = path_only.split("/")
    encoded = "/".join(urllib.parse.quote(p, safe="") if p else p for p in parts)
    return f"{encoded}?{query}" if sep else encoded


def call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + quote_path(path),
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with opener.open(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw[:300]}


def db_one(sql: str, args: tuple = ()):
    conn = sqlite3.connect(str(TEST_DB_PATH))
    try:
        return conn.execute(sql, args).fetchone()
    finally:
        conn.close()


print("=" * 66)
print("M3 标签与站点配置验证")
print(f"目标数据库：{TEST_DB_PATH}")
print("=" * 66)

if not TEST_DB_PATH.exists():
    print("[终止] 测试库不存在。请用 run_tests.py --with-api 运行。")
    sys.exit(2)

status, body = call("POST", "/auth/login",
                    {"username": settings.admin_username, "password": settings.admin_password})
if status != 200:
    print(f"[终止] 登录失败：{body}")
    sys.exit(1)
print("\n[OK] 已登录")

# ==================================================================
print("\n--- 权限边界 ---")
# ==================================================================
anon = urllib.request.build_opener()


def anon_status(method: str, path: str, body: dict | None = None) -> int:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + quote_path(path), data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with anon.open(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


for method, path in (
    ("GET", "/admin/tags"),
    ("POST", "/admin/tags"),
    ("PUT", "/admin/tags/1"),
    ("DELETE", "/admin/tags/1"),
    ("GET", "/admin/tags/1/usage"),
    ("GET", "/admin/site"),
    ("PUT", "/admin/site"),
):
    check(f"未登录 {method} {path} → 401", anon_status(method, path, {} if method in ("POST", "PUT") else None) == 401)

# ==================================================================
print("\n--- 后台标签列表 ---")
# ==================================================================
status, admin_tags = call("GET", "/admin/tags")
check("后台标签列表返回 200", status == 200, f"status={status}")
check("返回标签数组", isinstance(admin_tags["data"], list), f"{len(admin_tags.get('data') or [])} 个")
check("每个标签带 article_count",
      all("article_count" in t for t in admin_tags["data"]))

# 后台计数含草稿，公开接口只数已发布 —— 两者的差就是草稿的标签使用量
status, public_tags = call("GET", "/tags")
admin_counts = {t["id"]: t["article_count"] for t in admin_tags["data"]}
public_counts = {t["id"]: t["article_count"] for t in public_tags["data"]}

check("后台计数 >= 公开计数（后台含草稿）",
      all(admin_counts.get(i, 0) >= public_counts.get(i, 0) for i in public_counts),
      f"后台 {sum(admin_counts.values())} vs 公开 {sum(public_counts.values())} 关联数")

# ==================================================================
print("\n--- 新建标签 ---")
# ==================================================================
status, created = call("POST", "/admin/tags", {"name": "M3测试标签"})
check("新建标签返回 200", status == 200, f"status={status} {str(created)[:80]}")
new_tag_id = created["data"]["id"]

status, t_after = call("GET", "/admin/tags")
check("新建后标签数 +1",
      len(t_after["data"]) == len(admin_tags["data"]) + 1,
      f"{len(admin_tags['data'])} → {len(t_after['data'])}")

new_tag = next(t for t in t_after["data"] if t["id"] == new_tag_id)
check("slug 由标签名生成", bool(new_tag["slug"]), new_tag["slug"])
check("新标签文章数为 0", new_tag["article_count"] == 0, str(new_tag["article_count"]))

# 重名
status, err = call("POST", "/admin/tags", {"name": "M3测试标签"})
check("重名标签被拒（409）", status == 409, f"status={status}")
check("重名业务码为 40003", err.get("code") == 40003, f"code={err.get('code')}")

# 前后空格应视为同名
status, err = call("POST", "/admin/tags", {"name": "  M3测试标签  "})
check("前后空格的同名标签被拒", status == 409, f"status={status}")

# 空名
status, err = call("POST", "/admin/tags", {"name": "   "})
check("纯空白标签名被拒", status in (400, 422), f"status={status} code={err.get('code')}")

status, err = call("POST", "/admin/tags", {"name": ""})
check("空标签名被拒（422）", status == 422, f"status={status}")

status, err = call("POST", "/admin/tags", {"name": "x" * 50})
check("超长标签名被拒（422）", status == 422, f"status={status}")

# 非法颜色
status, err = call("POST", "/admin/tags", {"name": "颜色测试", "color": "red"})
check("非法颜色格式被拒（422）", status == 422, f"status={status}")

status, ok_color = call("POST", "/admin/tags", {"name": "颜色测试", "color": "#1e5cb8"})
check("合法十六进制颜色被接受", status == 200, f"status={status}")
color_tag_id = ok_color["data"]["id"]

# 中文标签名 → 中文 slug（ADR-07 的同一个取舍）
status, tags_now = call("GET", "/admin/tags")
color_tag = next(t for t in tags_now["data"] if t["id"] == color_tag_id)
check("中文标签名生成中文 slug", color_tag["slug"] == "颜色测试", color_tag["slug"])

# ==================================================================
print("\n--- 更新标签 ---")
# ==================================================================
status, _ = call("PUT", f"/admin/tags/{new_tag_id}", {"name": "M3测试标签已改名"})
check("更新标签返回 200", status == 200, f"status={status}")

status, tags_now = call("GET", "/admin/tags")
renamed = next(t for t in tags_now["data"] if t["id"] == new_tag_id)
check("标签名已更新", renamed["name"] == "M3测试标签已改名", renamed["name"])
check("【关键】改标签名不改 slug（旧链接不失效）",
      renamed["slug"] == new_tag["slug"],
      f"{new_tag['slug']} → {renamed['slug']}")

# 改成一个已存在的名字
existing_name = next(t["name"] for t in tags_now["data"] if t["id"] != new_tag_id)
status, err = call("PUT", f"/admin/tags/{new_tag_id}", {"name": existing_name})
check("改成已存在的标签名被拒（409）", status == 409, f"status={status}")

# 改成自己原来的名字不应报冲突
status, _ = call("PUT", f"/admin/tags/{new_tag_id}", {"name": "M3测试标签已改名"})
check("改成自己原有的名字不报冲突（查重排除自己）", status == 200, f"status={status}")

status, err = call("PUT", "/admin/tags/99999999", {"name": "不存在"})
check("更新不存在的标签返回 404", status == 404, f"status={status}")

# ==================================================================
print("\n--- 标签使用量查询（删除前预览）---")
# ==================================================================
status, usage = call("GET", f"/admin/tags/{new_tag_id}/usage")
check("查询使用量返回 200", status == 200, f"status={status}")
check("使用量含 article_count 与 published_count",
      "article_count" in usage["data"] and "published_count" in usage["data"],
      str(usage["data"]))
check("新标签使用量为 0", usage["data"]["article_count"] == 0, str(usage["data"]))

status, err = call("GET", "/admin/tags/99999999/usage")
check("查询不存在标签的使用量返回 404", status == 404, f"status={status}")

# ==================================================================
print("\n--- 删除标签的保护与级联 ---")
# ==================================================================

# 造一篇草稿并挂上标签
status, art = call("POST", "/admin/articles", {
    "title": "标签删除影响测试", "content_md": "正文",
    "status": "draft", "tag_ids": [new_tag_id],
})
article_id = art["data"]["id"]

status, usage2 = call("GET", f"/admin/tags/{new_tag_id}/usage")
check("关联后使用量变为 1", usage2["data"]["article_count"] == 1, str(usage2["data"]))
check("草稿不计入 published_count",
      usage2["data"]["published_count"] == 0,
      f"article_count={usage2['data']['article_count']} published={usage2['data']['published_count']}")

# 【核心】不带 force 删除必须被拒绝
status, err = call("DELETE", f"/admin/tags/{new_tag_id}")
check("【核心】标签仍在使用时默认拒绝删除（409）",
      status == 409, f"status={status}")
check("拒绝时业务码为 40006", err.get("code") == 40006, f"code={err.get('code')}")
check("拒绝时提示里给出了受影响文章数",
      "1" in str(err.get("message")),
      str(err.get("message"))[:80])

# 确认这次拒绝确实没有删掉东西
status, still_there = call("GET", f"/admin/tags/{new_tag_id}/usage")
check("被拒绝后标签依然存在", status == 200, f"status={status}")

# 带上 force 后成功
links_before = db_one(
    "SELECT COUNT(*) FROM article_tags WHERE tag_id = ?", (new_tag_id,)
)[0]
check("删除前存在关联行", links_before == 1, f"{links_before} 行")

status, del_result = call("DELETE", f"/admin/tags/{new_tag_id}?force=true")
check("带 force=true 后删除成功", status == 200, f"status={status} {str(del_result)[:80]}")
check("返回受影响文章数", del_result["data"]["affected_articles"] == 1,
      str(del_result["data"]))

# 【关键】CASCADE 必须清掉关联行
links_after = db_one(
    "SELECT COUNT(*) FROM article_tags WHERE tag_id = ?", (new_tag_id,)
)[0]
check("【关键】删除标签后关联行被 CASCADE 清掉", links_after == 0, f"残留 {links_after} 行")

# 文章本身必须还在
status, art_after = call("GET", f"/admin/articles/{article_id}")
check("【关键】删除标签不影响文章本身", status == 200, f"status={status}")
check("文章的标签已被摘掉", len(art_after["data"]["tags"]) == 0,
      str([t["name"] for t in art_after["data"]["tags"]]))

# 使用量查询对已删除标签返回 404
status, _ = call("GET", f"/admin/tags/{new_tag_id}/usage")
check("已删除标签的使用量查询返回 404", status == 404, f"status={status}")

# 无关联的标签可以直接删（不需要 force）
status, _ = call("DELETE", f"/admin/tags/{color_tag_id}")
check("无关联标签可直接删除（无需 force）", status == 200, f"status={status}")

# 清理
call("DELETE", f"/admin/articles/{article_id}")

# ==================================================================
print("\n--- 站点配置 ---")
# ==================================================================
status, cfg = call("GET", "/admin/site")
check("读取站点配置返回 200", status == 200, f"status={status}")
check("返回 values 字典", isinstance(cfg["data"]["values"], dict),
      f"{len(cfg['data']['values'])} 项")
original = dict(cfg["data"]["values"])

# 更新
status, upd = call("PUT", "/admin/site", {"values": {"site_title": "M3 测试标题"}})
check("更新站点配置返回 200", status == 200, f"status={status}")
check("返回更新后的完整配置",
      upd["data"]["values"]["site_title"] == "M3 测试标题",
      upd["data"]["values"]["site_title"])
check("未传的配置项保持不变",
      upd["data"]["values"]["author_name"] == original["author_name"],
      upd["data"]["values"]["author_name"])

# 公开接口应立刻反映
status, pub_cfg = call("GET", "/site")
check("公开站点接口同步更新",
      pub_cfg["data"]["values"]["site_title"] == "M3 测试标题",
      pub_cfg["data"]["values"]["site_title"])

# 未知键必须被拒
status, err = call("PUT", "/admin/site", {"values": {"author_nmae": "打错字了"}})
check("未知配置项被拒（400）", status == 400, f"status={status}")
check("提示里列出可用配置项",
      "author_name" in str(err.get("message")),
      str(err.get("message"))[:90])

# 数据库里不应该多出那行
row = db_one("SELECT COUNT(*) FROM site_config WHERE key = 'author_nmae'")
check("【关键】未知键没有写进数据库", row[0] == 0, f"存在 {row[0]} 行")

# 数字校验
status, err = call("PUT", "/admin/site", {"values": {"articles_per_page": "abc"}})
check("非数字的 articles_per_page 被拒", status == 400, f"status={status}")

status, err = call("PUT", "/admin/site", {"values": {"articles_per_page": "0"}})
check("articles_per_page=0 被拒（会导致除零）", status == 400, f"status={status}")

status, err = call("PUT", "/admin/site", {"values": {"articles_per_page": "999"}})
check("articles_per_page=999 被拒（超出 1-50）", status == 400, f"status={status}")

status, ok_page = call("PUT", "/admin/site", {"values": {"articles_per_page": "20"}})
check("合法的 articles_per_page 被接受", status == 200, f"status={status}")

# 空 values
status, err = call("PUT", "/admin/site", {"values": {}})
check("空的 values 被拒（422）", status == 422, f"status={status}")

# 非字符串的值
status, err = call("PUT", "/admin/site", {"values": {"site_title": 123}})
check("非字符串的配置值被拒（422）", status == 422, f"status={status}")

# 恢复原配置
call("PUT", "/admin/site", {
    "values": {
        "site_title": original["site_title"],
        "articles_per_page": original["articles_per_page"],
    }
})
status, restored = call("GET", "/admin/site")
check("配置已恢复原值",
      restored["data"]["values"]["site_title"] == original["site_title"],
      restored["data"]["values"]["site_title"])

print()
print("=" * 66)
print(f"通过 {passed} 项，失败 {len(failed)} 项")
if failed:
    print("失败清单：")
    for name in failed:
        print(f"  - {name}")
print("=" * 66)

sys.exit(1 if failed else 0)
