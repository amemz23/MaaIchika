#!/usr/bin/env python3
"""真机踩坑导向的审计（`check_json` / `check_params` 之外的那一层）。

`check_json` 管引用与结构，`check_params` 管数字合法性。这个脚本管**"能加载、能跑，但真机会失败"**
的那一类，规则全部来自本项目实际踩过的坑：

1. `max_hit` 太小 —— 每个节点默认只能命中 max_hit 次，之后会被框架**移出候选列表**。
   实测：剧情里 `勾连读`/`选语音` 各写 2，读到第 3 集就从候选里消失，链路卡在语音弹窗。
   → 被 ≥2 个父节点引用、或出现在"每轮循环都要用"的位置，max_hit <= 3 就报。

2. `[JumpBack]` 的目标没写 max_hit —— 回跳型节点没有上限就是死循环（AGENTS 第 3 条）。

3. 候选列表可能全 miss 且没有 on_error —— 这条链在这里**静默结束**，任务被判失败。
   （例：`演出_自动设置决定` 只有 [等待加载, 自己, 确认AUTO]，三者都没命中就断。）

4. `next` 为空、又不是验证型终止节点 —— 链尾落在谁身上都行，但不能是"随手写的空"。

5. 识别 ROI 覆盖了已知的对话/旁白文字带（y 460-660 中部），且用单字/短词做 expected ——
   剧情画面里误命中的高发组合（实测 `第` 在旁白上误命中，导致误判成集末）。

用法：python tools/audit.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "assets" / "resource" / "pipeline"
TERMINALS = {"公共_主页锚点", "公共_失败"}
# `tools/run.mjs` 也把「完成_*」当验证型终止节点（用于不落在主页上的收尾，比如恢复分辨率），审计口径保持一致
TERMINAL_PREFIXES = ("完成_",)
# 每轮循环都会重复使用的"工具型"节点：max_hit 必须够大
LOOPY_HINTS = ("勾连读", "选语音", "选未读", "点一下", "关公告", "等待加载", "回主页", "通信错误", "盲点推进")


def strip_attr(name):
    return name.replace("[JumpBack]", "").replace("[Anchor]", "").strip()


def main():
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8")

    nodes = {}  # name -> (file, body)
    for file in sorted(PIPE.glob("*.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        for name, body in data.items():
            if isinstance(body, dict) and not name.startswith("$"):
                nodes[name] = (file, body)

    parents = {}
    for name, (_, body) in nodes.items():
        for field in ("next", "on_error"):
            for ref in body.get(field) or []:
                if isinstance(ref, str):
                    parents.setdefault(strip_attr(ref), set()).add(name)

    problems = []

    for name, (file, body) in nodes.items():
        hit = body.get("max_hit")
        nxt = [strip_attr(x) for x in (body.get("next") or []) if isinstance(x, str)]
        errs = [strip_attr(x) for x in (body.get("on_error") or []) if isinstance(x, str)]
        where = f"{file.name}:{name}"

        # 1. max_hit 太小
        if hit is not None and hit <= 3:
            used_by = len(parents.get(name, ()))
            loopy = any(h in name for h in LOOPY_HINTS)
            if used_by >= 2 or loopy:
                problems.append(
                    f"[max_hit 偏小] {where}: max_hit={hit}，被 {used_by} 个父节点引用"
                    f"{'（工具型节点）' if loopy else ''} —— 用完会被移出候选列表，长流程会卡住"
                )

        # 2. JumpBack 目标没有 max_hit（在父节点视角检查）
        for field in ("next", "on_error"):
            for ref in body.get(field) or []:
                if isinstance(ref, str) and ref.startswith("[JumpBack]"):
                    target = strip_attr(ref)
                    tbody = nodes.get(target, (None, {}))[1]
                    if tbody.get("max_hit") is None:
                        problems.append(f"[回跳无上限] {where}.{field}: [JumpBack]{target} 没有 max_hit")

        # 2b. 引用「next 为空的处理器」却没写 [JumpBack] —— 这会直接把整条链掐断。
        #     这一条是本项目踩过三次的坑（演出_阶段面板 / 公共_点一下 / 公共_点一下排序），
        #     对应 MaaEnd 的原则：辅助节点一律 [JumpBack]，例外（验证型终止节点）必须显式豁免。
        for field in ("next", "on_error"):
            for ref in body.get(field) or []:
                if not isinstance(ref, str) or ref.startswith("[JumpBack]") or ref.startswith("[Anchor]"):
                    continue
                target = strip_attr(ref)
                if target not in nodes:
                    continue
                if target in TERMINALS or target.startswith(TERMINAL_PREFIXES):
                    continue  # 终止节点本来就必须普通引用
                if not (nodes[target][1].get("next") or []):
                    problems.append(
                        f"[漏写 JumpBack] {where}.{field}: {ref} 的 next 为空（它是个处理器），"
                        f"普通引用会让整条链在这里结束；应该写成 [JumpBack]{target}"
                    )

        # 3. 候选全 miss 且无 on_error
        if nxt and not errs:
            reco_types = {
                strip_attr(x): (nodes.get(strip_attr(x), (None, {}))[1].get("recognition") or {})
                for x in (body.get("next") or [])
                if isinstance(x, str)
            }
            all_soft = all(
                ((r.get("type") if isinstance(r, dict) else None) or "DirectHit") != "DirectHit"
                for r in reco_types.values()
            ) and not (set(nxt) & TERMINALS)
            flow_critical = name.startswith(("任务_", "故事_"))
            # 只要被任何父节点用 [JumpBack] 引用过，它就是「处理器」：做完会回父节点，不会让链静默结束
            # （它自己的 next 里常带自重试，所以不能要求"全部引用都是 JumpBack"）
            only_jumpback = any(
                r.startswith("[JumpBack]")
                for pbody in (nodes[p][1] for p in parents.get(name, ()))
                for field in ("next", "on_error")
                for r in (pbody.get(field) or [])
                if isinstance(r, str) and strip_attr(r) == name
            )
            if all_soft and flow_critical and len(nxt) <= 3 and not only_jumpback:
                problems.append(
                    f"[可能断链] {where}: next 只有 {len(nxt)} 个候选且都没有兜底（全 miss 时链会静默结束、没有 on_error）"
                )

        # 4. next 为空但不是验证型终止节点（[JumpBack] 辅助节点本来就该 next 为空，跳过）
        is_jumpback_helper = any(
            isinstance(r, str) and r.startswith("[JumpBack]") and strip_attr(r) == name
            for body2 in nodes.values()
            for f in ("next", "on_error")
            for r in (body2[1].get(f) or [])
        )
        if not nxt and name not in TERMINALS and not name.startswith(TERMINAL_PREFIXES) and not is_jumpback_helper:
            action = (body.get("action") or {}).get("type")
            if action not in ("StopTask",):
                problems.append(f"[空 next] {where}: next 为空且不是验证型终止节点（{action}）")

        # 5. （已移除）"短词 OCR + ROI 覆盖对白带"这条没法通用判断：
        #    按钮文字确实会落在 y 640-720，而剧情对白在 y 480-660，两者必然相邻。
        #    真正的做法是**按界面实测**（见开发手册 6.9「短词 OCR 的 ROI 要避开对白带」）。

    for p in problems:
        print(p)
    print(f"\n共 {len(problems)} 条；检查了 {len(nodes)} 个节点")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
