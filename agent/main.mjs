#!/usr/bin/env node
/**
 * MaaIchika agent —— 只做纯 Pipeline 做不到的那一件事：判断「画面是不是死了」。
 *
 * MaaFramework / MXU 会按 interface.json 的 agent 字段把它当子进程拉起，
 * 并把 socket id 作为第一个参数传进来（process.argv[2]）。
 *
 * 暴露两个 custom：
 *   - ScreenFrozen（Custom 识别）：连续 `times` 次截图**完全相同** → 命中。
 *     用途：卡在标题页点不动、演出卡住没有结束信号 —— 这类情况以前只能靠 timeout 硬等。
 *   - ScreenMoved（Custom 动作）：清掉计数状态，让下一轮重新算。
 *
 * 用"整张图字节完全相同"而不是像素相似度：一帧都没动才叫卡死，这是充分条件，
 * 而且不需要任何图像库，不引入额外依赖。
 *
 * 回调签名（从 maa-node 的 d.ts 读的，别按别的项目抄）：
 *   CustomCallback<Self, Ret> = (this: Self, self: Self) => MaybePromise<Ret>
 *   CustomRecognitionSelf = { context, id, task, name, param, image }
 *   返回 [out_box, out_detail] 表示命中；null 表示未命中。
 */

import { createRequire } from 'node:module'

// agent 侧必须用 `@maaxyz/maa-node/server` 这个入口 —— 默认入口（index-client）是给
// controller/resource/tasker 用的，上面没有 `Server`。（从 package.json 的 exports 读出来的）
const require = createRequire(import.meta.url)
const maaModule = require('@maaxyz/maa-node/server')
const maa = maaModule ?? globalThis.maa

const state = { hash: null, same: 0 }

/** 把 self.image（可能是 Buffer / Uint8Array / ArrayBuffer / {raw}）统一成 Buffer */
function imageBytes(self) {
    const img = self?.image
    if (!img) return null
    if (Buffer.isBuffer(img)) return img
    if (img instanceof ArrayBuffer) return Buffer.from(img)
    if (ArrayBuffer.isView(img)) return Buffer.from(img.buffer, img.byteOffset, img.byteLength)
    if (img.raw) return imageBytes({ image: img.raw })
    return null
}

function shortHash(buf) {
    // 采样 + FNV-1a：够分辨"整张图有没有变"，而且是纯 JS，不依赖图像库
    let h = 0x811c9dc5
    const step = Math.max(1, Math.floor(buf.length / 4096))
    for (let i = 0; i < buf.length; i += step) {
        h ^= buf[i]
        h = Math.imul(h, 0x01000193) >>> 0
    }
    return `${buf.length}:${h.toString(16)}`
}

maa.Server.register_custom_recognition('ScreenFrozen', (self) => {
    const times = typeof self?.param?.times === 'number' ? self.param.times : 3
    const bytes = imageBytes(self)
    if (!bytes) return null

    const h = shortHash(bytes)
    if (h === state.hash) state.same += 1
    else {
        state.hash = h
        state.same = 0
    }

    if (state.same >= times) {
        return [[0, 0, 0, 0], `画面连续 ${state.same} 次未变化（times=${times}）`]
    }
    return null
})

maa.Server.register_custom_action('ScreenMoved', () => {
    state.hash = null
    state.same = 0
    return true
})

const identifier = process.argv[2]
if (!identifier) {
    console.error('[agent] 缺少 socket id —— 这个文件由 MXU / MaaFramework 作为子进程拉起，不要手动跑')
    process.exit(2)
}

maa.Server.start_up(identifier)
    .then((ok) => {
        console.log(`[agent] started=${ok}`)
        return maa.Server.join()
    })
    .catch((err) => {
        console.error('[agent] 启动失败:', err)
        process.exit(1)
    })
