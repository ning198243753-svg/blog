"""M3 图片上传端到端验证（1 个接口，但覆盖最多边界）

【这个测试的关键不是「上传成功」，而是「压缩真的生效了」】
文档 05 写得很直白：不压缩的话 2MB 原图在 3Mbps 下要 5 秒以上才能显示。
如果压缩静默失效（比如漏了缩放、忘了转 WebP），
上传依然返回 200，页面也正常显示，只是博客变慢 ——
没有任何提示。所以必须逐项断言输出的真实属性。

同时验证四类「看起来成功但实际有问题」的情况：
- 伪装成图片的非图片文件（改扩展名绕过检查）
- 体积超限
- 尺寸超限（解压炸弹）
- 动图是否保留了动画（Pillow 默认会静默丢掉）
"""

import io
import json
import sqlite3
import struct
import sys
import urllib.error
import urllib.request
import uuid
from http.cookiejar import CookieJar
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests._env import TEST_DB_PATH, assert_not_dev_db  # noqa: E402

assert_not_dev_db("test_upload.py")

from app.config import settings  # noqa: E402

BASE = "http://127.0.0.1:8000/api"
failed = []
passed = 0

jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

# 上传目录：测试库与开发库共用同一个 uploads 目录，
# 所以本测试产生的文件必须在结尾清理掉，否则会污染开发环境。
UPLOAD_DIR = settings.upload_dir
created_files: list[Path] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    global passed
    if ok:
        passed += 1
    else:
        failed.append(name)
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def post_multipart(path: str, field_name: str, filename: str, content: bytes,
                   content_type: str = "application/octet-stream", authorized: bool = True):
    """手工构造 multipart/form-data 请求

    不用 requests 库：项目依赖里没有它，而且手工构造能顺带验证
    服务端对畸形 multipart 的处理。
    """
    boundary = f"----M3Test{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        BASE + path, data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    target = opener if authorized else urllib.request.build_opener()
    try:
        with target.open(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"_raw": raw[:300]}


def make_image(fmt: str, size: tuple[int, int], mode: str = "RGB",
               frames: int = 1, color=(120, 160, 200)) -> bytes:
    """用 Pillow 造一张真实图片

    必须造真图而不是拼字节：服务端会真的解码，
    伪造的文件头过不了解码这一步。
    """
    from PIL import Image

    buffer = io.BytesIO()
    if frames > 1:
        imgs = []
        for i in range(frames):
            img = Image.new(mode, size, (color[0], color[1], (color[2] + i * 40) % 256))
            imgs.append(img)
        imgs[0].save(buffer, format=fmt, save_all=True, append_images=imgs[1:],
                     duration=100, loop=0)
    else:
        img = Image.new(mode, size, color)
        img.save(buffer, format=fmt)
    return buffer.getvalue()


print("=" * 66)
print("M3 图片上传验证")
print(f"上传目录：{UPLOAD_DIR}")
print("=" * 66)

# ---------- 前置 ----------
status, body = post_multipart("/auth/login", "x", "x", b"x")  # 触发一次请求确认服务活着
status, login = urllib.request.Request(BASE + "/auth/login"), None
import urllib.parse  # noqa: E402

login_req = urllib.request.Request(
    BASE + "/auth/login",
    data=json.dumps({
        "username": settings.admin_username,
        "password": settings.admin_password,
    }).encode(),
    method="POST",
    headers={"Content-Type": "application/json"},
)
try:
    with opener.open(login_req, timeout=15) as resp:
        ok_login = json.loads(resp.read().decode())["code"] == 0
except urllib.error.HTTPError:
    ok_login = False

check("登录成功", ok_login)
if not ok_login:
    sys.exit(1)

# ---------- 权限 ----------
print("\n--- 权限边界 ---")
jpeg_bytes = make_image("JPEG", (800, 600))
status, err = post_multipart("/admin/upload", "file", "a.jpg", jpeg_bytes, "image/jpeg",
                             authorized=False)
