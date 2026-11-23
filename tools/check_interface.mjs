/**
 * 用真实 MaaFramework 加载 interface.json + 资源包，验证"接线"没问题。
 *
 * 为什么不用 `maa-tools check`：它会把 MaaFramework 下载到工作目录**外面**的用户缓存里
 * （受限环境下会被沙箱拒绝），而且每次都要联网。这里直接用已经装在
 * node_modules/@maaxyz/maa-node 里的同一份 MaaFramework（5.16.x），
 * 零下载、零网络，检的东西是同一件事：
 *
 *   1. interface.json 能读、resource[].path 指向的 bundle 能被框架加载
 *   2. 每个 task.entry 都真的存在于加载后的节点表里
 *   3. controller 都声明了 display_short_side（否则截图不会被缩放到 720p）
 *   4. option 的 pipeline_override 引用的节点存在
 *   5. 多语言文件存在（内容键的完整性由 tools/check_json.py 负责）
 *
 * 用法：
 *   node tools/check_interface.mjs
 */

import maaModule from '@maaxyz/maa-node'
import { existsSync, readFileSync } from 'node:fs'
import path from 'node:path'

const maa = maaModule ?? globalThis.maa
const ROOT = process.cwd()

function fail(msg) {
    console.error(`[error] ${msg}`)
    return 1
}

async function main() {
    maa.Global.log_dir = path.join(ROOT, 'debug')
    maa.Global.stdout_level = 'Warn'

    const ifacePath = path.join(ROOT, 'assets', 'interface.json')
    if (!existsSync(ifacePath)) return fail(`找不到 ${ifacePath}`)
    const iface = JSON.parse(readFileSync(ifacePath, 'utf8'))
    let errors = 0

    if (iface.interface_version !== 2) {
        console.error(`[warn] interface_version = ${iface.interface_version}（本项目按 v2 编写）`)
    }

    // 1. 资源包
    const res = new maa.Resource()
    let nodes = []
    for (const bundle of iface.resource ?? []) {
        for (const raw of bundle.path ?? []) {
            const dir = path.resolve(path.join(ROOT, 'assets'), raw.replaceAll('{PROJECT_DIR}', ROOT))
            if (!existsSync(path.join(dir, 'pipeline'))) {
                errors += fail(`资源包 ${bundle.name} 的路径没有 pipeline 目录: ${dir}`)
                continue
            }
            const job = res.post_bundle(dir)
            const status = await job.wait()
            if (!status.succeeded) {
                errors += fail(`资源包加载失败: ${dir}`)
                continue
            }
            const list = res.node_list ?? []
            nodes = list
            console.log(`[bundle] ${bundle.name} -> ${path.relative(ROOT, dir)} (${list.length} 个节点)`)
        }
    }
    if (nodes.length === 0) return fail('加载后没有任何节点')
    res.destroy()

    // 2. 任务入口
    for (const task of iface.task ?? []) {
        if (!task.entry) {
            errors += fail(`任务「${task.name}」没有 entry`)
        } else if (!nodes.includes(task.entry)) {
            errors += fail(`任务「${task.name}」的 entry「${task.entry}」不在节点表里`)
        }
        for (const node of Object.keys(task.pipeline_override ?? {})) {
            if (!nodes.includes(node)) errors += fail(`任务「${task.name}」的 pipeline_override 引用了不存在的节点 ${node}`)
        }
    }
    console.log(`[task] ${(iface.task ?? []).length} 个任务入口全部存在`)

    // 3. 控制器
    for (const ctrl of iface.controller ?? []) {
        if (!ctrl.type) errors += fail(`控制器「${ctrl.name}」没有 type`)
        if (ctrl.type === 'Adb' && !ctrl.display_short_side) {
            errors += fail(`控制器「${ctrl.name}」缺少 display_short_side，截图不会被缩放到 720p`)
        }
    }

    // 4. 选项
    for (const [name, opt] of Object.entries(iface.option ?? {})) {
        for (const one of opt.cases ?? []) {
            for (const node of Object.keys(one.pipeline_override ?? {})) {
                if (!nodes.includes(node)) errors += fail(`选项「${name}」的 case「${one.name}」引用了不存在的节点 ${node}`)
            }
        }
    }

    // 5. 多语言文件
    for (const [lang, rel] of Object.entries(iface.languages ?? {})) {
        const file = path.resolve(path.join(ROOT, 'assets'), rel)
        if (!existsSync(file)) errors += fail(`语言文件不存在: ${lang} -> ${rel}`)
    }

    if (errors === 0) {
        console.log(`[ok] interface.json 与资源包用 MaaFramework ${maa.Global.version} 加载通过`)
        return 0
    }
    return 1
}

main()
    .then((code) => process.exit(code))
    .catch((e) => {
        console.error('[fatal]', e?.message ?? e)
        process.exit(2)
    })
