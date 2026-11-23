#!/usr/bin/env python3
"""下载 PPOCR 模型到 assets/resource/model/ocr/。

没有模型时 OCR 节点会**静默不命中** —— 表现是"任务跑完了但什么都没做"，
和节点写错很难区分。所以换机器后第一件事就是跑这个。

用法：
    python tools/fetch_ocr.py            # 拉 ppocr_v6/small
    python tools/fetch_ocr.py --check    # 只检查在不在
"""

import argparse
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / "assets" / "resource" / "model" / "ocr"
FILES = ("det.onnx", "rec.onnx", "keys.txt")

# MaaCommonAssets 里 PPOCR v6 small 的打包（与 MaaFramework 默认检测一致）
URL = "https://github.com/MaaXYZ/MaaCommonAssets/releases/download/ppocr-v6/PPOCRv6-small.zip"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--url", default=URL)
    args = parser.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    have = [f for f in FILES if (DST / f).is_file()]
    if len(have) == len(FILES):
        print(f"OCR 模型齐全：{DST}")
        return
    if args.check:
        print(f"缺模型：{[f for f in FILES if f not in have]}（跑 python tools/fetch_ocr.py）")
        sys.exit(1)

    DST.mkdir(parents=True, exist_ok=True)
    print(f"下载 {args.url}")
    data = urllib.request.urlopen(args.url, timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            name = Path(member).name
            if name in FILES:
                (DST / name).write_bytes(zf.read(member))
                print(f"  -> {name}")
    missing = [f for f in FILES if not (DST / f).is_file()]
    if missing:
        raise SystemExit(f"压缩包里没找到 {missing}，手动放到 {DST} 也行")


if __name__ == "__main__":
    main()
