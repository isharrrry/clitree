#!/usr/bin/env python3
"""生成「库根相对路径 ＋ 层级字母编号」的依赖关系树（ASCII）。

编号规则：每一层用字母表示它在**同一父节点下**的序号（A=第 1 个、B=第 2 个…），
把各层字母连起来写进方括号，例如 [BACD] = 一层第 2 个 → 二层第 1 个 → 三层第 3 个 → 四层第 4 个。
同一个文件第二次出现时不再展开，改写为「↩ 见 [编号]」。

用法：
    python3 tools/deps_tree.py                 # 默认库根 = 本文件的上上层
    python3 tools/deps_tree.py --root <目录>
    python3 tools/deps_tree.py --out docs/DEPENDENCY-TREE.md
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import re
import sys

STDLIB = set(getattr(sys, "stdlib_module_names", set()))
THIRD_PARTY = {"PyQt5", "PySide6", "pytest"}

ENTRY_NOTES = {
    "pyproject.toml": "打包／入口声明（console_scripts）",
    "clitree/__main__.py": "python -m clitree（命令行入口）",
    "tools/make_screenshots.py": "独立脚本（生成界面截图）",
    "tools/deps_tree.py": "独立脚本（生成本文件）",
    "tests/fixtures/fakecli.py": "假 CLI（测试以子进程执行的入口）",
    "tests/conftest.py": "pytest 夹具与路径注入",
}

DATA_SUFFIXES = (".json", ".txt", ".toml", ".png", ".py")
# 只认「路径拼接」上下文里的目录/文件名，避免把普通单词（如 help 通道名）当成依赖

class Node:
    def __init__(self, path: str, note: str = "", kind: str = "py"):
        self.path = path
        self.note = note
        self.kind = kind


def letter(i: int) -> str:
    s, i = "", i + 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(ord("A") + r) + s
    return s


def module_index(root: pathlib.Path) -> dict:
    idx = {}
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts or ".pytest_cache" in p.parts:
            continue
        parts = list(p.relative_to(root).parts)
        mod = ".".join(parts[:-1]) if p.name == "__init__.py" else ".".join(parts[:-1] + [p.stem])
        if mod:
            idx[mod] = p.relative_to(root).as_posix()
    return idx


def imports_of(path: pathlib.Path, pkg_of_file: str) -> set:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return set()
    out: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            mod = base
            if node.level:
                parts = pkg_of_file.split(".") if pkg_of_file else []
                if path.name != "__init__.py":
                    parts = parts[:-1]
                up = node.level - 1
                if up:
                    parts = parts[:-up] if up <= len(parts) else []
                mod = ".".join([p for p in parts if p] + ([base] if base else []))
            for a in node.names:
                if mod:
                    out.add(f"{mod}.{a.name}")
            if mod:
                out.add(mod)      # `from x.y import Z` 里 Z 往往不是模块名，base 本身才是依赖
    return out


def _in_path_context(text: str, start: int, name: str) -> bool:
    """只把「路径拼接／打开文件」上下文里的字面量当成依赖，避免字典键之类的误报。"""
    head = text[max(0, start - 14):start].rstrip("\"'")
    tail = text[start + len(name):start + len(name) + 8].lstrip(" \"'")
    return bool(re.search(r"(/\s*|Path\(|open\()\s*$", head)) or tail.startswith("/")


def data_deps(path: pathlib.Path, root: pathlib.Path, known_modules: set) -> list:
    text = path.read_text(encoding="utf-8", errors="replace")
    found: dict = {}
    for m in re.finditer(r"""["']([\w./-]+\.(?:json|txt|toml|png|py))["']""", text):
        name = m.group(1)
        if name.endswith(".py") and name in known_modules:
            continue
        if not _in_path_context(text, m.start() + 1, name):
            continue
        for cand in (path.parent / name, root / name):
            if cand.is_file():
                rel = cand.relative_to(root).as_posix()
                found[rel] = Node(rel, "数据文件", kind="data")
                break
    for m in re.finditer(r"""["']([A-Za-z_][\w.-]*)["']""", text):
        name = m.group(1)
        if not _in_path_context(text, m.start() + 1, name):
            continue
        if name == root.name:          # 库根自己不是它的依赖
            continue
        cands = [d for d in root.rglob(name) if d.is_dir() and "__pycache__" not in d.parts]
        for cand in cands:
            rel = cand.relative_to(root).as_posix() + "/"
            if path.parent != root and root not in cand.parents and cand.parent != root:
                continue
            found[rel] = Node(rel, f"数据目录（{len(list(cand.iterdir()))} 项）", kind="dir")
    return [found[k] for k in sorted(found)]


def pyproject_children(root: pathlib.Path, idx: dict) -> list:
    p = root / "pyproject.toml"
    if not p.is_file():
        return []
    text = p.read_text(encoding="utf-8", errors="replace")
    out = {}
    for m in re.finditer(r"""(?m)^\s*[\w.-]+\s*=\s*["']([\w.]+):(\w+)["']""", text):
        mod = m.group(1)
        if mod in idx:
            out[idx[mod]] = Node(idx[mod], f"入口点 → {mod}:{m.group(2)}")
    return [out[k] for k in sorted(out)]


def build(root: pathlib.Path):
    idx = module_index(root)
    by_path = {v: k for k, v in idx.items()}
    known_modules = set(idx.values())

    entries = [Node(rel, note) for rel, note in ENTRY_NOTES.items() if (root / rel).is_file()]
    for p in sorted((root / "tests").glob("test_*.py")):
        entries.append(Node(p.relative_to(root).as_posix(), "测试入口（pytest 收集）"))
    if not entries:
        entries = [Node("pyproject.toml", "入口")]

    lines: list[str] = []
    seen: dict = {}
    width = {"n": 10}

    def children_of(node: Node) -> list:
        if node.kind != "py":
            return []
        p = root / node.path
        kids = []
        if node.path == "pyproject.toml":
            kids += pyproject_children(root, idx)
        else:
            pkg = by_path.get(node.path, "")
            for m in sorted(imports_of(p, pkg)):
                head = m.split(".")[0]
                if head in THIRD_PARTY or head in STDLIB:
                    continue
                target = idx.get(m)
                if target is None or target == node.path or target.endswith("__init__.py"):
                    continue
                kids.append(Node(target))
            kids += data_deps(p, root, known_modules)
        dedup: dict = {}
        for k in kids:
            if k.path != node.path:
                dedup.setdefault(k.path, k)
        return [dedup[k] for k in sorted(dedup)]

    def walk(node: Node, code: str, depth: int) -> None:
        pad = "    " * depth
        if node.path in seen:
            lines.append(f"{pad}[{code}] {node.path}   ↩ 见 [{seen[node.path]}]")
            return
        seen[node.path] = code
        width["n"] = max(width["n"], len(code) + 2)
        suffix = f"   ← {node.note}" if node.note else ""
        lines.append(f"{pad}[{code}] {node.path}{suffix}")
        for i, child in enumerate(children_of(node)):
            walk(child, code + letter(i), depth + 1)

    for i, e in enumerate(entries):
        walk(e, letter(i), 0)

    # 对齐：把编号列补到等宽
    fixed = []
    for ln in lines:
        m = re.match(r"^(\s*)\[([A-Z]+)\] (.*)$", ln)
        fixed.append(f"{m.group(1)}[{m.group(2)}]{' ' * (width['n'] - len(m.group(2)))}{m.group(3)}"
                     if m else ln)
    return fixed, len(entries)


def main() -> int:
    ap = argparse.ArgumentParser(description="依赖关系树（层级字母编号）")
    ap.add_argument("--root", default=str(pathlib.Path(__file__).resolve().parents[1]))
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    root = pathlib.Path(args.root).resolve()
    lines, n_entries = build(root)
    header = [
        f"库根：{root}",
        f"第一层（入口）：{n_entries} 个　　树行数：{len(lines)}",
        "编号＝每层在同一父节点下的序号字母（A=第 1 个）连写，如 [BACD]；同一文件第二次出现只给引用",
        "",
    ]
    text = "\n".join(header + lines)
    print(text)
    if args.out:
        p = root / args.out
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("```\n" + text + "\n```\n", encoding="utf-8")
        print(f"（已写入 {p}）", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
