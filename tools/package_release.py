#!/usr/bin/env python3
"""把 `install/` 打成一个**合规**的 GitHub Release 压缩包。

为什么需要它：一次性把"开箱即用"的整包发出去，包里就同时含有四种别人的东西
（MaaFramework LGPL-3.0 / MaaAgentBinary AGPL-3.0 / MXU AGPL-3.0 / node MIT+第三方），
少带一份许可证就是不合规。这个脚本固定做四件事：

1. 只挑**运行时需要**的文件（`install/cache`、`config`、`debug` 这些 MXU 跑出来的用户数据不打包）；
2. 把 `licenses/` 全量带上，并生成 `SOURCE-OFFER.md` —— 写清每个第三方组件的版本、授权、
   源码地址、"未修改、可直接替换"（LGPL §4 / AGPL §6 要的就是这些）；
3. 生成 `START-HERE.md`（给最终用户的 5 行上手说明）；
4. 顺手生成 `dist/RELEASE-NOTES.md`，贴到 GitHub Release 正文即可。

用法：
    python tools/fetch_licenses.py       # 先补齐 licenses/（只需一次）
    python tools/pack.py                 # assets -> install
    python tools/bundle_runtime.py       # node + agent -> install
    python tools/package_release.py      # -> dist/MaaIchika-v<ver>-win-x64.zip
    python tools/package_release.py --no-mxu    # 不打包 mxu.exe（少一份 AGPL 义务）
    python tools/package_release.py --check     # 只体检，不打包
"""

import argparse
import json
import shutil
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALL = ROOT / "install"
DIST = ROOT / "dist"
LICENSES = ROOT / "licenses"

# 从 install/ 里挑进包的东西（白名单：绝不整目录复制，避免把 cache/config/debug 带出去）
FROM_INSTALL = [
    "interface.json",
    "icon.png",
    "resource",
    "locales",
    "misc",
    "maafw",
    "node",
    "agent",
]

# licenses/ 里必须有这些（tools/fetch_licenses.py 负责生成）
REQUIRED_LICENSES = [
    "LGPL-3.0.txt",
    "GPL-3.0.txt",
    "AGPL-3.0.txt",
    "Node-LICENSE.txt",
    "MIT-MaaCommonAssets.txt",
]

SOURCE_ROWS = [
    (
        "MaaFramework",
        "v{fw}",
        "LGPL-3.0",
        "https://github.com/MaaXYZ/MaaFramework",
        "未修改；`maafw/*.dll` 可直接替换成你自己编译的版本（动态链接）",
    ),
    (
        "MaaAgentBinary（minitouch / maatouch）",
        "随 MaaFramework 发行包",
        "AGPL-3.0",
        "https://github.com/MaaXYZ/MaaAgentBinary",
        "未修改；`maafw/MaaAgentBinary/` 与 `agent/node_modules/@maaxyz/maa-node/agent/` 两处都有，各自自带 LICENSE",
    ),
    (
        "MXU",
        "{mxu}",
        "AGPL-3.0",
        "https://github.com/MaaXYZ/MXU",
        "未修改；`mxu.exe` 可直接替换",
    ),
    (
        "Node.js",
        "{node}",
        "MIT + 第三方",
        "https://github.com/nodejs/node",
        "未修改；`node/node.exe` 只给 agent 用",
    ),
    (
        "PPOCRv6-small 模型",
        "MaaCommonAssets tag ppocr-v6",
        "MIT",
        "https://github.com/MaaXYZ/MaaCommonAssets",
        "未修改；`resource/model/ocr/`",
    ),
    (
        "MaaIchika（本项目）",
        "v{ver}",
        "MIT",
        "https://github.com/amemz23/MaaIchika",
        "本项目自己的 Pipeline / 工具 / agent",
    ),
]

GAME_NOTICE = """
## 关于游戏素材

`resource/image/` 下的模板图与 `icon.png` **不是本项目授权范围**：

- 它们是从游戏画面裁下来的一小块 / 含角色形象，著作权归 **SEGA / Colorful Palette**；
- 用途仅限**图像匹配**（让自动化知道按钮在屏幕哪个位置），非官方、非商业，与权利方无关联；
- 权利方要求即删：删掉 `resource/image/` 与 `icon.png` 后程序仍可运行，只是需要重新裁模板。

「Project SEKAI COLORFUL STAGE! feat. Hatsune Miku」及角色名称、形象是 SEGA / Colorful Palette
的商标或注册商标。
"""


def node_version():
    exe = INSTALL / "node" / "node.exe"
    if not exe.is_file():
        return "（未打包）"
    try:
        out = subprocess.run([str(exe), "--version"], capture_output=True, text=True, timeout=20)
        return out.stdout.strip() or "（读不到版本）"
    except Exception:  # noqa: BLE001 - 拿不到版本不影响打包，降级成提示
        return "（读不到版本）"


