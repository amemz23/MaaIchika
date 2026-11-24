#!/usr/bin/env python3
"""把 agent 需要的运行时塞进 install/，让用户不用自己装 Node。

产物：
    install/node/node.exe                          Node 运行时（约 80MB）
    install/agent/main.mjs                         agent 本体
    install/agent/node_modules/@maaxyz/maa-node/   agent 依赖（含原生插件）
    assets/interface.json 的 agent 字段            指向上面两个

为什么放在 `install/agent/node_modules/` 而不是 `install/node_modules/`：
Node 的模块解析是从文件所在目录往上找 `node_modules`，放 agent 子目录里就够用，
不会污染 install/ 根目录（MXU 会读根目录下的 interface.json / resource / locales）。

用法：
    python tools/bundle_runtime.py           # 同步
    python tools/bundle_runtime.py --check   # 只检查缺什么
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install"
AGENT_SRC = ROOT / "agent"
PKG_SRC = ROOT / "node_modules" / "@maaxyz" / "maa-node"
NODE_CANDIDATES = [
    # 本机 DSH 运行时的 node（就是跑 tools/run.mjs 的那个）
    Path.home() / ".dsh" / "dsh-runtimes" / "dsh-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe",
]

AGENT_FIELD = {"child_exec": "node/node.exe", "child_args": ["agent/main.mjs"]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    node_exe = next((p for p in NODE_CANDIDATES if p.is_file()), None)
    missing = []
    if not node_exe:
        missing.append("node.exe（找不到；可用 --node 指定）")
    if not (AGENT_SRC / "main.mjs").is_file():
        missing.append("agent/main.mjs")
    if not PKG_SRC.is_dir():
        missing.append("node_modules/@maaxyz/maa-node")
    if missing:
        print("[缺少] " + "、".join(missing), file=sys.stderr)
        return 1

    if args.check:
        print(f"node: {node_exe}")
        print(f"agent: {(AGENT_SRC / 'main.mjs')}")
        print(f"maa-node: {PKG_SRC}")
        print(f"install 里已 bundle: {(INSTALL / 'node' / 'node.exe').is_file()}")
        return 0

    # 1) node 运行时
    (INSTALL / "node").mkdir(parents=True, exist_ok=True)
    shutil.copy2(node_exe, INSTALL / "node" / "node.exe")

    # 2) agent 本体
    dst_agent = INSTALL / "agent"
    if dst_agent.exists():
        shutil.rmtree(dst_agent)
    dst_agent.mkdir(parents=True)
    shutil.copy2(AGENT_SRC / "main.mjs", dst_agent / "main.mjs")

    # 3) agent 依赖（只带 maa-node，别把整个 node_modules 搬过去）
    dst_pkg = dst_agent / "node_modules" / "@maaxyz" / "maa-node"
    dst_pkg.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PKG_SRC, dst_pkg)

    # 4) interface.json 的 agent 字段
    iface_path = ROOT / "assets" / "interface.json"
    iface = json.loads(iface_path.read_text(encoding="utf-8"))
    iface["agent"] = AGENT_FIELD
    iface_path.write_text(json.dumps(iface, ensure_ascii=False, indent=4) + "\n", encoding="utf-8", newline="\n")

    size = sum(p.stat().st_size for p in (INSTALL / "node").rglob("*") if p.is_file())
    size += sum(p.stat().st_size for p in dst_agent.rglob("*") if p.is_file())
    print(f"[ok] install/node/node.exe + install/agent/（合计约 {size / 1024 / 1024:.0f} MB）")
    print(f"[ok] interface.json agent = {AGENT_FIELD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
