"""配置契约：文档化的 JSON schema（README §4/§7）+ `api_key_env` 环境变量契约。

补 test_config.py 未覆盖的：schema 常量与文档一致、`_note` 顶层键、运行态顶层字段
（`_rr_next`/`_updated`）合并、`api_key_env` 真实从 `os.environ` 取值（脱敏红线：配置只存变量名）。
"""
import json

from imagepool import _net, config, protocols

TOP_KEYS = {"pool_order", "providers", "_note"}
PROVIDER_KEYS = {"name", "endpoint", "model", "api_key_env", "free_quota",
                 "timeout", "description", "size_map", "format", "output_format"}
RUNTIME_TOP_KEYS = {"_rr_next", "_updated"}
RUNTIME_PROVIDER_KEYS = {"usage", "exhausted"}


def test_documented_schema_matches_source():
    assert config._TOP_KEYS == TOP_KEYS
    assert config._PROVIDER_KEYS == PROVIDER_KEYS
    assert set(config._RUNTIME_TOP_KEYS) == RUNTIME_TOP_KEYS
    assert set(config._RUNTIME_PROVIDER_KEYS) == RUNTIME_PROVIDER_KEYS


def test_note_is_allowed_top_key(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"_note": "脱敏说明", "pool_order": [], "providers": []}),
                 encoding="utf-8")
    assert config.load_config(str(p))["_note"] == "脱敏说明"


def test_api_key_env_field_is_allowed_provider_key(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"pool_order": ["p1"], "providers": [
        {"name": "p1", "endpoint": "https://e.test/v1/images/generations",
         "model": "m", "api_key_env": "IP_CONTRACT_KEY"}]}), encoding="utf-8")
    cfg = config.load_config(str(p))
    assert cfg["providers"][0]["api_key_env"] == "IP_CONTRACT_KEY"


def test_runtime_merges_top_level_rr_next(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"pool_order": ["p1"], "providers": [
        {"name": "p1", "endpoint": "e", "model": "m", "api_key_env": "K"}]}), encoding="utf-8")
    r = tmp_path / "r.json"
    r.write_text(json.dumps({"_rr_next": 2, "_updated": "2026-01-01T00:00:00+00:00"}),
                 encoding="utf-8")
    cfg = config.load_config(str(p), runtime_path=str(r))
    assert cfg["_rr_next"] == 2
    assert cfg["_updated"] == "2026-01-01T00:00:00+00:00"


def test_api_key_env_reads_os_environ(monkeypatch):
    """`api_key_env` 是环境变量名：真实 key 经 os.environ 注入 Authorization，绝不下库。"""
    monkeypatch.setenv("IP_CONTRACT_KEY", "sekret-value")
    captured = {}

    def fake(url, payload, headers, timeout=60):
        captured.update(headers)
        return 200, '{"data": [{"url": "https://i.test/x.png"}]}'

    monkeypatch.setattr(_net, "_post_json", fake)
    p = {"name": "agnes", "endpoint": "https://e.test/v1/images/generations",
         "model": "m", "api_key_env": "IP_CONTRACT_KEY", "size_map": {}}
    r = protocols.call_agnes(p, "pos", "square")
    assert r["urls"] == ["https://i.test/x.png"]
    assert captured["Authorization"] == "Bearer sekret-value"


def test_api_key_env_missing_yields_unconfigured(monkeypatch):
    monkeypatch.delenv("IP_CONTRACT_MISSING", raising=False)
    p = {"name": "agnes", "endpoint": "e", "model": "m",
         "api_key_env": "IP_CONTRACT_MISSING", "size_map": {}}
    r = protocols.call_agnes(p, "pos", "square")
    assert "未配置" in r["error"]
    assert r["exhausted"] is False
