"""help 通道探测 —— 安全策略与 rc 不可信（计划 §5.3）。"""
import pytest

from clitree.core import discovery as D
from clitree.core import rules as R

RULE_SET = R.load_rules()

REAL_HELP = """Usage: t [options]

Options:
  -v, --verbose    verbose
  -n, --count <n>  how many
"""
MANPAGE = "T(1)                          T Manual                          T(1)\n\nNAME\n       t - thing\n\nSYNOPSIS\n       t [options]\n"
NO_H_DECL = "Usage: t [options]\n\nOptions:\n  -a    a thing\n  -b    b thing\n"


def runner_from(mapping):
    calls = []

    def run(exe, args, timeout):
        calls.append(list(args))
        return mapping.get(tuple(args), (1, ""))

    return run, calls


def test_content_wins_over_rc():
    run, calls = runner_from({("--help",): (129, REAL_HELP)})
    res = D.probe("/usr/bin/t", RULE_SET, runner=run)
    assert res.ok is True, "rc=129 但有可用 help ⇒ 必须判成功"
    assert res.channel == ["--help"]
    assert len(calls) == 1


def test_dangerous_command_never_probed():
    run, calls = runner_from({})
    for exe in ("/sbin/shutdown", "/bin/dd", "/usr/sbin/mkfs.ext4", "/usr/bin/passwd"):
        res = D.probe(exe, RULE_SET, runner=run)
        assert res.ok is False
        assert "安全策略" in res.reason
    assert calls == [], "危险命令绝不许起进程"


def test_dash_h_skipped_when_not_declared_and_not_whitelisted():
    run, calls = runner_from({("--help",): (0, NO_H_DECL), ("/?",): (0, REAL_HELP)})
    res = D.probe("/usr/bin/notwhitelisted", RULE_SET, runner=run)
    assert ["-h"] not in [list(c) for c in calls], "未声明 -h 的命令不许跑 -h"
    assert res.ok is True


def test_dash_h_used_when_declared_in_help():
    text = "Usage: t [options]\n\nOptions:\n  -h, --help    show help\n"
    run, calls = runner_from({("--help",): (0, ""), ("-h",): (0, text)})
    res = D.probe("/usr/bin/t", RULE_SET, runner=run)
    assert res.ok is True
    # --help 空 ⇒ 无法据其声明；命令不在实测白名单 ⇒ 允许直接试 -h 之外必须先出现 --help
    assert calls[0] == ["--help"]


def test_man_page_triggers_fallback():
    run, calls = runner_from({("--help",): (0, MANPAGE), ("-h",): (0, REAL_HELP)})
    res = D.probe("/usr/bin/t", RULE_SET, runner=run)
    assert res.ok is True
    assert ["--help"] in res.channels_tried, "man 页必须先被识别但不算成功"
    assert res.channel == ["-h"], "识别出 man 页后改用 -h"
    assert res.man_page_seen is True


def test_all_channels_fail_keeps_raw_text():
    run, calls = runner_from({("--help",): (1, "garbage output")})
    res = D.probe("/usr/bin/t", RULE_SET, runner=run)
    assert res.ok is False
    assert "garbage" in res.raw_text
    assert len(calls) >= 2, "一条通道不行要试下一条"


def test_interactive_channel_for_gdb():
    run, calls = runner_from({("-batch", "-ex", "help all"): (0, "Command class: breakpoints\n\nawatch -- Set an access watchpoint.\nbreak -- Set breakpoint.\ncatch -- Catch.\ndisable -- Disable.\nenable -- Enable.\n")})
    res = D.probe("/usr/bin/gdb", RULE_SET, runner=run)
    assert res.ok is True
    assert calls[0] == ["-batch", "-ex", "help all"]
    assert res.dialect == "dashdash-interactive"


def test_grade_computed_from_text():
    assert D.grade_of(REAL_HELP, RULE_SET) in {"full", "weak", "usage-only"}
    assert D.grade_of("x\n", RULE_SET) == "usage-only"


def test_real_fakecli_end_to_end(fakecli):
    res = D.probe(fakecli, RULE_SET)
    assert res.ok is True
    assert "fakecli" in res.raw_text
    assert res.grade == "full"
    # 用包装脚本验证 rc 不可信的真实路径
    import os
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
        fh.write(f"#!/bin/sh\nexec {fakecli} --help-rc 129 \"$@\"\n")
        wrapper = fh.name
    os.chmod(wrapper, 0o755)
    try:
        res3 = D.probe(wrapper, RULE_SET)
        assert res3.ok is True and res3.rc != 0, f"rc={res3.rc} 却仍必须判成功"
    finally:
        os.unlink(wrapper)


def test_subcommand_path_comes_before_the_channel_flag():
    """子命令探测必须是 `git clone --help`，绝不能拼成 `git -h clone`（会把父命令的帮助当子命令的）。"""
    run, calls = runner_from({("clone", "--help"): (0, REAL_HELP)})
    res = D.probe("/usr/bin/git", RULE_SET, node_path=("clone",), runner=run)
    assert res.ok is True
    assert calls[0] == ["clone", "--help"], calls
    assert all(c[:1] != ["-h"] for c in calls), "绝不许出现 `-h clone` 这种错序"
