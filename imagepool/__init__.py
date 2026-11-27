"""imagepool —— 独立共享的图片生成 provider 池（node module 语义）。

迁移自已验证的出图实现（顺序消费池 + 轮转 + 配额兜底），
仅改接线：requests→stdlib、路径→参数化。

2026-10-18（v0.4.0，F1 副本清除）：engines（expression/pose/framing/wardrobe/face）
与默认池 data/*.default.json 已清除——本体特质内容不内嵌共享库；景别池 / 锚句
由调用方注入（compose_prompt(framing_pool=..., anchor_picker=...)）。
"""
from imagepool.config import ConfigError, load_config, save_config   # noqa: F401
from imagepool.pool import generate, ordered_active_providers         # noqa: F401
from imagepool.storage import save_image, to_data_uri                  # noqa: F401

__all__ = ["ConfigError", "load_config", "save_config",
           "generate", "ordered_active_providers", "save_image", "to_data_uri",
           # 组装 / 工艺 / 编排
           "build_craft", "generate_image", "render", "ShotSpec"]
# ── 组装 / 工艺 / 编排 ──
from imagepool.orchestrator import build_craft, generate_image, render  # noqa: E402,F401
from imagepool.contract import ShotSpec  # noqa: E402,F401