check("未登录上传返回 401", status == 401, f"status={status}")

# ---------- 正常上传 ----------
print("\n--- 正常上传（jpg）---")
status, res = post_multipart("/admin/upload", "file", "photo.jpg", jpeg_bytes, "image/jpeg")
check("上传 jpg 返回 200", status == 200, f"status={status} {str(res)[:120]}")

if status == 200:
    d = res["data"]
    created_files.append(UPLOAD_DIR / d["filename"])

    check("返回 url", d["url"].startswith("/uploads/"), d["url"])
    check("③ 输出格式是 WebP", d["format"] == "webp", d["format"])
    check("④ 文件名是随机串（不含原始名）",
          "photo" not in d["filename"] and d["filename"].endswith(".webp"),
          d["filename"])
    check("④ 文件名长度合理（16 位随机 + 扩展名）",
          len(d["filename"]) == len("0000000000000000.webp"), d["filename"])

    src_bytes = UPLOAD_DIR / d["filename"]
    check("文件真的写到了磁盘", src_bytes.exists(),
          f"{src_bytes.stat().st_size if src_bytes.exists() else 0} 字节")

    # ① 输出确实是 WebP（读文件头，不信返回值）
    if src_bytes.exists():
        head = src_bytes.read_bytes()[:12]
        check("① 磁盘上的文件确实是 WebP（RIFF....WEBP）",
              head[:4] == b"RIFF" and head[8:12] == b"WEBP",
              str(head[:12]))

    check("返回值里的 size 与实际文件大小一致",
          d["size"] == (src_bytes.stat().st_size if src_bytes.exists() else -1),
          f"{d['size']} vs {src_bytes.stat().st_size if src_bytes.exists() else 'N/A'}")

    check("图片尺寸未变（800px 未触及 1600 上限）",
          (d["width"], d["height"]) == (800, 600), f"{d['width']}×{d['height']}")

    check("记录了原图信息（便于验证压缩）",
          d["source_size"] == len(jpeg_bytes),
          f"原 {d['source_size']} → 新 {d['size']}")

# ---------- ② 缩放 ----------
print("\n--- ② 超过 1600px 的缩放 ---")
big = make_image("JPEG", (3200, 2400))
status, res_big = post_multipart("/admin/upload", "file", "big.jpg", big, "image/jpeg")
check("大图上传成功", status == 200, f"status={status}")

if status == 200:
    b = res_big["data"]
    created_files.append(UPLOAD_DIR / b["filename"])

    check("② 长边被缩到 1600", max(b["width"], b["height"]) == 1600,
          f"{b['width']}×{b['height']}")
    check("② 等比缩放（宽高比保持 4:3）",
          abs(b["width"] / b["height"] - 3200 / 2400) < 0.01,
          f"{b['width']}/{b['height']} = {b['width']/b['height']:.3f}")
    check("② 体积明显缩小", b["size"] < len(big) * 0.5,
          f"{len(big)} → {b['size']} 字节（{100*b['size']//len(big)}%）")

    # 用 Pillow 独立验证磁盘上的文件，而不是只信接口返回值
    from PIL import Image

    with Image.open(UPLOAD_DIR / b["filename"]) as im:
        check("独立验证：磁盘文件尺寸确实是 1600 长边",
              max(im.size) == 1600, f"{im.size}")
        check("独立验证：磁盘文件格式是 WEBP", im.format == "WEBP", str(im.format))

# ---------- 小图不放大 ----------
print("\n--- 小图不应被放大 ---")
small = make_image("PNG", (100, 80))
status, res_small = post_multipart("/admin/upload", "file", "tiny.png", small, "image/png")
if status == 200:
    s = res_small["data"]
    created_files.append(UPLOAD_DIR / s["filename"])
    check("小图尺寸不变（thumbnail 不会放大）",
          (s["width"], s["height"]) == (100, 80), f"{s['width']}×{s['height']}")

