#!/usr/bin/env python3
"""把分发 Release 需要的许可证全文抓到 `licenses/`。

为什么要单独一个脚本：`tools/package_release.py` 打出来的 zip 里带了 MaaFramework
（LGPL-3.0）、MaaAgentBinary / MXU（AGPL-3.0）、Node（MIT+第三方）、PPOCR 模型（MIT），
**分发这些二进制就必须随包附上对应的许可证全文**。手抄一遍不现实，所以让脚本抓：

- 能在本机找到的（`install/maafw/MaaAgentBinary/LICENSE`、Node 运行时的 `LICENSE`）优先用本地的
  —— 保证和随包的二进制是同一个版本；
- 找不到的再去上游取（多个 URL 依次尝试）。

用法：
    python tools/fetch_licenses.py            # 补齐缺的
    python tools/fetch_licenses.py --check    # 只检查缺哪些
    python tools/fetch_licenses.py --force    # 全部重下
"""

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DST = ROOT / "licenses"
NODE_DIR = (
    Path.home() / ".dsh" / "dsh-runtimes" / "dsh-primary-runtime" / "dependencies" / "node"
)

# 每项：输出文件名 -> (说明, [本机候选路径...], [下载 URL...], 最低字节数)
MANIFEST = {
    "LGPL-3.0.txt": (
        "MaaFramework（含 @maaxyz/maa-node）",
        [],
        ["https://raw.githubusercontent.com/MaaXYZ/MaaFramework/main/LICENSE.md"],
        3000,
    ),
    "GPL-3.0.txt": (
        "LGPL-3.0 §4(b) 要求同时附上 GPL-3.0 正文",
        [],
        [
            "https://raw.githubusercontent.com/spdx/license-list-data/main/text/GPL-3.0-only.txt",
            "https://www.gnu.org/licenses/gpl-3.0.txt",
        ],
        30000,
    ),
    "AGPL-3.0.txt": (
        "MaaAgentBinary（minitouch/maatouch）与 MXU",
        ["install/maafw/MaaAgentBinary/LICENSE", "install/resource/MaaAgentBinary/LICENSE"],
        [
            "https://raw.githubusercontent.com/spdx/license-list-data/main/text/AGPL-3.0-only.txt",
            "https://www.gnu.org/licenses/agpl-3.0.txt",
        ],
        30000,
    ),
    "Node-LICENSE.txt": (
        "随包分发的 node.exe",
        [
            str(NODE_DIR / "LICENSE"),
            str(Path.home() / ".dsh" / "dsh-runtimes" / "dsh-primary-runtime" / "dependencies" / "node" / "LICENSE"),
        ],
        ["https://raw.githubusercontent.com/nodejs/node/main/LICENSE"],
        3000,
    ),
    "MIT-MaaCommonAssets.txt": (
        "PPOCR 模型（MaaCommonAssets，Copyright (c) 2023 MAA）",
        [],
        ["https://raw.githubusercontent.com/MaaXYZ/MaaCommonAssets/main/LICENSE"],
        900,
    ),
    "MXU-NOTICE.txt": (
        "打包 mxu.exe 时的额外声明（正文见 AGPL-3.0.txt）",
        [],
        [
            "https://raw.githubusercontent.com/MaaXYZ/MXU/main/README.md",
        ],
        0,  # 这个文件由脚本自己写（见 ensure_mxu_notice），不走下载
    ),
}

MXU_NOTICE = """MXU 声明
=========

本发布包内附带的 `mxu.exe` 来自 MaaXYZ/MXU，授权为 **AGPL-3.0**（全文见同目录
`AGPL-3.0.txt`）。

- 上游：https://github.com/MaaXYZ/MXU
- 本项目**未修改** MXU，只是原样打包，方便用户开箱使用。
- 你可以用自己编译/下载的 mxu.exe 直接替换它。
- MXU 的源码由上游提供：https://github.com/MaaXYZ/MXU （tag / 发行版见其 Releases）。

MaaIchika 只提供 `interface.json` 与 `resource/` 资源包，MXU 只是图形外壳。
"""


def fetch(urls, min_size):
    last = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MaaIchika-fetch-licenses"})
            data = urllib.request.urlopen(req, timeout=60).read()
        except Exception as exc:  # noqa: BLE001 - 网络异常种类太多，一律记下继续试下一个
            last = f"{url} -> {exc}"
            continue
        if len(data) < min_size:
            last = f"{url} -> 只有 {len(data)} 字节（< {min_size}），内容不像许可证正文"
            continue
        return data, url
    raise SystemExit(f"[error] 全部来源都失败：{urls}\n        最后一次：{last}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    DST.mkdir(exist_ok=True)
    missing, done = [], []

    for name, (note, locals_, urls, min_size) in MANIFEST.items():
        out = DST / name
        if out.is_file() and out.stat().st_size > 0 and not args.force:
            done.append(f"{name}（已存在，{out.stat().st_size} 字节）")
            continue
        if args.check:
            missing.append(name)
            continue

        if name == "MXU-NOTICE.txt":
            out.write_text(MXU_NOTICE, encoding="utf-8", newline="\n")
            done.append(f"{name}（生成）")
            continue

        # 先找本机副本：和随包的二进制同源，比重新下载更准
        src = None
        for entry in locals_:
            candidate = Path(entry)
            if not candidate.is_absolute():
                candidate = ROOT / entry
            if candidate.is_file():
                src = candidate
                break
        if src is not None:
            shutil.copyfile(src, out)
            try:
                shown = src.relative_to(ROOT)
            except ValueError:
                shown = src
            done.append(f"{name}（本机 {shown}）")
            continue

        data, url = fetch(urls, min_size)
        out.write_bytes(data)
        done.append(f"{name}（下载自 {url}，{len(data)} 字节）")

    for line in done:
        print(f"[ok] {line}")
    for name in missing:
        print(f"[缺] {name} — {MANIFEST[name][0]}")
    if missing:
        print(f"\n{len(missing)} 份缺失；跑 python tools/fetch_licenses.py 补齐")
        return 1
    print(f"\nlicenses/ 齐全（{len(MANIFEST)} 份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
