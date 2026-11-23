# AGENTS.md —— MaaIchika 开发规范

给 AI Agent 与协作者的硬性约定。**动手前先读完**；环境与工具细节见
[开发手册](docs/zh_cn/developers/development.md)。

## 项目是什么

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的《世界计划 多彩舞台》
（Project SEKAI，**先做日服**）自动化。纯 Pipeline JSON，无自定义 agent。

**边界**（不是"暂未实现"，是永远不做）：

- 不做音游判定 —— 只用游戏内 AUTO。截图轮询的节奏根本跟不上判定时序，也没有必要。
- 不消耗任何付费货币、不自动抽卡、不自动购买。体力/Boost 只用游戏内正常消耗。
- 不修改内存、不注入进程、不改网络请求。所有操作都能在游戏界面里人手复现。
- 活动剧情不加速、不跳过（跳了就少水晶）。

## 目录约定

| 路径                                      | 作用                                                       |
| ----------------------------------------- | ---------------------------------------------------------- |
| `assets/interface.json`                   | 控制器、资源包、任务入口、多语言声明                       |
| `assets/resource/pipeline/*.json`         | 全部节点，一界面一文件                                     |
| `assets/resource/image/<界面>/<元素>.png` | 模板图，基准 1280×720                                      |
| `assets/resource/default_pipeline.json`   | 全局默认：`rate_limit` / `pre_delay` / `post_delay` / 阈值 |
| `assets/resource/model/ocr/`              | PPOCR 模型（不入库，`tools/fetch_ocr.py` 拉）              |
| `tools/`                                  | device / crop / score / analyze / probe / run / check_json |
| `docs/zh_cn/developers/`                  | 开发手册、识别基线                                         |

## 六条硬规矩

### 1. 坐标一律 1280×720

`roi`、`target`、`box` 都以 1280×720 为基准。设备必须是 16:9（`python tools/device.py fix`），
否则框架缩放后画布不是 1280×720，所有坐标和模板一起失效。

模板图必须**从 720p 截图原样裁下来**（`tools/crop.py` 就是这么做的），不许缩放后再裁。

### 2. 每个动作都要有识别依据，每个动作后都要有验证

点击前必须命中某个识别；点击后 `next` 要能覆盖所有可能的结果画面。**禁止盲点**：
除了 `DoNothing` / `StopTask` 这类不做事的节点，不允许出现"无识别 + 直接点击"。

### 3. `next` 是候选列表，不是执行序列

这一点最坑人，务必记牢：

```
A.next = [B, C]     # B 命中 → 执行 B → 走 B 自己的 next → C 永远不会执行
```

由此推出三条写法：

- **等待/弹窗/加载这类公共辅助节点，用 `[JumpBack]` 引用**，做完回父节点继续判断，
  否则会把主流程吞掉。
- **导航节点把"自己"放进 `next`**：点击丢了下一轮还能点，而不是把链卡死。
  配合 `max_hit` 上限防止无限点。
- **`[JumpBack]` 的目标节点一定要配 `max_hit`**，否则"回退 → 又命中 → 又回退"会死循环。
- **验证型终止节点只能直接引用，绝不能写 `[JumpBack]`**：它永远命中，加了回跳就是
  "命中 → 回跳 → 父节点重扫 → 又命中"的无限空转。
- **受保护的系统弹窗（如 Google 登录的 `ConsentActivity`）收不到注入按键**：
  `ClickKey` 会直接**动作失败**，必须改用 `Shell` 动作跑原始 adb（`input keyevent 4`）。

### 4. 不用固定延时等动画

`pre_delay` / `post_delay` 在 `default_pipeline.json` 里全局置 0。要等就识别"动画结束后
才出现的东西"（锚点），或给节点写 `timeout` 让框架重试 `next` 列表。

`timeout` 是**本节点 next 列表的识别窗口**，不是节点自己的识别等待时间 —— 想等某个画面
出现，把 timeout 加在**它的前一个节点**上。

### 5. 终止要有验证

"next 跑空 = 任务成功"是假象。每个任务链的终点必须落在**验证型终止节点**上
（`公共_主页锚点`，或 `完成_*` 系列）。`tools/run.mjs` 会按这条判定"完成（已验证）/
结束但未验证/失败"，CI 里也是这么卡的。

### 6. 任何循环都要有出口

`max_hit` 就是出口。没有 `max_hit` 的自循环会被 `tools/check_json.py` 报出来。

## 命名

- 节点：`界面_动作`，中文，如 `主页_进礼物箱`、`演出_开演`
- 公共节点：`公共_` 前缀，如 `公共_等待加载`、`公共_回主页`
- 任务入口：`任务_` 前缀，与 `interface.json` 的 `entry` 完全一致
- 图片：`image/<界面>/<元素>.png`，小写下划线

## 新增节点的标准流程

1. `python tools/device.py shot scratch/x.png` 截到目标界面
2. 在 `tools/crops.json` 里登记要裁的元素，`python tools/crop.py --sheet` 裁 + 出对照图
3. 写节点，`threshold` 先填 0.8
4. `node tools/score.mjs --dir scratch/shots` → `python tools/analyze_scores.py` 量出
   正/负样本分布，把建议阈值写回去；判别力不足（gap < 0.1）就换模板或换识别方式
5. `node tools/run.mjs 任务_xxx` 真机跑，看节点链和识别分数
6. `python tools/check_json.py` + `npm run check:maa` + `npm run format:check`

## 自检

提交前必须全过：

```bash
python tools/check_json.py      # JSON / 引用 / 占位 / 环无出口 / i18n
npm run check:maa               # 用真实 MaaFramework 加载 interface.json 与资源包
npm run format:check            # prettier
```

真机验证用 `node tools/run.mjs <任务入口>`，判定标准是"完成（已验证）"。

## 审查重点

1. **点击是否还有盲点**（无识别的 Click）
2. **辅助节点有没有 `[JumpBack]` + `max_hit`**
3. **链尾是不是验证型终止节点**（不是"next 跑空"）
4. **阈值是不是量出来的**（有没有跑 analyze_scores）
5. **有没有新增固定延时**
6. **多语言键是否两边一致**