# ---------- 各格式 ----------
print("\n--- 允许的四种格式 ---")
for fmt, ext, ctype, mode in (
    ("PNG", "png", "image/png", "RGBA"),
    ("WEBP", "webp", "image/webp", "RGB"),
    ("GIF", "gif", "image/gif", "P"),
):
    data = make_image(fmt, (600, 400), mode=mode)
    status, r = post_multipart("/admin/upload", "file", f"x.{ext}", data, ctype)
    if status == 200:
        created_files.append(UPLOAD_DIR / r["data"]["filename"])
    check(f"{fmt} 可上传", status == 200,
          f"status={status} {r.get('data', {}).get('format', '') if status == 200 else str(r)[:80]}")

# ---------- 动图 ----------
print("\n--- GIF 动图必须保留动画 ---")
animated_gif = make_image("GIF", (200, 150), mode="P", frames=5)
status, res_anim = post_multipart("/admin/upload", "file", "anim.gif", animated_gif, "image/gif")
check("动图上传成功", status == 200, f"status={status}")

if status == 200:
    a = res_anim["data"]
    created_files.append(UPLOAD_DIR / a["filename"])

    check("识别为动图（animated=True）", a["animated"] is True, str(a["animated"]))
    check("记录了帧数", a["frames"] == 5, f"frames={a['frames']}")

    # 【最关键】用 Pillow 独立打开磁盘上的文件，确认动画真的保留了。
    # Pillow 默认只写第一帧且不报错 —— 不这样验证就发现不了。
    from PIL import Image

    with Image.open(UPLOAD_DIR / a["filename"]) as im:
        actual_frames = getattr(im, "n_frames", 1)
    check("【关键】独立验证：磁盘上的 WebP 仍是 5 帧动画",
          actual_frames == 5, f"实际 {actual_frames} 帧")

# 静态图不应被误判为动图
status, res_static = post_multipart("/admin/upload", "file", "s.gif",
                                    make_image("GIF", (200, 150), mode="P", frames=1),
                                    "image/gif")
if status == 200:
    created_files.append(UPLOAD_DIR / res_static["data"]["filename"])
    check("静态 GIF 不被标记为动图", res_static["data"]["animated"] is False,
          str(res_static["data"]["animated"]))

# ---------- ① 伪装文件 ----------
print("\n--- ① 格式校验（伪造与不支持）---")

# 把文本改名成 .jpg —— 最典型的绕过尝试
status, err = post_multipart("/admin/upload", "file", "evil.jpg",
                             b"<?php system($_GET['c']); ?>", "image/jpeg")
check("① 伪装成 jpg 的文本被拒（40004）", status == 400, f"status={status}")
check("① 业务码为 40004", err.get("code") == 40004, f"code={err.get('code')}")

# 可执行文件改名
status, err = post_multipart("/admin/upload", "file", "payload.png",
                             b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 100, "image/png")
check("① 伪装成 png 的可执行文件被拒", status == 400, f"status={status}")

# 空文件
status, err = post_multipart("/admin/upload", "file", "empty.jpg", b"", "image/jpeg")
check("① 空文件被拒", status == 400, f"status={status}")

# 截断的图片（有正确的文件头但内容不全）
status, err = post_multipart("/admin/upload", "file", "truncated.jpg", jpeg_bytes[:100],
                             "image/jpeg")
check("① 截断的图片被拒（无法完整解码）", status == 400, f"status={status}")

# 真实但不支持的格式：BMP
from PIL import Image as _Image  # noqa: E402

bmp_buf = io.BytesIO()
_Image.new("RGB", (100, 100), (10, 20, 30)).save(bmp_buf, format="BMP")
status, err = post_multipart("/admin/upload", "file", "x.bmp", bmp_buf.getvalue(), "image/bmp")
check("① 不支持的真实格式（BMP）被拒", status == 400, f"status={status}")
check("① 提示里列出了允许的格式",
      any(k in str(err.get("message", "")) for k in ("jpg", "png", "webp", "gif")),
      str(err.get("message"))[:90])

