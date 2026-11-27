"""CLI（迁移自已验证的 image_gen 实现；去掉 craft 门禁 / --en / --allow-raw / 宿主路径写死。

用法：
  python -m imagepool --config c.json --prompt-file /tmp/craft.txt --size square
  python -m imagepool --config c.json --list-providers
  python -m imagepool --config c.json --state
  python -m imagepool --config c.json --prompt-file x --dry-run
  python -m imagepool --config c.json --reset-provider
"""
import argparse
import json
import sys

from imagepool import config
from imagepool import pool


def main(argv=None):
    ap = argparse.ArgumentParser(description="图片生成池（imagepool，独立零依赖实现）")
    ap.add_argument("--config", required=True, help="主配置 JSON（含 pool_order + providers）")
    ap.add_argument("--runtime", default="", help="运行态 sidecar JSON（缺省不落盘）")
    ap.add_argument("--out-dir", default=".", help="落盘目录（缺省 cwd）")
    ap.add_argument("--prompt-file", help="craft 模板文件（纯出图池不校验内容）")
    ap.add_argument("--size", choices=["portrait", "landscape", "square"], default="square")
    ap.add_argument("--provider", help="强制指定（跳过轮转）")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--rr", action="store_true", help="轮转模式")
    ap.add_argument("--negative", default="")
    ap.add_argument("--list-providers", action="store_true")
    ap.add_argument("--state", action="store_true")
    ap.add_argument("--reset-provider", action="store_true", help="重置所有 provider 的 exhausted")
    ap.add_argument("--mark-exhausted", type=str, help="把指定 provider 标记为已耗尽")
    ap.add_argument("--dry-run", action="store_true", help="只预览 provider，不调接口")
    args = ap.parse_args(argv)

    try:
        cfg = config.load_config(args.config, runtime_path=args.runtime or None)
    except config.ConfigError as e:
        sys.stderr.write(f"配置错误: {e}\n")
        return 2

    if args.list_providers:
        provs = pool.ordered_active_providers(cfg)
        print(f"池子顺序: {' → '.join(p['name'] for p in provs) or '（无可用）'}")
        for p in cfg.get("providers", []):
            status = "❌ 已耗尽" if p.get("exhausted") else "✅ 可用"
            u = (p.get("usage") or {}).get("total_calls", 0)
            s = (p.get("usage") or {}).get("total_success", 0)
            q = p.get("free_quota", 0)
            qs = f"（免费 {q} 张，已用 {u}，成功 {s}）" if q else ""
            print(f"  {p['name']:<10} {status}  {p.get('description', '')} {qs}")
        return 0

    if args.state:
        print("池子状态:")
        for p in cfg.get("providers", []):
            u = p.get("usage") or {}
            calls = u.get("total_calls", 0)
            succ = u.get("total_success", 0)
            last = u.get("last_used") or "从未"
            ex = "已耗尽" if p.get("exhausted") else "可用"
            tm = last[:19] if last != "从未" else last
            print(f"  {p['name']:<10} {ex:6s} | 调用 {calls:3d} 次 | 成功 {succ:3d} 次 | 最后 {tm}")
        print(f"  更新: {cfg.get('_updated', '从未')}")
        return 0

    if args.reset_provider:
        for p in cfg.get("providers", []):
            p["exhausted"] = False
        pool.save_config(cfg, config_path=args.config, runtime_path=args.runtime or None)
        print("✅ 已重置所有 provider")
        return 0

    if args.mark_exhausted:
        target = next((p for p in cfg.get("providers", []) if p["name"] == args.mark_exhausted), None)
        if target:
            target["exhausted"] = True
            pool.save_config(cfg, config_path=args.config, runtime_path=args.runtime or None)
            print(f"✅ 已标记 {args.mark_exhausted} 为已耗尽")
        else:
            print(f"❌ 未找到 provider: {args.mark_exhausted}")
        return 0

    if args.dry_run:
        provs = pool.ordered_active_providers(cfg)
        print("📋 预览（不生成）")
        print(f"  provider: {provs[0]['name'] if provs else '无可用 provider'}")
        print(f"  尺寸:     {args.size}")
        return 0

    if not args.prompt_file:
        sys.stderr.write("需要 --prompt-file（或 --list-providers / --state / --reset-provider / --mark-exhausted / --dry-run）\n")
        return 2

    try:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            raw = f.read()
    except OSError as e:
        sys.stderr.write(f"craft 文件不可读: {e}\n")
        return 2

    result = pool.generate(
        raw, cfg, config_path=args.config, runtime_path=args.runtime or None,
        out_dir=args.out_dir, size=args.size, n=args.n, negative=args.negative,
        force_provider=args.provider, rr=args.rr)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if "urls" in result else 1


if __name__ == "__main__":
    sys.exit(main())