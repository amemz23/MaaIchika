/**
 * 单点探针：拿一张截图 + 一份识别参数，问 MaaFramework「你到底看到了什么」。
 *
 * 用途：调 ColorMatch 的 count/HSV 区间、验证 OCR 能不能读出某段文字、
 * 确认 TemplateMatch 的分数和位置。比反复改 pipeline 再跑任务快得多。
 *
 * 三种模式：
 *   node tools/probe.mjs <图> tools/probe/xxx.json    # 手写参数
 *   node tools/probe.mjs --ocr <图> "[x,y,w,h]" "文字"
 *   node tools/probe.mjs --node 演出_结算 <图...>      # 直接取 pipeline 里节点的**真实**参数
 *
 * `--node` 是最可靠的一种：参数从资源包里 dump 出来，和真跑时一模一样，
 * 不用手抄（手抄的 probe json 很容易在 pipeline 改了之后变成过期的"假证据"）。
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
    } else if (argv[0] === '--node') {
        const nodeName = argv[1]
        const images = argv.slice(2).filter((a) => a.endsWith('.png'))
        if (images.length === 0) throw new Error('--node 后面要给至少一张截图')
        const dump = res.get_node_data_parsed(nodeName)
        if (!dump) throw new Error(`资源里没有节点 ${nodeName}`)
        const reco = dump.recognition ?? {}
        const type = reco.type ?? 'DirectHit'
        console.log(`[node] ${nodeName} recognition=${type} ${JSON.stringify(reco.param ?? {})}`)
        for (const image of images) {
            jobs.push({ label: `${nodeName} (${type})`, image, type, param: reco.param ?? {} })
        }
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
            // 注意：OCR / ColorMatch 的 status 成功**不等于**命中 —— 要看有没有被选中的结果
            `${job.label} @ ${path.basename(job.image)}: ${best ? 'HIT' : 'MISS'} ` +
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
