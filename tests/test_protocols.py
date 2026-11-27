"""协议层：各 provider 响应解析 + exhausted 分类（迁移自旧 call_*，仅 HTTP 接线变化）。

全 mock：patch imagepool._net._post_json（各 call_* 以 from imagepool import _net
引用，patch 才会真正拦截），零真网零真 key。
"""
import pytest

from imagepool import _net
from imagepool import protocols


@pytest.fixture(autouse=True)
def key(monkeypatch):
    monkeypatch.setenv("IP_KEY", "testkey")


def _mock_post(monkeypatch, status, body):
    def fake(url, payload, headers, timeout=60):
        return status, body
    monkeypatch.setattr(_net, "_post_json", fake)


def _p(fmt):
    return {"name": fmt, "endpoint": "https://e.test/v1/images/generations",
            "model": "m", "api_key_env": "IP_KEY",
            "size_map": {"portrait": "P", "landscape": "L", "square": "S"},
            "format": fmt}


def test_call_qwen_output_results(monkeypatch):
    _mock_post(monkeypatch, 200, '{"output": {"results": ["https://i.test/q.png"]}}')
    r = protocols.call_qwen(_p("qwen"), "pos", "square")
    assert r["urls"] == ["https://i.test/q.png"]
    assert r["provider"] == "qwen"


def test_call_qwen_passes_negative(monkeypatch):
    captured = {}

    def fake(url, payload, headers, timeout=60):
        captured.update(payload)
        return 200, '{"output": {"results": ["u.png"]}}'
    monkeypatch.setattr(_net, "_post_json", fake)
    protocols.call_qwen(_p("qwen"), "pos", "square", negative="nope")
    assert captured["parameters"]["negative_prompt"] == "nope"


def test_call_qwen_key_missing(monkeypatch):
    monkeypatch.delenv("IP_KEY")
    r = protocols.call_qwen(_p("qwen"), "pos", "square")
    assert "error" in r and r["exhausted"] is False


def test_call_qwen_401_exhausted(monkeypatch):
    _mock_post(monkeypatch, 401, "unauthorized")
    r = protocols.call_qwen(_p("qwen"), "pos", "square")
    assert "error" in r and r["exhausted"] is True


def test_call_qwen_433_not_exhausted(monkeypatch):
    _mock_post(monkeypatch, 433, "daily quota")
    r = protocols.call_qwen(_p("qwen"), "pos", "square")
    assert r["exhausted"] is False


def test_call_doubao_200(monkeypatch):
    _mock_post(monkeypatch, 200, '{"data": [{"url": "https://i.test/d.png"}]}')
    r = protocols.call_doubao(_p("doubao"), "pos", "square")
    assert r["urls"] == ["https://i.test/d.png"]


def test_call_doubao_quota_exhausted(monkeypatch):
    _mock_post(monkeypatch, 400, '{"error": {"message": "quota exhausted"}}')
    r = protocols.call_doubao(_p("doubao"), "pos", "square")
    assert "error" in r and r["exhausted"] is True


def test_call_sensenova_b64_data_uri(monkeypatch):
    _mock_post(monkeypatch, 200, '{"data": [{"b64_json": "AAAA"}]}')
    r = protocols.call_sensenova(_p("sensenova"), "pos", "square")
    assert r["urls"][0].startswith("data:image/png;base64,")


def test_call_sensenova_401_exhausted(monkeypatch):
    _mock_post(monkeypatch, 401, "bad key")
    r = protocols.call_sensenova(_p("sensenova"), "pos", "square")
    assert r["exhausted"] is True


def test_call_agnes_200(monkeypatch):
    _mock_post(monkeypatch, 200, '{"data": [{"url": "https://i.test/a.png"}]}')
    r = protocols.call_agnes(_p("agnes"), "pos", "square")
    assert r["urls"] == ["https://i.test/a.png"]


def test_call_agnes_429_not_exhausted(monkeypatch):
    _mock_post(monkeypatch, 429, "rate limit")
    r = protocols.call_agnes(_p("agnes"), "pos", "square")
    assert "error" in r and r["exhausted"] is False


def test_call_ark_200(monkeypatch):
    _mock_post(monkeypatch, 200, '{"data": [{"url": "https://i.test/ark.png"}]}')
    r = protocols.call_ark(_p("ark"), "pos", "square")
    assert r["urls"] == ["https://i.test/ark.png"]


def test_call_ark_429_exhausted(monkeypatch):
    _mock_post(monkeypatch, 429, "rate limited")
    r = protocols.call_ark(_p("ark"), "pos", "square")
    assert r["exhausted"] is True


def test_default_size_map_fallback(monkeypatch):
    _mock_post(monkeypatch, 200, '{"data": [{"url": "https://i.test/x.png"}]}')
    p = _p("agnes")
    p["size_map"] = {}
    r = protocols.call_agnes(p, "portrait", "square")
    assert r["urls"] == ["https://i.test/x.png"]


def test_network_exception_error_dict(monkeypatch):
    def fake(url, payload, headers, timeout=60):
        raise ConnectionError("boom")
    monkeypatch.setattr(_net, "_post_json", fake)
    r = protocols.call_agnes(_p("agnes"), "pos", "square")
    assert "error" in r and r["exhausted"] is False


