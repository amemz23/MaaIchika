<!-- markdownlint-disable MD033 MD041 -->

<p align="center">
  <img alt="MaaIchika" src="./assets/icon.png" width="160" height="160" />
</p>

<div align="center">

# MaaIchika

_✨ 世界计划 多彩舞台（日服）日常小助手 ✨_

[![MaaFramework](https://img.shields.io/badge/MaaFramework-v5.16+-876f69?logo=paddypower&logoColor=white)](https://github.com/MaaXYZ/MaaFramework)
[![license](https://img.shields.io/github/license/amemz23/MaaIchika)](./LICENSE)
[![platform](https://img.shields.io/badge/platform-Windows%20%7C%20Android-blueviolet)](https://github.com/amemz23/MaaIchika/releases)
[![release](https://img.shields.io/github/v/release/amemz23/MaaIchika?label=release)](https://github.com/amemz23/MaaIchika/releases)
[![downloads](https://img.shields.io/github/downloads/amemz23/MaaIchika/latest/total)](https://github.com/amemz23/MaaIchika/releases/latest)
[![stars](https://img.shields.io/github/stars/amemz23/MaaIchika?style=flat)](https://github.com/amemz23/MaaIchika/stargazers)

**14 个任务入口 · 13 个真机跑通「完成（已验证）」**

纯 Pipeline JSON，没有自己的算法 —— 识别交给 [MaaFramework](https://github.com/MaaXYZ/MaaFramework)，界面交给 [MXU](https://github.com/MaaXYZ/MXU)。

当前**只适用于日服**，而且还有不少东西在补（见下方「已知缺口」）。

**来自开发者的话：由于本项目极大程度上基于VibeCoding，所以难免会写错一些东西或者在特定机器上运行出错，如果遇到这类情况请提交issue，我会尽力去解决的**

</div>

---

## 📖 这是什么

把**每天重复的领奖励、读剧情、清体力**交给机器，你只负责打歌。

- **纯 Pipeline 驱动**：99% 的逻辑是 JSON 节点，加一个只做「判断画面是否卡死」的小 agent；
- **状态驱动**：每个点击前都有识别依据，每个动作后都要验证结果，链尾必须落在"主页锚点真的出现了"这类**验证型终点**上，而不是"流程没报错就算成功"；
- **阈值是量出来的**：所有阈值都来自真机截图的正/负样本打分（`tools/score.mjs` + `tools/analyze_scores.py`），出处见[识别基线](docs/zh_cn/developers/recognition-baseline.md)；
- **只用游戏内 AUTO**：不做任何音游判定 —— 截图轮询的时序根本跟不上音符。

## ⚠️ 使用须知

**这个工具的边界（不是"暂未实现"，是永远不做）**：

| 不做                | 原因                                                                 |
| ------------------- | -------------------------------------------------------------------- |
| 🚫 不做音游判定     | 只用游戏内 `AUTO`，不读谱面、不注入、不模拟判定                      |
| 🚫 不碰付费货币     | 不抽卡、不购买、不用水晶/饮料回体力（体力/Boost 只走游戏内正常消耗） |
| 🚫 不跳过活动剧情   | 跳了就不给水晶（或者只给一部分），所以只能纯点击推进，耗时较长       |
| 🚫 不点「通信開始」 | 那是上传成绩                                                         |

**风险自担**：自动化可能违反游戏用户协议，账号风险自负。本项目与 SEGA / Colorful Palette
无任何关联，非官方、非商业；游戏素材版权归其所有，详见 [第三方声明](THIRD-PARTY-NOTICES.md)。

**当前只保证日服**（`com.sega.pjsekai`）。国服 / 繁中服的文字和界面都不同，扩服要重新实测阈值。

## 🚀 食用指南

### 方式一：下载现成的包（推荐）

去 [Releases](https://github.com/amemz23/MaaIchika/releases/latest) 下 `MaaIchika-v*-win-x64.zip`，解压到**没有中文和空格的路径**，然后：

```bash
python tools/device.py check          # 自检：设备是不是 16:9、画布是不是 1280×720
python tools/device.py fix            # 不是 16:9 就跑这个（一次即可，重启设备失效）
```

双击 `mxu.exe`（建议管理员运行）→ 选设备 → 在任务列表里勾「清日常」队列 → 开始。

### 方式二：从源码跑（开发/无头）

```bash
npm install                           # 或在仓库根目录 pnpm install
python tools/fetch_ocr.py             # 拉 OCR 模型（约 30MB，不入库）

node tools/run.mjs --list             # 看有哪些任务入口
node tools/run.mjs 任务_启动            # 跑一个
node tools/run.mjs 任务_领礼包 任务_任务奖励   # 一次连接跑多个
```

`tools/run.mjs` 会打印每轮识别结果（命中/未命中、分数、OCR 文本），并按三种结论判定：

| 结论           | 含义                                                       |
| -------------- | ---------------------------------------------------------- |
| 完成（已验证） | 节点链落在 `公共_主页锚点` / `完成_*` 上 —— **真的做成了** |
| 结束但未验证   | 流程走完了但没到验证型终点 —— **当失败看**                 |
| 失败           | MaaFramework 报失败                                        |

### 设备必须是 16:9

MaaFramework 只按短边等比缩放，**不补偿宽高比**：

| 设备分辨率               | 缩放后画布                 | 结果                  |
| ------------------------ | -------------------------- | --------------------- |
| 2560×1440                | 1280×720                   | ✅ 正好是坐标基准     |
| 1080×1920（竖屏原生）    | 720×1280 → 横过来 1280×720 | ✅                    |
| 2400×3392（1:1.41 平板） | 1018×720                   | ❌ 坐标与模板一起失效 |

`tools/device.py fix` 会把分辨率临时覆盖成 16:9（`install/` 里已有脚本）。
竖屏原生设备要写**竖着**的宽高（`1440x2560`），写反了横屏游戏会被强制竖屏。

## ✨ 功能一览

> 图例：✅ 真机跑通并验证过　🔧 链路通但有前提/待补验　🚧 还没做

### 日常（`daily`）

- ✅ **🚀 启动游戏**：拉起日服 → 按返回键关掉 Google 登录弹窗 → 按需下载追加数据 → 点标题页（会重试）→ 关公告 → 走到主页。实测 **39.7s**
- ✅ **🎁 领礼包**：礼物箱一键领取；空箱就认「0件」直接返回。两条分支都真机闭环过（**7.2s**）
- ✅ **📋 任务奖励**：主页剪贴板 → 四个 tab（ライブ／ボーナス／定常／アチーブメント）各点一次「一括受け取り」→ 回主页（**12.4s**）。关键是**认按钮颜色而不是认文字**：可点时纯白、领完变灰，OCR 两种状态都命中
- 🔧 **🎯 每日挑战**：主页 → LIVE → チャレンジライブ → 切单位页 → 点可用角色 → 选曲 → 开 AUTO → 开演 → 结算。两个"打不了"的状态都验过（当天已打 **11.3s**、体力 0 **11.5s**）；**能打的那一场还没完整跑过**（每天一次，还没赶上）
- ✅ **🏠 回主页**：从任意子页面连点返回箭头，直到真的看见主页底部导航
- ✅ **⚙️ 设置/恢复分辨率**：`wm size` / `wm density` 一键切换（**0.4s**），收尾用

### 演出 / 清体力（`live`）

- ✅ **🎤 演出一场**：进单人场 → 开 AUTO（**验证 ON 态**才允许开演）→ 开演 → 等结束 → 逐页结算 → 回主页。真机 **183.4s** 全链通过
- ✅ **🔥 清火（单场）**：同上，但改走编成页齿轮「オートライブ回数」→ 決定。真机 **187.2s**
- ✅ **🔁 清火循环**：反复 开演→结算→重新导航，直到顶部 `0/25` 收工。真机 **171.9s** 打到 **0/25** 后回主页。判"真的打光了"要看节点链里有没有 `公共_体力为0`，而不是看"回没回主页"（结算半路失败也会回主页，但体力没清完 —— `tools/run.mjs` 会对这种情况打 `[warn]`）
- ✅ **🧾 收尾结算**：把停在结算界面的演出收拾干净（手动打歌或上次中断后用）。真机 **30.9s**
- ✅ **🎛️ 进演出页**：只走到编成页，不点开演、不消耗 Live Bonus（调试/手动挑歌用）

### 剧情（`story`）

- ✅ **📖 过剧情**：主页 → ストーリー → 主/活动故事 → 決定 → 选未读章节 → 语音弹窗（勾连读 + ボイスなし）→ 纯点击推进，**读到这本没有未读为止**才回主页（**8s** 进入，连续读实测 **1247s**）
- 🔧 **📚 读支线**：サイドストーリー → 角色选择 → 点第一个「前編」（OCR **0.997**）→ 回主页。链路 **22.6s 完成·已验证**，但本账号支线**全部带锁**，所以实际一集都没读到

> ⚠️ **剧情一旦开始就退不出来**：返回键和点击都只是推进对白，⋯ 菜单里只有 shiori/オート/スキップ 之类，**没有退出项**。这是游戏机制，
> 所以别在剧情播放时启动别的任务。

### 兜底与鲁棒性

- ✅ **🧊 卡死自动恢复**：连续 3 帧截图**字节完全相同** = 画面死了（自定义识别 `ScreenFrozen`）→ 杀进程冷启动 → 重走启动链 → 落回主页锚点。只在标题页 / 演出等待的 `on_error` 里触发，静态过场（TIPS 屏）不会误判。恢复链实测 **62s** 跑完
- ✅ **🖱️ 关公告/通知面板**：认面板右上角 X（同一 X 在不同面板上分数不同，阈值按最差正样本定）
- ✅ **⏳ 等加载**：认右下角初音头像，`[JumpBack]` 轮询等它消失 —— 等画面，不等秒数
- ✅ **📡 通信错误**：认「通信エラー」并点掉确认框（剧情读到一半会冒出来）

## 💻 支持环境

| 项     | 要求                                                                                 |
| ------ | ------------------------------------------------------------------------------------ |
| 系统   | Windows 10 / 11                                                                      |
| 设备   | Android 7.0+ 实机或模拟器（开 USB 调试），**画面必须 16:9**                          |
| 游戏   | Project SEKAI **日服** `com.sega.pjsekai`                                            |
| 运行时 | Release 包内已带 MaaFramework 与 Node；源码运行需要 Node 20+、Python 3.10+（Pillow） |

## 🧭 常用命令

```bash
# 设备
python tools/device.py info | check | fix | reset
python tools/device.py shot scratch/x.png      # 截图（同时存原始分辨率一份）
python tools/device.py tap 640 470             # 按 1280×720 坐标点击

# 跑任务 / 看结果
node tools/run.mjs --list
node tools/run.mjs 任务_演出一场
node tools/run.mjs 任务_清火 --repeat 25        # 循环由外面驱动（游戏自己不会循环）
python tools/report.py                         # 汇总各任务最后一次的结果

# 识别调试
node tools/probe.mjs --node 演出_结算 scratch/shots/r02.png   # 用节点真实参数探一张图
node tools/replay.mjs 演出_结算 scratch/shots/r02.png          # 把整条节点链离线跑一遍
python tools/analyze_scores.py                 # 正负样本分布 → 建议阈值

# 提交前自检（CI 里跑的就是这些）
python tools/check_json.py      # JSON / 引用 / 占位 / 盲点动作 / 环无出口 / i18n / Custom 名字
python tools/check_params.py    # ROI 越界 / 模板存在 / 阈值范围 / ColorMatch 通道
python tools/audit.py           # max_hit 偏小 / 回跳无上限 / 候选全 miss / 空 next
node tools/check_interface.mjs  # 用真实 MaaFramework 加载 interface.json 与资源包
npm run format:check            # prettier
```

## 🎯 设计原则

**1. 状态驱动，不猜**
没有识别的点击一律禁止（`check_json.py` 会拦）；动作之后必须能验证结果。"next 跑空"不算成功。

**2. `next` 是候选列表，不是执行序列**
这是 MaaFramework 最容易坑人的地方，本项目的三条约定：

- 等待/弹窗/加载类公共节点一律 `[JumpBack]` + `max_hit`，做完回父节点重新判断；
- 导航节点把**自己**放进 `next`：点击丢了下一轮重点，点成功了画面变了自然不再命中；
- 终点用**验证型节点**（主页底部导航真的出现了）收尾。

**3. 不用固定延时等动画**
`pre_delay` / `post_delay` 全局置 0。要等就识别"动画结束后才出现的东西"，或用 `post_wait_freezes` 等画面静止。

**4. 阈值和颜色区间都是量出来的**
模板打分、正负样本分布、gap 全在[识别基线](docs/zh_cn/developers/recognition-baseline.md)里能查到出处；
纯色按钮这类"颜色状态"用 `ColorMatch` 的像素数判定（实测结算页青绿按钮 `count` 9567~9589，
同一块区域在演出中只有 0~274）。

**5. 任何循环都要有出口**
`max_hit` 就是出口，没有 `max_hit` 的自循环会被 `check_json.py` 报出来。

## ❓ 常见问题

**Q：卡在标题页，点什么都没反应？**
先跑 `python tools/device.py check`。最常见原因是设备**不是 16:9**（画布变成 1018×720，所有坐标和模板一起错位），
`python tools/device.py fix` 后重启游戏即可。如果画布没问题但画面**完全不动**，会自动走「卡死恢复」：杀进程冷启动重来，节点链里能看到 `公共_卡死_*`。

**Q：任务跑完了但什么都没做？**
八成是 **OCR 模型没装** —— 缺模型时 OCR 节点会**静默不命中**，表现和"节点写错了"极难区分。
跑 `python tools/fetch_ocr.py --check` 确认 `assets/resource/model/ocr/` 里三个文件都在。

**Q：编成页的 AUTO 开关拨不动？**
**AUTO LIVE 每天有次数上限**，用完之后开关就拨不动了。所以现在的行为是：`演出_确认AUTO` 认不到 ON 态就**回主页收工、绝不开演** ——
不开 AUTO 的演出会打出 `LIVE FAILED` 白耗体力。早期"AUTO 状态时有时无"的怪现象也是它。

**Q：体力为 0 了还在点开演？**
不会。体力 0 时播放按钮是**灰的**（模板分从 1.000 掉到 0.614），`演出_开演` 阈值定在 0.90，只认"点得动"的亮按钮。

**Q：每日挑战/任务奖励已经领过了会怎样？**
都算正常结束：挑战页显示「本日分は終了しました。」、使命页的「一括受け取り」变灰，都会直接回主页并判「完成（已验证）」。

**Q：为什么 `0/25` 要用"首位数字模板 + OCR"两个条件？**
OCR 是子串匹配（`40/25`、`10/25` 都会命中 `0/25`），整串模板又会被 `10/25` 的视觉子串骗（1.000）。
实测：首位数字「0」窄模板在 `0/25` 得 1.000、`10/25` 0.871、`40/25` 0.529，配 OCR 兜底最稳。

## 🧱 目录结构

```text
assets/            interface.json（任务入口/控制器/多语言）、pipeline/（9 个文件 / 105 个节点）
                   resource/image/（模板图，1280×720 基准）、locales/、misc/LICENSE.md
agent/             custom.mjs（ScreenFrozen 画面卡死检测）+ main.mjs（agent 子进程入口）
tools/             device / crop / score / analyze_scores / probe / replay / run / report
                   check_json / check_params / audit / check_interface / pack / bundle_runtime
                   fetch_ocr / fetch_licenses / package_release / mxu_add_daily_config
docs/zh_cn/developers/   开发手册、识别基线、handoff（当前进度）、agent-plan、MaaEnd 写法对照
licenses/          随包分发的第三方许可证全文
install/           打包产物（不入库）
```

## 🛠️ 开发者

上手前先读 [AGENTS.md](AGENTS.md)（硬规矩），然后是：

- [开发手册](docs/zh_cn/developers/development.md) —— 环境、工具链、状态机约定、踩过的坑
- [识别基线](docs/zh_cn/developers/recognition-baseline.md) —— 每个模板的正/负样本分数与阈值出处
- [当前进度 handoff](docs/zh_cn/developers/handoff.md) —— 做到哪了、下一步是什么
- [和 MaaEnd 的写法对照](docs/zh_cn/developers/maaend-conventions.md) —— 对齐了哪些约定、哪些故意不跟

新增节点的标准流程：截图 → 在 `tools/crops.json` 登记并裁模板 → 写节点（阈值先填 0.8）→
`tools/score.mjs` + `tools/analyze_scores.py` 量 gap → `tools/run.mjs` 真机跑 → 跑完整套自检。

### 打包 Release

```bash
python tools/fetch_licenses.py     # 一次性：第三方许可证全文 -> licenses/
python tools/pack.py               # assets -> install
python tools/bundle_runtime.py     # node + agent -> install
python tools/package_release.py    # -> dist/MaaIchika-v<版本>-win-x64.zip
```

包里会带上 `licenses/` 与自动生成的 `SOURCE-OFFER.md`（每个第三方组件的版本、授权、源码地址、
"未修改、可直接替换"），合规义务由脚本兜住。

## 🚧 已知缺口

按"下一步该做什么"排序（详细进度见 [handoff](docs/zh_cn/developers/handoff.md)）：

1. **每日挑战「当天未打」的完整一场还没跑完** —— 选人/选角/选曲/开演都单独验证过，
   但每次想跑完整场时当天挑战都已用完（2026-11-25 那次又被一个"选曲确认误点播放按钮"的 bug
   浪费掉了，那个 bug 已修）。游戏日重置后即可补验。
2. **`公共_回主页` 阈值余量偏紧** —— 返回箭头有暗态，实测最低 0.603、阈值 0.80。实践没出问题，但值得留意。
3. **主页会漂到不同区域**（比如「セカイ / スクランブル交差点」），右上角礼物盒样式跟着变。
   现在用双模板覆盖了两种样式，换区域仍可能再变 —— 再变就再补一份模板。
4. **`任务_领礼包` 偶发「其实回到了主页、但判定失败」** —— 礼物页有物品时 `礼物_返回`
   会连点把 `max_hit` 耗尽。最近几次真机都正常通过，留作观察项。
5. **只保证日服** —— 扩国服/繁中服要补 OCR `expected` 并在对应客户端上重新实测阈值。

## 🙏 致谢与授权

**本项目自己的代码与配置**（pipeline JSON / `tools/` / `agent/` / 文档）采用 [MIT 协议](LICENSE)。

**游戏素材不适用 MIT**：`assets/resource/image/` 的模板图和 `assets/icon.png` 来自游戏截图与角色形象，
版权归 **SEGA / Colorful Palette**，仅用于图像匹配；本项目非官方、非商业、与其无任何关联，权利方要求即删。
详见 [第三方声明](THIRD-PARTY-NOTICES.md)。

依赖但**不分发**的项目：[MaaFramework](https://github.com/MaaXYZ/MaaFramework)（LGPL-3.0）、
[MXU](https://github.com/MaaXYZ/MXU)（AGPL-3.0）、
[MaaCommonAssets](https://github.com/MaaXYZ/MaaCommonAssets) 的 OCR 模型（MIT）。
写法上参考了 [MaaEnd](https://github.com/MaaEnd/MaaEnd)（**AGPL-3.0**，本仓库只对齐写法、未包含其任何代码或 JSON）。

## 🔗 相关链接

- [MaaFramework](https://github.com/MaaXYZ/MaaFramework) —— 识别与动作框架，Pipeline 协议文档在这里
- [MXU](https://github.com/MaaXYZ/MXU) —— 图形客户端（本项目 Release 包里已附带）
- [MaaEnd](https://github.com/MaaEnd/MaaEnd) —— 同框架项目，pipeline 写法的参考对象
- [Project SEKAI 日服官网](https://pjsekai.sega.jp/) —— 本项目只针对日服

## 🐛 反馈

遇到问题请到 [Issues](https://github.com/amemz23/MaaIchika/issues) 反馈，附上：

- `node tools/run.mjs <入口>` 的完整输出（含节点链与结论）
- `python tools/device.py info` 的输出（分辨率/画布）
- 出问题的界面截图（放到 `scratch/` 再贴上来）

有这三样，绝大多数问题看图就能定位。
