# Agent 计划（已验证的 API 事实 + 分两步走的方案）

## 已经确认的事实（从 `@maaxyz/maa-node` 的 d.ts 读出来的，不是猜的）

| API | 位置 | 说明 |
| --- | --- | --- |
| `resource.register_custom_recognition(name, func)` | `dist/resource.d.ts:27` | **可以进程内注册**，不用起独立 agent 进程 |
| `resource.register_custom_action(name, func)` | `dist/resource.d.ts:30` | 同上 |
| `maa.Server.register_custom_recognition/action` + `start_up(identifier)` | `dist/server.d.ts` | 标准 agent 协议（独立进程），MXU 走这条 |
| `context.get_hit_count(node_name)` | `dist/context.d.ts:49` | 只能**读**命中次数 |
| CustomRecognition 回调返回值 | `dist/types.d.ts` | `[out_box, out_detail] \| null`（返回 null = 未命中） |

**关键结论：没有找到"重置命中次数"的 API**（`get_hit_count` 只能读）。所以 `ClearHit` 这个想法目前做不了 —— 循环只能继续靠 `max_hit` 给足额度。

## 先别急着上 agent：清火循环其实不需要它

「一次把体力打光」用纯 Pipeline 就能表达，只要有出口：

```
清火循环 = 开演 → 等待结束 → 结算 → 回到编成页 → 体力为 0 ? 回主页 : 再开演
```

- 出口靠现成的 `公共_体力为0`（OCR 顶部 `0/25`，实测 0.999）
- 唯一的代价是 `演出_开演` / `演出_结算` 这类节点在一次运行里会被命中很多次，
  `max_hit` 必须给够（比如 30），否则补丁打完一次就被移出候选列表

**所以第一步应该是：用纯 Pipeline 做 `任务_清火循环`**，而不是先加 agent。
如果这条能跑通，"打光体力"的痛点就没了，agent 也就只剩下"按数值做判断"这类小众需求。

## 如果真要做 agent，最小方案

文件布局：

```
agent/
├── main.mjs          # 用 maa.Server 起 agent 进程（MXU 用）
└── custom.mjs        # 具体实现，run.mjs 里直接 register_custom_recognition 复用同一份
```

`interface.json` 加：

```json
"agent": { "child_exec": "node", "child_args": ["agent/main.mjs"] }
```

第一个值得做的 custom（成本低、收益明确）：

- **`ScreenFrozen`**（Custom 识别）：连续 N 次截图字节完全相同 → 命中。
  用途：`卡在标题页点不动`、`演出卡住没有结束信号` 这类**"画面死了"**的情况，
  现在只能靠长 timeout 硬等（就是这次踩的坑）。
  实现只需要比较 PNG 的哈希，不用图像库。
- **`ScreenMoved`**（Custom 动作）：清掉上面的状态。

第二个（需要点工作量）：**`BonusAtLeast`**（Custom 识别）：裁顶部 `n/25` 那块，
用 0-9 模板自己匹配出数字 → 命中条件 = `n >= min`。
这样"体力 ≥1 才开演"就不用枚举 25 个 OCR 节点了。

## 验证顺序（每一步都要能跑通再下一步）

1. `agent/custom.mjs` 里只实现 `ScreenFrozen`，先用 `tools/run.mjs` 进程内注册，
   写一个"标题页卡住"的测试任务，人为把游戏停住，确认能命中
2. 同一份实现接到 `agent/main.mjs`（`maa.Server`），用 MXU 验证 agent 进程能被拉起
3. 再考虑 `BonusAtLeast`
