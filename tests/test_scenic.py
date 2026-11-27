"""scenic 链式引擎测试（离线：不真网；链/启停/外部函数/验货/下载均用桩）。"""
import os

import pytest

from imagepool.scenic import engine, sources
from imagepool.scenic.contract import Candidate

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
EXT = os.path.join(TESTS_DIR, "_scenic_ext.py")


def ext_entry(fn):
    return "%s:%s" % (EXT, fn)


# —— 配置解析 ——


def test_load_config_missing_file_returns_empty():
    assert engine.load_config("/nonexistent/scenic-sources.yaml") == {}


def test_load_config_bad_yaml_returns_empty(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(": : : [ [", encoding="utf-8")
    assert engine.load_config(str(p)) == {}


def test_load_config_valid(tmp_path):
    p = tmp_path / "ok.yaml"
    p.write_text("version: 1\nchain: [a]\nlimit: 3\n", encoding="utf-8")
    cfg = engine.load_config(str(p))
    assert cfg["chain"] == ["a"]
    assert cfg["limit"] == 3


# —— 缺省配置路径语义（无 TRAVEL_HOME 假设） ——


def test_default_config_path_prefers_scenic_config(monkeypatch):
    monkeypatch.setenv("SCENIC_CONFIG", "/tmp/a.yaml")
    monkeypatch.setenv("IMAGEPOOL_SCENIC_CONFIG", "/tmp/b.yaml")
    assert engine.default_config_path() == "/tmp/a.yaml"


def test_default_config_path_falls_back_to_imagepool_env(monkeypatch):
    monkeypatch.delenv("SCENIC_CONFIG", raising=False)
    monkeypatch.setenv("IMAGEPOOL_SCENIC_CONFIG", "/tmp/b.yaml")
    assert engine.default_config_path() == "/tmp/b.yaml"


def test_default_config_path_empty_without_env(monkeypatch):
    monkeypatch.delenv("SCENIC_CONFIG", raising=False)
    monkeypatch.delenv("IMAGEPOOL_SCENIC_CONFIG", raising=False)
    assert engine.default_config_path() == ""


def test_load_config_no_default_returns_empty(monkeypatch):
    monkeypatch.delenv("SCENIC_CONFIG", raising=False)
    monkeypatch.delenv("IMAGEPOOL_SCENIC_CONFIG", raising=False)
    assert engine.load_config() == {}


def test_load_config_reads_imagepool_env(tmp_path, monkeypatch):
    p = tmp_path / "env.yaml"
    p.write_text("chain: [b]\n", encoding="utf-8")
    monkeypatch.delenv("SCENIC_CONFIG", raising=False)
    monkeypatch.setenv("IMAGEPOOL_SCENIC_CONFIG", str(p))
    assert engine.load_config()["chain"] == ["b"]


# —— resolve_entry ——


def test_resolve_entry_builtin():
    assert engine.resolve_entry("builtin:bing") is sources.bing_fetch
    assert engine.resolve_entry("builtin:nope") is None


def test_resolve_entry_path_function():
    assert callable(engine.resolve_entry(ext_entry("alpha")))
    assert engine.resolve_entry(ext_entry("nope")) is None
    assert engine.resolve_entry("/nonexistent.py:alpha") is None


def test_resolve_entry_bad_forms():
    assert engine.resolve_entry(None) is None
    assert engine.resolve_entry("nocolon") is None
    assert engine.resolve_entry(":func") is None
    assert engine.resolve_entry("mod:") is None


# —— 链顺序 / 启停 / 失败隔离 / 归一化 ——


def _cfg(chain, **provs):
    return {"chain": chain, "providers": provs}


def test_chain_order_follows_config():
    cfg = _cfg(["a", "b"], a={"entry": ext_entry("alpha")},
               b={"entry": ext_entry("alpha")})
    got = [c.source for c in engine.iter_candidates("x", {}, cfg)]
    assert got == ["a", "a", "b", "b"]


def test_disabled_provider_skipped():
    cfg = _cfg(["a", "b"],
               a={"entry": ext_entry("alpha"), "enabled": False},
               b={"entry": ext_entry("alpha")})
    got = [c.source for c in engine.iter_candidates("x", {}, cfg)]
    assert got == ["b", "b"]


def test_not_in_chain_ignored():
    cfg = _cfg(["a"], a={"entry": ext_entry("alpha")}, c={"entry": ext_entry("alpha")})
    got = [c.source for c in engine.iter_candidates("x", {}, cfg)]
    assert got == ["a", "a"]


def test_bad_entry_skipped():
    cfg = _cfg(["a", "b"], a={"entry": "builtin:nope"},
               b={"entry": ext_entry("alpha")})
    got = [c.source for c in engine.iter_candidates("x", {}, cfg)]
    assert got == ["b", "b"]


def test_provider_error_isolated():
    cfg = _cfg(["a", "b"], a={"entry": ext_entry("boom")},
               b={"entry": ext_entry("alpha")})
    got = [c.source for c in engine.iter_candidates("x", {}, cfg)]
    assert got == ["b", "b"]


def test_normalize_str_and_dict():
    cfg = _cfg(["a", "b"],
               a={"entry": ext_entry("alpha")},   # str
               b={"entry": ext_entry("local")})   # dict local
    cands = list(engine.iter_candidates("x", {}, cfg))
    assert cands[0].local is False and cands[0].ref.startswith("http")
    assert cands[2].local is True


def test_limit_caps_per_provider():
    cfg = _cfg(["a"], a={"entry": ext_entry("alpha")})
    cfg["limit"] = 1
    got = list(engine.iter_candidates("x", {}, cfg))
    assert len(got) == 1


def test_default_chain_when_no_cfg():
    got = list(engine.iter_candidates("x", {}, {}))
    assert got == []  # bing/pexels 需真网，离线返回空候选


# —— acquire / 下载 / 验货 ——


def test_acquire_local_no_verify(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)
    cand = Candidate(ref=str(img), source="persona", local=True)
    path, kept = engine.acquire(cand, str(tmp_path / "b.jpg"), {}, verify=None)
    assert kept is True and path == str(img)


def test_acquire_download_ok_offline(tmp_path):
    # file:// 直读本地小 jpg（改 min_bytes 阈值即可离线跑通下载+magic 闸门）
    img = tmp_path / "src.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    dst = tmp_path / "dst.jpg"
    ok = engine.download("file://" + str(img), str(dst), min_bytes=1)
    assert ok is True and dst.exists()
    # 大小闸门：过小 → False 不留残件
    tiny = tmp_path / "tiny.jpg"
    tiny.write_bytes(b"\xff\xd8\xff")
    bad = engine.download("file://" + str(tiny), str(tmp_path / "bad.jpg"), min_bytes=100)
    assert bad is False and not (tmp_path / "bad.jpg").exists()


def test_acquire_download_magic_reject(tmp_path):
    # 非图字节（如 HTML）→ magic 校验拒
    html = tmp_path / "page.jpg"
    html.write_bytes(b"<html><body>not image</body></html>" * 20)
    dst = tmp_path / "dst2.jpg"
    ok = engine.download("file://" + str(html), str(dst), min_bytes=1)
    assert ok is False and not dst.exists()


def test_acquire_verify_true_keeps(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)
    cand = Candidate(ref=str(img), source="p", local=True)
    path, kept = engine.acquire(cand, "", {}, verify=lambda p, c: True)
    assert kept is True and path == str(img)


def test_acquire_verify_false_drops_local_without_delete(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)
    cand = Candidate(ref=str(img), source="p", local=True)
    path, kept = engine.acquire(cand, "", {}, verify=lambda p, c: False)
    assert kept is False and path is None
    assert img.exists()  # 本地共享源不删


def test_acquire_verify_false_deletes_download(tmp_path):
    img = tmp_path / "src.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 64)
    dst = tmp_path / "dst.jpg"
    cand = Candidate(ref="file://" + str(img), source="p", local=False)
    path, kept = engine.acquire(cand, str(dst), {}, verify=lambda p, c: False)
    assert kept is False and path is None
    assert not dst.exists()  # 不落库


def test_acquire_verify_error_passes(tmp_path):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 16)
    cand = Candidate(ref=str(img), source="p", local=True)

    def boom(path, ctx):
        raise RuntimeError("vision down")

    path, kept = engine.acquire(cand, "", {}, verify=boom)
    assert kept is True  # 看不了就不验货 → 放行


def test_resolve_verify_from_cfg():
    cfg = {"hooks": {"verify": {"enabled": True, "entry": ext_entry("verify_ok")}}}
    assert callable(engine.resolve_verify(cfg))
    assert engine.resolve_verify({}) is None
    assert engine.resolve_verify(
        {"hooks": {"verify": {"enabled": False, "entry": ext_entry("verify_ok")}}}) is None


# —— 内置 source（离线部分） ——


def test_local_dir_fetch_flat_and_nested(tmp_path):
    (tmp_path / "flat.jpg").write_bytes(b"\xff\xd8\xff")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "inner.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "sub" / "readme.txt").write_text("no", encoding="utf-8")
    got = sources.local_dir_fetch("x", {}, {"dir": str(tmp_path)})
    refs = sorted(c["ref"] for c in got)
    assert any(r.endswith("flat.jpg") for r in refs)
    assert any(r.endswith("inner.png") for r in refs)
    assert all(c["local"] for c in got)


def test_local_dir_fetch_missing_dir():
    assert sources.local_dir_fetch("x", {}, {"dir": "/nonexistent"}) == []


def test_pexels_no_key_returns_empty(monkeypatch):
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    assert sources.pexels_fetch("x", {}, {}) == []
