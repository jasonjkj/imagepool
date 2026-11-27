#!/usr/bin/env python3
"""mcp_server.py — imagepool MCP 服务器（stdio 传输）。

把 imagepool 的能力暴露为 MCP 工具，供 Claude / WorkBuddy / 任意 MCP 客户端调用。
stdout 是 MCP 协议通道：日志一律走 stderr，不得污染 stdout。

出图工具（imagepool_generate / imagepool_render）需要一个 provider 池配置：
由环境变量 IMAGEPOOL_CONFIG 指向，或按调用传 config_path；落盘目录取
IMAGEPOOL_OUT_DIR（缺省 cwd）。未提供配置时抛清晰错误，不静默。
"""
from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from imagepool import build_craft, render
from imagepool import config as _config
from imagepool import pool as _pool
from imagepool.contract import ShotSpec

mcp = FastMCP(
    "imagepool",
    instructions=(
        "通用图片能力仓：provider 池出图 + 画面组装（build_craft）+ 一站式渲染（render）。"
        "build_craft 需要结构化 spec；render 会真实出图（消耗池子）。"
        "出图需配置 IMAGEPOOL_CONFIG（或传 config_path）。"
    ),
)


def _spec_from_json(spec_json: str) -> ShotSpec:
    data = json.loads(spec_json) if isinstance(spec_json, str) else (spec_json or {})
    return ShotSpec(**data)


def _data_from_json(data_json: str) -> dict:
    if not data_json:
        return {}
    return json.loads(data_json) if isinstance(data_json, str) else data_json


def _config_path(override: str = "") -> str:
    return override or os.environ.get("IMAGEPOOL_CONFIG", "")


def _pool_generate(config_path: str = ""):
    """构造一个 (prompt, negative=) -> dict 的出图回调，闭包绑定池配置。"""
    path = _config_path(config_path)
    if not path:
        raise ValueError("未配置出图池：设置 IMAGEPOOL_CONFIG 环境变量或传 config_path")
    cfg = _config.load_config(path)
    out_dir = os.environ.get("IMAGEPOOL_OUT_DIR", ".")

    def _gen(prompt, negative=None, **kw):
        return _pool.generate(prompt, cfg, config_path=path, out_dir=out_dir,
                              negative=negative or "", **kw)

    return _gen


@mcp.tool()
def imagepool_build_craft(spec_json: str, data_json: str = "") -> str:
    """由 spec（JSON）组装 craft 文本（纯函数，不出图）。

    Args:
        spec_json: ShotSpec 字段的 JSON，如 {"expression_block": "...", "context_sentence": "..."}
        data_json: 领域数据 JSON（pools/templates/negative 等）；留空用仓内默认池
    """
    return build_craft(_spec_from_json(spec_json), _data_from_json(data_json))


@mcp.tool()
def imagepool_generate(prompt: str, config_path: str = "", images_json: str = "") -> str:
    """直接走 provider 池出一张图（已成品的 prompt，不经捏合）。

    Args:
        prompt: 成品图片提示词
        config_path: 池配置 JSON 路径；留空用 IMAGEPOOL_CONFIG 环境变量
        images_json: 输入参考图（图生图）JSON 数组字符串，如
            ["data:image/png;base64,..."]；空串=纯文生
    """
    images = json.loads(images_json) if images_json else None
    kwargs = {"images": images} if images else {}
    result = _pool_generate(config_path)(prompt, **kwargs) or {}
    return json.dumps(result, ensure_ascii=False)


@mcp.tool()
def imagepool_render(spec_json: str, data_json: str = "", io_json: str = "",
                     config_path: str = "") -> str:
    """组装 + 一站式出图（真实消耗池子）。

    Args:
        spec_json: ShotSpec 字段 JSON
        data_json: 领域数据 JSON；留空用默认池
        io_json: 附加 io 覆盖 JSON（如 {"out_dir": "..."}）；留空用默认
        config_path: 池配置 JSON 路径；留空用 IMAGEPOOL_CONFIG 环境变量
    """
    io = _data_from_json(io_json)
    io.setdefault("generate", _pool_generate(config_path))
    result = render(_spec_from_json(spec_json), _data_from_json(data_json), io) or {}
    return json.dumps(result, ensure_ascii=False)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
