"""三平台「开新终端」适配。argv 直传，绝不拼 shell 字符串给本进程执行。"""
from __future__ import annotations

import os
import shlex
import shutil
import sys

LINUX_TERMINALS = [
    ("gnome-terminal", lambda cmd: ["gnome-terminal", "--", "bash", "-lc", cmd]),
    ("xfce4-terminal", lambda cmd: ["xfce4-terminal", "-x", "bash", "-lc", cmd]),
    ("konsole", lambda cmd: ["konsole", "-e", "bash", "-lc", cmd]),
    ("x-terminal-emulator", lambda cmd: ["x-terminal-emulator", "-e", "bash", "-lc", cmd]),
    ("xterm", lambda cmd: ["xterm", "-e", "bash", "-lc", cmd]),
]


def posix_command_line(argv: list[str]) -> str:
    return shlex.join(list(argv))


def windows_command_line(argv: list[str]) -> str:
    def q(a: str) -> str:
        if a == "" or any(c in a for c in ' \t"'):
            return '"' + a.replace('"', r"\"") + '"'
        return a

    return " ".join(q(a) for a in argv)


def build_terminal_argv(argv: list[str], platform: str | None = None) -> list[str] | None:
    plat = platform or sys.platform
    if plat.startswith("win"):
        line = windows_command_line(argv)
        if shutil.which("wt.exe") or shutil.which("wt"):
            return ["wt.exe", "cmd", "/k", line]
        return ["cmd", "/c", "start", "", "cmd", "/k", line]
    if plat == "darwin":
        line = posix_command_line(argv).replace("\\", "\\\\").replace('"', '\\"')
        script = f'tell application "Terminal" to do script "{line}"\nactivate'
        return ["osascript", "-e", script]
    line = posix_command_line(argv)
    for name, build in LINUX_TERMINALS:
        if shutil.which(name):
            return build(line)
    if os.environ.get("CLITREE_TERMINAL_OVERRIDE"):
        return [os.environ["CLITREE_TERMINAL_OVERRIDE"], "-e", "bash", "-lc", line]
    return None