# ---------- 体积 ----------
print("\n--- 体积上限 ---")
max_bytes = settings.upload_max_size_mb * 1024 * 1024
# 造一个超过上限的文件：用随机字节避免被压缩掉，但内容必须不是图片，
# 否则会先撞上「体积检查」——那正是我们要测的顺序
oversize = b"\xff\xd8\xff\xe0" + b"\x00" * (max_bytes + 1024)
status, err = post_multipart("/admin/upload", "file", "huge.jpg", oversize, "image/jpeg")
check(f"超过 {settings.upload_max_size_mb}MB 被拒", status == 400, f"status={status}")
check("体积超限业务码为 40005", err.get("code") == 40005, f"code={err.get('code')}")

# ---------- ⑤ 解压炸弹 ----------
print("\n--- ⑤ 解压炸弹防护 ---")
# 造一张尺寸极大但压缩后很小的 PNG：纯色图压缩率极高，
# 10000×10000 的纯色 PNG 只有几十 KB，但解码需要 300MB 内存。
from PIL import Image as _I  # noqa: E402

bomb_buf = io.BytesIO()
_I.new("RGB", (10000, 10000), (1, 2, 3)).save(bomb_buf, format="PNG", optimize=True)
bomb = bomb_buf.getvalue()
status, err = post_multipart("/admin/upload", "file", "bomb.png", bomb, "image/png")
check("⑤ 超大尺寸图片被拒（不是 OOM 崩溃）",
      status == 400, f"status={status}（体积仅 {len(bomb)//1024}KB）")
check("⑤ 业务码为 40004", err.get("code") == 40004, f"code={err.get('code')}")
check("⑤ 提示里给出了实际尺寸",
      "10000" in str(err.get("message", "")), str(err.get("message"))[:100])

# ---------- multipart 字段名 ----------
print("\n--- 请求格式 ---")
status, err = post_multipart("/admin/upload", "wrong_field", "a.jpg", jpeg_bytes, "image/jpeg")
check("字段名不是 file 时返回 422", status == 422, f"status={status}")

# ---------- URL 可访问性 ----------
print("\n--- 上传后的 URL ---")
if created_files:
    target = next((f for f in created_files if f.exists()), None)
    if target:
        # 开发环境由 Vite 代理 /uploads；这里直接打后端确认 FastAPI 侧不处理它
        status_code = None
        try:
            req = urllib.request.Request(f"http://127.0.0.1:8000/uploads/{target.name}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                status_code = resp.status
        except urllib.error.HTTPError as exc:
            status_code = exc.code
        # 文档 05 第 2.7 节：/uploads 由 Nginx 直接返回，不经过 FastAPI。
        # 所以开发时 FastAPI 返回 404 是**正确**的 ——
        # 它说明 FastAPI 没有拦这个路径。Vite 的 proxy 负责开发期的访问。
        check("FastAPI 不处理 /uploads（符合 ADR-02，由 Nginx/Vite 转发）",
              status_code == 404, f"status={status_code}")

# ---------- 清理 ----------
print("\n--- 清理测试产生的文件 ---")
removed = 0
for f in created_files:
    if f.exists():
        f.unlink()
        removed += 1
check("测试文件已清理", removed == len(created_files),
      f"删除 {removed}/{len(created_files)} 个")

# 确认 uploads 目录没有残留 .tmp
leftover_tmp = list(UPLOAD_DIR.glob(".*.tmp")) if UPLOAD_DIR.exists() else []
check("没有残留的临时文件", len(leftover_tmp) == 0, f"{len(leftover_tmp)} 个")

print()
print("=" * 66)
print(f"通过 {passed} 项，失败 {len(failed)} 项")
if failed:
    print("失败清单：")
    for name in failed:
        print(f"  - {name}")
print("=" * 66)

sys.exit(1 if failed else 0)
