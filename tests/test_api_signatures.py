"""公开 API 签名锁定：README §4 文档化的签名必须与源码一致——文档漂移即测试红。

只断言「参数名 + 顺序 + 默认值」：这是下游宿主按 tag 消费时真正依赖的契约面。
改动签名必须同步改 README + bump version（见 README §6）。
"""
import dataclasses
import inspect

import imagepool
from imagepool import compose, config, pool, protocols, storage
from imagepool.craft import gate, split, translate


def _params(fn):
    return inspect.signature(fn).parameters


def _names(fn):
    return list(_params(fn))


def _default(fn, name):
    return _params(fn)[name].default


def _required(fn, name):
    return _params(fn)[name].default is inspect.Parameter.empty


# ── 池子 / 配置 / 落盘 ──

def test_pool_generate_signature():
    fn = pool.generate
    assert _names(fn) == ["prompt", "cfg", "config_path", "runtime_path", "out_dir",
                          "size", "n", "negative", "force_provider", "rr", "images"]
    assert _required(fn, "prompt") and _required(fn, "cfg")
    assert _default(fn, "config_path") is None
    assert _default(fn, "runtime_path") is None
    assert _default(fn, "out_dir") == "."
    assert _default(fn, "size") == "square"
    assert _default(fn, "n") == 1
    assert _default(fn, "negative") == ""
    assert _default(fn, "force_provider") is None
    assert _default(fn, "rr") is False
    assert _default(fn, "images") is None


def test_config_signatures():
    assert _names(config.load_config) == ["config_path", "runtime_path"]
    assert _default(config.load_config, "runtime_path") is None
    assert _names(config.save_config) == ["cfg", "config_path", "runtime_path"]
    assert _default(config.save_config, "config_path") is None
    assert _default(config.save_config, "runtime_path") is None


def test_storage_signatures():
    assert _names(storage.to_data_uri) == ["src"]
    assert _names(storage.save_image) == ["url", "provider", "out_dir", "name_hint"]
    assert _default(storage.save_image, "name_hint") is None
    assert _required(storage.save_image, "out_dir")


def test_pool_ordered_active_signature():
    assert _names(pool.ordered_active_providers) == ["cfg"]


# ── 组装 / 工艺 / 编排 ──

def test_orchestrator_signatures():
    assert _names(imagepool.build_craft) == ["spec", "data"]
    assert _default(imagepool.build_craft, "data") is None
    assert _names(imagepool.generate_image) == ["craft_text", "io", "mode"]
    assert _default(imagepool.generate_image, "mode") == "person"
    assert _names(imagepool.render) == ["spec", "data", "io"]


def test_gate_signatures():
    assert _names(gate.validate_craft_prompt) == ["text", "rules"]
    assert _names(gate.assert_craft_or_die) == ["text", "allow_raw", "rules"]
    assert _default(gate.assert_craft_or_die, "allow_raw") is False
    assert _names(gate.extract_negative) == ["text"]
    assert _names(gate.strip_stamp) == ["text"]
    assert _names(gate.with_stamp) == ["text"]
    assert _names(gate.found_sections) == ["text"]


def test_split_signatures():
    assert _names(split.split_craft) == ["text"]
    assert _names(split.build_variant_craft) == ["base_secs", "background", "subject",
                                                 "picture", "size", "negative"]
    assert _names(split.build_hint_craft) == ["base_secs", "kink", "layer", "size",
                                              "banned", "mapping", "negative", "seed"]
    assert _names(split.build_explicit_craft) == ["base_secs", "kink", "size", "negative"]


def test_translate_signature():
    assert _names(translate.translate_craft_en) == ["craft_text", "backend", "timeout", "mode"]
    assert _default(translate.translate_craft_en, "backend") is None
    assert _default(translate.translate_craft_en, "timeout") == 120
    assert _default(translate.translate_craft_en, "mode") == "person"


def test_compose_signatures():
    assert _names(compose.compose_prompt) == ["spec", "framing_pool", "ref_tag_lookup", "anchor_picker"]
    assert _default(compose.compose_prompt, "anchor_picker") is None
    assert _names(compose.resolve_framing) == ["spec", "framing_pool", "ref_tag_lookup"]


# ── 契约 / 协议 / 导出面 ──

def test_shotspec_fields_and_defaults():
    fields = {f.name: f for f in dataclasses.fields(imagepool.ShotSpec)}
    assert list(fields) == ["expression_block", "context_sentence", "ref_image",
                            "shot_override", "scene_image", "mood", "pose_block",
                            "pose_strategy", "persona_dir", "outfit_block", "kink_block",
                            "style", "subject", "input_images", "size"]
    assert fields["expression_block"].default is dataclasses.MISSING
    assert fields["context_sentence"].default is dataclasses.MISSING
    assert fields["subject"].default == "person"
    assert fields["size"].default == "portrait"
    assert fields["pose_strategy"].default == "anchor_ref"


def test_protocols_contract():
    assert set(protocols.CALL_MAP) == {"qwen", "doubao", "ark", "sensenova", "agnes"}
    assert protocols.IMAGE_INPUT_PROVIDERS == {"ark", "sensenova"}
    assert protocols.supports_image_input("ark") and not protocols.supports_image_input("qwen")
    for name, fn in protocols.CALL_MAP.items():
        assert _names(fn) == ["p", "prompt", "size", "n", "negative", "images"], name


def test_top_level_exports_documented():
    for sym in imagepool.__all__:
        assert hasattr(imagepool, sym), sym
