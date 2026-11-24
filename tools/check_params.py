#!/usr/bin/env python3
"""ROI / 模板 / 阈值 的静态检查。

`check_json.py` 管结构与引用，这里管"数字对不对"：

1. 每个 `roi` 必须落在 1280×720 画布内（AGENTS 第 1 条：一切坐标以 1280×720 为基准）
2. 每个 `target` / `target_offset` 同理（点不到的画面外坐标 = 盲点）
3. 每个 `template` 文件必须真的存在于资源包的 `image/` 下
4. `threshold` 必须在 (0, 1] 内 —— 写 1.03 这种就永远命中不了
5. `ColorMatch` 的 `lower` / `upper` 通道数必须和 `method` 一致（4=RGB/40=HSV→3，6=GRAY→1），
   且 lower <= upper

用法：
    python tools/check_params.py          # 有问题返回 1
    python tools/check_params.py --quiet  # 只打印问题
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTERFACE = ROOT / "assets" / "interface.json"
BASE_W, BASE_H = 1280, 720
CHANNELS = {4: 3, 40: 3, 6: 1, 0: 3}  # cv: RGB / HSV / GRAY / BGR


def iter_rects(node):
    """把节点里所有 roi / target / begin / end 都挖出来（含 Or/And 内联子识别）。"""
    out = []

    def walk(obj, path):
        if isinstance(obj, dict):
            for key, val in obj.items():
                if key in ("roi", "target", "begin", "end", "target_offset", "roi_offset") and isinstance(val, list):
                    if len(val) == 4 and all(isinstance(v, (int, float)) for v in val):
                        out.append((path + "/" + key, key, val))
                elif key in ("any_of", "all_of") and isinstance(val, list):
                    for i, sub in enumerate(val):
                        walk(sub, f"{path}/{key}[{i}]")
                else:
                    walk(val, path + "/" + key)
        elif isinstance(obj, list):
            for i, val in enumerate(obj):
                walk(val, f"{path}[{i}]")

    walk(node, "")
    return out


def iter_templates(node):
    out = []

    def walk(obj, path):
        if isinstance(obj, dict):
            for key, val in obj.items():
                if key == "template":
                    items = val if isinstance(val, list) else [val]
                    for t in items:
                        if isinstance(t, str):
                            out.append(t)
                elif key in ("any_of", "all_of") and isinstance(val, list):
                    for i, sub in enumerate(val):
                        walk(sub, f"{path}/{key}[{i}]")
                else:
                    walk(val, path + "/" + key)
        elif isinstance(obj, list):
            for val in obj:
                walk(val, path)

    walk(node, "")
    return out


def iter_thresholds(node):
    out = []

    def walk(obj, path):
        if isinstance(obj, dict):
            for key, val in obj.items():
                if key == "threshold":
                    vals = val if isinstance(val, list) else [val]
                    for t in vals:
                        if isinstance(t, (int, float)):
                            out.append((path + "/threshold", float(t)))
                elif key in ("any_of", "all_of") and isinstance(val, list):
                    for i, sub in enumerate(val):
                        walk(sub, f"{path}/{key}[{i}]")
                else:
                    walk(val, path + "/" + key)
        elif isinstance(obj, list):
            for val in obj:
                walk(val, path)

    walk(node, "")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    interface = json.loads(INTERFACE.read_text(encoding="utf-8"))
    bundles = []
    for res in interface.get("resource", []):
        for raw in res.get("path", []):
            bundles.append((INTERFACE.parent / raw.replace("{PROJECT_DIR}", str(ROOT))).resolve())

    errors, warnings = [], []
    files = 0
    nodes = 0
    templates = 0

    for bundle in bundles:
        image_dir = bundle / "image"
        for file in sorted((bundle / "pipeline").glob("*.json")):
            files += 1
            data = json.loads(file.read_text(encoding="utf-8"))
            for name, body in data.items():
                if not isinstance(body, dict) or name.startswith("$"):
                    continue
                nodes += 1
                where = f"{file.name}:{name}"

                for path, key, rect in iter_rects(body):
                    x, y, w, h = rect
                    # 负数坐标/尺寸是 v5.6+ 的合法写法（从右/下边界算），跳过边界检查
                    if min(x, y, w, h) < 0:
                        continue
                    if x == 0 and y == 0 and w == 0 and h == 0:
                        continue  # 全屏
                    if x + w > BASE_W + 1 or y + h > BASE_H + 1:
                        errors.append(f"{where}{path}: {key}={rect} 超出 1280×720 画布")
                    if key in ("roi", "target") and (w == 0 or h == 0) and not (w == 0 and h == 0):
                        warnings.append(f"{where}{path}: {key}={rect} 宽或高为 0")

                for tpl in iter_templates(body):
                    templates += 1
                    if not (image_dir / tpl).is_file():
                        errors.append(f"{where}: template 不存在: image/{tpl}")

                for path, th in iter_thresholds(body):
                    if not (0 < th <= 1):
                        errors.append(f"{where}{path}: threshold={th} 必须在 (0, 1] 内")

                reco = body.get("recognition")
                param = reco.get("param") if isinstance(reco, dict) else None
                if isinstance(param, dict) and reco.get("type") == "ColorMatch":
                    method = param.get("method", 4)
                    want = CHANNELS.get(method)
                    lower, upper = param.get("lower"), param.get("upper")
                    if want and isinstance(lower, list) and isinstance(upper, list):
                        if len(lower) != want or len(upper) != want:
                            errors.append(f"{where}: ColorMatch method={method} 需要 {want} 通道，lower/upper 长度是 {len(lower)}/{len(upper)}")
                        elif any(lo > up for lo, up in zip(lower, upper)):
                            errors.append(f"{where}: ColorMatch lower 有分量大于 upper: {lower} vs {upper}")

    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)
    for e in errors:
        print(f"[error] {e}", file=sys.stderr)
    if not args.quiet:
        print(f"检查 {files} 个 pipeline 文件 / {nodes} 个节点 / {templates} 个模板引用，{len(errors)} 错误，{len(warnings)} 警告")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
