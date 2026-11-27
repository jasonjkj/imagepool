from imagepool.craft import split, gate

BASE = {"合规": "虚构", "规格": "竖屏，portrait", "风格": "时尚", "色板": "主=红",
        "身材": "东亚女性身形", "穿着": "白衬衫", "身体特征": "东亚女性",
        "背景": "职场", "主体": "一名女性，表情：微笑", "画面": "构图", "负向": "多人"}


def test_split_valid_craft():
    text = "\n".join(f"【{k}】{v}" for k, v in BASE.items())
    secs = split.split_craft(text)
    assert secs["穿着"] == "白衬衫" and secs["主体"].startswith("一名女性")


def test_split_invalid_returns_empty():
    assert split.split_craft("随便一段") == {}


def test_build_variant_keeps_identity_replaces_narrative():
    out = split.build_variant_craft(BASE, "咖啡馆", "同一人物，女性", "浅景深构图")
    _, reason = gate.validate_craft_prompt(out)
    assert "【穿着】白衬衫" in out and "【背景】咖啡馆" in out and "【画面】浅景深构图" in out


def test_build_hint_craft_safe_fragment():
    mapping = {"tag_visuals": {"丝袜": "腿部细节入画"},
               "category_visuals": {"pantyhose": {"subject": "腿部特写", "backgrounds": ["室内"]}},
               "fallback_visual": "生活场景"}
    kink = {"name": "丝袜", "tags": ["丝袜"], "guess_keywords": [], "category": "pantyhose"}
    out = split.build_hint_craft(BASE, kink, layer=1, mapping=mapping, seed=1)
    assert out and "谜底" not in out


def test_build_explicit_craft_empty_without_name():
    assert split.build_explicit_craft(BASE, {}) == ""
