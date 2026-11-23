/**
 * 无头运行器：直接用 MaaFramework 跑 pipeline，不经过 MXU 图形界面。
 *
 * 为什么要有它：MXU 是 GUI，跑一次任务要点好几下、还得人眼看日志；
 * 改了 pipeline 之后想快速回归只能靠这个脚本 —— 一条命令跑完，
 * 打印节点命中序列 + 识别得分，并把可视化图落到 debug/。
 *
 * 用法：
 *   node tools/run.mjs 启动                     跑单个任务入口
 *   node tools/run.mjs 每日签到 领取礼物         依次跑多个入口（同一次连接）
 *   node tools/run.mjs --list                   只加载资源并列出节点
 *   node tools/run.mjs 启动 --address 127.0.0.1:16384
 *   node tools/run.mjs 启动 --no-draw           不落可视化图（快一点）
 */

import maaModule from '@maaxyz/maa-node'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const maa = maaModule ?? globalThis.maa
const ROOT = process.cwd()
const ADB_CANDIDATES = [
    'C:/Users/Hokrikus/AppData/Local/Android/Sdk/platform-tools/adb.exe',
    'adb',
]

function parseArgs(argv) {
    const out = { entries: [], draw: true, timeout: 0, list: false, quiet: false }
    for (let i = 0; i < argv.length; i++) {
        const a = argv[i]
        if (a === '--list') out.list = true
        else if (a === '--no-draw') out.draw = false
        else if (a === '--quiet') out.quiet = true
        else if (a === '--address') out.address = argv[++i]
        else if (a === '--adb') out.adb = argv[++i]
        else if (a === '--timeout') out.timeout = Number(argv[++i])
        else if (a.startsWith('--')) throw new Error(`未知参数 ${a}`)
        else out.entries.push(a)
    }
    return out
}

const args = parseArgs(process.argv.slice(2))

function findAdb() {
    if (args.adb) return args.adb
    for (const p of ADB_CANDIDATES) {
        if (p === 'adb' || existsSync(p)) return p
    }
    throw new Error('找不到 adb，用 --adb 指定')
}

const debugDir = path.join(ROOT, 'debug')
mkdirSync(debugDir, { recursive: true })

let drawSeq = 0
function saveBuf(name, buf) {
    if (!args.draw || !buf || buf.byteLength === 0) return null
    const file = path.join(debugDir, `${String(++drawSeq).padStart(3, '0')}_${name.replace(/[\\/:*?"<>|]/g, '_')}.png`)
    writeFileSync(file, Buffer.from(buf))
    return path.basename(file)
}

function fmtBox(box) {
    if (!box) return ''
    // MaaFramework 的 Rect 在 node 绑定里是 [x, y, w, h] 元组
    if (Array.isArray(box)) return `[${box[0]},${box[1]},${box[2]},${box[3]}]`
    return `[${box.x},${box.y},${box.w ?? box.width},${box.h ?? box.height}]`
}

function describeReco(reco) {
    if (!reco) return ''
    const parts = [reco.hit ? 'HIT' : 'MISS']
    if (reco.box) parts.push(fmtBox(reco.box))
    const detail = reco.detail
    if (detail && !Array.isArray(detail)) {
        const best = detail.best
        if (best) {
            if (best.text !== undefined) parts.push(`"${best.text}"`)
            if (best.score !== undefined) parts.push(`score=${best.score.toFixed(3)}`)
            if (best.count !== undefined) parts.push(`count=${best.count}`)
        }
    }
    return parts.join(' ')
}

