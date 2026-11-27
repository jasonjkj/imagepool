from imagepool.contract import ShotSpec
from imagepool import compose

POOL = [
    {"id": "medium", "name": "半身", "ratio": "三分之二", "modes": ["selfie", "scene"],
     "phrase": "腰部以上半身构图", "negative": "不得怼脸", "face": "visible"},
]


def test_compose_without_ref_has_no_anchor():
    spec = ShotSpec(expression_block="温柔浅笑", context_sentence="在西湖边。",
                    shot_override="medium")
    prompt, phrase, src = compose.compose_prompt(spec, framing_pool=POOL)
    assert "【构图·景别】" in prompt and src == "override"
    assert "参照人物参考图" not in prompt


def test_compose_with_ref_uses_anchor_picker_injection():
    """F1（2026-10-18）：锚句不再内嵌仓内，由调用方注入 anchor_picker。"""
    spec = ShotSpec(expression_block="x", context_sentence="y。",
                    ref_image="/p/a.jpg", shot_override="medium")
    picker_calls = []

    def picker(has_ref, has_pose_block, has_shot):
        picker_calls.append((has_ref, has_pose_block, has_shot))
        return "锚句：参照人物参考图。"

    prompt, _, _ = compose.compose_prompt(spec, framing_pool=POOL,
                                          anchor_picker=picker)
    assert "参照人物参考图" in prompt
    assert picker_calls == [(True, False, True)]


def test_compose_without_anchor_picker_writes_no_anchor():
    """反面：未注入 anchor_picker → 有参考图也不写锚句（共享库不内嵌本体内容）。"""
    spec = ShotSpec(expression_block="x", context_sentence="y。",
                    ref_image="/p/a.jpg", shot_override="medium")
    prompt, _, _ = compose.compose_prompt(spec, framing_pool=POOL)
    assert "参照人物参考图" not in prompt


def test_compose_framing_pool_injection_required():
    """F1：景别池未注入（None / 空池）→ 无景别节，静默回退不阻塞。"""
    spec = ShotSpec(expression_block="x", context_sentence="y。",
                    shot_override="medium")
    prompt, phrase, src = compose.compose_prompt(spec)  # 无池
    assert "【构图·景别】" not in prompt and src == "neutral"
    prompt, phrase, src = compose.compose_prompt(spec, framing_pool=[])  # 空池
    assert "【构图·景别】" not in prompt and src == "neutral"


def test_pose_block_writes_pose_section():
    spec = ShotSpec(expression_block="x", context_sentence="y。", pose_block="撩发")
    prompt, _, _ = compose.compose_prompt(spec, framing_pool=[])
    assert "【姿势】撩发" in prompt


def test_ref_tag_lookup_callback_supplies_shot():
    spec = ShotSpec(expression_block="x", context_sentence="y。", ref_image="/p/a.jpg")
    prompt, _, src = compose.compose_prompt(
        spec, framing_pool=POOL, ref_tag_lookup=lambda img, base=None: "medium")
    assert src == "context"


def test_scene_image_near_shot_conflict_falls_back():
    spec = ShotSpec(expression_block="x", context_sentence="y。",
                    shot_override="medium", scene_image="/s.jpg")
    # medium 支持 scene，不冲突
    _, _, src = compose.compose_prompt(spec, framing_pool=POOL)
    assert src == "override"


def test_compose_person_includes_fusion_and_anchor():
    spec = ShotSpec(expression_block="微笑", context_sentence="湖边。")
    prompt, _, _ = compose.compose_prompt(spec)
    assert "【人景融合】" in prompt


def test_compose_none_subject_drops_fusion_and_anchor():
    spec = ShotSpec(expression_block="", context_sentence="雾中的山谷。", subject="none")
    prompt, _, _ = compose.compose_prompt(spec)
    assert "【人景融合】" not in prompt


def test_compose_none_subject_drops_pose_block():
    spec = ShotSpec(expression_block="", context_sentence="雾中的山谷。",
                    subject="none", pose_block="撩发")
    prompt, _, _ = compose.compose_prompt(spec)
    assert "【姿势】" not in prompt
