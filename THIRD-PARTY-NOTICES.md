# 第三方组件与素材声明

本仓库（MaaIchika）**自己的代码与配置**（pipeline JSON / `tools/` / `agent/` / 文档）以 [MIT](LICENSE) 授权。
本文件列出**不适用 MIT** 的部分 —— 它们各自属于别人，这里只说明来源和本项目怎么用。

## 运行依赖（都不随本仓库分发）

仓库里只有 Pipeline JSON、工具脚本和几个 agent 的 `.mjs`，**没有任何 `.exe` / `.dll` / `.onnx` 二进制**
（`git ls-files` 可复核）。下面这些组件由用户自己安装：

| 组件                                                                               | 授权         | 本项目怎么用                                                                     |
| ---------------------------------------------------------------------------------- | ------------ | -------------------------------------------------------------------------------- |
| [MaaFramework](https://github.com/MaaXYZ/MaaFramework)（含 `@maaxyz/maa-node`）    | **LGPL-3.0** | 通过 Adb 控制器驱动游戏；只引用、不修改                                          |
| [MXU](https://github.com/MaaXYZ/MXU)                                               | **AGPL-3.0** | 可选的图形客户端，由用户自行下载放进 `install/`；**本仓库不分发它**              |
| [MaaCommonAssets](https://github.com/MaaXYZ/MaaCommonAssets) 的 PPOCRv6-small 模型 | **MIT**      | `tools/fetch_ocr.py` 下载到 `assets/resource/model/ocr/`（不入库）               |
| [Node.js](https://nodejs.org)                                                      | MIT + 第三方 | `tools/bundle_runtime.py` 把本机 node 复制进 `install/`（不入库），只给 agent 用 |
| [prettier](https://prettier.io)                                                    | MIT          | 开发期格式化                                                                     |
| `@nekosu/maa-tools`                                                                | 未声明授权   | 开发期可选的官方校验（CI 里 `continue-on-error`）；不随任何产物分发              |

> ⚠️ `tools/pack.py` + `tools/bundle_runtime.py` 产出的 `install/` 目录里**会包含** MaaFramework 的
> DLL 和 Node 运行时。**如果把这个目录打成 Release 发布**，就得同时提供这些项目的许可证文本与
> 源码获取方式（LGPL §4 要求允许使用者替换该库）。最省事的做法是 Release 只发 `assets/` 与本仓库代码。

## 游戏素材（版权不属于本项目）

- `assets/resource/image/**` 里的模板图，全部是**从游戏截图上原样裁下来**的一小块（1280×720 基准）；
- `assets/icon.png` 含角色形象；
- 相关的著作权归 **SEGA / Colorful Palette**。

本项目的用法与边界：

- 用途**仅限图像匹配** —— 让自动化知道按钮/图标在屏幕的哪个位置，不是分发游戏资源、不是二次创作；
- 本项目**非官方**，与 SEGA / Colorful Palette **无任何关联**，不涉及任何付费内容或商业用途；
- 权利方若要求移除，删掉 `assets/resource/image/` 和 `assets/icon.png` 即可 —— 代码和工具不受影响，
  只是需要重新裁模板。

「Project SEKAI COLORFUL STAGE! feat. Hatsune Miku」及其中各角色名称、形象，
是 SEGA / Colorful Palette 的商标或注册商标。

## 只借了写法/思路的项目

| 项目                                       | 借了什么                                                                                                                                        |
| ------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| [MaaEnd](https://github.com/MaaEnd/MaaEnd) | pipeline 组织方式、`[JumpBack]` + `max_hit`、`post_wait_freezes` 等待画面静止等约定，见 [对比文档](docs/zh_cn/developers/maaend-conventions.md) |
| MaaFramework 官方文档 / sample             | ProjectInterface V2、Pipeline 5.x 协议写法、`Custom` 识别的回调签名                                                                             |
