# 上下文衔接（给下一个会话）

> 写于 2026-11-24；2026-11-25 更新（第二天真机验证，修了三个"只有真机才暴露"的坑）。接手时先读 `AGENTS.md`（硬规矩）和开发手册，本文只写**当前进度 + 下一步 + 容易再踩的坑**。

## 一句话状态

日服 PJSK 的 MaaFramework 自动化，**14 个任务入口、13 个已验证**（真机 `run.mjs` 报「完成（已验证）」）。
所有静态检查全绿：`check_json` / `check_params` / `audit` / `check_interface` / `maa-tools check` / prettier。
**`ScreenFrozen`（画面卡死检测）两条路都验过了**：`run.mjs` 进程内注册 ✅、MXU 的 agent 子进程 ✅。
**按钮状态识别**（白=可点 / 灰=已领完 / 青绿=主按钮）已替代 4 处纯 OCR，真机跑通。
**代码已推到 GitHub**（`amemz23/MaaIchika`，main 分支），CI（check.yml）绿。

## 已做通的任务（真机验证过的链路）

| 任务            | 关键链路                                                                                                         | 耗时                  |
| --------------- | ---------------------------------------------------------------------------------------------------------------- | --------------------- |
| 启动游戏        | 标题页（抄字 or「TAP TO START」）→ Google 弹窗 → 登录奖励 → 公告 → 主页                                          | 13~39s                |
| 领礼包          | 礼物箱：一键领取 / 「0件」空箱两条分支                                                                           | 7s                    |
| 任务奖励        | 四个 tab（ライブ/ボーナス/定常/アチーブメント）各点一次「一括受け取り」；按钮**白=可点/灰=已领完**由颜色识别判定 | 12.4s                 |
| 每日挑战        | 选人→选角→选曲→AUTO→开演→结算；当天已打会认「本日分は終了しました。」直接收工                                    | 6~11s（完整一场待验） |
| 演出一场        | 编成页 → 开 AUTO（**拖拽落点跟识别框走**）→ 确认 ON → 开演 → 结算 → 回主页                                       | 181.8s                |
| 清火（单场）    | 同演出，走齿轮「オートライブ回数」                                                                               | 187s                  |
| 清火循环        | 反复 开演→结算→重新导航，直到 `0/25` 收工                                                                        | 结构已通，整链待验    |
| 过剧情          | メイン/イベント +「続きから読む」→ 读到无未读才回主页                                                            | 8s / 连读 1247s       |
| 读支线          | サイドストーリー → 角色选择 → 「前編」；本账号全锁 → 干净退出                                                    | 22.6s                 |
| 收尾结算        | LIVE CLEAR/FAILED → 挑战浮层 → 逐页 次へ/OK → 回主页                                                             | 30.9s                 |
| 设置/恢复分辨率 | Shell 跑 `wm size` / `wm density`（+ 杀进程让新分辨率生效）                                                      | 0.4s                  |

## 下一步（按优先级）

1. **只剩「每日挑战完整一场」这一件待验**（每天只能打一次；2026-11-25 那次被下面的
   "选曲确认误点播放按钮" bug 浪费掉了，第二天重置后补）。`演出_结算` 的现场验证已在
   11-25 用一场完整演出＋一次收尾结算覆盖（见下方机制）。

2. **`任务_清火循环` 的整链还差最后一步**：11-25 已确认真机在跑、能连续开第二场
   （AUTO 恢复后 `清火_循环确认AUTO` 0.999 → `清火_循环开演` 0.918），但 Boost 有 41 点、
   打光要 ~2 小时，所以"打到 0/25 收工"那段还没实测过。等哪天 Boost 低的时候跑一次即可。

3. ~~按钮库抽象~~ —— ✅ 已收成「识别片段 + 节点名引用」：`08_按钮.json` 里三个片段
   （青绿主按钮 / 白底可点 / 灰底已领完），6 处重复的颜色参数各改成一行引用。
   **MaaFramework 5.16 上 `Or(any_of: ["节点名"])` 和 `And(all_of: ["节点名", 内联])` 都实测可用**
   （`tools/replay.mjs --inject` 验的）；`audit.py` 也加了「被 any_of/all_of/color_filter 引用
   过的节点算识别片段，不套用空 next 规则」。改颜色现在只要改一个地方。

4. ~~MXU 里验一次 agent 子进程~~ —— ✅ 2026-11-24 人工确认能拉起子进程。机制与坑见
   `docs/zh_cn/developers/agent-plan.md`。

5. ~~通用按钮库的「按钮状态」那一半~~ —— ✅ 已落地：`演出_结算` / `清火_循环结算` 用
   `Or(青绿主按钮颜色, OCR)`；`任务_奖励_一括_*` 用 `And(白底颜色, OCR)` + 四个 `*已领完`（灰底）节点。
   真机 12.4s / 16.3s 跑完四 tab「完成（已验证）」，把「灰按钮被 OCR 认出来空转」根治了。

