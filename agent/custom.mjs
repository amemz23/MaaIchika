#!/usr/bin/env node
/**
 * 自定义识别 / 自定义动作的**唯一实现** —— 只做纯 Pipeline 做不到的那一件事：判断「画面是不是死了」。
 *
 * 为什么单独一个文件：同一份代码要在两个地方注册，行为必须完全一致，
 * 否则会出现「MXU 里好的、runner 里坏」这种没法复现的 bug：
 *
 *   1. `agent/main.mjs` —— 走标准 agent 协议（`maa.Server`），MXU / MaaFramework 把它当子进程拉起
 *   2. `tools/run.mjs`  —— 进程内 `resource.register_custom_recognition()`，无头跑时不用起子进程
 *
 * 暴露两个 custom：
 *   - `ScreenFrozen`（Custom 识别）：同一个节点连续 `times` 次截图的**字节完全相同** → 命中。
 *     用途：卡在标题页点不动、演出卡住没有结束信号 —— 这类情况以前只能靠 timeout 硬等。
 *     参数：`{ "times": 3 }`（默认 3，即连续 3 帧一模一样）。
 *   - `ScreenMoved`（Custom 动作）：清掉该节点的计数，让下一轮从零开始攒帧。
 *     目前没有节点引用它（命中后 `ScreenFrozen` 自己会清零），留给手动调试。
 *
 * 用「整张图字节完全相同」而不是像素相似度：一帧都没动才叫卡死，这是充分条件，
 * 而且不需要任何图像库，不引入额外依赖。
 *
 * 回调签名（从 maa-node 的 d.ts 读的，别按别的项目抄）：
 *   CustomCallback<Self, Ret> = (this: Self, self: Self) => MaybePromise<Ret>
 *   CustomRecognitionSelf = { context, id, task, name, param, image, roi }
 *   返回 [out_box, out_detail] 表示命中；null 表示未命中。
 */

/** 每个节点名一份计数：标题页的卡死检测和演出的卡死检测互不干扰 */
const states = new Map()

/**
 * 把 self.image 统一成 Buffer。
 * 实测进程内注册（resource 侧）拿到的是 ArrayBuffer；agent 侧（Server）历史上出现过
 * Buffer / Uint8Array / { raw } 几种形态，这里全部兼容 —— 拿不到就返回 null（= 未命中），
 * 绝不抛异常：回调里抛异常会打断 Maa 的 N-API 线程。
 */
function imageBytes(self) {
    const img = self?.image
    if (!img) return null
    if (Buffer.isBuffer(img)) return img
    if (img instanceof ArrayBuffer) return Buffer.from(img)
    if (ArrayBuffer.isView(img)) return Buffer.from(img.buffer, img.byteOffset, img.byteLength)
    if (img.raw) return imageBytes({ image: img.raw })
    return null
}

/** 采样 + FNV-1a：够分辨「整张图有没有变」，纯 JS，不依赖图像库 */
function shortHash(buf) {
    let h = 0x811c9dc5
    const step = Math.max(1, Math.floor(buf.length / 4096))
    for (let i = 0; i < buf.length; i += step) {
        h ^= buf[i]
        h = Math.imul(h, 0x01000193) >>> 0
    }
    return `${buf.length}:${h.toString(16)}`
}

export function screenFrozen(self) {
    const raw = self?.param?.times
    const times = Number.isFinite(raw) && raw >= 2 ? Math.floor(raw) : 3
    const bytes = imageBytes(self)
    if (!bytes || bytes.byteLength === 0) return null

    const key = String(self?.name ?? '')
    const hash = shortHash(bytes)
    const state = states.get(key) ?? { hash: null, same: 0 }

    if (hash === state.hash) state.same += 1
    else {
        state.hash = hash
        state.same = 0
    }
    states.set(key, state)

    const frames = state.same + 1 // 含当前这一帧
    if (frames < times) return null

    // 命中即清零：恢复动作做完以后要重新攒够 times 帧才允许再命中。
    // 不清零的话，同一次卡死里每一轮都会命中，max_hit 会被瞬间耗光。
    states.delete(key)
    // box 给个 1×1 的合法矩形：Custom 识别的命中与否只看回调有没有返回值，
    // 但返回 [0,0,0,0] 有的版本会当成"空框"，1×1 更稳。动作一律是 DoNothing，框本身不影响点击。
    return [[0, 0, 1, 1], `画面连续 ${frames} 帧完全相同（times=${times}）`]
}

export function screenMoved(self) {
    states.delete(String(self?.name ?? ''))
    return true
}

/** `registry` 可以是 `maa.Resource`（进程内）或 `maa.Server`（agent 子进程），两者方法名一致 */
export function registerCustoms(registry) {
    registry.register_custom_recognition('ScreenFrozen', screenFrozen)
    registry.register_custom_action('ScreenMoved', screenMoved)
    return registry
}

/** 测试 / 调试用：把所有计数清空 */
export function resetState() {
    states.clear()
}
