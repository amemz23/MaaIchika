#!/usr/bin/env node
/**
 * MaaIchika agent —— 由 MaaFramework / MXU 按 interface.json 的 agent 字段当子进程拉起，
 * socket id 作为第一个参数传进来（process.argv[2]）。
 *
 * 这里只做**进程启动**：真正的自定义识别/动作实现在 `./custom.mjs`，
 * 和 `tools/run.mjs` 的进程内注册共用同一份代码（见该文件顶部注释）。
 *
 * 注意入口必须用 `@maaxyz/maa-node/server` —— 默认入口（index-client）是给
 * controller/resource/tasker 用的，上面没有 `Server`。（从 package.json 的 exports 读出来的）
 */

import { createRequire } from 'node:module'

import { registerCustoms } from './custom.mjs'

const require = createRequire(import.meta.url)
const maaModule = require('@maaxyz/maa-node/server')
const maa = maaModule ?? globalThis.maa

registerCustoms(maa.Server)

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
