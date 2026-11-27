"""imagepool.craft.split — craft 模板拆段/拼装（变体图零 LLM 路径）。

迁移自 image-generation/scripts/image_craft_split.py。
脱域：去掉 load_hint_mapping 的文件 IO（tags→视觉句式映射表改由调用方注入 mapping）。
"""
from __future__ import annotations

import re

from imagepool.craft import gate as craft_gate

IDENTITY_SECTIONS = ("合规", "规格", "风格", "色板", "身材", "穿着", "身体特征")
NARRATIVE_SECTIONS = ("背景", "主体", "画面")

_HINT_SUBJECT_EN = (
    "EN: solo woman only, no second person, no crowd, "
    "no mirror reflection, natural candid mood, subtle composed expression"
)
_HINT_EXPR_EN_DEFAULT = (
    "composed natural expression, relaxed posture, hint of intimacy in the frame"
)

_SIZE_SPEC = {
    "portrait": "竖屏，portrait",
    "landscape": "横屏，landscape",
    "square": "方图，square",
}

_HINT_LAYER_SHOT_POOL = {
    1: (
        "中景构图，环境叙事优先，旁证细节自然入画，人物放松",
        "中景构图，环境叙事优先，同一环境多点入镜，人物不经意",
        "中景构图，环境叙事优先，生活气息，旁证藏在中景里",
        "中景构图，环境叙事优先，人物与场景各占一半，细节自然浮现",
    ),
    2: (
        "中近景构图，浅景深，旁证细节更近一步，氛围镜头",
        "中近景构图，浅景深，镜头推近，旁证细节清晰可辨",
        "中近景构图，浅景深，环境虚化，人物微侧身",
        "中近景构图，浅景深，主体的注意力落在旁证上，氛围拉近",
    ),
    3: (
        "特写构图，浅景深，光线聚焦旁证细节，克制不直白",
        "特写构图，浅景深，细节点到即止，画面留白",
        "特写构图，浅景深，局部明暗对比，旁证悬而未决",
        "特写构图，浅景深，光线只照亮关键细节，余皆暗影",
    ),
}


def _norm_word(w):
    return (str(w or "")).replace(" ", "").replace("　", "").lower()


def _clean_banned(banned):
    return {_norm_word(w) for w in (banned or []) if len(_norm_word(w)) >= 2}


def _safe_fragment(text, banned_norm):
    t = _norm_word(text)
    return not any(b in t for b in banned_norm)


def _inherit_expression(base_secs: dict) -> str:
    subject = (base_secs or {}).get("主体") or ""
    m = re.search(
        r"(表情|神情)([：:，,]?)\s*([^；;。]*(?:；\s*EN[:：][^；;。]*)?)",
        subject)
    if not m:
        return ""
    frag = (m.group(3) or "").strip()
    if not frag or len(frag) < 2:
        return ""
    return "表情：" + frag


def split_craft(text: str) -> dict:
    """craft 正文 → {节名: 内容}。缺必需节（非 craft 结构）返回 {}。"""
    body = craft_gate.strip_stamp(text or "")
    secs = {}
    for m in re.finditer(r"^【([^】]+)】(.*?)(?=^【|\Z)", body, re.MULTILINE | re.DOTALL):
        secs[m.group(1).strip()] = m.group(2).strip()
    required = set(craft_gate.REQUIRED_SECTIONS)
    if not required.issubset(secs.keys()):
        return {}
    return secs


def build_variant_craft(base_secs: dict, background: str, subject: str, picture: str,
                        size: str = "portrait", negative: str = "") -> str:
    """身份段继承 + 叙事段替换 → 新 craft 正文（带戳）。"""
    lines = []
    for name in IDENTITY_SECTIONS:
        if name == "规格" and size in _SIZE_SPEC:
            lines.append(f"【{name}】{_SIZE_SPEC[size]}")
            continue
        v = base_secs.get(name)
        if v:
            lines.append(f"【{name}】{v}")
    lines.append(f"【背景】{background}")
    lines.append(f"【主体】{subject}")
    lines.append(f"【画面】{picture}")
    neg = negative or base_secs.get("负向") or ""
    if neg:
        lines.append(f"【负向】{neg}")
    return craft_gate.with_stamp("\n".join(lines) + "\n")