def test_ark_injects_image_field(monkeypatch):
    captured = {}
    def fake(url, payload, headers, timeout=60):
        captured.update(payload); return 200, '{"data":[{"url":"u"}]}'
    monkeypatch.setattr(_net, "_post_json", fake)
    protocols.call_ark(_p("ark"), "pos", "square", images=["data:image/png;base64,AAAA"])
    assert captured["image"] == ["data:image/png;base64,AAAA"]
    assert captured["sequential_image_generation"] == "disabled"


def test_ark_without_images_has_no_image_field(monkeypatch):
    captured = {}
    def fake(url, payload, headers, timeout=60):
        captured.update(payload); return 200, '{"data":[{"url":"u"}]}'
    monkeypatch.setattr(_net, "_post_json", fake)
    protocols.call_ark(_p("ark"), "pos", "square")
    assert "image" not in captured


def test_call_ark_omits_output_format_by_default(monkeypatch):
    captured = {}
    def fake(url, payload, headers, timeout=60):
        captured.update(payload); return 200, '{"data":[{"url":"u"}]}'
    monkeypatch.setattr(_net, "_post_json", fake)
    protocols.call_ark(_p("ark"), "pos", "square")
    assert "output_format" not in captured


def test_call_ark_sends_output_format_when_configured(monkeypatch):
    captured = {}
    def fake(url, payload, headers, timeout=60):
        captured.update(payload); return 200, '{"data":[{"url":"u"}]}'
    monkeypatch.setattr(_net, "_post_json", fake)
    p = _p("ark"); p["output_format"] = "png"
    protocols.call_ark(p, "pos", "square")
    assert captured["output_format"] == "png"


def test_ark_seedream5_skips_sequential(monkeypatch):
    # Seedream 5.0（Agent Plan 端点）不支持 sequential_image_generation → 不带
    captured = {}
    def fake(url, payload, headers, timeout=60):
        captured.update(payload); return 200, '{"data":[{"url":"u"}]}'
    monkeypatch.setattr(_net, "_post_json", fake)
    p = _p("ark"); p["model"] = "doubao-seedream-5-0-pro-260628"
    protocols.call_ark(p, "pos", "square", images=["data:image/png;base64,AAAA"])
    assert captured["image"] == ["data:image/png;base64,AAAA"]
    assert "sequential_image_generation" not in captured


def test_ark_seedream4_keeps_sequential(monkeypatch):
    # Seedream 4.5 需要 sequential_image_generation=disabled（单图）
    captured = {}
    def fake(url, payload, headers, timeout=60):
        captured.update(payload); return 200, '{"data":[{"url":"u"}]}'
    monkeypatch.setattr(_net, "_post_json", fake)
    p = _p("ark"); p["model"] = "doubao-seedream-4-5-251128"
    protocols.call_ark(p, "pos", "square", images=["data:image/png;base64,AAAA"])
    assert captured["sequential_image_generation"] == "disabled"


def test_ark_sensitive_block_not_exhausted(monkeypatch):
    # 内容安全审核拦截（400 + InputImageSensitiveContentDetected）= 单次失败，不报废 provider
    _mock_post(monkeypatch, 400,
               '{"error":{"code":"InputImageSensitiveContentDetected","message":"sensitive input"}}')
    r = protocols.call_ark(_p("ark"), "pos", "square", images=["data:image/png;base64,AAAA"])
    assert "error" in r and r["exhausted"] is False
    assert "安全审核拦截" in r["error"]


def test_doubao_sensitive_block_not_exhausted(monkeypatch):
    _mock_post(monkeypatch, 400,
               '{"error":{"code":"InputImageSensitiveContentDetected","message":"sensitive"}}')
    r = protocols.call_doubao(_p("doubao"), "pos", "square")
    assert "error" in r and r["exhausted"] is False


def test_supports_image_input():
    assert protocols.supports_image_input("ark")
    assert protocols.supports_image_input("sensenova")
    assert not protocols.supports_image_input("agnes")


def test_call_sensenova_edits_payload(monkeypatch):
    captured = {}

    def fake(url, payload, headers, timeout=60):
        captured.update({"url": url, "payload": payload})
        return 200, '{"data":[{"url":"https://i.test/s.png"}]}'
    monkeypatch.setattr(_net, "_post_json", fake)
    protocols.call_sensenova(_p("sensenova"), "pos", "square",
                             images=["data:image/png;base64,AAAA"])
    assert captured["url"].endswith("/images/edits")
    assert captured["payload"]["images"] == [{"image_url": "data:image/png;base64,AAAA"}]
    assert captured["payload"]["size"] == "auto"
    assert captured["payload"]["watermark"] is False


def test_call_sensenova_without_images_uses_generations(monkeypatch):
    captured = {}

    def fake(url, payload, headers, timeout=60):
        captured.update({"url": url, "payload": payload})
        return 200, '{"data":[{"url":"https://i.test/s.png"}]}'
    monkeypatch.setattr(_net, "_post_json", fake)
    protocols.call_sensenova(_p("sensenova"), "pos", "square")
    assert captured["url"].endswith("/images/generations")
    assert "images" not in captured["payload"]