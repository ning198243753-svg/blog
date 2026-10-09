"""M1 端到端接口验证

为什么不能只写单元测试：
单元测试直接调服务层函数，绕过了路由层、响应模型、异常处理器、
统一响应体包装 —— 而这几层才是最容易出错的地方（字段名拼错、
状态码错、异常被吞）。这里全部走真实 HTTP。

检查的不只是「200 有没有返回」，还包括：
- 统一响应体的形状（code/message/data 三件套必须在）
- 业务错误码是否与文档 05 一致
- 草稿是否真的对访客不可见
- 分页元信息是否自洽（pages 与 total/page_size 是否对得上）
"""

import json
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000/api"

failed: list[str] = []
passed = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
    else:
        failed.append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def quote_path(path: str) -> str:
    """对 URL 中「属于数据的那一段」做百分号编码

    中文 slug 是必然要做这一步的：HTTP 请求行只允许 ASCII，
    而 slug 里是汉字。urllib 不会替你编码，Axios 和浏览器会。

    关键是不能整段路径都编码 —— 那样 '/' 会变成 '%2F'，
    服务器就匹配不到路由了。所以按 '/' 切开，只编码各段的值，
    查询串保持原样（其中的中文同样需要编码）。
    """
    if "?" in path:
        raw_path, raw_query = path.split("?", 1)
    else:
        raw_path, raw_query = path, ""

    encoded = "/".join(urllib.parse.quote(seg, safe="") for seg in raw_path.split("/"))

    if raw_query:
        # 查询串按 k=v 逐项编码，保留 & 和 =
        parts = []
        for pair in raw_query.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                parts.append(f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}")
            else:
                parts.append(urllib.parse.quote(pair, safe=""))
        encoded += "?" + "&".join(parts)

    return encoded


def get(path: str) -> tuple[int, dict]:
    """返回 (HTTP 状态码, 解析后的响应体)"""
    url = BASE + quote_path(path)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"_raw": body}


def has_envelope(body: dict) -> bool:
    """统一响应体必须同时有 code / message / data 三个键"""
    return all(k in body for k in ("code", "message", "data"))


print("=" * 64)
print("M1 端到端接口验证")
print("=" * 64)

# ---------- 1. 健康检查 ----------
print("\n--- 健康检查 ---")
status, body = get("/health")
check("GET /api/health 返回 200", status == 200, f"status={status}")
check("响应体含统一三件套", has_envelope(body))
check("code 为 0", body.get("code") == 0, f"code={body.get('code')}")
check("数据库连通", body.get("data", {}).get("db") == "ok", str(body.get("data")))

# ---------- 2. 文章列表 ----------
print("\n--- 文章列表 ---")
status, body = get("/articles")
check("GET /api/articles 返回 200", status == 200, f"status={status}")
data = body.get("data", {})
check("含分页字段", all(k in data for k in ("items", "total", "page", "page_size", "pages")))
check("每页条数取自站点配置（10）", data.get("page_size") == 10, f"page_size={data.get('page_size')}")
check("首页返回 10 条", len(data.get("items", [])) == 10, f"实际 {len(data.get('items', []))}")
check("总数是 24 篇（不含 2 篇草稿）", data.get("total") == 24, f"total={data.get('total')}")
check("pages 与 total/page_size 自洽", data.get("pages") == 3, f"pages={data.get('pages')}")

first = data["items"][0]
check("列表项不含 content_html", "content_html" not in first, f"字段={sorted(first)}")
check("列表项不含 content_md", "content_md" not in first)
check("列表项含标签数组", isinstance(first.get("tags"), list))
check("时间带 Z 后缀", str(first.get("created_at", "")).endswith("Z"), first.get("created_at"))
check("按发布时间倒序", first["published_at"] >= data["items"][1]["published_at"],
      f"{first['published_at']} >= {data['items'][1]['published_at']}")

# ---------- 3. 分页 ----------
print("\n--- 分页 ---")
status, page2 = get("/articles?page=2")
check("第 2 页返回 200", status == 200)
check("第 2 页也是 10 条", len(page2["data"]["items"]) == 10, f"{len(page2['data']['items'])} 条")
s1 = {i["id"] for i in data["items"]}
s2 = {i["id"] for i in page2["data"]["items"]}
check("第 1、2 页无重叠", not (s1 & s2), f"重叠 {len(s1 & s2)} 条")

