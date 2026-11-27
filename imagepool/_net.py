"""HTTP 接线圈（迁移改造点）：旧 image_gen.py 用 requests，本包零第三方依赖，全走 stdlib。

返回 (status_code:int, body:str)。HTTPError 不抛——调用方按旧逻辑判定 4xx/5xx 语义。
网络异常 → (0, 异常文本)，与旧 requests 抛异常被 except 捕获的语义等价。
"""
import json
import urllib.error
import urllib.request


def _post_json(url, payload, headers, timeout=60):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers=dict(headers), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # 连接失败/超时/非法响应 → (0, str(e))
        return 0, str(e)


def _get_bytes(url, timeout=30):
    """下载字节流；失败/非 200 → None（旧 requests.get 非 200 走 return None）。"""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.read()
    except Exception:
        return None