#!/usr/bin/env python3
"""把 assets/ 打包成 MXU 能直接跑的 install/ 布局。

MXU 只认「它自己所在目录」下的 interface.json + resource/ + locales/，
所以仓库里改完资源必须同步过去一次。

用法：
    python tools/pack.py            # assets -> install
    python tools/pack.py --check    # 只比对，不写（CI 用）
"""

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "assets"
DST = ROOT / "install"

# assets/ 下要同步到 install/ 顶层的东西
TOP_ITEMS = ["interface.json", "resource", "locales", "misc"]
# 运行时不缺、但会拖慢拷贝的（OCR 模型约有 30MB，还是需要同步，否则 OCR 节点静默失效）
EXTRA_IGNORE = {"__pycache__", ".DS_Store"}


def walk_files(base: Path):
    for path in base.rglob("*"):
        if path.is_file() and not EXTRA_IGNORE.intersection(path.parts):
            yield path.relative_to(base)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    if not SRC.is_dir():
        raise SystemExit(f"找不到 {SRC}")
    DST.mkdir(parents=True, exist_ok=True)

    changed, missing = [], []
    for item in TOP_ITEMS:
        src = SRC / item
        if not src.exists():
            continue
        if src.is_file():
            dst = DST / item
            if not dst.is_file() or not filecmp.cmp(src, dst, shallow=False):
                changed.append(item)
            continue
        for rel in walk_files(src):
            dst = DST / item / rel
            if not dst.is_file():
                missing.append(f"{item}/{rel}")
            elif not filecmp.cmp(SRC / item / rel, dst, shallow=False):
                changed.append(f"{item}/{rel}")

    if args.check:
        for p in missing[:20]:
            print(f"[missing] {p}")
        for p in changed[:20]:
            print(f"[diff] {p}")
        total = len(missing) + len(changed)
        print(f"install/ 与 assets/ 有 {total} 处差异")
        sys.exit(1 if total else 0)

    for item in TOP_ITEMS:
        src = SRC / item
        if not src.exists():
            continue
        dst = DST / item
        if src.is_file():
            shutil.copy2(src, dst)
            continue
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(*EXTRA_IGNORE))

    # maafw/ 与 mxu.exe 是外部二进制，不该由本脚本管；缺了要提示
    if not (DST / "mxu.exe").is_file():
        print("[warn] install/mxu.exe 不存在：从 MXU Releases 下载后放进 install/")
    if not (DST / "maafw").is_dir():
        print("[warn] install/maafw 不存在：把 MaaFramework 发行包 bin/ 与 share/MaaAgentBinary 放进去")

    print(f"已同步 {len(changed) + len(missing)} 个文件到 install/")


if __name__ == "__main__":
    main()
