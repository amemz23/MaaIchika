#!/usr/bin/env python3
"""在 MXU 的配置里加一个「清日常」——按日常顺序排好的任务队列。

MXU 的配置存在 `install/config/mxu-MaaIchika.json`，结构：
  instances[] 每个就是一个配置标签页，里面 tasks[] 是按顺序执行的任务队列；
  taskName 用的是 `assets/interface.json` 里的 **name**（不是 label）。

日常顺序（顺序有意义：后面的任务都要求先回到主页）：
  启动 → 领礼包 → 任务奖励 → 每日挑战 → 清火

注意：**MXU 正在运行时它会把自己的内存状态写回这个文件**，所以改完必须让 MXU 重启；
如果关掉 MXU 后文件被覆盖（配置没出现），关掉 MXU 再跑一次本脚本即可。

用法：
    python tools/mxu_add_daily_config.py          # 加/更新「清日常」
    python tools/mxu_add_daily_config.py --list   # 只看当前有哪些配置
"""

import argparse
import json
import random
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "install" / "config" / "mxu-MaaIchika.json"

DAILY_NAME = "清日常"
DAILY_TASKS = ["设置分辨率", "启动", "领礼包", "任务奖励", "每日挑战", "清火"]


def rid(n=7):
    return "".join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    out = sys.stdout
    out.reconfigure(encoding="utf-8")

    if not CONFIG.is_file():
        sys.exit(f"找不到 MXU 配置：{CONFIG}\n先在 MXU 里打开一次这个项目")

    data = json.loads(CONFIG.read_text(encoding="utf-8"))

    if args.list:
        for inst in data.get("instances", []):
            names = [t["taskName"] for t in inst.get("tasks", [])]
            out.write(f"- {inst['name']}（{inst['controllerName']}/{inst['resourceName']}）：{names}\n")
        return

    # 取一台现有配置的 controller/resource 作为模板（新配置要跟着项目走）
    template = data["instances"][0] if data.get("instances") else {
        "controllerName": "Android",
        "resourceName": "Default",
    }

    tasks = [
        {
            "enabled": True,
            "enabledByController": {template["controllerName"]: True},
            "expanded": False,
            "id": rid(),
            "optionValues": {},
            "taskName": name,
        }
        for name in DAILY_TASKS
    ]

    existing = next((i for i in data.get("instances", []) if i.get("name") == DAILY_NAME), None)
    if existing:
        existing["tasks"] = tasks
        out.write(f"[更新] 配置「{DAILY_NAME}」：{DAILY_TASKS}\n")
    else:
        data.setdefault("instances", []).append(
            {
                "controllerName": template["controllerName"],
                "id": rid(),
                "name": DAILY_NAME,
                "resourceName": template["resourceName"],
                "tasks": tasks,
            }
        )
        out.write(f"[新增] 配置「{DAILY_NAME}」：{DAILY_TASKS}\n")

    CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    out.write(f"[ok] 已写入 {CONFIG.relative_to(ROOT)} —— 重启 MXU 生效\n")


if __name__ == "__main__":
    main()
