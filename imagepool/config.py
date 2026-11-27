"""配置层（迁移自旧 image_gen.py load_config/save_config，60-152 行）。

改造三处：
1. 路径不写死：config_path / runtime_path 全部入参注入。
2. 结构校验 = 未知键 ConfigError（typo 当场抓）；不查 env 存在性（旧 load_config
   不查，缺 key 由 call_* 兜底"未配置"）。
3. write_json_atomic（tools 基建）→ 本包内 os.replace 原子写，零第三方依赖。
其余字段语义（拆分静态↔运行态）与旧系统完全一致。
"""
import json
import os
from pathlib import Path

_TOP_KEYS = {"pool_order", "providers", "_note"}
_PROVIDER_KEYS = {"name", "endpoint", "model", "api_key_env", "free_quota",
                  "timeout", "description", "size_map", "format",
                  "output_format"}
_RUNTIME_PROVIDER_KEYS = ("usage", "exhausted")
_RUNTIME_TOP_KEYS = ("_rr_next", "_updated")


class ConfigError(Exception):
    """配置/输入错误。"""


def _check_provider_fields(p):
    for k in p:
        if k not in _PROVIDER_KEYS:
            raise ConfigError(f"provider 未知键: {k}")
    for req in ("name", "endpoint", "model"):
        if not p.get(req):
            raise ConfigError(f"provider 缺 {req}: {p.get('name') or '(空)'}")


def load_config(config_path, runtime_path=None):
    """主配置 + 可选运行态合并视图。未知键 = ConfigError。"""
    path = Path(config_path)
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        raise ConfigError(f"配置不可读: {path} ({e})") from e
    if not isinstance(cfg, dict):
        raise ConfigError("配置顶层必须是 object")
    for k in cfg:
        if k not in _TOP_KEYS:
            raise ConfigError(f"未知顶层键: {k}")
    for p in cfg.get("providers", []):
        if not isinstance(p, dict):
            raise ConfigError("providers[] 必须是 object")
        _check_provider_fields(p)
    if runtime_path:
        try:
            rt = json.loads(Path(runtime_path).read_text(encoding="utf-8")) or {}
        except Exception:
            return cfg  # sidecar 不存在/损坏：按主配置内运行态（兼容旧行为）
        rt_provs = rt.get("providers") or {}
        for p in cfg.get("providers", []):
            pr = rt_provs.get(p.get("name"))
            if pr:
                for k in _RUNTIME_PROVIDER_KEYS:
                    if k in pr:
                        p[k] = pr[k]
        for k in _RUNTIME_TOP_KEYS:
            if k in rt:
                cfg[k] = rt[k]
    return cfg


def _atomic_write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def save_config(cfg, config_path=None, runtime_path=None):
    """拆分落盘：静态字段→主配置，运行态→runtime（任一为 None 即只写另一侧）。"""
    static = dict(cfg)
    rt = {"providers": {}}
    for k in _RUNTIME_TOP_KEYS:
        if k in static:
            rt[k] = static.pop(k)
    provs = []
    for p in static.get("providers", []):
        q = dict(p)
        pr = {}
        for k in _RUNTIME_PROVIDER_KEYS:
            if k in q:
                pr[k] = q.pop(k)
        if pr:
            rt["providers"][q["name"]] = pr
        provs.append(q)
    static["providers"] = provs
    if config_path:
        _atomic_write(Path(config_path), static)
    if runtime_path:
        _atomic_write(Path(runtime_path), rt)