6. **README 已按真机重新校准**（任务奖励四 tab + 按钮两态、读支线 22.6s 的真实状态、AUTO 每日上限
   替代旧的"触控通道"猜想、卡死自动恢复）。另外 `03_任务.json` / `locales` 里两处过期 desc 一起改了。
   以后 README 只写**跑过一次的结论**，别再留"待验证"的旧数字。

## 这一轮挖出来的机制（不知道就会白折腾）

- **演出在 AUTO 没开时照样会开演 —— 根因是阈值偏低**（2026-11-25 踩的）：`演出_选曲确认` 阈值写
  0.67 时，在**编成页**上把右侧圆形**播放按钮**误认成「決定」拿到 0.779 就点了下去，直接绕过
  "验证 AUTO 才开演"这条硬规矩，整场 0 分 LIVE FAILED、白丢一场挑战。现在阈值 **0.90**，同一模板
  正样本实测 0.999~1.000；`清火_选曲` 同模板同坑一起改了。**教训：模板阈值不能为了让暗态也能命中
  就往下压 —— 压到 0.67 就会在别的页面上命中完全不同的按钮。**
- **拖拽类动作的落点必须跟着识别框算**：挑战场 AUTO 开关比单人场大一圈、整体偏右 ≈47px
  （单人场框 `[522,642,122,42]`、挑战场 `[569,643,122,42]`），TouchDown 写死 (530,665) 就按在空白上。
  现解：`anchor: "AUTO开关"` + `target: true` / `target: "[Anchor]AUTO开关"`，配**负宽高**的
  `target_offset` 把随机落点夹窄（Maa 是在 target 矩形内**随机取点**的，只给 `[-50,0]` 偏移会飘）。
  实测落点 `(538,655) → (620,661)`。详见开发手册 6.11。
- **`演出_结算开场.next` 必须带 `演出_阶段面板`**：挑战场结算会先弹「今週のチャレンジスタンプ」，
  浮层上没有 次へ/OK，漏了它就会卡到轮询超时（真机那次卡了 48 秒后任务失败）。
- **新的一天第一次冷启动有竞态**：`任务_启动` 2026-11-25 第一次跑失败（Google 登录 → 标题页点两下
  → 停在 LOGIN BONUS），立刻重跑就 13.1s 正常。怀疑是冷启动首帧残像 + 登录奖励画面同时出现。
  遇到就重跑，别急着改节点。
- **AUTO LIVE 每天有次数上限**。用完以后编成页的 AUTO 开关**拨不动**，`演出_确认AUTO` 永远认不到 ON 态。
  所以现在的行为是：**确认不到就回主页收工，绝不开演** —— 不开 AUTO 的演出会打出 `LIVE FAILED`，白耗体力。
  早期" AUTO 状态时有时无"的怪现象也是这个，不是被点击拨坏的。
- **体力 0 时播放按钮是灰的**（模板分从 1.000 掉到 0.614），`演出_开演` 阈值因此定 0.90。
- **`0/25` 不能用 OCR 也不能用整串模板判**：OCR 是子串匹配（`40/25`、`10/25` 全命中），整串模板会被 `10/25` 的视觉子串命中。
  现解：`And(首位数字「0」窄模板 0.93, OCR 兜底)`，实测 0/25=1.000、10/25=0.871、40/25=0.529。
- **編成页布局两套**：单人场齿轮在 (655,665)、挑战场在 (674,640)；挑战场 AUTO 开关更大。写死坐标必翻车。
- **章节列表两种版式**：活动故事有 `イベント/サイド` tab，主线故事没有 → 判据用 `And(章节号「第」, Or(tab文案, 书签图标))`。
- **语音弹窗两种版式**，新版「ボイスなし」在左半边（ROI `[340,460,600,150]`）。
- **结算浮层**：`チャレンジスタンプ` / `チャレンジステージランクUP` / `プレイヤーランクUP` / 「本日分は終了しました。」共用一个 `演出_阶段面板`（点画面中间）。
- **`wm size` 覆盖会被 OPPO 清掉**，清掉后画布变 1018×720、所有 ROI 错位（表现为"卡在标题页点不动"）。先跑 `python tools/device.py check`，错了就跑 `任务_设置分辨率`。
- **`on_error` 不是"只识别一次"**：框架用**父节点的 `timeout` + `rate_limit`** 反复轮询 `on_error` 候选。
  实测 4s/800ms 的父节点下，`on_error` 里的 Custom 识别被调了 3 次（第 3 次命中 `times: 3`）。
  → 但同一轮里 DirectHit 会先命中，所以 Custom 想攒帧就**必须**是 `on_error` 里唯一候选。
