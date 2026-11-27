"""ShotSpec — 一张画面的参数契约（画面五维度）。迁移自 photo/scripts/shot_spec.py。

维度归属：
  expression_block  上游渲染好的表情段（本层只接收拼好的文字，不二次 roll）
  pose_block        上游姿势引擎 roll 好的短语；None=不写【姿势】节
  shot_override     手动景别档名/id（显式 > 参考图派生标 > 泛化锚参考图）
  context_sentence  背景情境句（调用方按业务渲染）
  scene_image       真景图路径；None=纯文字背景
  ref_image         人物参考图；None=纯文生
  mood              情绪（预留持有，compose 当前不消费）
  outfit_block      上游渲染好的穿着段（业务块；None=不写）
  kink_block        上游渲染好的情趣段（业务块；None=不写）
  style             画风串（业务块；None=用仓内默认）
  size              portrait/landscape/square
  persona_dir       参考图 persona 目录（供 ref_tag_lookup 回调用）
本文件只定义契约，不含任何 IO / 引擎调用 / 业务状态。
"""
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ShotSpec:
    # ── 必填 ──
    expression_block: str
    context_sentence: str
    # ── 画面规格 ──
    ref_image: Optional[str] = None
    shot_override: Optional[str] = None
    scene_image: Optional[str] = None
    mood: Optional[str] = None
    pose_block: Optional[str] = None
    pose_strategy: str = "anchor_ref"
    persona_dir: Optional[str] = None
    # ── 业务渲染块（§14-8：业务渲染好放进 spec）──
    outfit_block: Optional[str] = None
    kink_block: Optional[str] = None
    style: Optional[str] = None
    subject: str = "person"          # person / none（空镜，无主体）
    input_images: Optional[List[str]] = None  # 喂模型的图源（图生图）；与 ref_image/scene_image 语义分离
    size: str = "portrait"
