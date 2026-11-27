"""scenic 契约：候选结构 + 错误类型。"""

from dataclasses import dataclass


class ScenicError(Exception):
    """scenic 链通用错误基类。"""


class ConfigError(ScenicError):
    """配置损坏（非缺失）。配置缺失时引擎回默认链，不 fail-closed 阻塞。"""


class ProviderError(ScenicError):
    """单 provider 内部错误（引擎捕获并按 fail-isolated 跳过）。"""


@dataclass(frozen=True)
class Candidate:
    """一条归一化候选。

    ref:     URL（local=False）或本地绝对路径（local=True）
    source:  来源名（YAML providers 的 key，输出标记用）
    local:   True=本地直发（persona / 线路池），不下载、不落新库
    """
    ref: str
    source: str
    local: bool = False