- **同一颗按钮有白/灰两态，OCR 分不出来**：`一括受け取り` 可点时纯白 (255,255,255)、领完变灰
  (127,127,144)。颜色像素数白 4975 / 灰 5491、互斥为 0 → 用 `ColorMatch` 的 count，阈值 3000。
  结算页的「次へ/OK」是青绿 (119,238,221)、count 9567~9589，而同一块区域演出中只有 0~274。
  **纯色块不能用 TemplateMatch 打分**（CCOEFF 对常数模板不稳定）。细节见开发手册 6.10。
- **`post_recognition` 验不了组合识别**：把 dump 出来的 `Or/And` 再喂回去会 MISS（子项单独都 HIT）。
  要验组合识别只能用 `tools/replay.mjs`（CustomController 喂固定截图跑整条节点链）。

## 框架层面的坑（每个都踩过）

| 坑                              | 现象                                                       | 规矩                                                |
| ------------------------------- | ---------------------------------------------------------- | --------------------------------------------------- |
| `max_hit` 用尽即移出候选        | 剧情读到第 3 集卡在语音弹窗                                | 循环里重复用的节点要给够（`勾连读`/`选语音` 都 40） |
| 漏写 `[JumpBack]`               | 命中的处理器 `next` 为空 → **整条链当场结束**              | 现在 `audit.py` 会报（本项已永久检查）              |
| DirectHit 候选排前面            | 永远命中，把真识别全抢了（`公共_点一下` 排 `结算` 前面时） | 兜底项一律放最后                                    |
| `[JumpBack]` 引用终止节点       | 到主页也命中 → 空转 300 次/811s                            | 验证型终止节点只能普通引用                          |
| 同一节点同时进 next 和 on_error | 框架报「重复路由」                                         | `check_json` 会拦                                   |
| 长 `timeout`                    | 模板一漏就白等 10 分钟                                     | `timeout` 是"next 的识别窗口"，给 5~20 秒           |
| 点同一按钮反复点                | 第二次可能点在下个界面的东西上                             | 用 `post_wait_freezes` 等画面稳定（MaaEnd 原则）    |

## 环境与命令

```bash
# 设备（OPPO Pad，adb 在 Android SDK platform-tools 下）
python tools/device.py check            # 先看画布是不是 1280x720
python tools/device.py fix              # 刷成 16:9（重启游戏后生效）
python tools/device.py shot scratch/x.png

# 跑任务（判定看是否「完成（已验证）」）
node tools/run.mjs --list
node tools/run.mjs 任务_启动
python tools/report.py                  # 汇总各任务最后一次的结果

# 检查（提交前全过）
python tools/check_json.py
python tools/check_params.py
python tools/audit.py
node tools/check_interface.mjs
npx maa-tools check                     # 需要联网下运行时
python tools/pack.py                    # assets -> install

# 发 Release（给最终用户的整包）
python tools/fetch_licenses.py          # 一次性：LGPL/GPL/AGPL/Node/MaaAssets 许可证全文 -> licenses/
python tools/package_release.py         # -> dist/MaaIchika-v<版本>-win-x64.zip + dist/RELEASE-NOTES.md
```

- Python：本机 DSH 运行时自带的那个（有 PIL/numpy、**没有 cv2**）；装过 Pillow 的普通 Python 也行
- Node：`node` 在 PATH 里即可；`tools/run.mjs` 找 adb 的顺序是 `--adb` > `$env:ADB_PATH` >
  `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe` > PATH 里的 `adb`
- **批量改 JSON 一律用 Python 文件**（`python -c` 遇到中文/引号必坏，这条已经坑过十几次）

## 交付物布局

```
assets/          interface.json（含 icon / agent 字段）、pipeline/（36 个 JSON / 102 节点）、image/、locales/
agent/custom.mjs ScreenFrozen / ScreenMoved 的**唯一实现**（run.mjs 进程内注册也用这一份）
agent/main.mjs   agent 子进程入口（maa.Server + socket id，用 @maaxyz/maa-node/server 入口）
install/         打包产物（不入库）：interface.json + icon.png + resource + locales + node/ + agent/
tools/           device / crop / score / analyze_scores / probe / replay / run / report / check_json / check_params / audit / pack / bundle_runtime / mxu_add_daily_config
docs/zh_cn/developers/   开发手册、识别基线、maaend-conventions.md、agent-plan.md、本文
```

`check_json.py` 里新增了一条永久检查：pipeline 里写的 `custom_recognition` / `custom_action` 名字
必须在 `agent/*.mjs` 里注册过 —— 名字写错时 Maa 加载期不报错，运行期就是永远 MISS。

MXU 侧配置：`python tools/mxu_add_daily_config.py` 会写入一个「清日常」队列
（设置分辨率 → 启动 → 领礼包 → 任务奖励 → 每日挑战 → 清火）。**MXU 退出时会写回配置，所以要先关 MXU 再跑**。

## 别做的事

- 不碰水晶/付费货币（`オートライブ回数` 对话框里的「クリスタルで回復」永远不勾）
- 不做音游判定（只用游戏内 AUTO）
- 剧情不加速不跳过
- 不点「通信開始」（那是上传成绩）
