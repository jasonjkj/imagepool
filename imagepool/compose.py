"""imagepool.compose — 画面规格组装层。迁移自 photo/scripts/compose.py。

职责：ShotSpec → (prompt 主体, 景别短语, 景别来源)。跨维度冲突守卫保留。
脱域（2026-10-18 F1 副本清除）：仓内 engines 副本（expression/pose/framing/wardrobe/face）
与默认池 data/*.default.json 已清除——**本体特质内容不内嵌共享库，由调用方注入**：
  persona 读文件 → ref_tag_lookup 回调；景别池 → framing_pool 注入；锚句 → anchor_picker 注入。
铁律保留：近景景别遇真景图回退泛化；池缺失/无标/坏标一律静默回退，永不阻塞出图。
"""


def _lookup_shot(pool, key):
    """注入池纯查表（机制）：按 id 或中文名取档；无池 / 未知 → None（调用方静默回退）。

    逐字对齐原 engines.framing.get_shot 的 _emit 结构（source 标记保留 "framing"）。
    """
    if not key or not pool:
        return None
    for s in pool:
        if key in (s.get("id"), s.get("name")):
            return {"text": s["phrase"], "shot": s["name"], "shot_id": s["id"],
                    "ratio": s.get("ratio", ""), "modes": s.get("modes", []),
                    "source": "framing",
                    "negative": s.get("negative", ""),
                    "face": s.get("face", "visible")}
    return None


_SCENE_BLOCK = ("实景图仅提供环境与氛围元素，不决定人物景别与画面占比，"
                "背景可虚化、可离远、可自行模拟，不必完整入画")
_FUSION = ("人物真实处于场景之中：人物大小与背景景深比例自然，受光方向与背景一致，"
           "脚下与身后有自然投影和反光，人景同框、立体融合，无贴图叠加的平面感")
_LENS_VISIBLE = "浅景深，背景柔和虚化，突出人物轮廓"
_LENS_HIDDEN = "广角镜头，人物与背景同处一个真实空间，透视比例自然"


def _conflicts_with_scene(result, has_scene):
    return has_scene and "scene" not in (result or {}).get("modes", [])


def resolve_framing(spec, framing_pool=None, ref_tag_lookup=None):
    """返回 (shot_dict, source)。shot_dict=None → 调用方走泛化锚参考图。"""
    has_scene = bool(spec.scene_image)
    if spec.shot_override:
        r = _lookup_shot(framing_pool, spec.shot_override)
        if r and not _conflicts_with_scene(r, has_scene):
            return r, "override"
    elif spec.ref_image and callable(ref_tag_lookup):
        tag = ref_tag_lookup(spec.ref_image, spec.persona_dir)
        if tag:
            r = _lookup_shot(framing_pool, tag)
            if r and not _conflicts_with_scene(r, has_scene):
                return r, "context"
    return None, "neutral"


def compose_prompt(spec, framing_pool=None, ref_tag_lookup=None, anchor_picker=None):
    """ShotSpec → (prompt, shot_phrase, shot_src)。prompt 只含画面主体；业务块调用方追加。

    anchor_picker：可选注入 `(has_ref, has_pose_block, has_shot) -> str`（本体锁脸锚句，
    2026-10-18 起不再内嵌仓内）。缺省 None = 不写锚句。
    """
    shot, shot_src = resolve_framing(spec, framing_pool, ref_tag_lookup)
    person = getattr(spec, "subject", "person") != "none"
    anchor = None
    if person and callable(anchor_picker):
        anchor = anchor_picker(bool(spec.ref_image), bool(spec.pose_block), bool(shot))

    parts = [spec.expression_block.rstrip("。"), spec.context_sentence.rstrip("。")]
    if shot:
        parts.append("【构图·景别】★最高优先级：最终画面景别固定为「%s」——%s"
                     % (shot["shot"], shot["text"]))
        if shot.get("negative"):
            parts.append("【构图·反选】" + shot["negative"])
        lens = _LENS_VISIBLE if shot.get("face") == "visible" else _LENS_HIDDEN
        parts.append("【镜头】" + lens)
    # 锚句：有参考图即写（显式景别时用 POSE_ONLY，不碰构图景别，避免与【构图·景别】双信号打架）
    if anchor:
        parts.append(anchor.rstrip("。"))
    if person and spec.pose_block:
        parts.append("【姿势】" + spec.pose_block)
    if person:
        parts.append("【人景融合】" + _FUSION)
    if spec.scene_image:
        parts.append(_SCENE_BLOCK.rstrip("。"))

    prompt = "\n".join(parts) + "。"
    return prompt, (shot or {}).get("text"), shot_src
