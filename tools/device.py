#!/usr/bin/env python3
"""设备工具：分辨率标准化 / 截图 / 点击（坐标一律 1280×720 基准）。

为什么要有这一层：

1. MaaFramework 只按 `display_short_side` **等比缩放**，不补偿宽高比。
   16:9 的 2560×1440 会缩成 1280×720（= 项目坐标基准），而 1:1.41 的平板
   会缩成 1018×720，坐标与模板图全部错位。所以先把设备刷成 16:9。
2. 本工具的所有 tap/swipe 坐标都按 1280×720 传入，内部换算成设备像素，
   这样"看图说话"时的坐标可以直接抄进 pipeline。

用法：
    python tools/device.py check              # 跑任务前自检
    python tools/device.py info
    python tools/device.py fix                # 刷成 1440x2560@420（竖屏原生平板）
    python tools/device.py fix --preset landscape-1080p
    python tools/device.py reset              # 还原物理分辨率
    python tools/device.py shot out.png       # 截图（同时存一份 720p）
    python tools/device.py tap 640 470        # 720 坐标点击
    python tools/device.py swipe 640 600 640 200 300
    python tools/device.py back / home
    python tools/device.py launch com.sega.pjsekai
    python tools/device.py awake              # 唤醒 + 常亮
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

BASE_W, BASE_H = 1280, 720
ROOT = Path(__file__).resolve().parent.parent

COMMON_ADB = [
    Path.home() / "AppData/Local/Android/Sdk/platform-tools/adb.exe",
    Path("C:/Program Files/Netease/MuMuPlayer-12.0/shell/adb.exe"),
    Path("C:/Leidian/LDPlayer9/adb.exe"),
]

# 16:9 预设。注意 `wm size` 解释的是**自然方向**的尺寸：
# 竖屏原生设备（平板/手机）要写竖着的宽高，横屏原生（模拟器）写横的。
PRESETS = {
    "portrait-tablet-1440": ("1440x2560", "420"),
    "portrait-phone-1080": ("1080x1920", "480"),
    "landscape-1080p": ("1920x1080", "320"),
    "landscape-1440p": ("2560x1440", "320"),
}
DEFAULT_PRESET = "portrait-tablet-1440"


def find_adb(explicit):
    if explicit:
        return explicit
    found = shutil.which("adb")
    if found:
        return found
    for path in COMMON_ADB:
        if path.exists():
            return str(path)
    raise SystemExit("找不到 adb：用 --adb 指定，或把 platform-tools 加进 PATH")


def run(adb, serial, *args, binary=False):
    cmd = [adb] + (["-s", serial] if serial else []) + list(args)
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise SystemExit(f"adb 失败: {' '.join(cmd)}\n{proc.stderr.decode('utf-8', 'replace').strip()}")
    if binary:
        return proc.stdout
    return proc.stdout.decode("utf-8", "replace").strip()


def parse_sizes(text):
    """返回 (物理尺寸, Override 尺寸或 None)。"""
    physical = override = None
    for line in text.splitlines():
        low = line.lower()
        if "physical size" in low:
            w, h = line.split(":")[1].strip().split("x")
            physical = (int(w), int(h))
        elif "override size" in low:
            w, h = line.split(":")[1].strip().split("x")
            override = (int(w), int(h))
    if physical is None:
        raise SystemExit(f"无法解析 wm size 输出:\n{text}")
    return physical, override


def effective_size(text):
    """生效的「当前方向」尺寸：Override 优先。"""
    _, override = parse_sizes(text)
    if override:
        return override
    return parse_sizes(text)[0]


def aspect_ok(w, h):
    long_side, short_side = max(w, h), min(w, h)
    return abs(long_side / short_side - BASE_W / BASE_H) < 0.01


def canvas_of(w, h):
    """框架缩放后的画布尺寸：短边固定 720。"""
    ratio = max(w, h) / min(w, h)
    return round(720 * ratio), 720


def cmd_check(adb, serial, size_text, density_text):
    physical, override = parse_sizes(size_text)
    w, h = effective_size(size_text)
    pw, ph = physical
    ok = True
    print(f"物理分辨率 : {pw}x{ph}")
    print(f"生效分辨率 : {w}x{h}" + ("  (Override)" if override else "  (未覆盖，即物理值)"))
    print(f"密度       : {density_text.split(':')[-1].strip()}")

    ratio = max(w, h) / min(w, h)
    canvas = canvas_of(w, h)
    if canvas == (BASE_W, BASE_H):
        print(f"宽高比     : {ratio:.3f} → 16:9  OK")
        print(f"画布       : {BASE_W}x{BASE_H}  OK")
    else:
        print(f"宽高比     : {ratio:.3f} → 不是 16:9  FAIL")
        print(f"画布       : {canvas[0]}x{canvas[1]}  FAIL（应为 {BASE_W}x{BASE_H}）")
        print("             处理：python tools/device.py fix")
        ok = False

    # 竖屏原生设备却被设成横屏尺寸 → 横屏游戏会被强制竖屏
    if ph > pw and w > h:
        print("方向       : FAIL —— 竖屏原生设备设成了横屏尺寸，游戏会被强制竖屏")
        print(f"             应写 {h}x{w}（宽高对调）")
        ok = False
    elif ph > pw:
        print("方向       : 竖屏原生 + 竖屏自然方向  OK")
    else:
        print("方向       : 横屏原生  OK")

    print("结论       : " + ("可以跑任务" if ok else "有问题，先 fix"))
    return ok


def main():
    parser = argparse.ArgumentParser(description="设备控制（坐标基准 1280x720）", add_help=True)
    parser.add_argument("action", choices=[
        "check", "info", "fix", "reset", "shot", "tap", "swipe", "back", "home",
        "launch", "awake", "key",
    ])
    parser.add_argument("rest", nargs="*", help="视 action 而定：坐标 / 路径 / 包名 / 按键")
    parser.add_argument("--adb", default=None)
    parser.add_argument("--serial", default=None)
    parser.add_argument("--preset", default=DEFAULT_PRESET, choices=sorted(PRESETS))
    parser.add_argument("--long", action="store_true", help="tap 改为长按 1s")
    parser.add_argument("--stayon", action="store_true", help="shot/tap 前顺带唤醒并常亮")
    args = parser.parse_args()

    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    adb = find_adb(args.adb)
    serial = args.serial

    if args.action in ("check", "info", "fix"):
        size_text = run(adb, serial, "shell", "wm", "size")
        density_text = run(adb, serial, "shell", "wm", "density")
        w, h = effective_size(size_text)
        if args.action == "check":
            sys.exit(0 if cmd_check(adb, serial, size_text, density_text) else 1)
        if args.action == "info":
            print(size_text)
            print(density_text)
            print(f"生效 {w}x{h}，16:9: {'是' if aspect_ok(w, h) else '否 —— 先 fix'}")
            sys.exit(0 if aspect_ok(w, h) else 1)
        if args.action == "fix":
            pw, ph = parse_sizes(size_text)[0]
            fw, fh = (int(x) for x in PRESETS[args.preset][0].split("x"))
            if not aspect_ok(fw, fh):
                raise SystemExit(f"{args.preset} 不是 16:9")
            # 竖屏原生设备：wm size 按自然方向解释，宽高要对调
            if ph > pw and fw > fh:
                fw, fh = fh, fw
                print(f"竖屏原生设备 → 按自然方向设置 {fw}x{fh}")
            run(adb, serial, "shell", "wm", "size", f"{fw}x{fh}")
            run(adb, serial, "shell", "wm", "density", PRESETS[args.preset][1])
            print(f"已设置 {fw}x{fh} / {PRESETS[args.preset][1]} dpi（重启游戏后生效）")
            return

    # 当前方向的显示尺寸：`wm size` 给的是自然方向，横屏游戏时需要宽高互换。
    # 直接问 window manager 拿 `cur=WxH`，比猜方向可靠。
    def current_size():
        try:
            out = run(adb, serial, "shell", "dumpsys", "window", "displays")
            import re

            m = re.search(r"cur=(\d+)x(\d+)", out)
            if m:
                return int(m.group(1)), int(m.group(2))
        except SystemExit:
            pass
        w, h = effective_size(size_text)
        return w, h

    def to_device_xy(x, y):
        # 短边映射到 720（与 MaaFramework 的 display_short_side 一致），等比缩放
        dw_, dh_ = current_size()
        scale = min(dw_, dh_) / BASE_H
        return round(x * scale), round(y * scale)

    action = args.action
    rest = args.rest

    if args.stayon and action in ("shot", "tap", "swipe", "launch"):
        run(adb, serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP")
        run(adb, serial, "shell", "svc", "power", "stayon", "true")

    if action == "reset":
        run(adb, serial, "shell", "wm", "size", "reset")
        run(adb, serial, "shell", "wm", "density", "reset")
        print("已还原物理分辨率")
        return

    if action == "awake":
        run(adb, serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP")
        run(adb, serial, "shell", "svc", "power", "stayon", "true")
        print("已唤醒 + 常亮")
        return

    if action == "shot":
        out = Path(rest[0]) if rest else ROOT / "scratch" / "shot.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        raw = out.with_name(out.stem + "_raw.png")
        data = run(adb, serial, "exec-out", "screencap", "-p", binary=True)
        raw.write_bytes(data)
        from PIL import Image

        img = Image.open(raw).convert("RGB")
        img.resize((BASE_W, BASE_H), Image.LANCZOS).save(out)
        print(f"{out}  (raw {raw.name}, {img.width}x{img.height})")
        return

    if action == "tap":
        x, y = (float(v) for v in rest[:2])
        dx, dy = to_device_xy(x, y)
        if args.long:
            run(adb, serial, "shell", "input", "swipe", str(dx), str(dy), str(dx), str(dy), "1000")
        else:
            run(adb, serial, "shell", "input", "tap", str(dx), str(dy))
        print(f"tap ({x},{y}) -> ({dx},{dy})")
        return

    if action == "swipe":
        x1, y1, x2, y2 = (float(v) for v in rest[:4])
        dur = rest[4] if len(rest) > 4 else "300"
        a = to_device_xy(x1, y1)
        b = to_device_xy(x2, y2)
        run(adb, serial, "shell", "input", "swipe", str(a[0]), str(a[1]), str(b[0]), str(b[1]), str(dur))
        print(f"swipe {a} -> {b} ({dur}ms)")
        return

    if action == "back":
        run(adb, serial, "shell", "input", "keyevent", "KEYCODE_BACK")
        print("BACK")
        return

    if action == "home":
        run(adb, serial, "shell", "input", "keyevent", "KEYCODE_HOME")
        print("HOME")
        return

    if action == "key":
        run(adb, serial, "shell", "input", "keyevent", rest[0])
        print(f"key {rest[0]}")
        return

    if action == "launch":
        pkg = rest[0] if rest else "com.sega.pjsekai"
        run(adb, serial, "shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")
        print(f"launched {pkg}")
        return

    raise SystemExit(f"未处理的动作: {action}")


if __name__ == "__main__":
    main()
