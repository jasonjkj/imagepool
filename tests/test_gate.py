import re
from imagepool.craft import gate

GOOD = ("【合规】虚构\n【规格】竖屏\n【风格】x\n【背景】y\n【身材】东亚女性身形\n"
        "【穿着】白衬衫\n【身体特征】东亚女性\n【主体】一名女性\n【画面】构图\n")


def test_valid_prompt_passes():
    ok, reason = gate.validate_craft_prompt(GOOD)
    assert ok, reason


def test_missing_section_rejected():
    ok, reason = gate.validate_craft_prompt("【合规】x")
    assert not ok and "缺节" in reason


def test_male_outfit_rejected():
    bad = GOOD.replace("【穿着】白衬衫", "【穿着】男士白衬衫")
    ok, reason = gate.validate_craft_prompt(bad)
    assert not ok and "男士" in reason


def test_female_anchor_required():
    bad = GOOD.replace("东亚女性身形", "自然身形").replace("东亚女性", "人物").replace("一名女性", "一个人")
    ok, reason = gate.validate_craft_prompt(bad)
    assert not ok and "女性" in reason


def test_custom_rules_override():
    rules = {"required_sections": ("甲",), "deny_re": re.compile("禁止X"),
             "anchor_re": re.compile("必须Y")}
    ok, reason = gate.validate_craft_prompt("【甲】必须Y", rules=rules)
    assert ok, reason


def test_stamp_roundtrip():
    assert gate.strip_stamp(gate.with_stamp("正文")) == "正文"


SCENE = "【合规】虚构\n【规格】竖屏\n【风格】写实\n【背景】山谷\n【画面】构图\n"


def test_scene_rules_pass_personless_craft():
    ok, reason = gate.validate_craft_prompt(SCENE, rules=gate.SCENE_RULES)
    assert ok, reason


def test_default_rules_still_reject_personless():
    ok, _ = gate.validate_craft_prompt(SCENE)   # 缺身材/穿着/身体特征/主体
    assert not ok
