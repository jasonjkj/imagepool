"""池逻辑：顺序消费 / 轮转(索引制) / exhausted 跳过 / 全败 / force / usage 记账。
pool.generate 走 CALL_MAP.get(p["name"])，测试 monkeypatch pool.CALL_MAP。"""
import json

from imagepool import pool


def _providers():
    return [
        {"name": "a", "endpoint": "e", "model": "m", "api_key_env": "K",
         "size_map": {}, "format": "openai", "free_quota": 0},
        {"name": "b", "endpoint": "e", "model": "m", "api_key_env": "K",
         "size_map": {}, "format": "openai", "free_quota": 0},
    ]


def _cfg():
    return {"pool_order": ["a", "b"], "providers": _providers()}


def _map(**fns):
    return fns


def test_ordered_active_respects_pool_order():
    assert [p["name"] for p in pool.ordered_active_providers(_cfg())] == ["a", "b"]


def test_ordered_active_skip_exhausted():
    cfg = _cfg()
    cfg["providers"][1]["exhausted"] = True
    assert [p["name"] for p in pool.ordered_active_providers(cfg)] == ["a"]


def test_ordered_active_unlisted_fall_after():
    cfg = _cfg()
    cfg["pool_order"] = ["zz"]
    assert [p["name"] for p in pool.ordered_active_providers(cfg)] == ["a", "b"]


def test_generate_success_advances_rr(monkeypatch):
    cfg = _cfg()
    calls = []

    def fa(p, prompt, size, n, negative):
        calls.append(p["name"])
        return {"urls": ["u"], "provider": p["name"], "model": "m"}

    def fb(p, prompt, size, n, negative):
        calls.append(p["name"])
        return {"urls": ["u"], "provider": p["name"], "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", _map(a=fa, b=fb))
    r = pool.generate("pos", cfg, size="square", rr=True)
    assert r["provider"] == "a"
    assert cfg["_rr_next"] == 1          # 成功后指针推进到下一家（整数索引）


def test_generate_skips_exhausted_and_succeeds(monkeypatch):
    cfg = _cfg()
    cfg["providers"][0]["exhausted"] = True
    calls = []

    def fb(p, prompt, size, n, negative):
        calls.append(p["name"])
        return {"urls": ["u"], "provider": "b", "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", _map(b=fb))
    r = pool.generate("pos", cfg)
    assert r["provider"] == "b"
    assert "a" not in calls


def test_generate_all_failed(monkeypatch):
    cfg = _cfg()

    def fbad(p, prompt, size, n, negative):
        return {"error": "x", "exhausted": False}
    monkeypatch.setattr(pool, "CALL_MAP", _map(a=fbad, b=fbad))
    r = pool.generate("pos", cfg)
    assert "error" in r
    assert len(r.get("details", [])) == 2


def test_generate_marks_exhausted_and_persists(monkeypatch, tmp_path):
    cfg = _cfg()
    rt = tmp_path / "r.json"

    def fa(p, prompt, size, n, negative):
        return {"error": "key 失效", "exhausted": True}

    def fb(p, prompt, size, n, negative):
        return {"urls": ["u"], "provider": "b", "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", _map(a=fa, b=fb))
    r = pool.generate("pos", cfg, runtime_path=str(rt))
    assert r["provider"] == "b"
    rt_data = json.loads(rt.read_text(encoding="utf-8"))
    assert rt_data["providers"]["a"]["exhausted"] is True


def test_generate_force_provider(monkeypatch):
    cfg = _cfg()

    def fb(p, prompt, size, n, negative):
        return {"urls": ["u"], "provider": "b", "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", _map(b=fb))
    r = pool.generate("pos", cfg, force_provider="b")
    assert r["provider"] == "b"
    assert cfg.get("_rr_next", 0) == 0   # force 模式不动轮转指针


def test_generate_unregistered_provider_skips(monkeypatch):
    cfg = _cfg()

    def fb(p, prompt, size, n, negative):
        return {"urls": ["u"], "provider": "b", "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", _map(b=fb))
    cfg["providers"][0]["name"] = "zz"   # a 改名为未注册名称
    r = pool.generate("pos", cfg)
    assert r["provider"] == "b"


