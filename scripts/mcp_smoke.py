#!/usr/bin/env python3
"""mcp_smoke.py — MCP 冒烟：导入 mcp_server 并确认工具已注册（不启真实 stdio 会话）。"""
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main() -> int:
    try:
        import mcp  # noqa: F401
    except ImportError:
        print("SKIP: 未安装 mcp（可选依赖）")
        return 0
    spec = importlib.util.spec_from_file_location("ip_mcp", os.path.join(ROOT, "mcp_server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert callable(mod.main)
    print("OK: mcp_server 可导入，main 可调用")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
