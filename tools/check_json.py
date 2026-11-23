#!/usr/bin/env python3
"""仓库自检：JSON 合法性 + Pipeline 引用完整性 + 多语言键 + 结构规范。

比"能解析"更严一层，这里还查四类容易悄悄坏掉的东西：

1. next / on_error 指向不存在的节点（Maa 只打 warning，运行起来就是静默结束）
2. 占位节点：DirectHit + DoNothing + 无 next —— 这种节点永远不会失败，也永远不会做事
3. 循环无出口：顺着 next 走，如果一条链路既没有终止节点也没有 max_hit 兜底，标出来
4. 多语言键缺失 / 两边键集合不一致

用法：
    python tools/check_json.py            # 全量检查
    python tools/check_json.py --quiet    # 只打印问题
退出码：0 通过；1 有问题（CI 直接用它卡 PR）。
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INTERFACE = ROOT / "assets" / "interface.json"
SKIP_DIRS = {".git", "node_modules", "install", "debug", "dist", "scratch", ".venv", "__pycache__"}
REF_FIELDS = ("next", "on_error")
ATTR_PREFIXES = ("[JumpBack]", "[Anchor]")


def iter_json_files():
    files = []
    for path in ROOT.rglob("*.json"):
        if any(part in SKIP_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return sorted(files)


def load_json(path, errors):
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        errors.append(f"{path.relative_to(ROOT)}: JSON 解析失败 (行 {exc.lineno} 列 {exc.colno}): {exc.msg}")
        return None


def strip_attr(name):
    out = name
    for prefix in ATTR_PREFIXES:
        out = out.replace(prefix, "")
    return out


def collect_nodes(interface, errors):
    """按 interface.json 的 resource[].path 收集节点名 -> (文件, 节点体)。"""
    base = INTERFACE.parent
    nodes = {}
    for res in interface.get("resource", []):
        for raw in res.get("path", []):
            bundle = (base / raw.replace("{PROJECT_DIR}", str(ROOT))).resolve()
            pipeline_dir = bundle / "pipeline"
            if not pipeline_dir.is_dir():
                errors.append(f"资源包缺少 pipeline 目录: {bundle}")
                continue
            for file in sorted(pipeline_dir.glob("*.json")):
                data = load_json(file, errors)
                if not isinstance(data, dict):
                    continue
                for name, body in data.items():
                    if not isinstance(body, dict):
                        continue
                    if name.startswith("$"):
                        continue  # MPE 编辑器写的布局元数据，Maa 会忽略
                    if name in nodes:
                        errors.append(f"节点重名: {name} 同时定义在 {nodes[name][0].name} 与 {file.name}")
                    nodes[name] = (file, body)
    return nodes


def check_interface(interface, nodes, errors):
    for task in interface.get("task", []):
        name = task.get("name", "<未命名任务>")
        entry = task.get("entry")
        if entry and entry not in nodes:
            errors.append(f"任务「{name}」的 entry 节点不存在: {entry}")
        for node in task.get("pipeline_override") or {}:
            if node not in nodes:
                errors.append(f"任务「{name}」的 pipeline_override 引用了不存在的节点: {node}")
    for opt_name, opt in (interface.get("option") or {}).items():
        for case in opt.get("cases", []):
            for node in case.get("pipeline_override") or {}:
                if node not in nodes:
                    errors.append(f"选项「{opt_name}」的 case「{case.get('name')}」引用了不存在的节点: {node}")
    for ctrl in interface.get("controller", []):
        if ctrl.get("type") == "Adb" and not ctrl.get("display_short_side"):
            errors.append(f"控制器「{ctrl.get('name')}」没有 display_short_side，截图不会被缩放到 720p")


def refs_of(body):
    out = []
    for field in REF_FIELDS:
        value = body.get(field) or []
        if isinstance(value, (str, dict)):
            value = [value]
        for target in value:
            if isinstance(target, dict):
                target = target.get("name", "")
            if target:
                out.append((field, target))
    return out


def check_refs(nodes, errors, warnings):
    for name, (file, body) in nodes.items():
        for field, target in refs_of(body):
            plain = strip_attr(target)
            if plain and plain not in nodes:
                errors.append(f"{file.name}: 节点 {name} 的 {field} 指向不存在的节点 {target}")


def check_placeholders(nodes, errors):
    """DirectHit + DoNothing + 无 next 的节点是纯占位：它永远命中、永远不做事。"""
    for name, (file, body) in nodes.items():
        reco = body.get("recognition")
        reco_type = (reco.get("type") if isinstance(reco, dict) else reco) or "DirectHit"
        action = body.get("action")
        act_type = (action.get("type") if isinstance(action, dict) else action) or "DoNothing"
        has_next = bool(body.get("next"))
        has_desc = bool(body.get("desc"))
        if reco_type == "DirectHit" and act_type == "DoNothing" and not has_next and not has_desc:
            errors.append(f"{file.name}: 节点 {name} 是 DirectHit+DoNothing+无 next 的占位，要么补识别，要么补 desc 说明为什么这样")


def check_loops(nodes, errors, warnings):
    """找"能绕回自己且没有任何 max_hit 兜底"的环。"""
    def successors(name):
        body = nodes[name][1]
        out = []
        for _, target in refs_of(body):
            plain = strip_attr(target)
            if plain in nodes:
                out.append(plain)
        return out

    for start in nodes:
        seen = {}
        stack = [(start, [start])]
        while stack:
            cur, path = stack.pop()
            for nxt in successors(cur):
                if nxt == start and len(path) >= 2:
                    cycle = path + [start]
                    guarded = any(nodes[n][1].get("max_hit") for n in set(cycle))
                    if not guarded:
                        warnings.append(f"环没有 max_hit 兜底: {' -> '.join(cycle)}")
                    continue
                if nxt in seen or len(path) > 12:
                    continue
                seen[nxt] = True
                stack.append((nxt, path + [nxt]))


def collect_i18n_keys(interface):
    keys = set()

    def walk(value):
        if isinstance(value, str) and value.startswith("$"):
            keys.add(value[1:])
        elif isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)

    walk(interface)
    return keys


def resolve_key(data, dotted):
    if dotted in data:
        return data[dotted]
    cur = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def check_locales(interface, errors):
    keys = collect_i18n_keys(interface)
    base = INTERFACE.parent
    per_lang = {}
    for lang, rel in (interface.get("languages") or {}).items():
        path = base / rel
        if not path.is_file():
            errors.append(f"语言文件不存在: {lang} -> {rel}")
            continue
        data = load_json(path, errors) or {}
        missing = []
        for dotted in keys:
            if resolve_key(data, dotted) is None:
                missing.append(dotted)
        for key in missing:
            errors.append(f"{rel}: 缺少 i18n 键 {key}")
        per_lang[lang] = set(data.keys())
    if len(per_lang) >= 2:
        langs = list(per_lang)
        all_keys = set().union(*per_lang.values())
        for lang in langs:
            extra = all_keys - per_lang[lang]
            if extra:
                warnings = "、".join(sorted(extra)[:5])
                errors.append(f"{lang} 缺少其他语言里有的键: {warnings}")
    return len(per_lang)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8")

    errors, warnings = [], []
    files = iter_json_files()
    parsed = {}
    for file in files:
        data = load_json(file, errors)
        if data is not None:
            parsed[file] = data

    nodes, languages = {}, 0
    if INTERFACE in parsed:
        interface = parsed[INTERFACE]
        nodes = collect_nodes(interface, errors)
        check_interface(interface, nodes, errors)
        check_refs(nodes, errors, warnings)
        check_placeholders(nodes, errors)
        check_loops(nodes, errors, warnings)
        languages = check_locales(interface, errors)
    else:
        errors.append(f"未找到 {INTERFACE.relative_to(ROOT)}")

    for w in warnings:
        print(f"[warn] {w}", file=sys.stderr)
    for e in errors:
        print(f"[error] {e}", file=sys.stderr)
    if not args.quiet:
        print(f"检查 {len(files)} 个 JSON，{len(nodes)} 个节点，{languages} 种语言，{len(errors)} 错误，{len(warnings)} 警告")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
