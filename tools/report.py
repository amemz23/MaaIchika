#!/usr/bin/env python3
"""把 debug/run_*.json 汇总成一张"各任务最后一次跑成什么样"的表。

用途：`tools/run.mjs` 每跑一个入口都会把节点链落到 `debug/run_<入口>.json`，
这里把这些碎片拼起来 —— 一眼看出哪个任务绿、哪个还欠验证、上次跑了多久、链尾落在哪。

用法：
    python tools/report.py            # 表格
    python tools/report.py --json     # 机器可读（接 CI / 看板用）
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEBUG = ROOT / "debug"
VERIFIED_TAILS = ("公共_主页锚点",)


def verdict_of(data: dict) -> str:
    nodes = data.get("nodes") or []
    tail = nodes[-1] if nodes else ""
    if data.get("verified") or tail in VERIFIED_TAILS or tail.startswith("完成_"):
        return "完成（已验证）"
    return "结束但未验证"


def collect():
    rows = []
    if not DEBUG.is_dir():
        return rows
    for file in sorted(DEBUG.glob("run_*.json")):
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        nodes = data.get("nodes") or []
        rows.append(
            {
                "entry": data.get("entry") or file.stem.removeprefix("run_"),
                "verdict": verdict_of(data),
                "seconds": round((data.get("ms") or 0) / 1000, 1),
                "steps": len(nodes),
                "tail": nodes[-1] if nodes else "-",
                "chain": " -> ".join(nodes),
                "mtime": datetime.fromtimestamp(file.stat().st_mtime).strftime("%m-%d %H:%M"),
            }
        )
    rows.sort(key=lambda r: (r["verdict"] != "完成（已验证）", r["entry"]))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    rows = collect()
    if not rows:
        print("还没有运行记录：先跑 node tools/run.mjs <任务入口>")
        return

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    tasks = [r for r in rows if r["entry"].startswith("任务_")]
    helpers = [r for r in rows if not r["entry"].startswith("任务_")]

    def dump(title, items):
        if not items:
            return
        print(f"\n== {title} ==")
        width = max(len(r["entry"]) for r in items) + 2
        print(f"{'入口'.ljust(width)}{'结论':<16}{'耗时':>8}{'步数':>6}  链尾 / 时间")
        for r in items:
            print(
                f"{r['entry'].ljust(width)}{r['verdict']:<16}{str(r['seconds']) + 's':>8}{r['steps']:>6}  "
                f"{r['tail']}  ({r['mtime']})"
            )

    ok = sum(1 for r in tasks if r["verdict"] == "完成（已验证）")
    print(f"最近 {len(rows)} 个入口的运行结果；其中任务入口 {len(tasks)} 个，{ok} 个已验证")
    dump("任务入口", tasks)
    dump("辅助节点（单独调试用，正常不在任务链尾）", helpers)

    bad = [r for r in tasks if r["verdict"] != "完成（已验证）"]
    if bad:
        print("\n未验证的任务（链尾没落在验证型终止节点上）：")
        for r in bad:
            print(f"  - {r['entry']}: {r['chain'] or '(空)'}")


if __name__ == "__main__":
    main()