async function main() {
    const adb = findAdb()
    console.log(`[adb] ${adb}`)

    // 把 Maa 自己的日志与识别可视化落到 debug/，出问题时能直接看它看到了什么
    maa.Global.log_dir = debugDir
    maa.Global.save_draw = args.draw
    maa.Global.save_on_error = args.draw
    maa.Global.stdout_level = process.env.DSH_TRACE ? 'Debug' : 'Warn'

    const devices = await maa.AdbController.find(adb)
    if (!devices || devices.length === 0) throw new Error('没有找到 ADB 设备')
    for (const d of devices) console.log(`[device] ${d[0]}  ${d[2]}`)

    let device = devices[0]
    if (args.address) {
        const hit = devices.find((d) => d[2] === args.address || d[2].startsWith(args.address))
        if (!hit) throw new Error(`找不到设备 ${args.address}`)
        device = hit
    }

    const [name, , address, screencap, input, config] = device
    console.log(`[use] ${name} ${address} screencap=${screencap} input=${input}`)

    // 缩放配置：把短边锁到 720，与 pipeline 的 1280x720 基准对齐。
    // 设备本身也必须接近 16:9，否则缩放后宽度不是 1280（见 docs/设备适配.md）。
    const cfgObj = JSON.parse(config || '{}')
    const mergedCfg = JSON.stringify({ ...cfgObj, image_target_short_side: 720 })

    const agentPath = maa.AdbController.agent_path()
    if (!existsSync(agentPath)) console.warn(`[warn] agent 目录不存在：${agentPath}（输入会降级为 AdbShell）`)

    const ctrl = new maa.AdbController(adb, address, screencap, input, mergedCfg, agentPath)
    const conn = await ctrl.post_connection().wait()
    if (!conn.succeeded) throw new Error('控制器连接失败')
    console.log('[connect] ok')

    const res = new maa.Resource()
    const bundleDir = path.join(ROOT, 'assets', 'resource')
    const load = await res.post_bundle(bundleDir).wait()
    if (!load.succeeded) throw new Error('资源加载失败（看上面的 Maa 日志）')

    const nodes = res.node_list ?? []
    console.log(`[resource] ${nodes.length} 个节点`)
    if (nodes.length === 0) throw new Error('资源里没有任何节点')
    if (args.list) {
        for (const n of nodes) console.log('  ' + n)
        return 0
    }
    if (args.entries.length === 0) throw new Error('没给任务入口，用 --list 看有哪些')

    const tasker = new maa.Tasker()
    tasker.controller = ctrl
    tasker.resource = res

    let failures = 0
    for (const entry of args.entries) {
        if (!nodes.includes(entry)) {
            console.error(`[error] 节点不存在：${entry}`)
            failures++
            continue
        }
        console.log(`\n===== 运行 ${entry} =====`)
        const t0 = Date.now()

        const taskSinkId = tasker.add_context_sink((context, msg) => {
            // 回调里抛异常会打断 Maa 的 N-API 线程，一律自己吞掉
            try {
                const raw = String(msg?.msg ?? '')
                const kind = raw.split('.')[0]
                if (process.env.DSH_TRACE) console.log(`  <${raw}>`)
                if (kind === 'NextList') {
                    if (!args.quiet && raw.endsWith('Succeeded')) {
                        const names = (msg.list ?? []).map((n) => (typeof n === 'string' ? n : n?.name))
                        console.log(`  next <- ${msg.name}: ${names.join(' | ')}`)
                    }
                } else if (kind === 'Recognition' && /(Succeeded|Failed)$/.test(raw)) {
                    const reco = tasker.recognition_detail(String(msg.reco_id))
                    console.log(`  [识别] ${msg.name} ${describeReco(reco)}`)
                    if (reco && process.env.DSH_VERBOSE) {
                        const file = saveBuf(`reco_${msg.name}`, reco.draws?.[0] ?? reco.raw)
                        if (file) console.log(`         -> debug/${file}`)
                    }
                } else if (kind === 'Action' && /(Succeeded|Failed)$/.test(raw)) {
                    const act = tasker.action_detail(String(msg.action_id))
                    if (act) console.log(`  [动作] ${msg.name} ${act.action} ${act.success ? 'ok' : '失败'}`)
                }
            } catch (e) {
                console.error('  [sink error]', e?.message ?? e)
            }
        })

        const job = tasker.post_task(entry)
        const status = await job.wait()
        const detail = job.get()
        tasker.remove_context_sink(taskSinkId)

        const ms = Date.now() - t0
        const nodeChain = (detail?.nodes ?? [])
            .map((id) => tasker.node_detail(String(id)))
            .filter(Boolean)
            .map((n) => n.name)

        // Maa 的"任务成功"只代表流程走完了，不代表真的做成了事。
        // 这里额外要求链尾落在**验证型终止节点**上（主页锚点 / 完成_*），
        // 否则报"结束但未验证"，免得下次又被"静默成功"骗过去。
        const last = nodeChain[nodeChain.length - 1] ?? ''
        const verified = last === '公共_主页锚点' || last.startsWith('完成_')
        const verdict = !status.succeeded ? '失败' : verified ? '完成（已验证）' : '结束但未验证'
        console.log(`----- ${entry}: ${verdict} ${(ms / 1000).toFixed(1)}s`)
        console.log(`      节点链: ${nodeChain.join(' -> ') || '(空)'}`)
        if (verdict !== '完成（已验证）') failures++
        writeFileSync(
            path.join(debugDir, `run_${entry.replace(/[\\/:*?"<>|]/g, '_')}.json`),
            JSON.stringify({ entry, status, ms, nodes: nodeChain, verified }, null, 2),
        )
    }

    // 打印资源加载阶段的告警/报错（节点重名、未知图片等）
    tasker.destroy()
    res.destroy()
    ctrl.destroy()
    return failures === 0 ? 0 : 1
}

main()
    .then((code) => process.exit(code))
    .catch((e) => {
        console.error('[fatal]', e?.message ?? e)
        process.exit(2)
    })
