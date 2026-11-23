/**
 * 模板判别力测量：用 MaaFramework 自己的 TemplateMatch 给"模板 × 截图"打分。
 *
 * 为什么要它：阈值不是拍脑袋定的。正样本要留足余量，负样本（别的界面）不能过线，
 * 两者中间才有安全区。这里直接调框架的识别，得到与运行时**完全一致**的分数，
 * 比自己用 numpy 复刻一遍可靠。
 *
 * 用法：
 *   node tools/score.mjs scratch/s04.png scratch/s10.png
 *   node tools/score.mjs --dir scratch --limit 60
 *   node tools/score.mjs --spec              # 只用 crops.json 里的模板，扫 scratch 下所有图
 */

import maaModule from '@maaxyz/maa-node'
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const maa = maaModule ?? globalThis.maa
const ROOT = process.cwd()

function parseArgs(argv) {
    const out = { images: [], dir: null, limit: 40, spec: false }
    for (let i = 0; i < argv.length; i++) {
        const a = argv[i]
        if (a === '--dir') out.dir = argv[++i]
        else if (a === '--limit') out.limit = Number(argv[++i])
        else if (a === '--spec') out.spec = true
        else out.images.push(a)
    }
    return out
}

const args = parseArgs(process.argv.slice(2))

// 从 crops.json 拿到模板清单（名字 -> 资源包内相对路径）
function loadTemplates() {
    const spec = JSON.parse(readFileSync(path.join(ROOT, 'tools', 'crops.json'), 'utf8'))
    return spec.crops.map((c) => ({ name: c.name, file: c.out.replaceAll('\\', '/'), note: c.note ?? '' }))
}

function listImages() {
    if (args.images.length > 0) return args.images.map((p) => path.resolve(ROOT, p))
    const dir = path.resolve(ROOT, args.dir ?? 'scratch')
    return readdirSync(dir)
        .filter((f) => f.endsWith('.png') && !f.includes('_raw') && f !== 'sheet.png')
        .slice(0, args.limit)
        .map((f) => path.join(dir, f))
}

async function main() {
    maa.Global.log_dir = path.join(ROOT, 'debug')
    maa.Global.stdout_level = 'Warn'
    const templates = loadTemplates()
    const images = listImages()
    if (images.length === 0) throw new Error('没有截图可测')

    const res = new maa.Resource()
    const loaded = await res.post_bundle(path.join(ROOT, 'assets', 'resource')).wait()
    if (!loaded.succeeded) throw new Error('资源加载失败')

    const tasker = new maa.Tasker()
    tasker.resource = res

    const rows = []
    for (const imgPath of images) {
        const buf = readFileSync(imgPath)
        const ab = buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)
        const row = { image: path.basename(imgPath), scores: {} }
        for (const t of templates) {
            const job = tasker.post_recognition(
                'TemplateMatch',
                { template: [t.file], threshold: 0, roi: [0, 0, 1280, 720], order_by: 'Score' },
                ab,
            )
            const status = await job.wait()
            let score = null
            let box = null
            if (status.succeeded) {
                const detail = job.get()
                const nodeId = detail?.nodes?.[0]
                const node = nodeId !== undefined ? tasker.node_detail(nodeId) : null
                const reco = node?.reco ?? null
                const best = reco?.detail && !Array.isArray(reco.detail) ? reco.detail.best : null
                score = best?.score ?? null
                box = best?.box ?? null
            }
            row.scores[t.name] = { score, box }
        }
        rows.push(row)
        if (process.env.DSH_VERBOSE) console.error(`scored ${row.image}`)
    }

    // 输出矩阵：行=截图，列=模板
    const names = templates.map((t) => t.name)
    const pad = Math.max(...names.map((n) => n.length), 10) + 1
    console.log('image'.padEnd(18) + names.map((n) => n.padStart(pad)).join(''))
    for (const r of rows) {
        const cells = names.map((n) => {
            const s = r.scores[n]?.score
            return (s === null || s === undefined ? '  -  ' : s.toFixed(3)).padStart(pad)
        })
        console.log(r.image.padEnd(18) + cells.join(''))
    }

    // 落 JSON 给 tools/analyze_scores.py 做按标签的假阳性统计
    writeFileSync(path.join(ROOT, 'scratch', 'scores.json'), JSON.stringify({ templates, rows }, null, 2))
    console.log('\n[写出] scratch/scores.json')

    tasker.destroy()
    res.destroy()
}

main().catch((e) => {
    console.error('[fatal]', e?.message ?? e)
    process.exit(1)
})
