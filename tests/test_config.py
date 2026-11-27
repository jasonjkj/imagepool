"""config 层：主配置 + runtime 拆分读写 + 未知键报错（结构校验，不查 env）。"""
import json

import pytest

from imagepool import config


@pytest.fixture
def minimal(tmp_path):
    cfg_path = tmp_path / "c.json"
    cfg_path.write_text(json.dumps({
        "pool_order": ["p1"],
        "providers": [{
            "name": "p1", "endpoint": "https://e.test/v1/images/generations",
            "model": "m-1", "api_key_env": "IP_TEST_KEY",
            "size_map": {"square": "1024x1024"}, "format": "openai",
        }],
    }), encoding="utf-8")
    return {"cfg": cfg_path}


def test_load_config_merges_runtime(minimal, tmp_path):
    (tmp_path / "r.json").write_text(json.dumps({
        "providers": {"p1": {"usage": {"total_calls": 3}, "exhausted": True}},
    }), encoding="utf-8")
    cfg = config.load_config(str(minimal["cfg"]), runtime_path=str(tmp_path / "r.json"))
    assert cfg["providers"][0]["usage"]["total_calls"] == 3
    assert cfg["providers"][0]["exhausted"] is True
    cfg2 = config.load_config(str(minimal["cfg"]))
    assert not cfg2["providers"][0].get("exhausted")   # 无 runtime sidecar：未耗尽


def test_save_config_splits_static_and_runtime(tmp_path):
    p = tmp_path / "c.json"
    cfg = {"pool_order": ["p1"], "providers": [{
        "name": "p1",
        "usage": {"total_calls": 1, "total_success": 1},
        "exhausted": False,
    }]}
    rt_path = tmp_path / "r.json"
    config.save_config(cfg, config_path=str(p), runtime_path=str(rt_path))
    static = json.loads(p.read_text(encoding="utf-8"))
    assert static["providers"][0]["name"] == "p1"
    assert "usage" not in static["providers"][0]   # 运行态不进主配置（git 干净）
    rt = json.loads(rt_path.read_text(encoding="utf-8"))
    assert rt["providers"]["p1"]["usage"]["total_calls"] == 1


def test_unknown_provider_field_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"pool_order": [], "providers": [{
        "name": "p1", "endpoint": "x", "model": "m",
        "unknown_extra": True,
    }]}), encoding="utf-8")
    with pytest.raises(config.ConfigError, match="未知键"):
        config.load_config(str(bad))


def test_unknown_top_field_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"pool_order": [], "providers": [], "zzz": 1}),
                   encoding="utf-8")
    with pytest.raises(config.ConfigError, match="未知顶层键"):
        config.load_config(str(bad))


def test_missing_required_provider_field_raises(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"pool_order": [], "providers": [{
        "name": "p1", "endpoint": "x",
    }]}), encoding="utf-8")
    with pytest.raises(config.ConfigError, match="缺 model"):
        config.load_config(str(bad))