"""执行器：argv 直传（绝不经 shell）＋ 三模式（后台 / 静默 / 新终端）。"""
from __future__ import annotations

import subprocess
import threading
import time
from dataclasses import dataclass, field

from . import terminals

FALSEY = {"0", "false", "off", "no", "none", ""}

# 表单最末尾「其他输入」在 values 里的键：内容按空白拆开、追加到命令末尾
EXTRA_KEY = "@extra"


def decode_line(raw: bytes) -> str:
    """子进程输出逐行解码：先 UTF-8，再 GBK，最后替换兜底（绝不抛异常）。

    实测：`narnat` 输出 UTF-8（0xe4 0xbd 0xa0 = 你），而 Windows 的 ping 中文帮助是
    GBK —— 固定任一种都会炸（曾报 "gbk codec can't decode byte 0x80"）。
    按 \\n 切行不会切坏多字节字符：两种编码的多字节序列都不含 0x0A。
    """
    for enc in ("utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


@dataclass
class RunResult:
    argv: list[str] = field(default_factory=list)
    rc: int | None = None
    state: str = "ok"
    elapsed_ms: int = 0
    note: str = ""


@dataclass
class RunHandle:
    argv: list[str] = field(default_factory=list)
    state: str = "running"
    rc: int | None = None
    result: RunResult | None = None
    proc: object | None = field(default=None, repr=False)
    event: threading.Event | None = field(default=None, repr=False)
    stopped: bool = False

    def stop(self) -> None:
        """终止这个运行（再次点击正在运行的那个按钮时调用）。已结束则什么也不做。"""
        self.stopped = True
        p = self.proc
        if p is None:
            return
        try:
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=3)
                except Exception:
                    p.kill()
        except Exception:
            pass

    def wait(self, timeout: float | None = None):
        if self.event is not None:
            self.event.wait(timeout)
        elif self.proc is not None:
            try:
                self.proc.wait(timeout=timeout)
            except Exception:
                pass
        return self.result


def build_argv(exe: str, node, values: dict) -> list[str]:
    """把表单值变成 argv 列表。**绝不拼接 shell 字符串。**

    「其他输入」（EXTRA_KEY）按空白拆开后追加到 argv 最后。
    """
    argv = [exe]
    values = values or {}

    for spec in node.options:
        if spec.position is not None or not spec.names:
            continue
        val = None
        for key in spec.value_keys():
            if key in values:
                val = values[key]
                break
        if val is None:
            continue
        if not spec.takes_value:
            if val is True:
                argv.append(spec.key)
            elif isinstance(val, str) and val.strip().lower() not in FALSEY:
                argv.append(spec.key)
            continue
        items = val if isinstance(val, (list, tuple)) else [val]
        for item in items:
            if item is None or (isinstance(item, str) and not item.strip()):
                continue
            argv.extend([spec.key, str(item)])

    for spec in sorted([o for o in node.options if o.position is not None], key=lambda o: o.position):
        val = None
        for key in spec.value_keys():
            if key in values:
                val = values[key]
                break
        if val is None or (isinstance(val, str) and not val.strip()):
            continue
        argv.append(str(val))

    extra = values.get(EXTRA_KEY)
    if isinstance(extra, str) and extra.strip():
        argv.extend(extra.split())

    return argv


class Runner:
    """后台/静默两模式用同一套线程泵；新终端模式只负责把窗口叫起来。"""

    def start_background(self, argv, on_line=None, on_done=None) -> RunHandle:
        started = time.time()
        # 不用 text=True：Windows 上它取 locale 编码（GBK），而子进程可能输出 UTF-8
        # （narnat 实测）——逐行走 decode_line，两种都认。
        # 用默认读缓冲：bufsize=0 的原始 FileIO 会按字节 readline，输出一多 syscall 就爆炸；
        # 带缓冲的 readline 仍是「读到 \n 即返回」，实时性不变。
        proc = subprocess.Popen(list(argv), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL)
        handle = RunHandle(argv=list(argv), state="running", proc=proc, event=threading.Event())

        def pump():
            try:
                if proc.stdout is not None:
                    for raw in proc.stdout:
                        if on_line:
                            on_line(decode_line(raw).rstrip("\r\n"))
                rc = proc.wait()
            except Exception as exc:  # pragma: no cover
                rc = -1
                if on_line:
                    on_line(f"[clitree] 读取输出失败: {exc}")
            state = "stopped" if handle.stopped else ("ok" if rc == 0 else "fail")
            note = "用户停止" if handle.stopped else ""
            result = RunResult(argv=list(argv), rc=rc, state=state, note=note,
                               elapsed_ms=int((time.time() - started) * 1000))
            handle.rc, handle.state, handle.result = rc, state, result
            if on_done:
                on_done(result)
            handle.event.set()

        threading.Thread(target=pump, name="clitree-bg", daemon=True).start()
        return handle

    def start_silent(self, argv, on_line=None, on_done=None) -> RunHandle:
        started = time.time()
        proc = subprocess.Popen(list(argv), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL)
        handle = RunHandle(argv=list(argv), state="running", proc=proc, event=threading.Event())

        def pump():
            try:
                rc = proc.wait()
            except Exception:
                rc = -1
            state = "stopped" if handle.stopped else ("ok" if rc == 0 else "fail")
            result = RunResult(argv=list(argv), rc=rc, state=state,
                               elapsed_ms=int((time.time() - started) * 1000),
                               note="用户停止" if handle.stopped else "静默模式：不产生日志")
            handle.rc, handle.state, handle.result = rc, state, result
            if on_done:
                on_done(result)
            handle.event.set()

        threading.Thread(target=pump, name="clitree-silent", daemon=True).start()
        return handle

    def start_terminal(self, argv, platform=None) -> RunHandle:
        term_argv = terminals.build_terminal_argv(list(argv), platform=platform)
        if term_argv is None:
            return RunHandle(argv=list(argv), state="error", rc=None,
                             result=RunResult(argv=list(argv), rc=None, state="error",
                                              note="本机找不到可用的终端模拟器"))
        try:
            subprocess.Popen(term_argv, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except Exception as exc:
            return RunHandle(argv=list(argv), state="error", rc=None,
                             result=RunResult(argv=list(argv), rc=None, state="error", note=str(exc)))
        return RunHandle(argv=list(argv), state="launched", rc=None,
                         result=RunResult(argv=list(argv), rc=None, state="launched",
                                          note="已在外部终端启动（拿不到子进程 rc，不判成败）"))