def build_hint_craft(base_secs: dict, kink: dict, layer: int, size: str = "portrait",
                     banned=None, mapping=None, negative: str = "", seed=None) -> str:
    """特质暗示图 craft（Phase B）：身份段继承 + tags 视觉句式替换叙事段。"""
    import random
    banned_norm = _clean_banned(banned) if banned is not None else _clean_banned(
        list((kink or {}).get("guess_keywords") or []) + [(kink or {}).get("name")])
    mapping = mapping or {}
    tag_visuals = mapping.get("tag_visuals") or {}
    cat_visuals = mapping.get("category_visuals") or {}
    rng = random.Random(seed) if seed is not None else random

    fragments = []
    for tag in (kink or {}).get("tags") or []:
        frag = tag_visuals.get(str(tag))
        if frag and _safe_fragment(frag, banned_norm) and frag not in fragments:
            fragments.append(frag)
    if fragments:
        frag_pool = rng.sample(fragments, k=min(len(fragments), 2)) \
            if len(fragments) > 1 else fragments[:]
        fragments = frag_pool[: rng.randint(1, len(frag_pool))] \
            if len(frag_pool) > 1 else frag_pool
    else:
        cat = cat_visuals.get((kink or {}).get("category") or "") or {}
        frag = (cat.get("subject") or "") or mapping.get("fallback_visual") or ""
        if not frag or not _safe_fragment(frag, banned_norm):
            frag = mapping.get("fallback_visual") or ""
        if not frag or not _safe_fragment(frag, banned_norm):
            return ""
        fragments = [frag]

    cat = cat_visuals.get((kink or {}).get("category") or "") or {}
    bg_pool = cat.get("backgrounds") or []
    if bg_pool:
        background = rng.choice(bg_pool)
    else:
        background = cat.get("background") or "室内生活场景，暖光，日常氛围"
    try:
        layer_i = int(layer or 1)
    except (TypeError, ValueError):
        layer_i = 1
    shot_pool = _HINT_LAYER_SHOT_POOL.get(layer_i) or _HINT_LAYER_SHOT_POOL[1]
    picture = rng.choice(shot_pool)

    expr = _inherit_expression(base_secs)
    if expr and not _safe_fragment(expr, banned_norm):
        expr = ""
    if not expr:
        expr = f"表情：{_HINT_EXPR_EN_DEFAULT}"
    subject = "同一人物，" + "，".join(fragments) + f"；{expr}；{_HINT_SUBJECT_EN}"
    for part in (background, subject, picture):
        if not _safe_fragment(part, banned_norm):
            return ""

    return build_variant_craft(base_secs, background, subject, picture,
                               size=size, negative=negative)


_EXPLICIT_PICTURE = "近景或特写构图，光线聚焦主体，画面直白而克制，情绪浓度高，摊牌氛围"


def build_explicit_craft(base_secs: dict, kink: dict, size: str = "portrait",
                         negative: str = "") -> str:
    """特质明示图 craft（Phase C）：摊牌时刻——特质本体视觉化，谜底合法入画。"""
    kink = kink or {}
    name = str(kink.get("name") or "").strip()
    if not name:
        return ""
    kws = [str(w).strip() for w in (kink.get("guess_keywords") or [])
           if str(w).strip()][:2]
    hint3 = str(kink.get("hint_lv3") or "").strip()

    seg = [f"与「{name}」直接相关的画面呈现"]
    if kws:
        seg.append("画面元素明确指向" + "、".join(kws))
    if hint3:
        seg.append(hint3)
    subject = "同一人物，主动呈现，" + "，".join(seg) + "，神情坦然带着一点挑衅，情绪外放"
    background = "私密空间，暖光偏暗，氛围浓度高于日常，摊牌时刻"

    return build_variant_craft(base_secs, background, subject, _EXPLICIT_PICTURE,
                               size=size, negative=negative)
