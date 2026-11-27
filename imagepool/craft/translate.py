"""imagepool.craft.translate — 中文 craft 整篇英译。迁移自 image-generation/scripts/craft_translate.py。

脱域：原本反向 import image_orchestrator 的 get_best_backend/call_free_model（免费 LLM 池）
→ 改为调用方注入 backend 回调 (craft_text, system_prompt) -> Optional[str]。
格式还原 / 残留检测 / 女性锚保险原样保留（只告警不阻断）。
"""
from __future__ import annotations

import re
import sys
from typing import Optional, Tuple

TRANSLATE_SYSTEM = (
    "你是资深图片提示词英译。输入是中文图片提示词，每节有中文标题【××】。"
    "输出规则：每节只输出一次——中文标题【××】原样保留，标题后的正文一律改为英文"
    "（输入里已有的 EN: 英文短语直接并入英文正文、删掉 EN: 前缀）；中文正文不保留。"
    "『女性』字样必须放在【主体】节正文第一行开头，不得出现在其他节。"
    "不得出现『男士/男式/男款/男装』。保留全部细节（场景/人物/服装/露感/表情/"
    "构图/光影/负向词），不得增删内容、不输出解释。"
    "格式必须还原原输入：节顺序不变、每节一行（【标题】+正文）、"
    "节间空行数量与原输入一致、末尾【负向】节保留。只输出译文。"
)

_FEMALE_ANCHOR_RE = re.compile(r"女性|女人|女装|女体|女主|东亚女|轻熟女|少女|少女感|女孩")
_ANCHOR_SECTIONS = ("身材", "穿着", "身体特征", "主体")

_SCENE_TRANSLATE_SYSTEM = (
    "你是资深图片提示词英译。输入是中文图片提示词，每节有中文标题【××】。"
    "输出规则：每节只输出一次——中文标题【××】原样保留，标题后的正文一律改为英文"
    "（输入里已有的 EN: 英文短语直接并入英文正文、删掉 EN: 前缀）；中文正文不保留。"
    "本图为无人物场景/空镜，不得引入任何人物或人体主体描述，不得出现任何性别或人体主体词汇。"
    "保留全部细节（场景/环境/构图/光影/负向词），不得增删内容、不输出解释。"
    "格式必须还原原输入：节顺序不变、每节一行（【标题】+正文）、"
    "节间空行数量与原输入一致、末尾【负向】节保留。只输出译文。"
)


def _parse_sections(text: str):
    out = []
    for m in re.finditer(r"(?:^|\n)(\n*)【([^】]+)】(.*?)(?=\n*【|\Z)", text, re.S):
        out.append((m.group(2), m.group(1).count("\n"), m.group(3).strip()))
    return out


def translate_craft_en(craft_text: str, backend=None, timeout: int = 120,
                       mode: str = "person") -> Tuple[Optional[str], str]:
    """整篇中文 craft → 英文。backend 为 None 或失败 → (None, 原因)。

    mode=="none" → 空镜路径：用无人物系统提示、不做女性锚注入。"""
    if not callable(backend):
        return None, "无英译后端（io.translate_backend 未提供）"
    system = _SCENE_TRANSLATE_SYSTEM if mode == "none" else TRANSLATE_SYSTEM
    try:
        text = backend(craft_text, system)
    except Exception as e:  # 回调异常不阻断
        return None, f"英译后端异常: {e}"
    if not text:
        return None, "英译后端返回空"
    # 空镜模式下不要做任何女性锚注入（也不触发残留中文告警的强制补救）
    return _harden(text, craft_text, enforce_female=(mode != "none")), "ok"


def _harden(translated: str, src: str, enforce_female: bool = True) -> str:
    body_no_head = re.sub(r"【[^】]+】", "", translated)
    zh_left = re.findall(r"[\u4e00-\u9fff]+", body_no_head)
    if zh_left:
        print(f"⚠️  translate: 英译正文残留中文 {len(zh_left)} 处: {zh_left[:4]}", file=sys.stderr)
    en_secs = {t: b for t, _, b in _parse_sections(translated)}
    if enforce_female:
        blob = "\n".join(en_secs.get(k) or "" for k in _ANCHOR_SECTIONS)
        if not _FEMALE_ANCHOR_RE.search(blob):
            if "主体" in en_secs:
                translated = re.sub(r"(【主体】)", r"\1女性。", translated, count=1)
            else:
                translated = translated.rstrip("\n") + "\n【主体】女性。\n"
    return _restore_layout(src, translated)


def _restore_layout(src: str, translated: str) -> str:
    src_secs = _parse_sections(src)
    en_map = {t: b for t, _, b in _parse_sections(translated)}
    out = []
    missing = []
    for title, blanks, _ in src_secs:
        body = en_map.pop(title, None)
        if body is None:
            missing.append(title)
            continue
        out.append("\n" * blanks + "【%s】%s" % (title, body))
    if missing:
        print(f"⚠️  translate: 译文中缺节 {missing}，已从原文回填（保持结构）", file=sys.stderr)
    extra = [t for t in en_map if en_map[t]]
    if extra:
        print(f"⚠️  translate: 译文多出节 {extra}，已保留在末尾", file=sys.stderr)
        for t in extra:
            out.append("【%s】%s" % (t, en_map[t]))
    if not out:
        return translated
    return "\n".join(out).rstrip("\n") + "\n"