def test_rr_start_name_respects_pointer():
    cfg = _cfg()
    cfg["_rr_next"] = 1
    assert pool.rr_start_name(cfg) == "b"
    cfg["_rr_next"] = 99
    assert pool.rr_start_name(cfg) == "b"  # 越界取模


def test_generate_passes_images_to_provider(monkeypatch):
    cfg = {"pool_order": ["ark"], "providers": [
        {"name": "ark", "endpoint": "e", "model": "m", "api_key_env": "K", "size_map": {}}]}
    seen = {}
    def fa(p, prompt, size, n, negative, images=None):
        seen["images"] = images; return {"urls": ["u"], "provider": "ark", "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", {"ark": fa})
    pool.generate("pos", cfg, images=["data:image/png;base64,AAAA"])
    assert seen["images"] == ["data:image/png;base64,AAAA"]


def test_generate_images_filter_unsupported(monkeypatch):
    cfg = {"pool_order": ["agnes", "ark"], "providers": [
        {"name": "agnes", "endpoint": "e", "model": "m", "api_key_env": "K", "size_map": {}},
        {"name": "ark", "endpoint": "e", "model": "m", "api_key_env": "K", "size_map": {}}]}
    called = []
    def fagnes(p, prompt, size, n, negative, images=None):
        called.append("agnes"); return {"urls": ["u"], "provider": "agnes", "model": "m"}
    def fark(p, prompt, size, n, negative, images=None):
        called.append("ark"); return {"urls": ["u"], "provider": "ark", "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", {"agnes": fagnes, "ark": fark})
    pool.generate("pos", cfg, images=["data:image/png;base64,AAAA"])
    assert called == ["ark"]


def test_generate_images_no_supporting_provider(monkeypatch):
    cfg = {"pool_order": ["agnes"], "providers": [
        {"name": "agnes", "endpoint": "e", "model": "m", "api_key_env": "K", "size_map": {}}]}
    r = pool.generate("pos", cfg, images=["data:image/png;base64,AAAA"])
    assert "error" in r


def test_generate_bad_image_path_errors(monkeypatch):
    cfg = {"pool_order": ["ark"], "providers": [
        {"name": "ark", "endpoint": "e", "model": "m", "api_key_env": "K", "size_map": {}}]}
    monkeypatch.setattr(pool, "CALL_MAP", {"ark": lambda *a, **k: {"urls": ["u"]}})
    r = pool.generate("pos", cfg, images=["/no/such/file.png"])
    assert "error" in r


def test_generate_text_only_calls_five_arg_provider(monkeypatch):
    cfg = _cfg()
    def fa(p, prompt, size, n, negative):        # 老式 5 参 double，证纯文生路径不变
        return {"urls": ["u"], "provider": "a", "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", _map(a=fa, b=fa))
    assert pool.generate("pos", cfg)["provider"] == "a"


def test_generate_images_with_rr_advances_pointer(monkeypatch):
    cfg = {"pool_order": ["ark", "b"], "providers": [
        {"name": "ark", "endpoint": "e", "model": "m", "api_key_env": "K", "size_map": {}},
        {"name": "b", "endpoint": "e", "model": "m", "api_key_env": "K", "size_map": {}}]}
    def fa(p, prompt, size, n, negative, images=None):
        return {"urls": ["u"], "provider": "ark", "model": "m"}
    monkeypatch.setattr(pool, "CALL_MAP", {"ark": fa, "b": lambda *a, **k: {"urls": ["u"]}})
    r = pool.generate("pos", cfg, images=["data:image/png;base64,AAAA"], rr=True)
    assert r["provider"] == "ark"
    assert cfg["_rr_next"] == 1


def test_generate_images_force_unsupported_named(monkeypatch):
    cfg = {"pool_order": ["agnes"], "providers": [
        {"name": "agnes", "endpoint": "e", "model": "m", "api_key_env": "K", "size_map": {}}]}
    r = pool.generate("pos", cfg, images=["data:image/png;base64,AAAA"], force_provider="agnes")
    assert "error" in r and "agnes" in r["error"]