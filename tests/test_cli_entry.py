"""CLI 入口锁定：console script 映射 + 模块入口 + 离线分支（mark/reset/全耗尽）。

补 test_cli.py 未覆盖的：`pyproject` 入口契约、`--help` 参数面、`--mark-exhausted` /
`--reset-provider` 状态写回、全池耗尽的退出码。全程离线，不触网。
"""
import json
import os
import tomllib

import pytest

from imagepool import __main__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCUMENTED_FLAGS = ["--config", "--runtime", "--out-dir", "--prompt-file", "--size",
                    "--provider", "--n", "--rr", "--negative", "--list-providers",
                    "--state", "--reset-provider", "--mark-exhausted", "--dry-run"]


def _pyproject():
    with open(os.path.join(ROOT, "pyproject.toml"), "rb") as f:
        return tomllib.load(f)


def _write_cfg(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({
        "pool_order": ["p1"],
        "providers": [{"name": "p1", "endpoint": "https://e.test/images/generations",
                       "model": "m", "api_key_env": "IP_TEST_KEY",
                       "size_map": {"square": "2K"}, "format": "openai"}],
    }), encoding="utf-8")
    return cfg


def test_console_scripts_mapping_matches_docs():
    scripts = _pyproject()["project"]["scripts"]
    assert scripts["imagepool"] == "imagepool.__main__:main"
    assert scripts["imagepool-mcp"] == "mcp_server:main"


def test_cli_entry_callable():
    assert callable(__main__.main)


def test_cli_help_lists_all_documented_flags(capsys):
    with pytest.raises(SystemExit) as e:
        __main__.main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for flag in DOCUMENTED_FLAGS:
        assert flag in out, f"CLI --help 缺参数: {flag}"


def test_cli_mark_exhausted_then_reset_persists(tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    rt = tmp_path / "r.json"

    rc = __main__.main(["--config", str(cfg), "--runtime", str(rt),
                        "--mark-exhausted", "p1"])
    assert rc == 0
    assert "已标记" in capsys.readouterr().out
    assert json.loads(rt.read_text(encoding="utf-8"))["providers"]["p1"]["exhausted"] is True

    rc = __main__.main(["--config", str(cfg), "--runtime", str(rt), "--reset-provider"])
    assert rc == 0
    assert "已重置" in capsys.readouterr().out
    assert json.loads(rt.read_text(encoding="utf-8"))["providers"]["p1"]["exhausted"] is False


def test_cli_mark_unknown_provider_reports(tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    rc = __main__.main(["--config", str(cfg), "--mark-exhausted", "nope"])
    assert rc == 0
    assert "未找到" in capsys.readouterr().out


def test_cli_all_exhausted_exit1(tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    rt = tmp_path / "r.json"
    rt.write_text(json.dumps({"providers": {"p1": {"exhausted": True}}}), encoding="utf-8")
    craft = tmp_path / "craft.txt"
    craft.write_text("任意提示词", encoding="utf-8")

    rc = __main__.main(["--config", str(cfg), "--runtime", str(rt),
                        "--prompt-file", str(craft), "--out-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert "error" in out
