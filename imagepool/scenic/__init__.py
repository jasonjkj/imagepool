"""scenic — 真景图 provider 链（机制进仓，内容注入）。

图片检索通道：YAML 配置 → 按 chain 顺序跑 provider → 归一化候选 →
可选外部验货 hook（决定是否落库）；与包内既有「生图」通道并列。

纯 stdlib + pyyaml（yaml 仅在 load_config 内惰性 import）：
不读 .env、不翻译中英文、不碰任何宿主资源；
密钥 / 目录 / 抓取条数 / 验货 hook 全部经配置与 ctx 注入（外层决定）。
"""

from .contract import Candidate, ConfigError, ProviderError, ScenicError
from . import engine, sources

__all__ = [
    "Candidate",
    "ConfigError",
    "ProviderError",
    "ScenicError",
    "engine",
    "sources",
]
