"""池逻辑（迁移自旧 image_gen.py 行 122-155 + 337-391）。

顺序消费 / _rr_next 整型索引轮转 / exhausted 跳过 / usage 记账语义原样。唯一接线：
config 拆分走 imagepool.config，落盘走 imagepool.storage，路径全部入参。
"""
from datetime import datetime, timezone

from imagepool import protocols
from imagepool.config import save_config
from imagepool.protocols import CALL_MAP
from imagepool.storage import save_image, to_data_uri


def active_providers(cfg):
    return [p for p in cfg.get("providers", []) if not p.get("exhausted", False)]


def ordered_active_providers(cfg):
    """按 pool_order 声明顺序返回可用 provider（不在池子的排后面兜底）。"""
    by_name = {p["name"]: p for p in cfg.get("providers", [])}
    out = []
    for name in cfg.get("pool_order", []):
        p = by_name.get(name)
        if p and not p.get("exhausted", False):
            out.append(p)
    seen = {p["name"] for p in out}
    for p in cfg.get("providers", []):
        if p["name"] not in seen and not p.get("exhausted", False):
            out.append(p)
    return out


def rr_start_name(cfg):
    """轮转起点：_rr_next 是整型索引，指向 pool_order 第 idx 家（越界取模）。"""
    pool_order = cfg.get("pool_order", [])
    if not pool_order:
        return None
    idx = int(cfg.get("_rr_next", 0) or 0) % len(pool_order)
    return pool_order[idx]


def rr_advance(cfg, provider_name):
    """轮转推进：指针移到成功者的下一个（写 cfg['_rr_next'] 整数索引，由调用方落盘）。"""
    pool_order = cfg.get("pool_order", [])
    if provider_name in pool_order:
        cfg["_rr_next"] = (pool_order.index(provider_name) + 1) % len(pool_order)


def generate(prompt, cfg, config_path=None, runtime_path=None, out_dir=".", size="square",
             n=1, negative="", force_provider=None, rr=False, images=None):
    """顺序消费池生成一图。成功 → {urls, provider, model, local}；全败 → {error, details}。

    传入 images（参考图）时为图生图：归一化后仅保留支持图生图的 provider。"""
    providers = cfg.get("providers", [])

    def _provider_by_name(name):
        for p in providers:
            if p.get("name") == name:
                return p
        return None

    if force_provider:
        order = [_provider_by_name(force_provider)]
    else:
        order = ordered_active_providers(cfg)
        # 轮转模式：从上次成功者的下一个 provider 起步（人人有机会，交替消耗）
        if rr and order:
            start = rr_start_name(cfg)
            names = [p["name"] for p in order]
            if start in names:
                i = names.index(start)
                order = order[i:] + order[:i]

    norm = None
    if images:
        try:
            norm = [to_data_uri(s) for s in images]
        except OSError as e:
            return {"error": f"输入图不可读: {e}"}
        order = [p for p in order if p is not None and protocols.supports_image_input(p["name"])]
        if not order:
            if force_provider:
                return {"error": f"强制 provider 不支持图生图: {force_provider}"}
            return {"error": "无可用的图生图 provider"}

    if not order or not any(order):
        return {"error": "所有 provider 均已耗尽"}

    errors = []
    for p in order:
        if p is None:
            errors.append(f"未知 provider: {force_provider}")
            continue
        fn = CALL_MAP.get(p["name"])
        if not fn:
            # 未注册：skip 继续（旧逻辑 errors.append + continue，不中断整池）
            errors.append(f"{p['name']}: 未注册")
            continue

        result = fn(p, prompt, size, n, negative, images=norm) if images \
            else fn(p, prompt, size, n, negative)

        # 记录调用
        usage = p.setdefault("usage", {})
        usage["total_calls"] = usage.get("total_calls", 0) + 1
        usage["last_used"] = datetime.now(timezone.utc).isoformat()

        if "urls" in result:
            usage["total_success"] = usage.get("total_success", 0) + 1
            cfg["_updated"] = usage["last_used"]
            if rr and not force_provider:
                rr_advance(cfg, p["name"])
            save_config(cfg, config_path=config_path, runtime_path=runtime_path)
            # 下载图片到本地
            if result["urls"]:
                local = save_image(result["urls"][0], p["name"], out_dir=out_dir)
                if local:
                    result["local"] = local
            return result

        if result.get("exhausted"):
            p["exhausted"] = True
            errors.append(f"{p['name']}: 已耗尽 → 跳过")
            save_config(cfg, config_path=config_path, runtime_path=runtime_path)
            continue

        errors.append(f"{p['name']}: {result.get('error', '失败')}")
        save_config(cfg, config_path=config_path, runtime_path=runtime_path)

    return {"error": "所有 provider 均失败", "details": errors}