"""README 自包含参考面锁定：章节 / 公共符号 / env / CLI / 无 dev 绝对路径。

README 是「不读源码即可使用 / 集成」的唯一入口——缺章节或缺符号即测试红。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README_PATH = os.path.join(ROOT, "README.md")

REQUIRED_SECTIONS = [
    "## 1. 定位",
    "## 2. 安装",
    "## 3. 用法 / CLI",
    "## 4. API / 模块参考",
    "## 5. 集成方式",
    "## 6. 版本 / 发布",
    "## 7. env 变量表",
    "## 8. 测试",
    "## 9. 边界 / 已知缺口",
]

PUBLIC_SYMBOLS = [
    "load_config", "save_config", "generate", "ordered_active_providers",
    "save_image", "to_data_uri",
    "build_craft", "generate_image", "render", "ShotSpec",
    "validate_craft_prompt", "assert_craft_or_die", "extract_negative",
    "split_craft", "build_variant_craft", "build_hint_craft", "build_explicit_craft",
    "translate_craft_en", "compose_prompt", "resolve_framing", "anchor_picker",
    "supports_image_input",
]

ENV_VARS = ["api_key_env", "IMAGEPOOL_CONFIG", "IMAGEPOOL_OUT_DIR",
            "SCENIC_CONFIG", "IMAGEPOOL_SCENIC_CONFIG", "PEXELS_API_KEY"]

CLI_FLAGS = ["--config", "--runtime", "--out-dir", "--prompt-file", "--size",
             "--provider", "--n", "--rr", "--negative", "--list-providers",
             "--state", "--reset-provider", "--mark-exhausted", "--dry-run"]


def _read():
    with open(README_PATH, encoding="utf-8") as f:
        return f.read()


def test_readme_exists():
    assert os.path.isfile(README_PATH)


def test_readme_has_all_required_sections():
    text = _read()
    for sec in REQUIRED_SECTIONS:
        assert sec in text, f"README 缺章节: {sec}"


def test_readme_documents_public_symbols():
    text = _read()
    for sym in PUBLIC_SYMBOLS:
        assert sym in text, f"README 未记录公共符号: {sym}"


def test_readme_documents_env_vars():
    text = _read()
    for var in ENV_VARS:
        assert var in text, f"README 未记录 env 变量: {var}"


def test_readme_documents_cli_flags():
    text = _read()
    for flag in CLI_FLAGS:
        assert flag in text, f"README 未记录 CLI 参数: {flag}"


def test_readme_documents_install():
    text = _read()
    assert "pip install" in text
    assert "python -m imagepool" in text


_FORBIDDEN_ABS = ["/" + "Users/", "file:" + "///"]


def test_readme_has_no_dev_machine_absolute_paths():
    text = _read()
    for pat in _FORBIDDEN_ABS:
        assert pat not in text, "README 出现本机绝对路径/链接（跨机 landmine）"
