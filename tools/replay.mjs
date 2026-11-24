/**
 * 离线回放：把 pipeline 里的**真实节点**跑在一张截图上，看它认不认、点哪里、往下走哪条链。
 *
 * 为什么需要它（踩过的坑）：`probe.mjs --node` 把 dump 出来的组合识别（Or/And）再喂回去会 MISS，
 * 而同一份参数里的 ColorMatch / OCR 单独跑都 HIT —— **组合识别必须在节点上下文里跑才准**。
 * 真机跑一次要几十秒、还要设备在线、还不是每次都能复现那个画面；回放一张图只要几百毫秒，
 * 而且和真跑走的是同一套识别代码（同一个 Resource + Tasker，只是 screencap 换成固定图片）。
 *
 * 原理：`maa.CustomController` 允许自己提供 screencap / click / shell，
 * 所以整条节点链能在一张静态图上跑起来，点击被记录下来而不真的发出去。
 *
 * 用法：
 *   node tools/replay.mjs 演出_结算 scratch/shots/r02.png
 *   node tools/replay.mjs 任务_奖励_一括_ボーナス scratch/shots/btn_mission.png scratch/shots/btn_tab_bonus.png
 *   node tools/replay.mjs --expect miss 任务_奖励_一括_ボーナス scratch/shots/btn_tab_bonus.png
 *   node tools/replay.mjs --inject scratch/新节点.json 测试_节点 scratch/shots/r02.png
 *     （`--inject` 会先把文件里的节点 override 进资源包 —— 试新写法不用改 pipeline）
 *
 * 退出码：全部符合预期 0；有不符合 1（可以进 CI，喂真实截图当回归）。
 */

import maaModule from '@maaxyz/maa-node'
import { readFileSync, mkdirSync } from 'node:fs'
import path from 'node:path'

const maa = maaModule ?? globalThis.maa
const ROOT = process.cwd()
const MAX_STEPS = 6

const argv = process.argv.slice(2)
// 先摘掉「--flag 值」这种成对参数，剩下的才是「节点名 + 图」
const opts = {}
const rest = []
for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith('--')) {
        opts[argv[i].slice(2)] = argv[++i]
        continue
    }
    rest.push(argv[i])
}
const expect = opts.expect ?? 'hit'
const injectFile = opts.inject ?? null
const node = rest[0]
const images = rest.slice(1).filter((a) => a.endsWith('.png'))
if (!node || images.length === 0 || !['hit', 'miss'].includes(expect)) {
    console.error('用法：node tools/replay.mjs [--expect hit|miss] [--inject 节点.json] <节点名> <图.png...>')
    process.exit(2)
}

function loadImage(rel) {
    const buf = readFileSync(path.resolve(ROOT, rel))
    return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)
}

