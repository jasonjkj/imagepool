"""scenic 内置 provider（stdlib-only，各自独立可拆）。

每个 fetch 函数契约（与外部函数完全等价）：
  fetch(query: str, ctx: dict, opts: dict) -> list[str | dict]
  返回 str（URL / 本地路径）或 {"ref": ..., "local": bool}；
  抛异常 = 本渠道失败（引擎按 fail-isolated 跳过）。

内置源只有三种通用机制，不含任何宿主资源引用：
  bing        必应图库 murl 直链提取（无需密钥；suffix/reject/n 由 opts）
  pexels      Pexels API v1 搜索（密钥由 opts.api_key 或 env PEXELS_API_KEY 注入）
  local_dir   本地目录池直发（dir 由 opts 指定；persona / 线路池等复用）
"""
import json
import os
import re
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
_BING_FALLBACK_KEEP = 2  # 非直链（无图片扩展名结尾）最多保留条数


def bing_fetch(query, ctx, opts):
    """必应图库检索 → murl 直链列表（≤ n）。网络失败 → []（调用方走兜底链）。"""
    opts = opts or {}
    n = int(opts.get("n", 8))
    suffix = opts.get("suffix", "")
    reject = [r.lower() for r in (opts.get("reject") or [])]
    q = urllib.parse.quote((query or "") + suffix)
    url = "https://www.bing.com/images/search?q=%s&qft=+filterui:photo-photo" % q
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
    except Exception:
        return []
    raw = re.findall(r'murl&quot;:&quot;(.*?)&quot;', html)
    if not raw:
        raw = re.findall(r'"murl":"(.*?)"', html)
    out = []
    fallback = 0
    for u in raw:
        u = u.replace("\\/", "/").replace("\\u0026", "&").replace("&amp;", "&")
        if not u.lower().startswith("http"):
            continue
        if any(r in u.lower() for r in reject):
            continue
        if u.lower().endswith(_IMAGE_EXTS):
            out.append(u)
        elif fallback < _BING_FALLBACK_KEEP:
            fallback += 1
            out.append(u)
        if len(out) >= n:
            break
    return out


def pexels_fetch(query, ctx, opts):
    """Pexels API v1 搜索 → 图片 URL 列表。

    密钥：opts.api_key 优先，否则 env PEXELS_API_KEY；缺 key → []（不抛）。
    orientation / per_page 由 opts；查询词由调用方给（英文语义归调用方）。
    """
    opts = opts or {}
    key = opts.get("api_key") or os.environ.get("PEXELS_API_KEY", "")
    if not key:
        return []
    orientation = opts.get("orientation", "landscape")
    per_page = int(opts.get("per_page", 10))
    q = urllib.parse.quote(query or "")
    url = ("https://api.pexels.com/v1/search?query=%s&per_page=%d&orientation=%s"
           % (q, per_page, orientation))
    try:
        req = urllib.request.Request(url, headers={"Authorization": key, "User-Agent": UA})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore"))
    except Exception:
        return []
    return [p.get("src", {}).get("original")
            for p in data.get("photos", []) if p.get("src", {}).get("original")]


def local_dir_fetch(query, ctx, opts):
    """本地目录池直发：dir 由 opts 指定（~ 展开）。平铺文件 + 一层子目录聚合。"""
    d = os.path.expanduser((opts or {}).get("dir", ""))
    if not d or not os.path.isdir(d):
        return []
    out = []
    for sub in sorted(os.listdir(d)):
        p = os.path.join(d, sub)
        if os.path.isdir(p):
            for f in sorted(os.listdir(p)):
                if f.lower().endswith(_IMAGE_EXTS):
                    out.append({"ref": os.path.join(p, f), "local": True})
        elif p.lower().endswith(_IMAGE_EXTS):
            out.append({"ref": p, "local": True})
    return out
