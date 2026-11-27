import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_mcp_requirements_file_exists():
    with open(os.path.join(ROOT, "requirements-mcp.txt"), encoding="utf-8") as f:
        assert "mcp" in f.read()


def test_pyproject_declares_mcp_optional():
    with open(os.path.join(ROOT, "pyproject.toml"), encoding="utf-8") as f:
        text = f.read()
    assert "optional-dependencies" in text and "mcp" in text


def test_mcp_server_importable_when_mcp_installed():
    import pytest
    pytest.importorskip("mcp")
    spec = importlib.util.spec_from_file_location("ip_mcp", os.path.join(ROOT, "mcp_server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.main)


def _load_server():
    import pytest
    pytest.importorskip("mcp")
    spec = importlib.util.spec_from_file_location("ip_mcp2", os.path.join(ROOT, "mcp_server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _empty_pool_config(tmp_path):
    p = tmp_path / "pool.json"
    p.write_text('{"pool_order": [], "providers": []}', encoding="utf-8")
    return str(p)


def test_build_craft_tool_returns_craft():
    mod = _load_server()
    out = mod.imagepool_build_craft(
        '{"expression_block": "温柔浅笑", "context_sentence": "在西湖边。"}')
    assert "【合规】" in out and "【画面】" in out


def test_generate_tool_wires_pool_config(tmp_path):
    # 回归：旧实现直接调 generate(prompt) 会 TypeError（generate 需 cfg）。
    mod = _load_server()
    out = mod.imagepool_generate("a prompt", config_path=_empty_pool_config(tmp_path))
    assert "error" in out  # 空池优雅报错，而非崩在签名上


def test_render_tool_wires_pool_config(tmp_path):
    mod = _load_server()
    out = mod.imagepool_render(
        '{"expression_block": "温柔浅笑", "context_sentence": "在西湖边。"}',
        config_path=_empty_pool_config(tmp_path))
    assert "error" in out


def test_mcp_generate_forwards_images(monkeypatch):
    import mcp_server, imagepool.pool as _pool
    captured = {}
    def fake_gen(prompt, cfg, config_path=None, out_dir=".", **kw):
        captured.update(kw); return {"urls": ["u"], "provider": "ark", "model": "m"}
    monkeypatch.setattr(_pool, "generate", fake_gen)
    monkeypatch.setenv("IMAGEPOOL_CONFIG", "x.json")
    monkeypatch.setattr(mcp_server._config, "load_config", lambda p: {"pool_order": [], "providers": []})
    mcp_server.imagepool_generate("pos", images_json='["data:image/png;base64,AAAA"]')
    assert captured.get("images") == ["data:image/png;base64,AAAA"]