def clear_readonly(root):
    """把目录树里的只读属性清掉。

    Windows 上 `shutil.rmtree` 删不掉只读文件 —— `install/icon.png` 就自带 ReadOnly 属性
    （从素材导出时带上的），上一次打包留下的 stage 目录因此删不掉、第二次打包直接 PermissionError。
    """
    for path in root.rglob("*"):
        try:
            path.chmod(stat.S_IWRITE)
        except OSError:
            pass


def force_rmtree(path):
    if not path.exists():
        return
    clear_readonly(path)
    shutil.rmtree(path)


def check(with_mxu):
    problems = []
    version = None
    iface = INSTALL / "interface.json"
    if iface.is_file():
        version = json.loads(iface.read_text(encoding="utf-8")).get("version")
    else:
        problems.append("install/interface.json 不存在 —— 先跑 python tools/pack.py")

    for item in FROM_INSTALL:
        if not (INSTALL / item).exists():
            problems.append(f"install/{item} 不存在")
    for name in REQUIRED_LICENSES:
        if not (LICENSES / name).is_file():
            problems.append(f"licenses/{name} 不存在 —— 跑 python tools/fetch_licenses.py")
    if with_mxu and not (INSTALL / "mxu.exe").is_file():
        problems.append("install/mxu.exe 不存在（要么放进去，要么加 --no-mxu）")

    # 只提示、不阻断：这两个也许有人会用 mkdocs 之类的方式另外分发
    for extra in ("install/cache", "install/config", "install/debug"):
        if (ROOT / extra).exists():
            print(f"[info] {extra} 存在，但不会被打进包（那是 MXU 跑出来的用户数据）")
    return version, problems


def write_source_offer(dst, version, node_ver, mxu_ver):
    rows = "\n".join(
        f"| {name} | {ver.format(fw='5.16.1', node=node_ver, mxu=mxu_ver, ver=version)} "
        f"| {lic} | {url} | {note} |"
        for name, ver, lic, url, note in SOURCE_ROWS
    )
    text = f"""# 第三方组件与源码获取方式

本发布包（MaaIchika v{version}）里除了本项目自己的 Pipeline / 工具之外，还打进了下面这些
**别人的东西**。它们的授权都允许分发，条件是随包提供许可证全文与源码获取方式 —— 这就是本文件的作用。

| 组件 | 版本 | 授权 | 源码 | 本项目做了什么 |
| --- | --- | --- | --- | --- |
{rows}

许可证全文都在本目录的 `licenses/` 里：

- `LGPL-3.0.txt`、`GPL-3.0.txt` —— MaaFramework（LGPL-3.0 §3/§4 要求同时附 GPL-3.0 正文）
- `AGPL-3.0.txt` —— MaaAgentBinary、MXU
- `Node-LICENSE.txt` —— Node.js 及其内嵌的第三方组件
- `MIT-MaaCommonAssets.txt` —— PPOCR 模型
- `MXU-NOTICE.txt` —— 打包 MXU 时的额外说明
- 上一层目录的 `LICENSE` —— MaaIchika 自己的 MIT

**没有任何一个第三方组件被修改过。** 想换成自己编译的版本，直接覆盖对应的
`maafw/*.dll`、`maafw/MaaAgentBinary/*`、`mxu.exe`、`node/node.exe` 即可。
{GAME_NOTICE}"""
    (dst / "SOURCE-OFFER.md").write_text(text, encoding="utf-8", newline="\n")


def write_start_here(dst, version, with_mxu):
    mxu_line = (
        "- 双击 `mxu.exe`（首次可能提示以管理员运行）→ 选设备 → 在任务列表里勾「清日常」→ 开始"
        if with_mxu
        else "- 用你自己的 MXU 打开这个目录里的 `interface.json`（把本目录当 MXU 的根目录）"
    )
    text = f"""# MaaIchika v{version} —— 怎么用

1. 解压到一个**没有中文和空格**的路径，例如 `D:\\MaaIchika`。
2. 手机/平板开 USB 调试，用数据线连电脑，`adb devices` 能看到设备。
3. 设备必须是 **16:9**：解压后在本目录跑
   `python tools\\device.py check`，不是 16:9 就跑 `python tools\\device.py fix`。
{mxu_line}

## 里面有什么

| 路径 | 说明 |
| --- | --- |
| `interface.json` + `resource/` + `locales/` | 本项目本体（Pipeline 与模板图） |
| `maafw/` | MaaFramework 运行时（LGPL-3.0，可直接替换） |
| `node/` + `agent/` | agent 运行时与「画面卡死」检测（ScreenFrozen） |
| `tools/` | 截图 / 裁模板 / 跑任务 / 自检脚本 |
| `licenses/` + `SOURCE-OFFER.md` | 第三方组件授权与源码获取方式（**请勿删除**） |

## 注意

- 自动化可能违反游戏用户协议，**账号风险自负**；本项目不碰付费货币、不抽卡、不购买。
- 模板图与图标版权归 SEGA / Colorful Palette，详细声明见 `SOURCE-OFFER.md` 末尾。
"""
    (dst / "START-HERE.md").write_text(text, encoding="utf-8", newline="\n")


