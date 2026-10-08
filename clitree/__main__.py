"""命令行入口：默认开 GUI；也提供规则与解析的自检子命令（便于迭代规则）。"""
from __future__ import annotations

import argparse
import json
import sys

from .core import discovery, lazy, parser, rules as rules_mod


def _dump_rules(args) -> int:
    rules = rules_mod.load_rules()
    print(json.dumps(rules, ensure_ascii=False, indent=2))
    return 0


def _check_rules(args) -> int:
    errs = rules_mod.check_rules(args.path)
    if errs:
        for e in errs:
            print("RULES-CHECK=FAIL", e)
        return 2
    print("RULES-CHECK=PASS path=%s" % (args.path or rules_mod.default_rules_path()))
    return 0


def _parse(args) -> int:
    rules = rules_mod.load_rules()
    if args.help_file:
        with open(args.help_file, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        res = parser.parse_help(text, rules, cmd=args.command or "")
        probe = None
    else:
        probe = discovery.probe(args.command, rules)
        if not probe.ok:
            print("PROBE=FAIL reason=%s" % probe.reason)
            return 1
        res = parser.parse_help(probe.raw_text, rules, cmd=args.command)
        print("PROBE=OK channel=%s rc=%s grade=%s" % (" ".join(probe.channel), probe.rc, probe.grade))
    print("DIALECT=%s GRADE=%s" % (res.dialect, res.grade))
    print("PARAMS=%d SUBCOMMANDS=%d" % (len(res.options), len(res.subcommands)))
    if not args.tree:
        for o in res.options:
            print("  %-28s %-9s %s" % (o.label, o.widget, (o.desc or "")[:60]))
        for s in res.subcommands:
            print("  %-28s %s" % (s.name, s.desc[:50]))
        return 0
    loader = lazy.TreeLoader(rules)
    root = loader.load_root(args.command)
    for node in root.walk():
        print("  " * (node.depth - 1) + f"{node.name}  [{node.load_state}]"
              + (f"  params={len(node.options)}" if node.options else ""))
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="clitree", description="CLI 参数树可视化执行器")
    ap.add_argument("command", nargs="?", help="要加载的 CLI 命令（不给则开 GUI）")
    ap.add_argument("--dump-rules", action="store_true", help="打印生效规则（默认＋用户覆盖）")
    ap.add_argument("--check-rules", action="store_true", help="校验规则文件")
    ap.add_argument("--path", help="要校验的规则文件（配合 --check-rules）")
    ap.add_argument("--parse", action="store_true", help="只解析并打印，不开 GUI")
    ap.add_argument("--help-file", help="直接解析一个 help 文本文件（配合 --parse）")
    ap.add_argument("--tree", action="store_true", help="连同树一起打印（会真去探测）")
    args = ap.parse_args(argv)

    if args.dump_rules:
        return _dump_rules(args)
    if args.check_rules:
        return _check_rules(args)
    if args.tree:
        args.parse = True
    if args.parse:
        if not args.command and not args.help_file:
            print("--parse 需要给命令或 --help-file")
            return 2
        return _parse(args)

    from .app import run_gui

    return run_gui(["clitree"] + ([args.command] if args.command else []))


if __name__ == "__main__":
    sys.exit(main())
