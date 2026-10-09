"""图片处理与存储（文档 05 第 4.7 节 / ADR-02）

【为什么这个模块的每一步都不能省】
ADR-02 选择了「图片存本地、由 Nginx 直接返回」，代价是图片流量
全部压在自己 3Mbps 的带宽上。文档 05 写得很直白：
2MB 的原图在 3Mbps 下要 5 秒以上才能显示，博客会变得不可用。
所以压缩不是优化项，而是这条决策能否成立的先决条件。

四件事必须做（文档 05 第 4.7 节「服务端必做处理」）：
① 校验真实格式（不能只看扩展名）
② 超过 1600px 的图片等比缩放
③ 转为 WebP
④ 文件名用随机串

【本次额外加的两道保护，文档里没写】
⑤ 解压炸弹防护：2MB 的 PNG 可以解出上亿像素，解码时吃光内存。
   在 4G 内存的单机上，这会让**所有**请求一起挂掉，不只是这次上传。
⑥ 图片数量与总体积不设限，但把「孤儿文件」的代价写进 README。

关于 GIF：文档要求「允许 gif」且「转为 WebP」，但这两条在动图上冲突 ——
Pillow 默认只写第一帧，动图会**静默**变成静图（不报错、不警告）。
这里用 save_all=True 输出动画 WebP，两条要求都满足且无数据损失。
"""

import io
import secrets
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.core.errors import BizError, ErrorCode

# 允许的输入格式（文档 05 第 4.7 节）
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF"}

# Pillow 的格式名与我们要提示给用户的扩展名不是一一对应：
# JPEG 的实际扩展名有 .jpg 和 .jpeg 两种写法。
FORMAT_LABELS = {
    "JPEG": "jpg",
    "PNG": "png",
    "WEBP": "webp",
    "GIF": "gif",
}

# ⑤ 解压炸弹防护阈值。
#
# 定这两个数的依据：
# - 8000×8000 = 6400 万像素，解码成 RGB 约占 192MB 内存，
#   在 4G 单机上属于「一次请求就吃掉 5% 内存」，不可接受。
# - 5000 万像素覆盖了所有真实相机和手机（当前主流在 1200 万~1 亿，
#   但超过 5000 万的图在博客上没有任何意义）。
MAX_IMAGE_PIXELS = 50_000_000
MAX_IMAGE_SIDE = 8000

# WebP 输出质量。85 是「肉眼难辨差异」的常用起点；
# 再往上体积增长快而观感提升极小，往下到 70 以下开始出现可见块效应。
WEBP_QUALITY = 85

# 动画 WebP 的参数：
# - duration 必须逐帧给，否则 Pillow 用默认值，动图节奏会变
# - loop=0 表示无限循环
# - minimize_size 会尝试更小的编码，代价是编码时间
ANIMATED_WEBP_MINIMIZE = True


