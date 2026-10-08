"""执行器：argv 直传（绝不经 shell）＋ 三模式（计划 §5.4）。"""
import sys
import time

import pytest

from clitree.core import executor as E
from clitree.core import terminals as T
from clitree.core.model import CommandNode, ParamSpec

PY = sys.executable


def node_with_fakecli():
    return CommandNode(
        name="fakecli",
        path=["fakecli"],
        desc="",
        options=[
            ParamSpec(names=["-v", "--verbose"], takes_value=False, desc="verbose", widget="checkbox"),
            ParamSpec(names=["-n", "--count"], takes_value=True, desc="how many", widget="spin"),
            ParamSpec(names=["-o", "--output"], takes_value=True, desc="out file", widget="path"),
            ParamSpec(names=["-m", "--mode"], takes_value=True, desc="mode", widget="combo",
                      choices=["fast", "slow", "auto"]),
            ParamSpec(names=[], takes_value=True, desc="target", widget="text", position=0,
                      required="required"),
        ],
    )


# ---- argv 构造：安全关键 ----

def test_build_argv_uses_long_names_and_lists():
    argv = E.build_argv("fakecli", node_with_fakecli(), {"--verbose": True, "--count": "3",
                                                        "--output": "a b;rm -rf /", "@0": "host1"})
    assert argv == ["fakecli", "--verbose", "--count", "3", "--output", "a b;rm -rf /", "host1"]


def test_build_argv_skips_unchecked_and_empty():
    argv = E.build_argv("fakecli", node_with_fakecli(), {"--verbose": False, "--count": "",
                                                        "--output": None, "@0": ""})
    assert argv == ["fakecli"]


def test_build_argv_repeats_multi_values():
    node = CommandNode(name="t", path=["t"], desc="",
                       options=[ParamSpec(names=["-I", "--include"], takes_value=True, desc="",
                                          widget="multi")])
    argv = E.build_argv("t", node, {"--include": ["a", "b c", "d"]})
    assert argv == ["t", "--include", "a", "--include", "b c", "--include", "d"]


def test_dangerous_value_stays_one_argv_element():
    payload = "x; touch /tmp/pwned && echo hi"
    argv = E.build_argv("fakecli", node_with_fakecli(), {"--output": payload})
    assert argv == ["fakecli", "--output", payload]
    assert not any(part in ("&&", ";", "touch") for part in argv)
    assert len(argv) == 3


# ---- 三模式 ----

def test_background_streams_lines(fakecli):
    lines, done = [], []
    h = E.Runner().start_background([PY, fakecli, "--count", "1"], on_line=lines.append,
                                    on_done=lambda r: done.append(r))
    h.wait(timeout=10)
    assert len(lines) >= 3
    assert all("FAKECLI line" in l for l in lines[:3])
    assert done and done[0].state == "ok" and done[0].rc == 0


def test_background_marks_failure(fakecli):
    done = []
    h = E.Runner().start_background([PY, fakecli, "--fail"], on_line=lambda l: None,
                                    on_done=done.append)
    h.wait(timeout=10)
    assert done[0].rc == 3 and done[0].state == "fail"


def test_silent_emits_no_lines(fakecli):
    lines, done = [], []
    h = E.Runner().start_silent([PY, fakecli], on_line=lines.append, on_done=done.append)
    h.wait(timeout=10)
    assert lines == [], "静默模式不许产生任何日志"
    assert done[0].state == "ok"


def test_silent_records_failure_without_log(fakecli):
    lines, done = [], []
    h = E.Runner().start_silent([PY, fakecli, "--fail"], on_line=lines.append, on_done=done.append)
    h.wait(timeout=10)
    assert lines == []
    assert done[0].state == "fail"


def test_terminal_mode_is_launched_but_unknown_rc(fakecli, tmp_path, monkeypatch):
    seen = {}

    def fake_popen(argv, **kw):
        seen["argv"] = argv

        class P:
            pid = 1

            def wait(self, timeout=None):
                return 0

        return P()

    monkeypatch.setattr(E.subprocess, "Popen", fake_popen)
    res = E.Runner().start_terminal([PY, fakecli], platform="linux")
    assert res is not None
    assert res.state == "launched", "新终端拿不到 rc ⇒ 只能是 launched，不许谎报成功"
    assert res.rc is None


# ---- 终端适配 ----

def test_terminal_argv_linux_targets_a_real_emulator():
    argv = T.build_terminal_argv(["echo", "hi there"], platform="linux")
    assert argv is not None
    assert argv[0].endswith(("gnome-terminal", "xfce4-terminal", "konsole", "xterm", "x-terminal-emulator"))
    assert "hi there" in " ".join(argv)


def test_terminal_argv_quotes_posix():
    cmd = T.posix_command_line(["echo", "a b; echo pwned"])
    assert "a b; echo pwned" in cmd
    assert cmd.count("'") >= 2, "含特殊字符必须被引起来"


def test_terminal_argv_windows_uses_cmd_start():
    argv = T.build_terminal_argv(["prog.exe", "a b"], platform="win32")
    assert argv is not None and argv[0].lower().endswith(("cmd", "cmd.exe", "wt.exe", "wt"))


def test_terminal_argv_macos_uses_osascript():
    argv = T.build_terminal_argv(["prog", "a"], platform="darwin")
    assert argv is not None and argv[0].endswith("osascript")


# ---- 停止（执行中再点一次）----

def test_stop_terminates_running_process(fakecli):
    done = []
    h = E.Runner().start_silent([PY, fakecli, "--sleep", "30"], on_done=done.append)
    time.sleep(0.4)
    h.stop()
    h.wait(timeout=10)
    assert done, "停止后必须回调结果"
    assert done[0].state == "stopped", done[0]


def test_stop_background_also_works(fakecli):
    lines, done = [], []
    h = E.Runner().start_background([PY, fakecli, "--sleep", "30"], on_line=lines.append,
                                    on_done=done.append)
    time.sleep(0.4)
    h.stop()
    h.wait(timeout=10)
    assert done[0].state == "stopped"


def test_stop_on_finished_run_is_noop(fakecli):
    done = []
    h = E.Runner().start_silent([PY, fakecli], on_done=done.append)
    h.wait(timeout=10)
    h.stop()          # 已经结束 ⇒ 不该抛异常、也不该改状态
    assert done[0].state == "ok"
