"""CLI：dry-run 不调接口 / list-providers / state；缺配置报错；坏用法退出码。"""
import json

from imagepool import __main__


def _write_cfg(tmp_path):
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({
        "pool_order": ["p1"],
        "providers": [{"name": "p1", "endpoint": "https://e.test/images/generations",
                       "model": "m", "api_key_env": "NOPE_NOPE",
                       "size_map": {"square": "2K"}, "format": "openai"}],
    }), encoding="utf-8")
    return cfg


def test_dry_run_no_network(tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    rc = __main__.main(["--config", str(cfg), "--dry-run"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "p1" in out


def test_list_providers(tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    rc = __main__.main(["--config", str(cfg), "--list-providers"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "p1" in out and "✅" in out


def test_state(tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    rc = __main__.main(["--config", str(cfg), "--state"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "p1" in out


def test_missing_config_usage_error(tmp_path, capsys):
    rc = __main__.main(["--config", str(tmp_path / "nope.json"), "--list-providers"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "错误" in err


def test_missing_prompt_file_usage_error(tmp_path, capsys):
    cfg = _write_cfg(tmp_path)
    rc = __main__.main(["--config", str(cfg)])
    err = capsys.readouterr().err
    assert rc == 2
    assert "--prompt-file" in err