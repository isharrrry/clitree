"""help 通道探测：安全第一，且不看 rc 只看内容（计划 §5.3）。"""
from __future__ import annotations

import os
import pathlib
import re
import subprocess
import sys
from dataclasses import dataclass, field

from .executor import decode_line
from .parser import grade_of

NEVER_GUESS_DASH_H_FALLBACK = ["sort", "df", "du", "free", "ls", "watch", "ps", "top", "kill",
                               "pkill", "mount", "lsblk", "lscpu", "ip", "ss"]


@dataclass
class ProbeResult:
    ok: bool = False
    raw_text: str = ""
    channel: list[str] = field(default_factory=list)
    rc: int | None = None
    grade: str = "usage-only"
    dialect: str = "unknown"
    reason: str = ""
    man_page_seen: bool = False
    channels_tried: list[list[str]] = field(default_factory=list)


def _channels(rules: dict) -> list[list[str]]:
    return [list(c) for c in (rules.get("helpChannels") or {}).get("order")
            or [["--help"], ["-h"], ["/?"], ["-?"], ["help"], ["-help"]]]


def _deny(rules: dict) -> set:
    return set((rules.get("helpChannels") or {}).get("denyNeverProbe") or [])


def _never_guess(rules: dict) -> set:
    cfg = rules.get("helpChannels") or {}
    return set(cfg.get("dashHNeverGuess") or NEVER_GUESS_DASH_H_FALLBACK)


def _whitelist(rules: dict) -> set:
    return set((rules.get("helpChannels") or {}).get("dashHMeasuredWhitelist") or [])


def _interactive(rules: dict) -> dict:
    return (rules.get("helpChannels") or {}).get("interactiveChannels") or {}


def basename(cmd: str) -> str:
    head = (cmd or "").strip().split()[0] if (cmd or "").strip() else ""
    return pathlib.Path(head).name


def _argv_for(cmd: str, args: list[str]) -> list[str]:
    """命令可能是一个路径；.py 且没有执行位时用当前解释器跑。"""
    head = cmd.strip()
    p = pathlib.Path(head)
    if p.suffix == ".py" and p.is_file() and not os.access(p, os.X_OK):
        return [sys.executable, head, *args]
    return [head, *args]


def _default_runner(cmd: str, args: list[str], timeout: float):
    env = dict(os.environ)
    env.update({"PAGER": "cat", "MANPAGER": "cat", "GIT_PAGER": "cat", "SYSTEMD_PAGER": "cat"})
    try:
        proc = subprocess.run(_argv_for(cmd, args), capture_output=True,
                              timeout=timeout, stdin=subprocess.DEVNULL, env=env)
        out = _decode_output((proc.stdout or b"") + (proc.stderr or b""))
        return proc.returncode, out
    except subprocess.TimeoutExpired:
        return 124, ""
    except FileNotFoundError as exc:
        return 127, f"not found: {exc}"
    except Exception as exc:  # pragma: no cover - 兜底，绝不抛给 UI
        return 126, f"error: {exc}"


def _decode_output(raw: bytes) -> str:
    """整段输出解码：逐行试探编码（UTF-8 → GBK → 替换），再把 CRLF 折成 \\n。

    和 executor.decode_line 同一条实测依据：help 文本也可能是 UTF-8（新版工具）
    或 GBK（Windows 自带工具），不能固定取 locale 编码。
    """
    text = "\n".join(decode_line(line) for line in raw.split(b"\n"))
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _usable(text: str, rules: dict) -> bool:
    if not text or not text.strip():
        return False
    if grade_of(text, rules) in ("full", "weak"):
        return True
    # usage-only：只有一行用法也算拿到了东西
    return bool(re.search(r"(?i)(usage|用法|使用情况|options|选项)", text))


def _declares_dash_h(text: str, rules: dict) -> bool:
    pat = (rules.get("helpChannels") or {}).get("dashHDeclarationPattern")
    if not pat:
        pat = r"(?i)(^|\s)-h\b[^\n]{0,40}\bhelp\b|--help[^\n]{0,40}\s+-h\b"
    try:
        return bool(re.search(pat, text, re.M))
    except re.error:
        return False


def _is_man(text: str, rules: dict) -> bool:
    first = (text.splitlines() or [""])[0].strip()
    for p in (rules.get("manPage") or {}).get("detect") or []:
        try:
            if re.match(p, first):
                return True
        except re.error:
            continue
    return False


def probe(cmd: str, rules: dict, node_path: tuple = (), runner=None, timeout: float | None = None):
    """探测一个 CLI（或它的子命令）的帮助。返回 ProbeResult；永不抛异常。"""
    cfg = rules.get("helpChannels") or {}
    timeout = float(timeout if timeout is not None else cfg.get("timeoutMs", 5000) / 1000.0)
    max_bytes = int(cfg.get("maxOutputBytes", 262144))
    run = runner or _default_runner
    name = basename(cmd)
    path = list(node_path)

    if name in _deny(rules):
        return ProbeResult(ok=False, reason=f"安全策略：{name} 属于危险命令，任何通道都不探测",
                           channel=[])

    first_text, man_seen = "", False
    calls: list[list[str]] = []
    interactive = _interactive(rules).get(name)
    if interactive and not path:
        plan = [list(x) for x in interactive]
    else:
        # 子命令路径必须在选项**之前**：`git clone --help` 对，
        # `git -h clone` 会把父命令的帮助当成子命令的（实测踩过）
        plan = [list(path) + list(args) for args in _channels(rules)]

    for args in plan:
        if args and args[-1] == "-h" and not path:
            allowed = (man_seen or _declares_dash_h(first_text, rules) or name in _whitelist(rules)
                       or (not first_text.strip() and name not in _never_guess(rules)))
            if not allowed:
                continue
        calls.append(args)
        rc, text = run(cmd, args, timeout)
        text = text[:max_bytes]
        if text and not first_text:
            first_text = text
        if _is_man(text, rules):
            man_seen = True
            continue
        if _usable(text, rules):
            from .parser import parse_help

            parsed = parse_help(text, rules, cmd=name)
            return ProbeResult(ok=True, raw_text=text, channel=args, rc=rc,
                               grade=parsed.grade, dialect=parsed.dialect, reason="ok",
                               man_page_seen=man_seen, channels_tried=list(calls))

    return ProbeResult(ok=False, raw_text=first_text, channel=calls[-1] if calls else [],
                       rc=None, grade=grade_of(first_text, rules) or "usage-only",
                       dialect="", reason="所有 help 通道都没有给出可用内容",
                       man_page_seen=man_seen, channels_tried=list(calls))
