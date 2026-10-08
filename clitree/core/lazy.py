"""懒加载：点「加载」只出 2 层，子命令被点开时才探测（D3 / 计划 §5.2）。"""
from __future__ import annotations

from . import discovery
from .model import CommandNode
from .parser import parse_help


class TreeLoader:
    def __init__(self, rules: dict, probe_fn=None, max_depth: int | None = None, cmd_hint: str = ""):
        self.rules = rules
        self.probe_fn = probe_fn or (lambda exe, rules, node_path=(): discovery.probe(exe, rules, node_path))
        self.max_depth = int(max_depth if max_depth is not None
                             else (rules.get("subcommands") or {}).get("maxDepth", 3))
        self._cache: dict[tuple, tuple] = {}
        self._root: CommandNode | None = None
        self.executable = ""
        self.cmd_hint = cmd_hint
        self.probe_count = 0

    # ---------------------------------------------------------------- 内部
    def _probe(self, node_path: tuple):
        key = (self.executable, node_path)
        if key in self._cache:
            return self._cache[key]
        self.probe_count += 1
        res = self.probe_fn(self.executable, self.rules, node_path)
        self._cache[key] = res
        return res

    def _fill(self, node: CommandNode, res) -> None:
        if not res.ok:
            node.load_state = "failed"
            node.error = res.reason or "拿不到 help"
            node.raw_text = res.raw_text or ""
            return
        parsed = parse_help(res.raw_text, self.rules, cmd=self.cmd_hint or node.name)
        node.options = list(parsed.options) + list(parsed.positionals)
        node.dialect = parsed.dialect
        node.grade = parsed.grade
        node.raw_text = parsed.raw_text
        node.load_state = "loaded"
        node.error = None
        node.probe_meta = {"channel": list(res.channel or []), "rc": res.rc,
                           "grade": res.grade, "dialect": parsed.dialect,
                           "raw_text": res.raw_text or ""}
        node.subcommands = []
        for sub in parsed.subcommands:
            if node.depth + 1 <= self.max_depth:
                node.add_subcommand(sub.name, sub.desc)

    # ---------------------------------------------------------------- 对外
    def load_root(self, executable: str) -> CommandNode:
        self.executable = executable
        self.cmd_hint = executable.strip().split()[0] if executable.strip() else executable
        name = self.cmd_hint.rsplit("/", 1)[-1] or executable
        root = CommandNode(name=name, path=[name], desc="")
        self._root = root
        res = self._probe(())
        self._fill(root, res)
        root.load_state = "loaded" if res.ok else "failed"
        return root

    def expand(self, node: CommandNode, retry: bool = False) -> CommandNode:
        if node.depth >= self.max_depth:
            return node
        if node.load_state == "loaded" and not retry:
            return node
        if node.load_state == "failed" and not retry:
            return node
        node.load_state = "loading"
        res = self._probe(tuple(node.path[1:]))
        if not res.ok and retry:
            self._cache.pop((self.executable, tuple(node.path[1:])), None)
            self.probe_count += 1
            res = self.probe_fn(self.executable, self.rules, tuple(node.path[1:]))
            self._cache[(self.executable, tuple(node.path[1:]))] = res
        self._fill(node, res)
        return node

    def expand_all(self, node: CommandNode) -> int:
        """广度优先把子命令展开到上限（GUI 的「全量展开」用，可中断由调用方决定）。"""
        n = 0
        queue = list(node.subcommands)
        while queue:
            cur = queue.pop(0)
            if cur.depth >= self.max_depth:
                continue
            if cur.load_state == "pending":
                self.expand(cur)
                n += 1
            queue.extend(cur.subcommands)
        return n
