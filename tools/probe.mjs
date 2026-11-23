/**
 * 单点探针：拿一张截图 + 一份识别参数，问 MaaFramework「你到底看到了什么」。
 *
 * 用途：调 ColorMatch 的 count/HSV 区间、验证 OCR 能不能读出某段文字、
 * 确认 TemplateMatch 的分数和位置。比反复改 pipeline 再跑任务快得多。
 *
 * 用法：
 *   node tools/probe.mjs scratch/shots/s04.png tools/probe/loading_band.json
 *   node tools/probe.mjs --ocr scratch/shots/g01.png "[860,630,200,60]" "0件"
 */

import maaModule from '@maaxyz/maa-node'
import { readFileSync } from 'node:fs'
import path from 'node:path'

const maa = maaModule ?? globalThis.maa
const ROOT = process.cwd()

function readImage(p) {
    const buf = readFileSync(path.resolve(ROOT, p))
    return buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength)
}

async function main() {
    maa.Global.log_dir = path.join(ROOT, 'debug')
    maa.Global.stdout_level = 'Warn'

    const argv = process.argv.slice(2)
    const res = new maa.Resource()
    const loaded = await res.post_bundle(path.join(ROOT, 'assets', 'resource')).wait()
    if (!loaded.succeeded) throw new Error('资源加载失败')
    const tasker = new maa.Tasker()
    tasker.resource = res

    let jobs = []
    if (argv[0] === '--ocr') {
        const [, image, roi, expected] = argv
        jobs.push({
            label: `OCR ${expected}`,
            image,
            type: 'OCR',
            param: { expected: expected.split('|'), roi: JSON.parse(roi) },
        })
    } else {
        const spec = JSON.parse(readFileSync(path.resolve(ROOT, argv[1]), 'utf8'))
        const items = Array.isArray(spec) ? spec : [spec]
        for (const item of items) {
            for (const image of argv.slice(0)) {
                if (!image.endsWith('.png')) continue
            }
            jobs.push({ label: item.label ?? item.type, image: argv[0], type: item.type, param: item.param })
        }
    }

    for (const job of jobs) {
        const task = tasker.post_recognition(job.type, job.param, readImage(job.image))
        const status = await task.wait()
        const detail = task.get()
        const node = detail?.nodes?.length ? tasker.node_detail(String(detail.nodes[0])) : null
        const reco = node?.reco ?? null
        const obj = reco?.detail && !Array.isArray(reco.detail) ? reco.detail : null
        const best = obj?.best ?? null
        const box = Array.isArray(best?.box) ? best.box.join(',') : '-'
        console.log(
            `${job.label} @ ${path.basename(job.image)}: ${status.succeeded ? 'HIT' : 'MISS'} ` +
                `box=[${box}]` +
                (best?.count !== undefined ? ` count=${best.count}` : '') +
                (best?.score !== undefined ? ` score=${best.score.toFixed(3)}` : '') +
                (best?.text !== undefined ? ` text="${best.text}"` : '') +
                ` (全部结果 ${obj?.all?.length ?? 0} 个)`,
        )
        if (process.env.DSH_VERBOSE && obj?.all) {
            for (const r of obj.all.slice(0, 8)) {
                console.log(
                    `   - box=[${(r.box ?? []).join(',')}]` +
                        (r.count !== undefined ? ` count=${r.count}` : '') +
                        (r.score !== undefined ? ` score=${r.score.toFixed(3)}` : '') +
                        (r.text !== undefined ? ` text="${r.text}"` : ''),
                )
            }
        }
    }

    tasker.destroy()
    res.destroy()
}

main().catch((e) => {
    console.error('[fatal]', e?.message ?? e)
    process.exit(1)
})
