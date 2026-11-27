"""落盘层（迁移自旧 image_gen.py save_image，298-334 行，逐行复制）。

唯一接线改动：
1. 硬编码 CACHE 目录 → out_dir 入参（调用方决定落盘位置）。
2. requests.get → _net._get_bytes（stdlib，失败返回 None）。
data URI 直写 / 后缀跟 URL 剥 query / 识别不到兜底 .png 等语义原样保留。
"""
import base64
from datetime import datetime
from urllib.parse import urlparse

from imagepool import _net

_MIME_BY_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".webp": "image/webp"}


def to_data_uri(src):
    """图源归一化（图生图输入用）：data: / http(s) 原样返回；
    本地路径读文件转 `data:<mime>;base64,<b64>`；读不到/非字符串抛 OSError。"""
    if not isinstance(src, str):
        raise OSError(f"输入图源必须是字符串，实际 {type(src).__name__}")
    if src.startswith("data:") or src.startswith("http://") or src.startswith("https://"):
        return src
    from pathlib import Path
    path = Path(src)
    data = path.read_bytes()
    mime = _MIME_BY_EXT.get(path.suffix.lower(), "image/png")
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def save_image(url, provider, out_dir, name_hint=None):
    """下载图片到 out_dir，返回本地路径。支持 http(s) URL 与 data:image/*;base64,URI。"""
    from pathlib import Path
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = name_hint or provider
    # data URI：b64 直写（sensenova 等 b64_json provider 无下载 URL）
    if url.startswith("data:"):
        try:
            header, _, b64 = url[len("data:"):].partition(",")
            fmt = header.split(";")[0].split("/")[-1]  # png / jpeg / webp
            ext = {".png": ".png", ".jpg": ".jpg", ".jpeg": ".jpg", ".webp": ".webp"}.get(
                "." + fmt, ".png")
            fpath = out / f"{stem}_{ts}{ext}"
            fpath.write_bytes(base64.b64decode(b64))
            return str(fpath)
        except Exception:
            return None
    # 后缀跟 URL 走（签名 URL 需剥 query）；识别不到兜底 .png
    path = urlparse(url).path
    ext = ".png"
    for cand in (".jpg", ".jpeg", ".png", ".webp"):
        if path.lower().endswith(cand):
            ext = ".jpg" if cand == ".jpeg" else cand
            break
    fpath = out / f"{stem}_{ts}{ext}"
    data = _net._get_bytes(url, timeout=30)
    if data is None:
        return None
    fpath.write_bytes(data)
    return str(fpath)