status, page3 = get("/articles?page=3")
check("第 3 页返回剩余 4 条", len(page3["data"]["items"]) == 4, f"{len(page3['data']['items'])} 条")

status, page9 = get("/articles?page=9")
check("超出页码返回空列表而非报错", status == 200 and page9["data"]["items"] == [], f"status={status}")

# ---------- 4. 文章详情 ----------
print("\n--- 文章详情 ---")
slug = first["slug"]
status, detail = get(f"/articles/{slug}")
check("GET /api/articles/{slug} 返回 200", status == 200)
check("详情含 content_html", "content_html" in detail.get("data", {}))
check("公开详情不含 content_md", "content_md" not in detail.get("data", {}))
check("正文渲染出 <pre>（代码块正常）", "<pre>" in detail["data"]["content_html"])
check("正文渲染出 <table>", "<table>" in detail["data"]["content_html"])

# 阅读数自增
before = detail["data"]["view_count"]
status, detail2 = get(f"/articles/{slug}")
after = detail2["data"]["view_count"]
check("阅读数自增 1", after == before + 1, f"{before} → {after}")

# ---------- 4b. 上下篇 ----------
print("\n--- 上下篇 ---")
d = detail2["data"]
check("详情含 prev 字段", "prev" in d)
check("详情含 next 字段", "next" in d)

# 首页第一条是最新文章，它不应该有「下一篇」（更新的）
latest = data["items"][0]
status, latest_detail = get(f"/articles/{latest['slug']}")
check("最新一篇没有 next", latest_detail["data"]["next"] is None,
      str(latest_detail["data"]["next"]))

# 最后一页最后一条是最旧文章，它不应该有「上一篇」（更早的）
oldest = page3["data"]["items"][-1]
status, oldest_detail = get(f"/articles/{oldest['slug']}")
check("最旧一篇没有 prev", oldest_detail["data"]["prev"] is None,
      str(oldest_detail["data"]["prev"]))

# 中间的文章两侧都应该有
middle = data["items"][3]
status, middle_detail = get(f"/articles/{middle['slug']}")
md = middle_detail["data"]
check("中间文章有 prev 和 next",
      md["prev"] is not None and md["next"] is not None,
      f"prev={md['prev'] and md['prev']['title']} next={md['next'] and md['next']['title']}")

# 相邻关系必须对称：A 的 next 应该是 B，而 B 的 prev 应该是 A。
# 这条断言防的是「方向搞反」—— 如果 prev/next 的定义写反了，
# 单独看每一篇都正常，只有交叉验证才能发现。
if md["next"]:
    status, next_detail = get(f"/articles/{md['next']['slug']}")
    check("相邻关系对称（A.next 的 prev 是 A）",
          next_detail["data"]["prev"] is not None
          and next_detail["data"]["prev"]["slug"] == middle["slug"],
          f"{middle['slug']} → next {md['next']['slug']} → prev "
          f"{next_detail['data']['prev'] and next_detail['data']['prev']['slug']}")

# 上下篇不能是草稿
all_neighbor_slugs = []
for item in data["items"][:5]:
    status, dd = get(f"/articles/{item['slug']}")
    for key in ("prev", "next"):
        if dd["data"][key]:
            all_neighbor_slugs.append(dd["data"][key]["slug"])
check("上下篇中不含草稿", not any("草稿" in s for s in all_neighbor_slugs),
      f"检查了 {len(all_neighbor_slugs)} 个相邻链接")

# ---------- 5. 标签 ----------
print("\n--- 标签 ---")
status, tags = get("/tags")
check("GET /api/tags 返回 200", status == 200)
tag_list = tags["data"]
check("返回 8 个标签", len(tag_list) == 8, f"{len(tag_list)} 个")
check("含 article_count 字段", "article_count" in tag_list[0])
check("按文章数降序", tag_list[0]["article_count"] >= tag_list[-1]["article_count"],
      f"{tag_list[0]['article_count']} >= {tag_list[-1]['article_count']}")
# 草稿共 3 个关联行，若被计入则总数会多 3
total_counted = sum(t["article_count"] for t in tag_list)
check("标签计数合计为 35（不含草稿的 3 条关联）", total_counted == 35, f"合计 {total_counted}")

