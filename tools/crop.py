#!/usr/bin/env python3
"""按 spec 裁剪模板图，并可选生成一张带标注的对照图。

模板图必须是**从 720p 截图上原样裁下来**的一小块，不能缩放、不能带半透明动效。
所以这里统一：src 用 tools/device.py shot 产出的 1280×720 图，box 是 720 坐标。

用法：
    python tools/crop.py                # 按 tools/crops.json 全量裁剪
    python tools/crop.py --sheet        # 额外生成 scratch/sheet.png 便于肉眼核对
    python tools/crop.py --only title   # 只跑名字里含 title 的条目
"""

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "tools" / "crops.json"
IMAGE_DIR = ROOT / "assets" / "resource" / "image"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sheet", action="store_true")
    parser.add_argument("--only", default=None)
    args = parser.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    made = []
    for item in spec["crops"]:
        name = item["name"]
        if args.only and args.only not in name:
            continue
        src = ROOT / item["src"]
        if not src.is_file():
            print(f"[skip] 源图不存在: {src.relative_to(ROOT)}")
            continue
        x, y, w, h = item["box"]
        img = Image.open(src).convert("RGB")
        if img.size != (1280, 720):
            print(f"[error] {src.name} 不是 1280x720（{img.size}），模板会整体错位")
            continue
        out = IMAGE_DIR / item["out"]
        out.parent.mkdir(parents=True, exist_ok=True)
        img.crop((x, y, x + w, y + h)).save(out)
        made.append((name, out, w, h, item.get("note", "")))
        print(f"[crop] {name:24s} {w:3d}x{h:<3d} -> {out.relative_to(ROOT)}")

    if args.sheet and made:
        pad, label_h = 12, 18
        cell_w = max(m[2] for m in made) + pad * 2
        cell_h = max(m[3] for m in made) + pad * 2 + label_h
        cols = min(4, len(made))
        rows = (len(made) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), (40, 40, 48))
        draw = ImageDraw.Draw(sheet)
        for i, (name, out, w, h, _) in enumerate(made):
            cx, cy = (i % cols) * cell_w + pad, (i // cols) * cell_h + pad
            sheet.paste(Image.open(out), (cx, cy))
            draw.rectangle([cx, cy, cx + w, cy + h], outline=(120, 220, 160))
            draw.text((cx, cy + h + 3), f"{name} {w}x{h}", fill=(230, 230, 230))
        dst = ROOT / "scratch" / "sheet.png"
        dst.parent.mkdir(exist_ok=True)
        sheet.save(dst)
        print(f"[sheet] {dst.relative_to(ROOT)}  ({len(made)} 张)")


if __name__ == "__main__":
    main()
