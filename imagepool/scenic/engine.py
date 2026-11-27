"""scenic 链式引擎：配置解析 → 链构建 → 候选归一化 → 下载/验货/落库。

核心不翻译、不读 .env、不碰宿主资源；一切经 cfg（YAML）+ ctx（只读）注入。

配置语义：
  chain:    [provider 名按优先级排列]（主渠道 → fallback）；不在 chain 的一律不调
  limit:    每 provider 最多产出候选条数（每次抓几条，外层可配）
  storage:  {dir: 落库根}（外层可配）
  providers.<name>: {enabled, entry, options}
    entry: builtin:<内置> | <module>:<func> | <绝对路径.py>:<func>
  hooks.verify: {enabled, entry, options}  验货 hook（决定要不要落库）

降级口径：配置缺失/损坏 → 回默认内置链（[bing, pexels]），不 fail-closed 阻塞旅行链路；
单 provider 加载失败/抛异常 → stderr 一行 + 跳过；验货缺失/异常 → 放行（看不了就不验货）。
"""
import importlib.util
import os
import sys
import urllib.request

from . import sources
from .contract import Candidate, ConfigError

DEFAULT_CHAIN = ["bing", "pexels"]

_BUILTINS = {
    "bing": sources.bing_fetch,
    "pexels": sources.pexels_fetch,
    "local_dir": sources.local_dir_fetch,
}


def default_config_path():
    """缺省配置文件：env SCENIC_CONFIG 优先，其次 env IMAGEPOOL_SCENIC_CONFIG；
    都没有 → 空串（无默认配置，load_config 返回 {} 走默认链）。"""
    return (os.environ.get("SCENIC_CONFIG")
            or os.environ.get("IMAGEPOOL_SCENIC_CONFIG")
            or "")


def load_config(path=None):
    """读 YAML 配置；未给路径且无默认配置 / 文件缺失 / 损坏 → {}（调用方用默认链）。"""
    p = path or default_config_path()
    if not p or not os.path.exists(p):
        return {}
    import yaml
    try:
        with open(p, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_entry(entry):
    """解析 provider entry → callable；解析失败 → None（调用方 stderr + 跳过）。

    支持三种形态：
      builtin:<name>             内置源（sources.py）
      <module>:<func>            import 模块（如 my_pkg.extras.imagesearch:bing_image_search）
      <路径.py>:<func>           任意文件按路径延迟加载（外部函数，最通用）
    """
    if not entry or not isinstance(entry, str):
        return None
    if entry.startswith("builtin:"):
        return _BUILTINS.get(entry[len("builtin:"):])
    if ":" not in entry:
        return None
    head, _, func = entry.rpartition(":")
    # 路径形态：含路径分隔符或 .py 结尾 → 按文件加载（importlib 延迟，不新增跨模块顶层 import）
    if os.sep in head or head.endswith(".py"):
        mod_path = os.path.expanduser(head)
        if not os.path.exists(mod_path):
            return None
        try:
            spec = importlib.util.spec_from_file_location(
                "scenic_ext_%d" % abs(hash(mod_path)), mod_path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:
            return None
        return getattr(mod, func, None)
    # 模块形态
    try:
        mod = __import__(head, fromlist=[func])
    except Exception:
        return None
    return getattr(mod, func, None)


def _normalize(item, source):
    """provider 返回 str 或 dict → Candidate；非法条目 → None。"""
    if isinstance(item, str):
        return Candidate(ref=item, source=source)
    if isinstance(item, dict):
        return Candidate(ref=item.get("ref") or "", source=item.get("source") or source,
                         local=bool(item.get("local")))
    return None


def iter_candidates(query, ctx, cfg):
    """按 chain 顺序遍历可用 provider → 归一化候选迭代器（fail-isolated）。

    query: 实际搜索串（调用方给；英文语义归调用方，核心不翻译）。
    ctx:   只读上下文（spot/query/limit/cache_dir/scenic_root/last_path/...）。
    """
    cfg = cfg or {}
    providers = cfg.get("providers") or {}
    chain = cfg.get("chain") or DEFAULT_CHAIN
    limit = int(cfg.get("limit") or (ctx or {}).get("limit") or 5)
    for name in chain:
        spec = providers.get(name)
        if spec is None:
            continue
        if isinstance(spec, dict) and spec.get("enabled") is False:
            continue
        entry = spec.get("entry") if isinstance(spec, dict) else None
        fn = resolve_entry(entry)
        if fn is None:
            print("scenic: provider %r 加载失败，跳过" % name, file=sys.stderr)
            continue
        opts = spec.get("options") if isinstance(spec, dict) else {}
        got = 0
        try:
            for item in fn(query or "", ctx or {}, opts or {}) or []:
                cand = _normalize(item, name)
                if cand is None or not cand.ref:
                    continue
                yield cand
                got += 1
                if got >= limit:
                    break
        except Exception as e:
            print("scenic: provider %r 异常，跳过: %s" % (name, e), file=sys.stderr)
            continue


def resolve_verify(cfg):
    """从配置解析验货 hook → callable(path, ctx) -> bool；缺失/禁用/失败 → None（不验货）。"""
    cfg = cfg or {}
    hook = (cfg.get("hooks") or {}).get("verify") or {}
    if not isinstance(hook, dict) or not hook.get("enabled"):
        return None
    return resolve_entry(hook.get("entry"))


def _looks_like_image(head):
    """magic-byte 校验：JPEG / PNG / WEBP / GIF / BMP 头。"""
    head = head or b""
    return (head[:3] == b"\xff\xd8\xff"
            or head[:8] == b"\x89PNG\r\n\x1a\n"
            or (head[:4] == b"RIFF" and head[8:12] == b"WEBP")
            or head[:6] in (b"GIF87a", b"GIF89a")
            or head[:2] == b"BM")


def download(url, dst, min_bytes=30000, timeout=20, check_magic=True):
    """stdlib 下载：大小闸门 + 可选 magic 校验；失败 False 不留残件。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": sources.UA})
        data = urllib.request.urlopen(req, timeout=timeout).read()
    except Exception:
        return False
    if len(data) < min_bytes:
        return False
    if check_magic and not _looks_like_image(data[:12]):
        return False
    with open(dst, "wb") as f:
        f.write(data)
    return True


def acquire(cand, dst, ctx, cfg=None, verify=None):
    """把候选落到 dst：URL → 下载；然后可选验货 hook 决定是否落库。

    返回 (path, kept)。kept=False 时已删除下载残件（不落库），调用方继续下一条；
    本地候选（local=True）验货不通过时不删共享源文件，仅跳过。
    验货缺失/异常 → 放行（quality 过滤不是安全闸，看不了就不验货）。
    """
    if cand.local:
        path = cand.ref
    else:
        os.makedirs(os.path.dirname(dst) or ".", exist_ok=True)
        if not download(cand.ref, dst):
            return None, False
        path = dst
    hook = verify if verify is not None else resolve_verify(cfg)
    if hook is None:
        return path, True
    try:
        keep = bool(hook(path, ctx or {}))
    except Exception as e:
        print("scenic: verify 异常，放行: %s" % e, file=sys.stderr)
        return path, True
    if not keep:
        if not cand.local:
            try:
                os.unlink(path)
            except OSError:
                pass
        return None, False
    return path, True
