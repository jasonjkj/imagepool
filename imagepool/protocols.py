"""协议层 call_*（迁移自旧 image_gen.py call_qwen/…/call_ark，157-295 行，逐行复制）。

唯一接线改动：requests.post(...) → _net._post_json(endpoint, payload, headers, timeout)。
判定语义（200 解析 / 401 key 失效耗尽 / 429 限流不禁用 / 400・quota・exhausted → 耗尽）
与旧代码完全一致；call_qwen 独特 433（日配额用完不禁用）保留。
"""
from imagepool import _net

DEFAULT_SIZE_MAP = {"portrait": "2048x2048", "landscape": "2048x2048", "square": "2048x2048"}


def _key(p):
    """api_key_env 对应环境变量取值（空 → 由各 call_* 判"未配置"）。"""
    import os
    return os.environ.get(p["api_key_env"], "")


def call_qwen(p, prompt, size, n=1, negative="", images=None):
    key = _key(p)
    if not key:
        return {"error": f"{p['api_key_env']} 未配置", "exhausted": False}
    size_map = p.get("size_map", DEFAULT_SIZE_MAP)
    payload = {
        "model": p["model"],
        "input": {"prompt": prompt},
        "parameters": {"prompt_extend": True, "watermark": False, "size": size_map.get(size, DEFAULT_SIZE_MAP["square"]), "n": n},
    }
    if negative:
        payload["parameters"]["negative_prompt"] = negative
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    try:
        status, text = _net._post_json(p["endpoint"], payload, headers, p.get("timeout", 60))
        if status == 200:
            results = json_loads(text).get("output", {}).get("results", [])
            if results:
                return {"urls": results, "provider": p["name"], "model": p["model"]}
            return {"error": f"无图片: {text[:200]}", "exhausted": False}
        if status == 401: return {"error": "key 失效", "exhausted": True}
        if status == 433: return {"error": "日配额用完", "exhausted": False}
        return {"error": f"HTTP {status}: {text[:200]}", "exhausted": False}
    except Exception as e:
        return {"error": str(e), "exhausted": False}


def call_doubao(p, prompt, size, n=1, negative="", images=None):
    key = _key(p)
    if not key:
        return {"error": f"{p['api_key_env']} 未配置", "exhausted": False}
    size_map = p.get("size_map", DEFAULT_SIZE_MAP)
    payload = {"model": p["model"], "prompt": prompt, "n": n, "size": size_map.get(size, DEFAULT_SIZE_MAP["square"])}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    try:
        status, text = _net._post_json(p["endpoint"], payload, headers, p.get("timeout", 60))
        if status == 200:
            urls = [item["url"] for item in json_loads(text).get("data", [])]
            if urls: return {"urls": urls, "provider": p["name"], "model": p["model"]}
            return {"error": f"无图片: {text[:200]}", "exhausted": False}
        err = text.lower()
        if "inputimagesensitivecontentdetected" in err:
            # 内容安全审核拦截：单次失败，不是额度耗尽——不报废 provider
            # （否则一张敏感参考图就把整个源锁死，换正常图也用不了）
            return {"error": f"输入图被安全审核拦截: {text[:200]}", "exhausted": False}
        if status in (400, 402, 429) or any(k in err for k in ["quota", "exhausted", "insufficient"]):
            return {"error": f"已耗尽: {text[:200]}", "exhausted": True}
        return {"error": f"HTTP {status}: {text[:200]}", "exhausted": False}
    except Exception as e:
        return {"error": str(e), "exhausted": False}


def call_sensenova(p, prompt, size, n=1, negative="", images=None):
    key = _key(p)
    if not key:
        return {"error": f"{p['api_key_env']} 未配置", "exhausted": False}
    size_map = p.get("size_map", DEFAULT_SIZE_MAP)
    endpoint = p["endpoint"]
    if images:
        # 图生图：参考图编辑接口 /v1/images/edits（pool 已把参考图归一化为 data URI）
        endpoint = p.get("edit_endpoint") or endpoint.replace(
            "/images/generations", "/images/edits")
        payload = {
            "model": p["model"],
            "images": [{"image_url": u} for u in images],
            "prompt": prompt,
            "n": n,
            "size": "auto",
            "watermark": False,
            "prompt_extend": True,
        }
    else:
        payload = {"model": p["model"], "prompt": prompt, "n": n,
                   "size": size_map.get(size, DEFAULT_SIZE_MAP["square"])}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    try:
        status, text = _net._post_json(endpoint, payload, headers, p.get("timeout", 60))
        if status == 200:
            urls = []
            for item in json_loads(text).get("data", []):
                if "url" in item:
                    urls.append(item["url"])
                elif "b64_json" in item:
                    urls.append(f"data:image/png;base64,{item['b64_json']}")
            if urls: return {"urls": urls, "provider": p["name"], "model": p["model"]}
            return {"error": f"无图片: {text[:200]}", "exhausted": False}
        if status == 401: return {"error": "key 失效", "exhausted": True}
        return {"error": f"HTTP {status}: {text[:200]}", "exhausted": False}
    except Exception as e:
        return {"error": str(e), "exhausted": False}


