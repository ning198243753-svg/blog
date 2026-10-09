"""M3 文章 CRUD 端到端验证（5 个接口）

【这个测试会执行 DELETE，所以它连的必须是测试库】

M1 期间发生过两次事故：测试脚本直接对着开发库跑 DELETE，
把 26 篇文章和 1 个管理员清空了，而报错信息只显示「列表为空」，
完全看不出是数据没了。本文件因此有三重保护：

1. 启动时调用 assert_not_dev_db()，连的是开发库就直接退出
2. 结尾打印实际连接的数据库文件路径，让「连了哪个库」始终可见
3. 在测试库上跑，不碰开发数据

另外这个测试不只验证「能写成功」，还验证**写失败时不留脏数据**：
M3 全是写操作，其中删除不可逆，所以「失败路径」比 M1/M2 更需要覆盖。
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

assert_not_dev_db("test_article_crud.py")

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
    """对 URL 路径里的数据段做百分号编码，保留 / 和查询串

    【为什么必须做这件事】
    中文 slug 不能让 urllib 直接拼进 URL。http.client 在发送请求行时
    用 ASCII 编码，遇到中文会抛：
        UnicodeEncodeError: 'ascii' codec can't encode characters
    这个报错发生在 build_opener().open() 内部，堆栈里全是 http.client
    的代码，看不出是「slug 里有中文」导致的。

    浏览器和 Axios 会自动做这一步，所以前端不会有这个问题 ——
    只有手写请求的测试脚本需要自己处理。

    【必须先切掉查询串】
    第一版写成「先按 / 切分，再逐段 quote(safe="")」，结果是
    "/articles?page_size=50" 被编码成 "/articles%3Fpage_size%3D50" ——
    ? 和 = 都被吃掉了。请求打到一个不存在的路径上，服务端返回 404，
    响应体是 {"code":40400,"data":null}，于是测试报
        TypeError: 'NoneType' object is not subscriptable
    完全看不出真正的原因是「问号被编码了」。

    正确顺序：先分离 ? 之后的查询串（它本来就已经是编码过的），
    只对路径部分逐段编码。
    """
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
            return exc.code, {"_raw": raw[:200]}


def db_count(sql: str, args: tuple = ()) -> int:
    conn = sqlite3.connect(str(TEST_DB_PATH))
    try:
        return conn.execute(sql, args).fetchone()[0]
    finally:
        conn.close()


print("=" * 66)
print("M3 文章 CRUD 验证")
print(f"目标数据库：{TEST_DB_PATH}")
print("=" * 66)

if not TEST_DB_PATH.exists():
    print(f"[终止] 测试库不存在。请用 run_tests.py --with-api 运行。")
    sys.exit(2)

# ---------- 0. 登录 ----------
print("\n--- 前置：登录 ---")
status, body = call("POST", "/auth/login",
                    {"username": settings.admin_username, "password": settings.admin_password})
check("登录成功", status == 200 and body.get("code") == 0, f"status={status}")
if status != 200:
    print("[终止] 无法登录，后续测试无意义")
    sys.exit(1)

# ---------- 1. 未登录时后台接口必须全部拒绝 ----------
print("\n--- 未登录访问后台（权限边界）---")
anon = urllib.request.build_opener()  # 不带 Cookie


def anon_call(method: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with anon.open(req, timeout=15) as resp:
            return resp.status
    except urllib.error.HTTPError as exc:
        return exc.code


check("未登录 GET /admin/articles → 401", anon_call("GET", "/admin/articles") == 401)
check("未登录 POST /admin/articles → 401", anon_call("POST", "/admin/articles", {}) == 401)
check("未登录 PUT /admin/articles/1 → 401", anon_call("PUT", "/admin/articles/1", {}) == 401)
check("未登录 DELETE /admin/articles/1 → 401", anon_call("DELETE", "/admin/articles/1") == 401)
check("未登录 GET /admin/articles/1 → 401", anon_call("GET", "/admin/articles/1") == 401)

# ---------- 2. 后台列表含草稿 ----------
print("\n--- 后台列表（含草稿）---")
status, pub = call("GET", "/articles?page_size=50")
published_total = pub["data"]["total"]

status, admin_list = call("GET", "/admin/articles?page_size=50")
check("后台列表返回 200", status == 200, f"status={status}")
admin_total = admin_list["data"]["total"]
check("后台列表包含草稿（数量多于公开列表）", admin_total > published_total,
      f"后台={admin_total} 公开={published_total}")

status, drafts = call("GET", "/admin/articles?status=draft&page_size=50")
check("可按 status=draft 过滤", status == 200 and drafts["data"]["total"] > 0,
      f"草稿={drafts['data']['total']}")
check("过滤结果确实都是草稿",
      all(a["status"] == "draft" for a in drafts["data"]["items"]),
      f"检查了 {len(drafts['data']['items'])} 篇")

status, pub_only = call("GET", "/admin/articles?status=published&page_size=50")
check("可按 status=published 过滤",
      all(a["status"] == "published" for a in pub_only["data"]["items"]),
      f"共 {pub_only['data']['total']} 篇")

check("后台列表不含 content_html（省带宽）",
      "content_html" not in json.dumps(admin_list["data"]["items"][:1]),
      f"字段={sorted(admin_list['data']['items'][0].keys())}")

status, bad = call("GET", "/admin/articles?status=nonsense")
check("非法 status 值被拒（422）", status == 422, f"status={status}")

# ---------- 3. 新建草稿 ----------
print("\n--- 新建文章 ---")
before_total = admin_total

status, created = call("POST", "/admin/articles", {
    "title": "M3 测试文章：验证 CRUD",
    "content_md": "# 标题\n\n这是**测试**内容。\n\n```python\nprint('hi')\n```\n",
    "status": "draft",
})
check("新建草稿返回 200", status == 200, f"status={status} body={str(created)[:120]}")
check("返回新文章 id", isinstance(created.get("data", {}).get("id"), int),
      str(created.get("data")))
new_id = created["data"]["id"]

status, after = call("GET", "/admin/articles?page_size=50")
check("新建后总数 +1", after["data"]["total"] == before_total + 1,
      f"{before_total} → {after['data']['total']}")

# 详情：带 content_md 与 content_html
status, detail = call("GET", f"/admin/articles/{new_id}")
check("后台详情返回 200", status == 200, f"status={status}")
d = detail["data"]
check("详情含 content_md（编辑必需）", "content_md" in d and d["content_md"],
      d.get("content_md", "")[:30])
check("详情含 content_html", bool(d.get("content_html")), d.get("content_html", "")[:40])
check("Markdown 已渲染成 HTML（含 <strong>）", "<strong>" in d["content_html"],
      d["content_html"][:80])
check("围栏代码渲染成 <pre>", "<pre>" in d["content_html"])
check("草稿的 published_at 为 null", d["published_at"] is None, str(d["published_at"]))
check("slug 由标题生成", bool(d["slug"]), d["slug"])
check("摘要自动从正文提取", bool(d["summary"]), d["summary"][:40])

# 草稿不对访客可见
status, _ = call("GET", f"/articles/{d['slug']}")
check("草稿在公开接口返回 404", status == 404, f"status={status}")

# ---------- 4. 更新 ----------
print("\n--- 更新文章 ---")
status, upd = call("PUT", f"/admin/articles/{new_id}", {"title": "M3 测试文章：已改名"})
check("只改标题返回 200", status == 200, f"status={status}")

status, d2 = call("GET", f"/admin/articles/{new_id}")
check("标题已更新", d2["data"]["title"] == "M3 测试文章：已改名", d2["data"]["title"])
check("【关键】只改标题时正文没有被清空",
      d2["data"]["content_md"] == d["content_md"],
      f"正文长度 {len(d['content_md'])} → {len(d2['data']['content_md'])}")
check("slug 保持不变（改标题不改链接）",
      d2["data"]["slug"] == d["slug"],
      f"{d['slug']} → {d2['data']['slug']}")

# 改正文 → content_html 必须跟着变
status, _ = call("PUT", f"/admin/articles/{new_id}", {
    "content_md": "## 新正文\n\n这里有一个[链接](https://example.com)。\n"
})
status, d3 = call("GET", f"/admin/articles/{new_id}")
check("改正文后 content_html 同步重渲染",
      "<h2>" in d3["data"]["content_html"] and "新正文" in d3["data"]["content_html"],
      d3["data"]["content_html"][:60])
check("链接被保留", 'href="https://example.com"' in d3["data"]["content_html"])

# XSS 防护：在写接口也要生效
status, _ = call("PUT", f"/admin/articles/{new_id}", {
    "content_md": "正文\n\n<script>alert('xss')</script>\n\n<img src=x onerror=alert(1)>\n"
})
status, d4 = call("GET", f"/admin/articles/{new_id}")
html = d4["data"]["content_html"]

# 【这里的断言方式很重要，值得说清楚】
#
# 第一版写的是 `"onerror" not in html`，结果是失败的 —— 但代码其实是对的。
# 原因：markdown-it 的 html=False 会把源码里的原始 HTML 整体转义成文本，
# 于是 content_html 里出现的是：
#     &lt;img src=x onerror=alert(1)&gt;
# 也就是页面上显示 "img src=x onerror=alert(1)" 这几个字。
# 那是**纯文本**，浏览器不会把它当标签解析，也就不会执行 —— 安全。
#
# 但字符串搜索分不清这两种情况：
#     <img onerror=...>            ← 危险：真属性，会执行
#     &lt;img onerror=...&gt;    ← 安全：只是文本
# 两者都含 "onerror" 这个词。
#
# 所以正确的断言是用 HTML 解析器判断「它是不是一个真实存在的属性」，
# 而不是在字符串里找关键词。这与 M1 的 markdown 测试是同一个原则：
# 判断标签要用解析器，不要用字符串搜索。

from html.parser import HTMLParser  # noqa: E402


class DangerousTagFinder(HTMLParser):
    """收集所有真实存在的危险标签与事件属性

    HTMLParser 只识别真正的标签结构：被转义的 &lt;img&gt; 不会被解析成
    标签，因此这里收集到的每一项都是浏览器真的会解析执行的东西。
    """

    DANGEROUS_TAGS = {"script", "iframe", "object", "embed", "form", "style"}

    def __init__(self) -> None:
        super().__init__()
        self.dangerous_tags: list[str] = []
        self.event_attrs: list[tuple[str, str]] = []
        self.js_urls: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        self._inspect(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._inspect(tag, attrs)

    def _inspect(self, tag, attrs):
        if tag in self.DANGEROUS_TAGS:
            self.dangerous_tags.append(tag)
        for name, value in attrs:
            # on* 是事件处理器属性，浏览器会执行它的值
            if name.lower().startswith("on"):
                self.event_attrs.append((tag, name))
            if name.lower() in ("href", "src") and value:
                if value.strip().lower().startswith(("javascript:", "data:")):
                    self.js_urls.append((tag, value[:40]))


finder = DangerousTagFinder()
finder.feed(html)

check("写入时无危险标签（script/iframe 等）", not finder.dangerous_tags,
      f"发现 {finder.dangerous_tags}" if finder.dangerous_tags else "解析器判定 0 个")
check("写入时无事件属性（onerror/onclick 等）", not finder.event_attrs,
      f"发现 {finder.event_attrs}" if finder.event_attrs else "解析器判定 0 个")
check("写入时无 javascript:/data: 协议链接", not finder.js_urls,
      f"发现 {finder.js_urls}" if finder.js_urls else "解析器判定 0 个")

# 反过来说明：危险内容仍然以「文本形式」可见，而不是被悄悄删掉
# （strip=True 删除标签本身，文本保留 —— 这样作者能看到自己写了什么）
check("危险内容以转义文本形式保留（可读、不可执行）",
      "onerror" in html and "&lt;img" in html,
      "页面上会显示这几个字，但不会被解析成标签")

# 发布
status, _ = call("PUT", f"/admin/articles/{new_id}", {"status": "published"})
status, d5 = call("GET", f"/admin/articles/{new_id}")
check("发布后 status 为 published", d5["data"]["status"] == "published", d5["data"]["status"])
check("发布后写入 published_at", d5["data"]["published_at"] is not None,
      str(d5["data"]["published_at"]))
check("published_at 带 Z 后缀", str(d5["data"]["published_at"]).endswith("Z"),
      str(d5["data"]["published_at"]))
first_published_at = d5["data"]["published_at"]

# 发布后访客可见
status, _ = call("GET", f"/articles/{d5['data']['slug']}")
check("发布后公开接口可访问", status == 200, f"status={status}")

# 转回草稿：published_at 应保留
status, _ = call("PUT", f"/admin/articles/{new_id}", {"status": "draft"})
status, d6 = call("GET", f"/admin/articles/{new_id}")
check("转回草稿后 published_at 被保留（不清空）",
      d6["data"]["published_at"] == first_published_at,
      f"{first_published_at} → {d6['data']['published_at']}")

# 再发布：时间不变（不跳到列表最前）
call("PUT", f"/admin/articles/{new_id}", {"status": "published"})
status, d7 = call("GET", f"/admin/articles/{new_id}")
check("重新发布不改变 published_at（不会跳到列表最前）",
      d7["data"]["published_at"] == first_published_at,
      f"{first_published_at} → {d7['data']['published_at']}")

# ---------- 5. 标签关联 ----------
print("\n--- 标签关联 ---")
status, tags_resp = call("GET", "/tags")
all_tags = tags_resp["data"]
if len(all_tags) >= 2:
    t1, t2 = all_tags[0]["id"], all_tags[1]["id"]
    status, _ = call("PUT", f"/admin/articles/{new_id}", {"tag_ids": [t1, t2]})
    status, dt = call("GET", f"/admin/articles/{new_id}")
    check("标签已关联", len(dt["data"]["tags"]) == 2,
          str([t["name"] for t in dt["data"]["tags"]]))
    check("标签顺序/内容正确",
          {t["id"] for t in dt["data"]["tags"]} == {t1, t2})

    # 传 [] 表示清空
    call("PUT", f"/admin/articles/{new_id}", {"tag_ids": []})
    status, dt2 = call("GET", f"/admin/articles/{new_id}")
    check("传空数组清空标签", len(dt2["data"]["tags"]) == 0,
          str([t["name"] for t in dt2["data"]["tags"]]))

    # 不传 tag_ids 表示不改
    call("PUT", f"/admin/articles/{new_id}", {"tag_ids": [t1]})
    call("PUT", f"/admin/articles/{new_id}", {"title": "只改标题"})
    status, dt3 = call("GET", f"/admin/articles/{new_id}")
    check("不传 tag_ids 时标签保持不变", len(dt3["data"]["tags"]) == 1,
          str([t["name"] for t in dt3["data"]["tags"]]))

    # 不存在的标签 id
    status, err = call("PUT", f"/admin/articles/{new_id}", {"tag_ids": [999999]})
    check("不存在的标签 id 被拒", status == 400, f"status={status} code={err.get('code')}")
    check("错误信息里指出了缺失的 id", "999999" in str(err.get("message")),
          str(err.get("message")))

    # 重复 id 应去重
    call("PUT", f"/admin/articles/{new_id}", {"tag_ids": [t1, t1, t1]})
    status, dt4 = call("GET", f"/admin/articles/{new_id}")
    check("重复标签 id 被去重", len(dt4["data"]["tags"]) == 1,
          f"{len(dt4['data']['tags'])} 个标签")

# ---------- 6. slug 冲突 ----------
print("\n--- slug 冲突处理 ---")
status, a1 = call("POST", "/admin/articles",
                  {"title": "重复标题测试", "content_md": "一", "status": "draft"})
status, a2 = call("POST", "/admin/articles",
                  {"title": "重复标题测试", "content_md": "二", "status": "draft"})
id1, id2 = a1["data"]["id"], a2["data"]["id"]
status, s1 = call("GET", f"/admin/articles/{id1}")
status, s2 = call("GET", f"/admin/articles/{id2}")
check("标题重复时第二个自动加后缀", s1["data"]["slug"] != s2["data"]["slug"],
      f"{s1['data']['slug']} vs {s2['data']['slug']}")
check("后缀形式为 -2", s2["data"]["slug"].endswith("-2"), s2["data"]["slug"])

# 显式指定重复 slug 也应被去重
status, a3 = call("POST", "/admin/articles",
                  {"title": "指定 slug 测试", "slug": "my-custom-slug",
                   "content_md": "x", "status": "draft"})
status, a4 = call("POST", "/admin/articles",
                  {"title": "另一个标题", "slug": "my-custom-slug",
                   "content_md": "y", "status": "draft"})
status, s3 = call("GET", f"/admin/articles/{a3['data']['id']}")
status, s4 = call("GET", f"/admin/articles/{a4['data']['id']}")
check("显式指定的重复 slug 也被去重", s3["data"]["slug"] != s4["data"]["slug"],
      f"{s3['data']['slug']} vs {s4['data']['slug']}")

# ---------- 7. 参数校验 ----------
print("\n--- 参数校验（失败路径）---")
status, err = call("POST", "/admin/articles", {"title": "", "content_md": "x"})
check("空标题被拒（422）", status == 422, f"status={status}")

status, err = call("POST", "/admin/articles", {"title": "只有标题"})
check("缺 content_md 被拒（422）", status == 422, f"status={status}")

status, err = call("POST", "/admin/articles",
                   {"title": "x" * 200, "content_md": "y"})
check("超长标题被拒（422）", status == 422, f"status={status}")

status, err = call("POST", "/admin/articles",
                   {"title": "状态非法", "content_md": "x", "status": "whatever"})
check("非法 status 被拒（422）", status == 422, f"status={status}")

status, err = call("PUT", "/admin/articles/99999999", {"title": "不存在"})
check("更新不存在的文章返回 404", status == 404, f"status={status}")
check("404 业务码为 40400", err.get("code") == 40400, f"code={err.get('code')}")

status, err = call("DELETE", "/admin/articles/99999999")
check("删除不存在的文章返回 404", status == 404, f"status={status}")

status, err = call("GET", "/admin/articles/99999999")
check("查询不存在的文章返回 404", status == 404, f"status={status}")

# ---------- 8. 删除与级联 ----------
print("\n--- 删除 ---")
status, _ = call("PUT", f"/admin/articles/{new_id}", {"tag_ids": [all_tags[0]["id"]]})
links_before = db_count(
    "SELECT COUNT(*) FROM article_tags WHERE article_id = ?", (new_id,)
)
check("删除前存在标签关联行", links_before > 0, f"{links_before} 行")

before_del_total = call("GET", "/admin/articles?page_size=50")[1]["data"]["total"]
status, _ = call("DELETE", f"/admin/articles/{new_id}")
check("删除返回 200", status == 200, f"status={status}")

after_del_total = call("GET", "/admin/articles?page_size=50")[1]["data"]["total"]
check("删除后总数 -1", after_del_total == before_del_total - 1,
      f"{before_del_total} → {after_del_total}")

status, _ = call("GET", f"/admin/articles/{new_id}")
check("删除后详情返回 404", status == 404, f"status={status}")

# 【关键】外键 CASCADE 必须清掉关联行，否则会留下孤儿数据
# 孤儿行不会报错，但会让标签的文章计数虚高 —— 静默的脏数据
links_after = db_count(
    "SELECT COUNT(*) FROM article_tags WHERE article_id = ?", (new_id,)
)
check("【关键】删除文章后关联行被 CASCADE 清掉", links_after == 0,
      f"残留 {links_after} 行")

# 标签本身不能被删掉（只是关联没了）
status, tags_after = call("GET", "/tags")
check("删除文章不影响标签本身", len(tags_after["data"]) == len(all_tags),
      f"{len(all_tags)} → {len(tags_after['data'])}")

# 清理其余测试文章
for aid in (id1, id2, a3["data"]["id"], a4["data"]["id"]):
    call("DELETE", f"/admin/articles/{aid}")

# ---------- 9. 数据一致性收尾 ----------
print("\n--- 收尾：确认没有留下脏数据 ---")
orphans = db_count(
    "SELECT COUNT(*) FROM article_tags WHERE article_id NOT IN (SELECT id FROM articles)"
)
check("没有孤儿关联行", orphans == 0, f"{orphans} 行")

drafts_left = db_count("SELECT COUNT(*) FROM articles WHERE title LIKE 'M3 测试文章%'")
check("测试文章已清理干净", drafts_left == 0, f"残留 {drafts_left} 篇")

print()
print("=" * 66)
print(f"通过 {passed} 项，失败 {len(failed)} 项")
if failed:
    print("失败清单：")
    for name in failed:
        print(f"  - {name}")
print("=" * 66)

sys.exit(1 if failed else 0)
