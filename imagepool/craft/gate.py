"""imagepool.craft.gate — 生图提示词门禁。迁移自 image-generation/scripts/image_craft_gate.py。

脱域：结构节/男装禁令/女性锚保留为仓内生产默认，validate_craft_prompt 支持 rules 覆盖。
"""
from __future__ import annotations

import re
from typing import Optional, Tuple

REQUIRED_SECTIONS = ("合规", "规格", "风格", "背景", "身材", "穿着",
                     "身体特征", "主体", "画面")
CRAFT_STAMP = "# imagepool-craft-v1"

_SECTION_RE = re.compile(r"^【([^】]+)】", re.MULTILINE)
_SECTION_BODY_RE = re.compile(r"^【([^】]+)】(.*?)(?=^【|\Z)", re.MULTILINE | re.DOTALL)
_MALE_OUTFIT_RE = re.compile(r"男士|男式|男款|男装")
_FEMALE_ANCHOR_RE = re.compile(r"女性|女人|女装|女体|女主|东亚女|轻熟女|少女|少女感|女孩")
_ANCHOR_SECTIONS = ("身材", "穿着", "身体特征", "主体")

_DEFAULT_RULES = {"required_sections": REQUIRED_SECTIONS,
                  "deny_re": _MALE_OUTFIT_RE, "anchor_re": _FEMALE_ANCHOR_RE,
                  "anchor_sections": _ANCHOR_SECTIONS}

SCENE_REQUIRED_SECTIONS = ("合规", "规格", "风格", "背景", "画面")
SCENE_RULES = {"required_sections": SCENE_REQUIRED_SECTIONS,
               "deny_re": None, "anchor_re": None, "anchor_sections": ()}


def _rules(rules):
    r = dict(_DEFAULT_RULES)
    if rules:
        r.update(rules)
    return r


def strip_stamp(text: str) -> str:
    t = (text or "").strip()
    if t.startswith(CRAFT_STAMP):
        t = t[len(CRAFT_STAMP):].lstrip("\n")
    return t.strip()


def with_stamp(text: str) -> str:
    return f"{CRAFT_STAMP}\n{strip_stamp(text)}\n"


def found_sections(text: str) -> set:
    return set(_SECTION_RE.findall(strip_stamp(text) or ""))


def _section_bodies(text: str) -> dict:
    return {n: (b or "").strip() for n, b in _SECTION_BODY_RE.findall(text or "")}


def _anchor_blob(secs: dict, sec_names) -> str:
    """锚句检索文本：优先锚节；锚节全缺时回退到全文各节（支持自定义 rules 的任意节名）。"""
    present = [secs.get(k) or "" for k in sec_names if k in secs]
    if present:
        return "\n".join(present)
    return "\n".join(secs.values())


def validate_craft_prompt(text: str, rules=None) -> Tuple[bool, str]:
    """返回 (ok, reason)。ok 时 reason 为空。"""
    r = _rules(rules)
    body = strip_stamp(text)
    if not body:
        return False, "提示词为空"
    found = found_sections(body)
    if not found:
        return False, "不是 craft 模板（缺【合规】等结构节）。"
    missing = [s for s in r["required_sections"] if s not in found]
    if missing:
        return False, f"模板缺节: {', '.join('【'+s+'】' for s in missing)}"
    secs = _section_bodies(body)
    wear = secs.get("穿着") or ""
    subject = secs.get("主体") or ""
    deny_re = r.get("deny_re")
    if deny_re and (deny_re.search(wear) or deny_re.search(subject)):
        return False, "主体穿着禁止「男士/男式/男款/男装」"
    anchor_re = r.get("anchor_re")
    if anchor_re:
        blob = _anchor_blob(secs, r.get("anchor_sections") or _ANCHOR_SECTIONS)
        if not anchor_re.search(blob):
            return False, "缺女性主体锚：请在【身材】/【穿着】/【身体特征】/【主体】写明女性"
    return True, ""


def assert_craft_or_die(text: str, *, allow_raw: bool = False, rules=None) -> str:
    body = strip_stamp(text)
    if allow_raw:
        return body
    ok, reason = validate_craft_prompt(body, rules=rules)
    if not ok:
        raise SystemExit(f"❌ 门禁: {reason}")
    return body


def extract_negative(text: str) -> Optional[str]:
    body = strip_stamp(text)
    m = re.search(r"^【负向】(.*?)(?=^【|\Z)", body, re.MULTILINE | re.DOTALL)
    if not m:
        return None
    return m.group(1).strip() or None
