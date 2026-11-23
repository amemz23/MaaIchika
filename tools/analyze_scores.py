#!/usr/bin/env python3
"""按标签统计每个模板的正/负样本分数分布，给出建议阈值。

分数来自 tools/score.mjs（直接调 MaaFramework 的 TemplateMatch，
和运行时完全一致），所以这里的结论可以直接抄进 pipeline。

用法：
    node tools/score.mjs --dir scratch/shots      # 先跑出 scratch/scores.json
    python tools/analyze_scores.py                # 再分析
    python tools/analyze_scores.py --apply        # 顺便把建议阈值写回 pipeline（只改不一致的）
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORES = ROOT / "scratch" / "scores.json"
LABELS = ROOT / "tools" / "labels.json"
PIPELINE = ROOT / "assets" / "resource" / "pipeline"

MARGIN = 0.05  # 正样本要留的余量


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    data = json.loads(SCORES.read_text(encoding="utf-8"))
    labels = json.loads(LABELS.read_text(encoding="utf-8"))
    states = labels["states"]
    expect = labels["expect"]

    # template 资源路径（image/ 下） -> crops.json 里的 name
    crops = json.loads((ROOT / "tools" / "crops.json").read_text(encoding="utf-8"))["crops"]
    path_of = {c["name"]: c["out"].replace("\\", "/") for c in crops}

    rows = {r["image"]: r["scores"] for r in data["rows"]}
    report = []
    for tpl in data["templates"]:
        name = tpl["name"]
        want = set(expect.get(name, []))
        pos, neg = [], []
        for image, scores in rows.items():
            st = states.get(image, "other")
            val = scores.get(name, {}).get("score")
            if val is None:
                continue
            (pos if st in want else neg).append((val, image, st))

        if not pos:
            report.append((name, None, None, None, None, "没有正样本（先在 labels.json 里标注）"))
            continue

        pos.sort(reverse=True)
        neg.sort(reverse=True)
        min_pos, min_pos_img, _ = pos[-1]
        max_neg, max_neg_img, max_neg_st = neg[0] if neg else (0.0, "-", "-")
        gap = min_pos - max_neg
        if gap < 0.10:
            verdict = "判别力不足：正负样本贴太近，换模板或缩小 roi"
        else:
            verdict = "OK"
        suggested = round(min(min_pos - MARGIN, (min_pos + max_neg) / 2), 2)
        report.append((name, min_pos, max_neg, max_neg_img, max_neg_st, suggested, verdict, gap))

    print(f"{'模板':22s}{'正样本min':>9s}{'负样本max':>9s}{'gap':>7s}  负样本天花板          建议阈值")
    for r in report:
        if r[1] is None:
            print(f"{r[0]:22s}  -- {r[5]}")
            continue
        name, min_pos, max_neg, max_neg_img, max_neg_st, suggested, verdict, gap = r
        print(
            f"{name:22s}{min_pos:9.3f}{max_neg:9.3f}{gap:7.3f}  {max_neg_img}({max_neg_st})".ljust(62)
            + f"{suggested:.2f}  {'' if verdict == 'OK' else '⚠ ' + verdict}"
        )

    if not args.apply:
        return

    applied = 0
    for name, min_pos, max_neg, _, _, suggested, verdict, gap in [r for r in report if r[1] is not None]:
        rel = path_of.get(name)
        if not rel:
            continue
        if gap < 0.10:
            # 判别力不足时**不要**动阈值：拿 max_neg + 0.03 会写出 >1.0 的阈值（永远不命中），
            # 或者写出贴着负样本的值（到处误判）。这种情况该换模板，不是调数字。
            print(f"[skip] {name}: gap={gap:.3f} 太小，先换模板/缩小 roi，不动阈值")
            continue
        # 取值：在正样本最低分下方留 0.05 余量，同时不超过正负中点
        recommended = min(min_pos - MARGIN, (min_pos + max_neg) / 2)
        recommended = max(0.50, min(0.95, recommended))
        for file in PIPELINE.glob("*.json"):
            text = file.read_text(encoding="utf-8")
            if f'"template": ["{rel}"]' not in text:
                continue
            pattern = re.compile(
                r'("template": \["' + re.escape(rel) + r'"\],\s*\n\s*"roi": \[[^\]]*\],\s*\n\s*"threshold": )([0-9.]+)'
            )
            new_text, n = pattern.subn(lambda m: m.group(1) + f"{recommended:.2f}", text)
            if n and new_text != text:
                file.write_text(new_text, encoding="utf-8", newline="\n")
                print(f"[apply] {file.name}: {name} threshold -> {recommended:.2f}")
                applied += 1
    print(f"[apply] 共更新 {applied} 处")


if __name__ == "__main__":
    main()
