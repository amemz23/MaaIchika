# 从 MaaEnd 抄来的约定（以及我们不抄的地方）

蓝本：[MaaEnd/MaaEnd](https://github.com/MaaEnd/MaaEnd) 的
[`.agents/skills/pipeline-guide/SKILL.md`](https://raw.githubusercontent.com/MaaEnd/MaaEnd/7c7274d435600522acdce597fcd677da7cd19189/.agents/skills/pipeline-guide/SKILL.md)。
它跟我们一样是纯 Pipeline JSON 的 MaaFramework 项目，踩过的坑高度重合，所以直接对齐它的写法。

## 采纳的

### 1. 同一个按钮不要无脑重复点

MaaEnd 的原话：_「避免对同一按钮重复点击——第二次点击可能作用于下一界面的其他元素」_。
它们让**验证节点**决定要不要再点（`next: ["VerifyNextScreen", "[JumpBack]ClickConfirm"]`），
而不是把节点挂进自己的 `next` 里狂点。

我们改过的地方：

- `标题_点击开始` 的 `max_hit` 从 200 收到 **15**（之前为了"点不动就继续点"直接开到 200，等于放弃了这条原则）

### 2. 等画面稳定用 `post_wait_freezes`，不要加大 `timeout`

点击会触发过场动画，动画期间做识别必然 MISS。MaaEnd 的做法是给点击节点加
`post_wait_freezes`（"画面静止 N 毫秒后再继续"），而不是把 `timeout` 调大硬等。

我们改过的地方：

- `标题_点击开始` 加 `post_wait_freezes: { time: 300, target: [0, 0, 0, 0] }`

### 3. `timeout` 是"本节点 next 的识别窗口"，不是"愿意等多久"

之前 `标题_点击开始` 写 `timeout: 600000`，一旦锚点漏了就白等 10 分钟。
现在统一按 **5~20 秒**给，宁可多轮重扫。

### 4. 组合识别比单模板稳（`And` / `Or`）

MaaEnd 常把"背景 + 图标"用 `And` 拼起来；我们的用法：

- `Or`：`标题_点击开始` = 抄字模板 **或** OCR「TAP TO START」（抄字会变暗/位移，单锚点必漏）
- `And`：`故事_本集结束` = 章节号「第」**且**（列表 tab 文案 **或** 书签图标）——用它区分"章节列表"和"剧情播放"

### 5. OCR `expected` 的默认值要显式

MaaEnd 用 `tools/add_node_defaults.py` 给节点补齐 `rate_limit: 0` / `pre_delay: 0` / `post_delay: 0`，
因为协议默认 `rate_limit=1000ms`、`pre_delay/post_delay=200ms`，**省略字段会引入隐式等待**。
我们是在 `default_pipeline.json` 里全局设（`rate_limit: 600`、两个 delay 都 0），效果一样。

## 不抄的（以及为什么）

### 1. OCR `expected` 我们允许写片段

MaaEnd 要求 `expected` 写**完整文本**，截断时必须加 `// @i18n-skip` 并在注释里保留原文。
我们**故意**写片段，理由：

| 我们的写法              | 为什么不能用完整文本                                        |
| ----------------------- | ----------------------------------------------------------- |
| `第`（章节号列）        | 话数不定（第1話 / 第20話），完整文本每本都要枚举            |
| `0/25`                  | 体力数值会变，1/25 就 MISS —— 正好是我们要的"只有 0 才命中" |
| `サイド`                | 卡片上是两行「サイド」「ストーリー」，整串跨行 OCR 认不出来 |
| `前編` / `一括受け取り` | 这俩其实是完整文本，没问题                                  |

代价是误命中面变大，所以配套要求：**ROI 必须窄**（`第` 的 ROI 只框章节号那一列、`0/25` 只框顶部数字）。
这一条是我们和 MaaEnd 最大的分歧，属于"用 ROI 换灵活度"。

### 2. 没有 go-service / Custom 动作

MaaEnd 有 go-service 提供 `SubTask`、`ClearHitCount`、`ExpressionRecognition` 等自定义节点，
能写表达式、能清命中计数。我们是纯 Pipeline，没有 agent —— 所以：

- 需要"清计数"的地方用 `max_hit` 设计绕开
- 需要"顺序执行子任务"的地方只能把节点摊平（这也是为什么 `任务_任务奖励` 的四个 tab 是四个领取节点而不是循环）

### 3. 命名用中文 `界面_动作`，不是 PascalCase

MaaEnd 用 `ResellMain` / `DailyProtocolPassInMenu` 这种 PascalCase + 模块前缀。
我们的节点是 `公共_回主页` / `故事_连点` 这种中文命名，`tools/run.mjs` 的判定和 README 里的
表格都建立在这个命名上，不打算改。

## 还能再抄的（待办）

- **`pre_wait_freezes`**：进演出/开演前的转场也可以用（现在靠 `公共_等待加载` 认初音头像）
- **`box_index`**：`And` 组合识别时用它指定"以哪个子识别的框作为点击目标"，我们现在都是点第一个
- **节点测试**：MaaEnd 有 `docs/.../node-testing.md`，我们是靠 `tools/probe.mjs` + `tools/run.mjs` 手工验
