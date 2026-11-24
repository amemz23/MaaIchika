# Agent / Custom 识别（已上线的那一半 + 查到的 API 事实 + 还没做的）

## 现在有什么

| 东西                          | 位置                                                  | 状态                                                   |
| ----------------------------- | ----------------------------------------------------- | ------------------------------------------------------ |
| `ScreenFrozen`（Custom 识别） | `agent/custom.mjs`                                    | ✅ 真机验证过                                          |
| `ScreenMoved`（Custom 动作）  | `agent/custom.mjs`                                    | 注册了但**没有节点引用**（命中后自己会清零，留着备用） |
| agent 子进程入口              | `agent/main.mjs`                                      | `maa.Server` 启动，订阅 socket id；**MXU 侧待验**      |
| 进程内注册                    | `tools/run.mjs`                                       | ✅ 无头跑时自动注册，`Custom` 节点照样能命中           |
| 用它的节点                    | `标题_画面卡死`、`演出_画面卡死`、`清火_循环画面卡死` | ✅ 各挂在对应等待节点的 `on_error` 上                  |
| 补救链                        | `公共_卡死_重启游戏` → `公共_卡死_启动游戏`           | ✅ 真机走通（force-stop → StartApp → 标题 → 主页锚点） |

为什么要有它：卡在标题页点不动、演出 420 秒都没结束信号 —— 这类「画面死了」以前只能靠长
timeout 硬等，等到超时还只能盲点一下屏幕然后判失败。现在能当场认出来，改成冷启动重来。

## 从 `@maaxyz/maa-node` 的 d.ts 查到的 API 事实（不是猜的）

| API                                                                      | 位置                     | 说明                                                                             |
| ------------------------------------------------------------------------ | ------------------------ | -------------------------------------------------------------------------------- |
| `resource.register_custom_recognition(name, func)`                       | `dist/resource.d.ts:27`  | **进程内注册**，`tools/run.mjs` 走这条                                           |
| `resource.register_custom_action(name, func)`                            | `dist/resource.d.ts:30`  | 同上                                                                             |
| `maa.Server.register_custom_recognition/action` + `start_up(identifier)` | `dist/server.d.ts`       | 标准 agent 协议（独立进程），MXU 走这条                                          |
| `context.get_hit_count(node_name)`                                       | `dist/context.d.ts:49`   | 只能**读**命中次数                                                               |
| CustomRecognition 回调返回值                                             | `dist/types.d.ts:54`     | `[out_box, out_detail] \| null`（null = 未命中）                                 |
| pipeline 侧字段名                                                        | `dist/pipeline.d.ts:137` | `type: "Custom"` + `param.custom_recognition` / `param.custom_recognition_param` |

**没有「重置命中次数」的 API**（`get_hit_count` 只能读），所以循环仍然只能靠 `max_hit` 给足额度。

## 真机实测出来的机制（这几条决定了节点该怎么写）

1. **`on_error` 列表不是"只识别一次"**：框架会用**父节点的 `timeout` 和 `rate_limit`** 反复轮询
   `on_error` 里的候选，直到那个 timeout 用完。实测：父节点 4s/800ms 时，`on_error` 里的 Custom
   识别被调用了 3 次（第 3 次命中 `times: 3`）。
   → 所以 `times: 3` 挂在 `on_error` 里能攒够帧；挂在 `next` 里**每一轮也各拿 1 帧**。
2. **`on_error` 里 DirectHit 会把 Custom 饿死**：同一轮内候选按顺序识别，DirectHit 永远命中，
   于是在 `on_error = ["Custom节点", "DirectHit节点"]` 里，Custom 永远只有第 1 次采样机会。
   → 想让 Custom 攒帧，它就**必须是 on_error 里唯一的候选**（这就是 `演出_等待结束` 的
   `on_error` 只剩 `演出_画面卡死`、而把老的 `演出_点屏幕` 挪到卡死节点自己的 `on_error` 里的原因）。
3. **`times` 越大越稳、越慢**：`rate_limit` 800~900ms 时 `times: 3` ≈ 2.4~2.7 秒。
   实测游戏主页（有角色待机动画）连跑 12 轮都不会误命中，静态的系统设置页第 3 帧就命中。
4. **不能挂进 `next`**：启动过程中「プロジェクトセカイによろこばせ。」和 TIPS 两屏本来就是静态画面，
   挂 `next` 会被误判成卡死、把正常启动重启掉。**只挂 `on_error`。**
5. **命中后必须清零计数**：不清零的话同一次卡死里每一轮都命中，`max_hit` 瞬间耗光。
6. **Custom 识别名字写错不会报错**，运行期就是永远 MISS —— 现在 `tools/check_json.py`
   会扫 `agent/*.mjs` 里注册过的名字来拦（`check_custom_names`）。

## 待办

1. **MXU 侧验 agent 子进程**：`python tools/bundle_runtime.py` + `python tools/pack.py` 之后
   用 `install/mxu.exe` 真跑一次，确认 `ScreenFrozen` 在 MXU 里也能命中（runner 只能验进程内注册）。
   看 `install/` 下有没有 `node/node.exe`、`agent/main.mjs`、`agent/custom.mjs`、
   `agent/node_modules/@maaxyz/maa-node`。agent 起不来时 MXU 日志里会有一行 `[agent] ...`。
2. **`BonusAtLeast`**（Custom 识别，收益不明）：裁顶部 `n/25` 那块，用 0-9 模板自己拼数字 →
   命中条件 = `n >= min`，省掉枚举 25 个 OCR 节点。现在 `公共_体力为0` 的 `And(首位数字, OCR)`
   只判「是不是 0」，够用了，所以优先级低。

## 验证方法（不用真的把游戏弄卡死）

```bash
# 进程内注册能不能被 Custom 节点解析到 + 静态/动态画面能不能区分：
# 把设备停在**静态画面**（系统设置页）上跑，期望 2 次 MISS 后 HIT
node tools/run.mjs 标题_点击开始      # 静态画面上跑：15s 超时 -> 标题_画面卡死 HIT -> 冷启动 -> 主页锚点

python tools/check_json.py            # Custom 名字没注册会在这里报错
```

`scratch/test_frozen.mjs`（不入库）是这次用的一次性验证脚本，四种模式
（`静态` / `动态` / `等待` / `演出`）分别验命中、不误命中、`on_error` 轮询窗口、演出侧接线。