status, by_tag = get(f"/tags/{tag_list[0]['slug']}")
check("GET /api/tags/{slug} 返回 200", status == 200)
check("按标签过滤条数与计数一致",
      by_tag["data"]["total"] == tag_list[0]["article_count"],
      f"列表 {by_tag['data']['total']} vs 计数 {tag_list[0]['article_count']}")

# ---------- 6. 归档 ----------
print("\n--- 归档 ---")
status, archive = get("/archive")
check("GET /api/archive 返回 200", status == 200)
groups = archive["data"]
check("返回 8 个年月分组", len(groups) == 8, f"{len(groups)} 组")
check("分组按年月倒序", (groups[0]["year"], groups[0]["month"]) > (groups[-1]["year"], groups[-1]["month"]),
      f"{groups[0]['year']}-{groups[0]['month']} > {groups[-1]['year']}-{groups[-1]['month']}")
check("各组 count 与 articles 长度一致", all(g["count"] == len(g["articles"]) for g in groups))
archived_total = sum(g["count"] for g in groups)
check("归档合计 24 篇（不含草稿）", archived_total == 24, f"合计 {archived_total}")

# ---------- 7. 搜索 ----------
print("\n--- 搜索 ---")
status, sr = get("/search?q=Vue")
check("GET /api/search?q=Vue 返回 200", status == 200)
check("搜到含 Vue 的文章", sr["data"]["total"] > 0, f"total={sr['data']['total']}")
check("结果标题都含 Vue", all("Vue" in i["title"] or "Vue" in (i["summary"] or "") for i in sr["data"]["items"]))

status, sr2 = get("/search?q=SQLite")
check("换关键词结果不同", sr2["data"]["total"] != sr["data"]["total"],
      f"Vue={sr['data']['total']} SQLite={sr2['data']['total']}")

# ---------- 8. 站点配置 ----------
print("\n--- 站点配置 ---")
status, site = get("/site")
check("GET /api/site 返回 200", status == 200)
values = site["data"]["values"]
check("含 8 项配置", len(values) == 8, f"{len(values)} 项")
check("site_title 非空", bool(values.get("site_title")), values.get("site_title"))

print("\n" + "=" * 64)
print("异常路径")
print("=" * 64)

# ---------- 9. 异常路径 ----------
print("\n--- 404 系列 ---")
status, body = get("/articles/this-slug-does-not-exist")
check("不存在的 slug 返回 404", status == 404, f"status={status}")
check("404 业务码为 40400", body.get("code") == 40400, f"code={body.get('code')}")
check("404 也有统一响应体", has_envelope(body))

# 草稿必须对访客不可见，且返回 404 而非 403。
# 注意 slug 的真实形态：全角冒号被转成连字符，汉字保留 ——
# 所以是「草稿还没写完的思考-一」而不是「草稿：还没写完的思考 一」。
status, body = get("/articles/草稿还没写完的思考-一")
check("草稿详情返回 404（不是 403）", status == 404, f"status={status}")
check("草稿 404 也走统一业务码", body.get("code") == 40400, f"code={body.get('code')}")

# 草稿也不能出现在列表和归档里
status, draft_check_archive = get("/archive")
all_archived_slugs = [i["slug"] for g in draft_check_archive["data"] for i in g["articles"]]
check("草稿不出现在归档中",
      not any("草稿" in s for s in all_archived_slugs),
      f"归档共 {len(all_archived_slugs)} 篇")

status, body = get("/not-an-endpoint")
check("不存在的路径返回 404", status == 404, f"status={status}")

print("\n--- 422 系列（参数校验）---")
status, body = get("/articles?page=0")
check("page=0 被拒（422）", status == 422, f"status={status}")
check("422 业务码为 42200", body.get("code") == 42200, f"code={body.get('code')}")

status, body = get("/articles?page_size=999")
check("page_size=999 被拒（422）", status == 422, f"status={status}")

status, body = get("/search")
check("搜索缺 q 参数被拒（422）", status == 422, f"status={status}")

status, body = get("/search?q=")
check("搜索空关键词被拒（422）", status == 422, f"status={status}")

status, body = get("/search?q=" + "a" * 51)
check("搜索关键词超 50 字被拒（422）", status == 422, f"status={status}")

print("\n" + "=" * 64)
print(f"通过 {passed} 项，失败 {len(failed)} 项")
if failed:
    print("失败清单：")
    for name in failed:
        print(f"  - {name}")
print("=" * 64)

sys.exit(1 if failed else 0)