def _read_upload(content: bytes) -> Image.Image:
    """把上传的字节解码成 Pillow 图像

    【为什么必须在这里解码，而不是看扩展名或 Content-Type】
    Content-Type 和文件名都是客户端说了算的，伪造成本为零。
    把 .php 改名成 .jpg 就能绕过扩展名检查。
    唯一可靠的判断方式是「这张图能不能被真正解码」——
    解码成功就说明它是真实图片，且能得到它的真实格式与尺寸。
    """
    if not content:
        raise BizError(ErrorCode.PARAM_INVALID, message="上传内容为空", http_status=400)

    # 先按体积拦一道。放在解码之前，避免为超限文件做无用功。
    max_bytes = settings.upload_max_size_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise BizError(
            ErrorCode.IMAGE_TOO_LARGE,
            message=f"图片体积超过 {settings.upload_max_size_mb}MB 限制",
            http_status=400,
        )

    try:
        image = Image.open(io.BytesIO(content))
        # verify() 只能发现「文件头与内容不符」这类问题，且调用后
        # 图像对象就不能再用了，所以这里用 load() 做完整解码验证。
        image.load()
    except UnidentifiedImageError:
        raise BizError(
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            message="无法识别的图片格式（仅支持 jpg / png / webp / gif）",
            http_status=400,
        ) from None
    except (OSError, ValueError) as exc:
        # 截断的文件、损坏的图片等
        raise BizError(
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            message=f"图片文件损坏或无法解码：{exc}",
            http_status=400,
        ) from None

    # ① 真实格式校验：解码拿到的 format 才是真的
    fmt = (image.format or "").upper()
    if fmt not in ALLOWED_FORMATS:
        allowed = " / ".join(sorted(FORMAT_LABELS.values()))
        raise BizError(
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            message=f"不支持的图片格式 {fmt or '未知'}（仅支持 {allowed}）",
            http_status=400,
        )

    # ⑤ 解压炸弹：解码成功后立刻检查真实像素数。
    # 注意这一步是「已经付了解码代价之后」才做的 ——
    # 真正的第一道防线是 Pillow 自己的 MAX_IMAGE_PIXELS（见模块底部）。
    width, height = image.size
    if width * height > MAX_IMAGE_PIXELS or max(width, height) > MAX_IMAGE_SIDE:
        raise BizError(
            ErrorCode.IMAGE_FORMAT_UNSUPPORTED,
            message=(
                f"图片尺寸过大（{width}×{height}）。"
                f"上限为 {MAX_IMAGE_SIDE}px 边长且不超过 "
                f"{MAX_IMAGE_PIXELS // 1_000_000} 百万像素"
            ),
            http_status=400,
        )

    return image


def _resize(image: Image.Image) -> Image.Image:
    """② 等比缩放到 upload_max_width 以内

    用 thumbnail 而不是 resize：
    - thumbnail 自动保持宽高比，且**只在图片更大时才缩小**，
      不会把小图放大（放大只会让文件更大、更模糊）
    - resize 需要自己算比例，算错就是拉伸变形

    用 LANCZOS 重采样：缩小时质量最好的算法，
    代价是比 BILINEAR 慢一些，但对上传这种低频操作完全可以接受。
    """
    limit = settings.upload_max_width
    if max(image.size) <= limit:
        return image

    image = image.copy()
    image.thumbnail((limit, limit), Image.Resampling.LANCZOS)
    return image


def _to_webp_bytes(image: Image.Image) -> bytes:
    """③ 转为 WebP

    【动画的处理】
    GIF 动图如果按普通图片保存，Pillow 只会写入第一帧 ——
    不报错、不警告，动图静默变成静图。这是很难被发现的数据损失，
    因为上传成功、页面显示正常，只是"不动了"。

    所以这里检测 n_frames，多帧时走 save_all 分支，
    并把每一帧的时长原样传给 WebP（不传的话 Pillow 用默认值，
    动图的节奏会变快或变慢）。
    """
    buffer = io.BytesIO()

    frame_count = getattr(image, "n_frames", 1)

    if frame_count > 1:
        # 动图：逐帧取出并转成 RGB/RGBA。
        # 为什么不用 image.save(..., save_all=True) 直接写？
        # 因为 GIF 调色板模式的帧直接转 WebP 有时会出偏色，
        # 逐帧转换能保证每帧都是正确的颜色模式。
        frames = []
        durations = []
        for i in range(frame_count):
            image.seek(i)
            frame = image.convert("RGBA")
            frames.append(frame)
            durations.append(image.info.get("duration", 100))

        frames[0].save(
            buffer,
            format="WEBP",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=image.info.get("loop", 0),
            quality=WEBP_QUALITY,
            minimize_size=ANIMATED_WEBP_MINIMIZE,
        )
    else:
        # 静态图。WebP 不支持 P 模式（调色板），必须转成 RGB 或 RGBA，
        # 否则 save 会抛 OSError: cannot write mode P as WEBP
        if image.mode in ("P", "LA"):
            # 有透明通道的转 RGBA，没有的转 RGB
            has_alpha = "transparency" in image.info or image.mode == "LA"
            image = image.convert("RGBA" if has_alpha else "RGB")
        elif image.mode == "CMYK":
            # CMYK 是印刷色彩模式，WebP 不支持
            image = image.convert("RGB")

        image.save(buffer, format="WEBP", quality=WEBP_QUALITY, method=4)

    return buffer.getvalue()


