#!/usr/bin/env python3
"""生成识别基线文档：每个模板的来源、阈值、实测分数。

数据来自 tools/crops.json（裁图出处）+ tools/labels.json（界面标签）+
scratch/scores.json（框架打分）。这样"阈值为什么是这个数"永远有出处可查，
而不是散落在聊天记录里。

用法：
    node tools/score.mjs --dir scratch/shots    # 先打分
    python tools/gen_baseline.py               # 生成 docs/zh_cn/developers/recognition-baseline.md
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "zh_cn" / "developers" / "recognition-baseline.md"


def load(p):
    f = ROOT / p
    return json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    crops = load("tools/crops.json")["crops"]
    labels = load("tools/labels.json")
    scores = load("scratch/scores.json")

    states = labels["states"] if labels else {}
    expect = labels["expect"] if labels else {}
    rows = {r["image"]: r["scores"] for r in scores["rows"]} if scores else {}

    lines = [
        "# 识别基线",
        "",
        "> 本文件由 `python tools/gen_baseline.py` 生成，**不要手改**。",
        "> 数据来源：模板由图中的 720p 截图像素级裁出，分数由 MaaFramework 自己的",
        "> TemplateMatch（method 5, TM_CCOEFF_NORMED）在同一批截图上实测。",
        "> 重新生成：`node tools/score.mjs --dir scratch/shots && python tools/gen_baseline.py`。",
        "",
        "## 模板一览",
        "",
        "| 模板 | 来源 | 尺寸 | 正样本最低分 | 负样本最高分 | 判别力 gap | 现用阈值 | 说明 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    from PIL import Image

    for c in crops:
        name = c["name"]
        img_path = ROOT / "assets" / "resource" / "image" / c["out"]
        size = Image.open(img_path).size if img_path.is_file() else ("?", "?")
        want = set(expect.get(name, []))
        pos, neg = [], []
        for image, sc in rows.items():
            val = sc.get(name, {}).get("score")
            if val is None:
                continue
            (pos if states.get(image, "other") in want else neg).append((val, image))
        if pos and neg:
            min_pos, min_img = min(pos)
            max_neg, max_neg_img = max(neg)
            gap = f"{min_pos - max_neg:.3f}"
            pos_s = f"{min_pos:.3f}"
            neg_s = f"{max_neg:.3f} ({max_neg_img})"
        elif pos:
            min_pos = min(pos)[0]
            pos_s, neg_s, gap = f"{min_pos:.3f}", "—", "—"
        else:
            pos_s, neg_s, gap = "—", "—", "—"
        lines.append(
            f"| `{c['out']}` | `{c['src']}` {c['box']} | {size[0]}×{size[1]} | "
            f"{pos_s} | {neg_s} | {gap} | — | {c.get('note', '')} |"
        )

    lines += [
        "",
        "## 判别力怎么读",
        "",
        "- **正样本最低分**：在所有「应该命中」的截图上，最差的那次得了多少分。",
        "- **负样本最高分**：在所有「不该命中」的截图上，最高蹭到多少分。",
        "- **gap**：两者之差。gap ≥ 0.2 说明阈值有充足余量；gap < 0.1 说明这个模板",
        "  和别的画面分不开，该换模板（裁得更紧、去掉半透明边缘）或换识别方式。",
        "",
        "## 关键教训",
        "",
        "1. **带圆底的图标会和别的圆钮混淆**：返回箭头如果连白色圆底一起裁，主页左上角",
        "   的「世界/区域」按钮能拿到 0.959。只裁箭头字形后，主页跌到 0.515、真箭头仍是 1.000。",
        "2. **同一元素在不同面板上分数不同**：公告的 X 在一种面板上 1.000，在「通知列表」",
        "   面板上只有 0.787。阈值要按**最差的正样本**定，不是按最好。",
        "3. **会被特效遮挡的元素不能当锚点**：演出中的 `AUTO LIVE` 胶囊实测最低 0.41，",
        "   拿它判断「还在演出中」会在半场误判结束。改成只等「结束信号」。",
        "4. **有的元素有暗态**：编成页的播放按钮在过渡时偏暗，模板只掉到 0.61（正常 0.94+）。",
        "   所以这个节点靠 `max_hit` 多次重试等到它亮起来，而不是把阈值压到 0.6 去迎合暗态。",
        "5. **OCR 比模板更适合认大字**：`LIVE CLEAR!`、结算按钮这类文字，OCR 不受",
        "   背景亮带影响，而且天然跨语言。",
        "",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"[写出] {OUT.relative_to(ROOT)}（{len(crops)} 个模板）")


if __name__ == "__main__":
    main()