def call_agnes(p, prompt, size, n=1, negative="", images=None):
    key = _key(p)
    if not key:
        return {"error": f"{p['api_key_env']} 未配置", "exhausted": False}
    size_map = p.get("size_map", DEFAULT_SIZE_MAP)
    payload = {"model": p["model"], "prompt": prompt, "n": n, "size": size_map.get(size, DEFAULT_SIZE_MAP["square"])}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    try:
        status, text = _net._post_json(p["endpoint"], payload, headers, p.get("timeout", 30))
        if status == 200:
            urls = [item["url"] for item in json_loads(text).get("data", [])]
            if urls: return {"urls": urls, "provider": p["name"], "model": p["model"]}
            return {"error": f"无图片: {text[:200]}", "exhausted": False}
        if status == 401: return {"error": "key 失效", "exhausted": True}
        if status == 429: return {"error": "限流", "exhausted": False}
        return {"error": f"HTTP {status}: {text[:200]}", "exhausted": False}
    except Exception as e:
        return {"error": str(e), "exhausted": False}


def call_ark(p, prompt, size, n=1, negative="", images=None):
    """火山方舟图像生成（标准端点 /api/v3 与 Agent Plan 端点 /api/plan/v3 共用）。
    可用模型取决于端点与账号开通：Agent Plan 端点现仅收 5.0-pro；标准端点支持 4.5 / 5.0-pro 等。
    size 可为像素档（如 1440x2560）或分辨率档；OpenAI 兼容解析 data[].url。"""
    key = _key(p)
    if not key:
        return {"error": f"{p['api_key_env']} 未配置", "exhausted": False}
    size_map = p.get("size_map", DEFAULT_SIZE_MAP)
    payload = {
        "model": p["model"],
        "prompt": prompt,
        "n": n,
        "size": size_map.get(size, DEFAULT_SIZE_MAP["square"]),
        "watermark": False,
    }
    # output_format 按配置发送：Seedream 4.5 不支持该参数（发送即 400 InvalidParameter），
    # 未配置一律不发，仅在显式配置时才带上。
    if p.get("output_format"):
        payload["output_format"] = p["output_format"]
    if images:
        payload["image"] = list(images)
        # Seedream 5.0（Agent Plan 端点）不支持 sequential_image_generation（传了报
        # InvalidParameter）；4.0/4.5 需要 disabled 走单图（避免默认组图）。按模型适配。
        if not _is_seedream_5(p["model"]):
            payload["sequential_image_generation"] = "disabled"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    try:
        status, text = _net._post_json(p["endpoint"], payload, headers, p.get("timeout", 60))
        if status == 200:
            urls = [item["url"] for item in json_loads(text).get("data", [])]
            if urls: return {"urls": urls, "provider": p["name"], "model": p["model"]}
            return {"error": f"无图片: {text[:200]}", "exhausted": False}
        err = text.lower()
        if "inputimagesensitivecontentdetected" in err:
            # 内容安全审核拦截：单次失败，不是额度耗尽——不报废 provider
            # （否则一张敏感参考图就把整个源锁死，换正常图也用不了）
            return {"error": f"输入图被安全审核拦截: {text[:200]}", "exhausted": False}
        if status in (400, 402, 429) or any(k in err for k in ["quota", "exhausted", "insufficient"]):
            return {"error": f"已耗尽: {text[:200]}", "exhausted": True}
        return {"error": f"HTTP {status}: {text[:200]}", "exhausted": False}
    except Exception as e:
        return {"error": str(e), "exhausted": False}


CALL_MAP = {
    "qwen": call_qwen,
    "doubao": call_doubao,
    "ark": call_ark,
    "sensenova": call_sensenova,
    "agnes": call_agnes,
}

IMAGE_INPUT_PROVIDERS = {"ark", "sensenova"}


def _is_seedream_5(model):
    """Seedream 5.x 判定：模型 ID 含 5-0 / 5.0（4.5 不含，不会误判）。"""
    m = (model or "").lower()
    return "5-0" in m or "5.0" in m


def supports_image_input(name):
    """该 provider 是否支持把输入参考图喂给模型（图生图）。"""
    return name in IMAGE_INPUT_PROVIDERS


def json_loads(text):
    """响应体解析（调用方 try/except 兜底，与旧 r.json() 语义等价）。"""
    import json
    return json.loads(text)