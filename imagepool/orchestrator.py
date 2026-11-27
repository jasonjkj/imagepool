"""imagepool.orchestrator — 编排骨架：build_craft / generate_image / render。

设计 §14-2 / §14-8：
- build_craft(spec, data)        纯函数：取景别 + compose + 套分节模板 + 上戳。
- generate_image(craft_text, io) 门禁 +（可选）英译 + 池子出图 + 落盘。
- render(spec, data, io)         便捷包装。
业务渲染块（穿着/情趣/画风）由 spec 携带；领域内容经 data 注入（缺省用仓内默认池）。
"""
from __future__ import annotations

from imagepool import compose
from imagepool.craft import gate as craft_gate
from imagepool.craft import translate as craft_translate
from imagepool.contract import ShotSpec

_DEFAULT_TEMPLATES = {
    "合规": "所有角色均为虚构，非真人非明星非网红",
    "规格": "竖屏，portrait",
    "风格": ("时尚职业写真，人物写实细节，自然光影；"
             "EN: fashion photography, realistic details, cinematic natural lighting, glamour style"),
    "身材": ("自然匀称的女性身形，比例修长，曲线适度；"
             "EN: natural slim female figure, long legs, moderate curves"),
    "身体特征": ("东亚女性，五官精致立体，自然妆容，发质柔顺；"
                 "EN: East Asian woman, delicate refined facial features, natural makeup, silky hair"),
    "主体": "画面中仅此一名女性人物，画面中绝不允许出现第二个人物、路人、人影、镜像或倒影",
    "画面": ("时尚艺术大片质感，杂志摄影构图，光影氛围突出服装线条与身体曲线之美，张力十足；"
             "EN: fashion editorial photography, magazine composition, dramatic lighting"),
}
_SECTION_ORDER = ("合规", "规格", "风格", "背景", "身材", "穿着", "身体特征", "主体", "画面")
_DEFAULT_NEGATIVE = ("extra person, second person, multiple people, crowd, group shot, "
                     "mirror reflection, duplicated figure, another woman, man, male")
_SIZE_SPEC = {"portrait": "竖屏，portrait", "landscape": "横屏，landscape", "square": "方图，square"}

# ── 空镜（subject=none）：无人物场景向模板，仅 合规/规格/风格/背景/画面 五节 ──
_SCENE_DEFAULT_TEMPLATES = {
    "合规": "所有画面均为虚构场景，非真实地点、非真人非明星非网红",
    "规格": "竖屏，portrait",
    "风格": ("写实场景摄影，环境细节丰富，自然光影；"
             "EN: realistic scenery photography, rich environmental details, natural lighting"),
    "画面": ("电影感空镜构图，环境氛围突出，画面中无任何人物；"
             "EN: cinematic empty-scene composition, atmospheric environment, no people"),
}
_SCENE_SECTION_ORDER = ("合规", "规格", "风格", "背景", "画面")
_SCENE_DEFAULT_NEGATIVE = "person, people, woman, man, human, figure, face, crowd, hands"


def build_craft(spec: ShotSpec, data: dict = None) -> str:
    """组装 + 工艺 → 带戳 craft 正文（纯函数，可单测）。

    subject=="none" → 空镜：用场景模板/五节顺序/场景负向，不产出任何人物分节。"""
    data = data or {}
    pools = data.get("pools") or {}
    scene = getattr(spec, "subject", "person") == "none"
    base_templates = _SCENE_DEFAULT_TEMPLATES if scene else _DEFAULT_TEMPLATES
    templates = {**base_templates, **(data.get("templates") or {})}
    order = _SCENE_SECTION_ORDER if scene else _SECTION_ORDER
    default_negative = _SCENE_DEFAULT_NEGATIVE if scene else _DEFAULT_NEGATIVE

    photo_prompt, _shot_phrase, _src = compose.compose_prompt(
        spec, framing_pool=pools.get("framing"), ref_tag_lookup=data.get("ref_tag_lookup"),
        anchor_picker=data.get("anchor_picker"))

    secs = dict(templates)
    secs["规格"] = _SIZE_SPEC.get(spec.size, templates.get("规格", "竖屏，portrait"))
    secs["背景"] = (spec.context_sentence or "").rstrip("。")
    if spec.style:
        secs["风格"] = spec.style
    if not scene:
        secs["穿着"] = spec.outfit_block or ""
        if spec.kink_block:
            secs["主体"] = secs.get("主体", "") + "；" + spec.kink_block

    lines = []
    for name in order:
        body = secs.get(name) or ""
        if name == "画面":
            body = (body + "\n\n" + photo_prompt).strip()
        lines.append(f"【{name}】{body}")
    negative = data.get("negative") or default_negative
    lines.append(f"【负向】{negative}")
    return craft_gate.with_stamp("\n".join(lines) + "\n")


def generate_image(craft_text: str, io: dict = None, mode: str = "person") -> dict:
    """门禁 →（可选）英译 → 池子出图 → 返回结果 dict。

    mode=="none" → 空镜：用 SCENE_RULES 门禁、英译走场景模式。
    io["images"] 有值 → 以 images=… 透传给 generate（图生图）。"""
    io = io or {}
    rules = io.get("craft_rules") or (craft_gate.SCENE_RULES if mode == "none" else None)
    body = craft_gate.assert_craft_or_die(craft_text, rules=rules)
    negative = craft_gate.extract_negative(body)
    if callable(io.get("translate_backend")):
        en, _note = craft_translate.translate_craft_en(
            body, backend=io["translate_backend"], mode=mode)
        if en:
            body = craft_gate.strip_stamp(en)
    generate = io.get("generate")
    if not callable(generate):
        raise ValueError("io['generate'] 未提供（出图函数）")
    images = io.get("images")
    if images:
        return generate(body, negative=negative, images=images) or {}
    return generate(body, negative=negative) or {}


def render(spec: ShotSpec, data: dict = None, io: dict = None) -> dict:
    """build_craft + generate_image 便捷包装（从 spec 派生 mode 与输入图）。"""
    mode = "none" if getattr(spec, "subject", "person") == "none" else "person"
    io = dict(io or {})
    io.setdefault("images", getattr(spec, "input_images", None))
    return generate_image(build_craft(spec, data), io, mode=mode)
