"""端到端黑盒 e2e：CLI 级入口 + craft 全链（门禁→拆段→组装→渲染）。

真实走 CLI（`imagepool.__main__.main`）与编排 API；唯一被替换的是「出图 provider」
（monkeypatch 注入固定响应，返回 data URI），全程不打真实网络 / 不用真 key。
每个用例用 tmp_path 隔离，配置从仓内 example 复制而来，绝不写回仓库。
"""
import base64
import json
import os

import pytest

from imagepool import __main__
from imagepool import pool as imagepool_pool
from imagepool import _net
from imagepool import orchestrator
from imagepool.contract import ShotSpec
from imagepool.craft import gate, split

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXAMPLE_CONFIG = os.path.join(ROOT, "config.example.json")
EXAMPLE_RUNTIME = os.path.join(ROOT, "runtime.example.json")


class NetworkForbidden(BaseException):
    """网络拦网：BaseException 不被 provider 的 except Exception 吞掉。"""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def _boom(*a, **k):
        raise NetworkForbidden("e2e 禁止真实网络请求")
    monkeypatch.setattr(_net, "_post_json", _boom)
    monkeypatch.setattr(_net, "_get_bytes", _boom)


@pytest.fixture
def pool_paths(tmp_path):
    cfg = tmp_path / "config.json"
    rt = tmp_path / "runtime.json"
    cfg.write_bytes(open(EXAMPLE_CONFIG, "rb").read())
    rt.write_bytes(open(EXAMPLE_RUNTIME, "rb").read())
    return cfg, rt


def _fake_provider(name="ark"):
    """固定响应 provider：返回 data URI，落盘不触网。"""
    calls = []

    def fake(p, prompt, size, n=1, negative="", images=None):
        calls.append({"name": p["name"], "prompt": prompt, "size": size,
                      "negative": negative, "images": images})
        b64 = base64.b64encode(b"fake-image-bytes").decode()
        return {"urls": [f"data:image/png;base64,{b64}"],
                "provider": p["name"], "model": p["model"]}

    return fake, calls


def _person_spec():
    return ShotSpec(
        expression_block="温柔浅笑",
        context_sentence="在杭州西湖边的咖啡馆。",
        shot_override="medium",
        outfit_block="白色真丝衬衫",
        style="时尚职业写真",
        size="portrait",
    )


def test_e2e_list_providers_exit0(pool_paths, capsys):
    cfg, rt = pool_paths
    rc = __main__.main(["--config", str(cfg), "--runtime", str(rt), "--list-providers"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "池子顺序" in out
    assert "ark" in out
    assert "✅ 可用" in out


def test_e2e_state_exit0(pool_paths, capsys):
    cfg, rt = pool_paths
    rc = __main__.main(["--config", str(cfg), "--runtime", str(rt), "--state"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "池子状态" in out
    assert "ark" in out


def test_e2e_dry_run_exit0(pool_paths, capsys):
    cfg, rt = pool_paths
    rc = __main__.main(["--config", str(cfg), "--runtime", str(rt), "--dry-run", "--size", "portrait"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "预览" in out
    assert "ark" in out


def test_e2e_craft_chain_build_split_gate_then_cli_render(pool_paths, tmp_path,
                                                           monkeypatch, capsys):
    cfg, rt = pool_paths
    spec = _person_spec()

    craft = orchestrator.build_craft(spec, {})
    assert craft.startswith(gate.CRAFT_STAMP)
    for sec in gate.REQUIRED_SECTIONS:
        assert f"【{sec}】" in craft, sec

    secs = split.split_craft(craft)
    assert set(gate.REQUIRED_SECTIONS).issubset(secs)
    assert secs["穿着"] == "白色真丝衬衫"
    assert "西湖边" in secs["背景"]

    ok, reason = gate.validate_craft_prompt(craft)
    assert ok, reason
    body = gate.assert_craft_or_die(craft)
    assert body == gate.strip_stamp(craft)

    craft_file = tmp_path / "craft.txt"
    craft_file.write_text(body, encoding="utf-8")
    fake, calls = _fake_provider()
    monkeypatch.setitem(imagepool_pool.CALL_MAP, "ark", fake)

    rc = __main__.main(["--config", str(cfg), "--runtime", str(rt),
                        "--prompt-file", str(craft_file), "--out-dir", str(tmp_path),
                        "--size", "portrait", "--negative", "extra person"])
    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result.get("urls")
    assert result["provider"] == "ark"
    assert result.get("local")
    assert os.path.dirname(result["local"]) == str(tmp_path)
    assert calls[0]["name"] == "ark"
    assert "【合规】" in calls[0]["prompt"]
    assert calls[0]["negative"] == "extra person"


def test_e2e_render_full_chain_with_fake_generate(tmp_path):
    seen = {}

    def fake_generate(prompt, negative=None, **kw):
        seen["prompt"] = prompt
        seen["negative"] = negative
        seen["kw"] = kw
        return {"local": str(tmp_path / "out.png"), "urls": ["data:image/png;base64,AAAA"],
                "provider": "ark"}

    io = {"generate": fake_generate, "out_dir": str(tmp_path)}
    result = orchestrator.render(_person_spec(), {}, io)
    assert result.get("local")
    assert not seen["prompt"].startswith(gate.CRAFT_STAMP)
    assert "【合规】" in seen["prompt"]
    assert seen["negative"]
    assert "second person" in seen["negative"]


def test_e2e_render_gate_blocks_non_craft(tmp_path):
    io = {"generate": lambda *a, **k: {"urls": ["u"]}, "out_dir": str(tmp_path)}
    with pytest.raises(SystemExit):
        orchestrator.generate_image("随手一段，不是 craft。", io)


def test_e2e_empty_scene_subject_none(pool_paths, tmp_path, monkeypatch, capsys):
    cfg, rt = pool_paths
    spec = ShotSpec(expression_block="", context_sentence="清晨雾中的山谷。", subject="none")

    craft = orchestrator.build_craft(spec, {})
    for sec in ("【身材】", "【穿着】", "【身体特征】", "【主体】"):
        assert sec not in craft, sec
    for sec in ("【合规】", "【规格】", "【风格】", "【背景】", "【画面】", "【负向】"):
        assert sec in craft, sec
    assert "女性" not in craft

    ok, reason = gate.validate_craft_prompt(craft, rules=gate.SCENE_RULES)
    assert ok, reason
    negative = gate.extract_negative(craft)
    assert negative and "people" in negative

    craft_file = tmp_path / "scene.txt"
    craft_file.write_text(gate.strip_stamp(craft), encoding="utf-8")
    fake, calls = _fake_provider()
    monkeypatch.setitem(imagepool_pool.CALL_MAP, "ark", fake)

    rc = __main__.main(["--config", str(cfg), "--runtime", str(rt),
                        "--prompt-file", str(craft_file), "--out-dir", str(tmp_path),
                        "--size", "portrait"])
    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result.get("urls")
    assert result.get("local")
    assert "【画面】" in calls[0]["prompt"]
    assert "【主体】" not in calls[0]["prompt"]
