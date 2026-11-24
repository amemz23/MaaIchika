#!/usr/bin/env python3
"""生成 assets/icon.png —— MXU 在任务列表左上角显示的图标。

设计：初音绿（#39C5BB）的圆角方块 + 白色八分音符。
不用字体渲染（机器上不一定有合适字体），音符用基本图元拼：符头椭圆 + 符干 + 符尾。

尺寸 256×256（MXU 会自己缩放），同时导出 512 的高清版备用。
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "icon.png"

S = 512  # 先在大画布上画，再缩放，边缘更干净
TEAL_TOP = (60, 220, 205)
TEAL_BOTTOM = (24, 160, 155)


def rounded_mask(size, radius):
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    return mask


def gradient(size):
    img = Image.new("RGB", (size, size))
    d = ImageDraw.Draw(img)
    for y in range(size):
        t = y / (size - 1)
        d.line(
            [(0, y), (size, y)],
            fill=(
                int(TEAL_TOP[0] + (TEAL_BOTTOM[0] - TEAL_TOP[0]) * t),
                int(TEAL_TOP[1] + (TEAL_BOTTOM[1] - TEAL_TOP[1]) * t),
                int(TEAL_TOP[2] + (TEAL_BOTTOM[2] - TEAL_TOP[2]) * t),
            ),
        )
    return img


bg = gradient(S).convert("RGBA")
bg.putalpha(rounded_mask(S, int(S * 0.22)))

note = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(note)

# 符头（稍微倾斜的椭圆）
head = Image.new("RGBA", (200, 160), (0, 0, 0, 0))
ImageDraw.Draw(head).ellipse([0, 0, 199, 159], fill=(255, 255, 255, 255))
head = head.rotate(-20, resample=Image.BICUBIC, expand=True)
note.alpha_composite(head, (100, 300))

# 符干
d.rectangle([268, 110, 292, 360], fill=(255, 255, 255, 255))
# 符尾（两个弧线用多边形近似）
d.polygon([(268, 110), (392, 152), (392, 196), (268, 168)], fill=(255, 255, 255, 255))
d.polygon([(268, 196), (368, 230), (368, 266), (268, 240)], fill=(255, 255, 255, 255))

bg.alpha_composite(note)

# 底部细高光，增加层次
gloss = Image.new("RGBA", (S, S), (0, 0, 0, 0))
gd = ImageDraw.Draw(gloss)
gd.ellipse([-S * 0.3, -S * 0.75, S * 1.3, S * 0.35], fill=(255, 255, 255, 28))
gloss.putalpha(Image.composite(gloss.getchannel("A"), Image.new("L", (S, S), 0), rounded_mask(S, int(S * 0.22))))
bg.alpha_composite(gloss)

bg.resize((256, 256), Image.LANCZOS).save(OUT)
bg.resize((512, 512), Image.LANCZOS).save(ROOT / "assets" / "icon@512.png")
print(f"[ok] {OUT} (256x256) + assets/icon@512.png")