def write_release_notes(version, node_ver, mxu_ver, with_mxu, size_mb):
    mxu_row = f"| MXU | {mxu_ver} | AGPL-3.0 |" if with_mxu else ""
    text = f"""# MaaIchika v{version}

日服 Project SEKAI 的 MaaFramework 自动化 —— 本包是**开箱即用**的完整版（约 {size_mb:.0f} MB）。

## 包内含什么

| 内容 | 版本 | 授权 |
| --- | --- | --- |
| MaaIchika（Pipeline / 工具 / agent） | v{version} | MIT |
| MaaFramework | v5.16.1 | LGPL-3.0 |
| MaaAgentBinary（minitouch / maatouch） | 随 MaaFramework | AGPL-3.0 |
| Node.js | {node_ver} | MIT + 第三方 |
{mxu_row}
| PPOCRv6-small 模型 | MaaCommonAssets | MIT |

**源码获取方式**：见包内 `SOURCE-OFFER.md`（每个组件的上游地址 + 版本）。所有第三方组件均为
**未修改**的原样打包，可用自己编译的版本直接替换。

**游戏素材**（`resource/image/`、`icon.png`）版权归 SEGA / Colorful Palette，本项目非官方、非商业，
仅用于图像匹配，详见包内声明。

## 用法

解压 → 确认设备是 16:9（`python tools/device.py check`）→ 打开 `mxu.exe` → 选「清日常」队列 → 开始。
细节见 `START-HERE.md`。

## 变更

<!-- 在这里写这次改了什么 -->

## 已知问题

- AUTO LIVE 每天有次数上限，用完后编成页的 AUTO 开关拨不动，任务会**干净收工不开演**（不白耗体力）
- 每日挑战「当天未打」的完整一场仍在等时机验证（其余任务入口都已真机跑通）
- 结算半路失败时链路会降级回主页；判断"体力是否真的打光"要看节点链里有没有 `公共_体力为0`
"""
    path = DIST / "RELEASE-NOTES.md"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只体检，不打包")
    parser.add_argument("--no-mxu", action="store_true", help="不打包 mxu.exe")
    parser.add_argument("--mxu-version", default="见上游 Releases", help="写进 SOURCE-OFFER 的 MXU 版本")
    args = parser.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    with_mxu = not args.no_mxu
    version, problems = check(with_mxu)
    if problems:
        for p in problems:
            print(f"[缺] {p}", file=sys.stderr)
        return 1
    node_ver = node_version()
    print(f"[ok] interface.json version = {version}；node = {node_ver}；mxu = {'打包' if with_mxu else '不打包'}")
    if args.check:
        print(f"[ok] licenses/ 齐全（{len(REQUIRED_LICENSES)} 份必需 + 可选）")
        return 0

    stage_root = DIST / "stage"
    pkg_name = f"MaaIchika-v{version}-win-x64"
    stage = stage_root / pkg_name
    force_rmtree(stage)
    stage.mkdir(parents=True)

    for item in FROM_INSTALL:
        src = INSTALL / item
        dst = stage / item
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        print(f"[copy] {item}")
    if with_mxu:
        shutil.copy2(INSTALL / "mxu.exe", stage / "mxu.exe")
        print("[copy] mxu.exe")

    # 项目自己的文档与工具：README 给用户，tools 便于自查，licenses 是合规必需
    shutil.copy2(ROOT / "LICENSE", stage / "LICENSE")
    shutil.copy2(ROOT / "THIRD-PARTY-NOTICES.md", stage / "THIRD-PARTY-NOTICES.md")
    shutil.copy2(ROOT / "README.md", stage / "README.md")
    shutil.copytree(ROOT / "tools", stage / "tools")
    shutil.copytree(LICENSES, stage / "licenses")
    # 用户可以自己跑自检/截图，但不需要仓库里的开发期杂物
    for junk in ("tools/__pycache__",):
        force_rmtree(stage / junk)
    clear_readonly(stage)

    write_source_offer(stage, version, node_ver, args.mxu_version)
    write_start_here(stage, version, with_mxu)

    total = sum(p.stat().st_size for p in stage.rglob("*") if p.is_file())
    size_mb = total / 1024 / 1024
    zip_path = DIST / f"{pkg_name}.zip"
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(stage.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(stage_root))
    zip_mb = zip_path.stat().st_size / 1024 / 1024

    notes = write_release_notes(version, node_ver, args.mxu_version, with_mxu, zip_mb)
    print(f"\n[ok] 内容 {size_mb:.1f} MB → 压缩后 {zip_mb:.1f} MB")
    print(f"[ok] {zip_path.relative_to(ROOT)}")
    print(f"[ok] Release 正文模板：{notes.relative_to(ROOT)}")
    print("[i] 贴 GitHub 之前别忘了把 RELEASE-NOTES.md 的「变更」一节写完")
    return 0


if __name__ == "__main__":
    sys.exit(main())