async function replay(res, imageRel) {
    const image = loadImage(imageRel)
    const clicks = []
    let touch = null
    const ctrl = new maa.CustomController({
        connect: () => true,
        get_features: () => ['mouse', 'keyboard'],
        get_info: () => JSON.stringify({ width: 1280, height: 720, orientation: 1 }),
        screencap: () => image,
        click: (x, y) => {
            clicks.push(`click(${x},${y})`)
            return true
        },
        // 只实现 click 不够：框架对 CustomController 默认走 touch 手势，
        // 少了这三个动作会报 Click 失败，链路就会错走到 on_error 上去
        touch_down: (contact, x, y) => {
            touch = `(${x},${y})`
            return true
        },
        touch_move: () => true,
        touch_up: () => {
            if (touch) clicks.push(`touch${touch}`)
            touch = null
            return true
        },
        swipe: (x1, y1, x2, y2) => {
            clicks.push(`swipe(${x1},${y1})->(${x2},${y2})`)
            return true
        },
        shell: () => '',
        start_app: () => true,
        stop_app: () => true,
    })
    const conn = await ctrl.post_connection().wait()
    if (!conn.succeeded) throw new Error('CustomController 连接失败')

    const tasker = new maa.Tasker()
    tasker.controller = ctrl
    tasker.resource = res

    const chain = []
    const recos = []
    const actions = []
    let stop = false
    const sink = tasker.add_context_sink((context, msg) => {
        try {
            const raw = String(msg?.msg ?? '')
            if (raw.startsWith('Recognition') && /(Succeeded|Failed)$/.test(raw)) {
                const detail = tasker.recognition_detail(String(msg.reco_id))
                const best = detail?.detail && !Array.isArray(detail.detail) ? detail.detail.best : null
                recos.push({
                    name: String(msg.name),
                    hit: !!detail?.hit,
                    box: best?.box ?? detail?.box ?? null,
                    count: best?.count,
                    text: best?.text,
                })
            } else if (raw.startsWith('Action') && /(Succeeded|Failed)$/.test(raw)) {
                const act = tasker.action_detail(String(msg.action_id))
                actions.push(`${msg.name}:${act?.action ?? '?'}:${act?.success ? 'ok' : 'fail'}`)
            } else if (raw.startsWith('Node') && raw.endsWith('Succeeded')) {
                chain.push(String(msg.name))
                if (chain.length >= MAX_STEPS && !stop) {
                    stop = true
                    tasker.post_stop()
                }
            }
        } catch (e) {
            console.error('  [sink error]', e?.message ?? e)
        }
    })

    // 回放只关心识别结果，不需要真等节点 12 秒的 next 窗口
    res.override_pipeline({ [node]: { timeout: 1200, rate_limit: 200 } })
    const job = tasker.post_task(node)
    await job.wait()
    const detail = job.get()
    tasker.remove_context_sink(sink)

    const nodeChain = (detail?.nodes ?? [])
        .map((id) => tasker.node_detail(String(id)))
        .filter(Boolean)
        .map((n) => n.name)

    tasker.destroy()
    ctrl.destroy()

    const first = recos.find((r) => r.name === node) ?? null
    return { image: path.basename(imageRel), hit: !!first?.hit, first, chain: nodeChain, clicks, actions }
}

async function main() {
    const logDir = path.join(ROOT, 'debug', 'replay')
    mkdirSync(logDir, { recursive: true })
    maa.Global.log_dir = logDir
    maa.Global.stdout_level = 'Fatal'

    const res = new maa.Resource()
    const loaded = await res.post_bundle(path.join(ROOT, 'assets', 'resource')).wait()
    if (!loaded.succeeded) throw new Error('资源加载失败')
    if (injectFile) {
        const nodes = JSON.parse(readFileSync(path.resolve(ROOT, injectFile), 'utf8'))
        res.override_pipeline(nodes)
        console.log(`[inject] ${injectFile} -> ${Object.keys(nodes).join(', ')}`)
    }

    let bad = 0
    for (const img of images) {
        const r = await replay(res, img)
        const f = r.first
        const ok = expect === 'hit' ? r.hit : !r.hit
        if (!ok) bad++
        const detail = f
            ? `识别框=${JSON.stringify(f.box)}${f.count !== undefined ? ` count=${f.count}` : ''}${f.text ? ` text="${f.text}"` : ''}`
            : '(没跑到这个节点)'
        console.log(`${ok ? '[ok]  ' : '[FAIL]'} ${(r.hit ? 'HIT ' : 'MISS').padEnd(5)} ${r.image.padEnd(24)} ${node}  ${detail}`)
        if (r.chain.length) console.log(`       节点链: ${r.chain.slice(0, MAX_STEPS).join(' -> ')}`)
        // 静态图上同一个节点会反复命中（真实场景里画面会变），这里只展示前几次免得刷屏
        if (r.clicks.length) console.log(`       点击: ${r.clicks.slice(0, 6).join(' ')}${r.clicks.length > 6 ? ' …' : ''}`)
        if (r.actions.length) {
            console.log(`       动作: ${r.actions.slice(0, 6).join(' | ')}${r.actions.length > 6 ? ' …' : ''}`)
        }
    }
    res.destroy()
    console.log(`\n${images.length} 张图，${bad} 张不符合 expect=${expect}`)
    return bad
}

main()
    .then((bad) => process.exit(bad > 0 ? 1 : 0))
    .catch((e) => {
        console.error('[fatal]', e?.message ?? e)
        process.exit(2)
    })