def _random_filename() -> str:
    """④ 生成随机文件名

    【为什么不用原始文件名】
    - 路径注入：原文件名可能是 "../../etc/passwd"
    - 重名覆盖：两张都叫 photo.jpg 的图会互相覆盖
    - 中文与特殊字符：需要在 URL 里编码，且不同系统行为不一致
    - 隐私：用户的文件名可能包含真实姓名、日期等信息

    用 secrets 而不是 random：random 的随机数可预测，
    而「预测出下一个文件名」意味着可以枚举别人上传的图片。
    16 个十六进制字符 = 64 位随机，碰撞概率可忽略。

    统一用 .webp 扩展名：输出格式一定是 WebP（见 _to_webp_bytes）。
    """
    return f"{secrets.token_hex(8)}.webp"


def save_image(content: bytes) -> dict:
    """完整的图片入库流程，返回 {url, filename, width, height, size, format}

    流程顺序不可以调换：
        解码验证 → 尺寸检查 → 缩放 → 转 WebP → 写盘
    特别是「解码验证」必须在最前：后面的每一步都假设
    content 是一张真实的、尺寸合法的图片。
    """
    image = _read_upload(content)
    source_format = (image.format or "").upper()
    original_size = image.size
    frame_count = getattr(image, "n_frames", 1)
    is_animated = frame_count > 1

    image = _resize(image)
    webp_bytes = _to_webp_bytes(image)

    # 写盘。先写临时文件再改名有两个好处：
    # 1. 万一写一半进程被杀，不会留下一个「看起来存在但损坏」的文件
    # 2. 改名是原子操作，Nginx 不会读到半个文件
    upload_dir = settings.upload_dir
    upload_dir.mkdir(parents=True, exist_ok=True)

    filename = _random_filename()
    final_path = upload_dir / filename
    temp_path = upload_dir / f".{filename}.tmp"

    try:
        temp_path.write_bytes(webp_bytes)
        temp_path.replace(final_path)
    except OSError as exc:
        # 磁盘满、权限不对等。清理临时文件后报错，
        # 否则会在 uploads 目录里堆积 .tmp 文件。
        temp_path.unlink(missing_ok=True)
        raise BizError(
            ErrorCode.INTERNAL_ERROR,
            message=f"图片写入失败：{exc}",
            http_status=500,
        ) from None

    return {
        # URL 是给前端直接放进 <img src> 的，所以带 /uploads 前缀
        "url": f"/uploads/{filename}",
        "filename": filename,
        "width": image.size[0],
        "height": image.size[1],
        "size": len(webp_bytes),
        "format": "webp",
        # 以下三个字段是给调用方判断压缩效果的，前端可以不用
        "source_format": FORMAT_LABELS.get(source_format, source_format.lower()),
        "source_size": len(content),
        "source_width": original_size[0],
        "source_height": original_size[1],
        "animated": is_animated,
        "frames": frame_count if is_animated else 1,
    }


# ------------------------------------------------------------------
# Pillow 全局保护：解压炸弹的第一道防线
#
# 上面 _read_upload 里的尺寸检查发生在「已经解码之后」——
# 也就是说内存已经被吃掉了。Pillow 自己的 MAX_IMAGE_PIXELS 会在
# 解码前就根据文件头里的尺寸声明拒绝过大的图，
# 是真正的第一道防线，所以必须设置。
#
# 设成略高于我们的业务阈值：让「尺寸偏大但可能合法」的图
# 走到我们的检查里，给出更友好的中文提示；
# 而明显离谱的（比如 100000×100000）由 Pillow 直接拦下。
# ------------------------------------------------------------------
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
