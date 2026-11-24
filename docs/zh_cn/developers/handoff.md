# 上下文衔接（给下一个会话）

> 写于 2026-11-24（同日更新：接上了 agent 的 `ScreenFrozen`）。接手时先读 `AGENTS.md`（硬规矩）和开发手册，本文只写**当前进度 + 下一步 + 容易再踩的坑**。

## 一句话状态

日服 PJSK 的 MaaFramework 自动化，**15 个任务入口、14 个已验证**（真机 `run.mjs` 报「完成（已验证）」）。
所有静态检查全绿：`check_json` / `check_params` / `audit` / `check_interface` / `maa-tools check` / prettier。
**唯一的 Custom 识别 `ScreenFrozen`（画面卡死检测）已上线并通过真机验证**，只差 MXU 侧验一次 agent 子进程。

## 已做通的任务（真机验证过的链路）

| 任务            | 关键链路                                                                      | 耗时               |
| --------------- | ----------------------------------------------------------------------------- | ------------------ |
| 启动游戏        | 标题页（抄字 or「TAP TO START」）→ Google 弹窗 → 公告 → 主页                  | 39s                |
| 领礼包          | 礼物箱：一键领取 / 「0件」空箱两条分支                                        | 7s                 |
| 任务奖励        | 四个 tab（ライブ/ボーナス/定常/アチーブメント）各点一次「一括受け取り」       | 9.5s               |
| 每日挑战        | 选人→选角→选曲→AUTO→开演→结算；当天已打会认「本日分は終了しました。」直接收工 | 6~11s              |
| 演出一场        | 编成页 → 确认/开启 AUTO → 开演 → 结算 → 回主页                                | 183s               |
| 清火（单场）    | 同演出，走齿轮「オートライブ回数」                                            | 187s               |
| 清火循环        | 反复 开演→结算→重新导航，直到 `0/25` 收工                                     | 结构已通，整链待验 |
| 过剧情          | メイン/イベント +「続きから読む」→ 读到无未读才回主页                         | 8s / 连读 1247s    |
| 读支线          | サイドストーリー → 角色选择 → 「前編」；本账号全锁 → 干净退出                 | 19s                |
| 设置/恢复分辨率 | Shell 跑 `wm size` / `wm density`（+ 杀进程让新分辨率生效）                   | 0.4s               |

## 下一步（按优先级）

1. **MXU 里验一次 agent 子进程**（唯一剩下的收尾）—— 代码侧已经做完了：`agent/custom.mjs`
   是唯一实现，`agent/main.mjs` 和 `tools/run.mjs`（进程内注册）共用它；`标题_画面卡死` /
   `演出_画面卡死` / `清火_循环画面卡死` 已挂到对应等待节点的 `on_error`，命中后走
   `公共_卡死_重启游戏` → `公共_卡死_启动游戏` 冷启动恢复。**真机已经验过**：静态画面 3 帧命中、
   动态画面 12 轮不误命中、`on_error` 轮询窗口够用、恢复链 62 秒跑到主页锚点。
   待做：`python tools/bundle_runtime.py && python tools/pack.py` 之后用 `install/mxu.exe` 跑一次，
   确认 agent 子进程能被拉起（runner 只能验进程内注册这条路）。机制与坑见
   `docs/zh_cn/developers/agent-plan.md`。

2. **通用按钮库**（MaaEnd 的第二层，收益最大）—— 现在每个弹窗都手写 OCR（`次へ`/`OK`/`受け取る`/`確定`/`確認`/`はい`/`閉じる`）。要做的是收 5~6 个**视觉类型**模板（白底/黄底确认、圆环/对号、X 关闭），每个都必须做正负样本打分（阈值 gap ≥ 0.1），然后先替换 `演出_结算` 和 `任务_奖励_确认` 验证。**需要人工看图裁模板。**

3. **补两个待验**（只等时机，不需要改代码）：
    - 每日挑战「当天未打」的完整一场（每天只能打一次，第二天重置后即可验）
    - `任务_清火循环` 整链：等 AUTO LIVE 每日次数恢复（见下）后跑到体力耗尽

4. **README 有三处已过期**：任务奖励（已四 tab 全接，不再是"只接ライブ"）、读支线真实状态、AUTO 每日上限的说明。

## 这一轮挖出来的机制（不知道就会白折腾）

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
```

- Python：`C:\Users\Hokrikus\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe`（有 PIL/numpy，无 cv2）
- Node：同目录 `node\bin\node.exe`
- **批量改 JSON 一律用 Python 文件**（`python -c` 遇到中文/引号必坏，这条已经坑过十几次）

## 交付物布局

```
assets/          interface.json（含 icon / agent 字段）、pipeline/（36 个 JSON / 98 节点）、image/、locales/
agent/custom.mjs ScreenFrozen / ScreenMoved 的**唯一实现**（run.mjs 进程内注册也用这一份）
agent/main.mjs   agent 子进程入口（maa.Server + socket id，用 @maaxyz/maa-node/server 入口）
install/         打包产物（不入库）：interface.json + icon.png + resource + locales + node/ + agent/
tools/           device / crop / score / analyze_scores / probe / run / report / check_json / check_params / audit / pack / bundle_runtime / mxu_add_daily_config
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
