"""块模型解析测试 —— 断言来自本机实测形态（计划 §11.3/§11.4）。"""
import pytest

from clitree.core import parser as P
from clitree.core import rules as R

RULE_SET = R.load_rules()


def parse(text):
    return P.parse_help(text, RULE_SET, cmd="test")


# ---- 方言识别（计划 §5.3 / §11.8）----

def test_man_page_dialect_detected(help_text):
    r = parse(help_text("git-clone.manpage.txt"))
    assert r.dialect == "man-page"


def test_dashdash_interactive_dialect_detected(help_text):
    r = parse(help_text("gdb.help-all.txt"))
    assert r.dialect == "dashdash-interactive"
    names = [o.names[0] for o in r.commands]
    assert "awatch" in names and "break" in names
    assert len(r.commands) >= 150


def test_usage_posix_dialect_detected(help_text):
    assert parse(help_text("pnpm.help.txt")).dialect == "usage-posix"
    assert parse(help_text("tar.help.txt")).dialect == "usage-posix"


# ---- 关键形态（每一条都来自实测）----

def test_pnpm_value_with_brackets_and_two_line_block(help_text):
    r = parse(help_text("pnpm.help.txt"))
    opt = r.find("--color")
    assert opt is not None, "pnpm 的 --color[=<COLOR>] 必须被解析出来"
    assert opt.takes_value is True
    assert "Force colored output" in opt.desc, "描述在下一缩进行 ⇒ 必须做续行合并"


def test_tar_multi_alias_single_option(help_text):
    r = parse(help_text("tar.help.txt"))
    opt = r.find("--catenate")
    assert opt is not None
    assert opt.names == ["-A", "--catenate", "--concatenate"], opt.names


def test_tar_continuation_is_not_a_new_option(help_text):
    r = parse(help_text("tar.help.txt"))
    assert r.find("--occurrence") is not None
    # 续行里出现的 --delete / --extract 是描述文字，绝不能变成独立参数
    occ = r.find("--occurrence")
    assert "--delete" not in occ.names
    for name in ("--delete", "--extract", "--list"):
        o = r.find(name)
        assert o is None or "occurrence" not in o.desc.lower()


def test_gcc_single_dash_long_name(help_text):
    r = parse(help_text("gcc.help.txt"))
    assert r.find("-pass-exit-codes") is not None, "GNU 单横线长名必须支持"


def test_python3_colon_separated_value(help_text):
    """实测形态：`-c cmd : program passed in as string`（冒号前是取值名）；
    `-b     : issue warnings ...` 冒号前没有取值名 ⇒ 是开关，不是取值。"""
    r = parse(help_text("python3.help.txt"))
    c = r.find("-c")
    assert c is not None and c.takes_value is True
    assert "program passed" in c.desc
    b = r.find("-b")
    assert b is not None and b.takes_value is False


def test_ping_options_and_positional(help_text):
    r = parse(help_text("ping.h.txt"))
    m = r.find("-M")
    assert m is not None and m.takes_value is True
    c = r.find("-c")
    assert c is not None and c.takes_value is True
    assert any(p.position is not None for p in r.positionals), "usage 行里的 <destination> 必须成为位置参数"


# ---- 分级（计划 §5.3）----

@pytest.mark.parametrize(
    "fixture,allowed",
    [
        ("tcpdump.help.txt", {"weak", "usage-only"}),
        ("nc.help.txt", {"weak", "usage-only"}),
        ("nslookup.help.txt", {"weak", "usage-only"}),
        ("pnpm.help.txt", {"full"}),
        ("tar.help.txt", {"full"}),
        ("systemctl.help.txt", {"full"}),
    ],
)
def test_grade(help_text, fixture, allowed):
    assert parse(help_text(fixture)).grade in allowed


# ---- 每一条 fixture 都要能跑通且报出块数（回归基线）----

ALL_FIXTURES = [
    "pnpm.help.txt", "git.help.txt", "tar.help.txt", "dotnet.help.txt", "python3.help.txt",
    "pip.help.txt", "git-clone.manpage.txt", "git-clone.h.txt", "dotnet-build.h.txt",
    "gcc.help.txt", "ping.h.txt", "windows-ping.h.txt", "windows-ping.zh.h.txt",
    "curl.help-all.txt", "ssh.help.txt",
    "tcpdump.help.txt", "awk.help.txt", "ip.help.txt", "rsync.help.txt", "systemctl.help.txt",
    "gdb.help.txt", "strace.help.txt", "mtr.help.txt", "tracepath.help.txt", "nc.help.txt",
    "nslookup.help.txt", "lsblk.help.txt", "gdb.help-all.txt", "git-help-a.txt",
]


@pytest.mark.parametrize("fixture", ALL_FIXTURES)
def test_every_fixture_parses_without_error(help_text, fixture):
    r = parse(help_text(fixture))
    assert r.dialect in {"usage-posix", "blocks-only", "man-page", "dashdash-interactive"}
    assert r.grade in {"full", "weak", "usage-only", "man-page"}
    assert r.raw_text, "原始文本必须保留（未识别时给用户看原文）"


def test_parser_outputs_structured_data(help_text):
    """解析产出的是结构化数据（列表/字符串），不是拼好的命令行。"""
    r = parse(help_text("ping.h.txt"))
    for o in r.options:
        assert isinstance(o.names, list) and all(isinstance(n, str) for n in o.names)
        assert isinstance(o.desc, str)
        assert isinstance(o.takes_value, bool)


def test_option_values_are_not_counted_as_positional():
    """usage 里 `[-C <path>]`、`[-c <name>=<value>]` 是选项的取值，不是位置参数。"""
    text = ("usage: git [--version] [--help] [-C <path>] [-c <name>=<value>] "
            "[--exec-path[=<path>]] <command> [<args>]\n\nOptions:\n  -C <path>   run as if started in <path>\n")
    r = parse(text)
    tokens = {p.value_token for p in r.positionals}
    assert tokens == {"<command>", "<args>"}, tokens


def test_cjk_positionals_are_kept_and_placeholder_skipped(help_text):
    """`用法：git clone [<选项>] [--] <仓库> [<路径>]` ⇒ 抽到 <仓库>(必填) 与 <路径>(可选)，跳过 <选项>。"""
    r = parse(help_text("git-clone.h.txt"))
    got = {p.value_token: p.required for p in r.positionals}
    assert "<仓库>" in got and got["<仓库>"] == "required", got
    assert "<路径>" in got and got["<路径>"] == "optional", got
    assert "<选项>" not in got


# ---- 必填口径（2026-10 修订）：选项一律可选，只有位置参数分必填/可选 ----

def test_ping_options_are_all_optional(help_text):
    """实测：usage 是 `ping [options] <destination>` ⇒ 全是可选，不该出现「未标注」。
    （2026-10 迭代：-4/-6 数字短选项纳入解析，32 → 34。）"""
    r = parse(help_text("ping.h.txt"))
    assert len(r.options) == 34
    assert {o.required for o in r.options} == {"optional"}
    assert r.usage_marks_required is True


def test_windows_ping_bare_word_target_and_numeric_options(help_text):
    """Windows ping 实测（windows-ping.h.txt）：usage 折 4 行、位置参数是**裸词**
    target_name（必填，表单里必须有一个地方填目标 IP）；`-4`/`-6` 是数字短选项；
    `-n count` 里的取值词不能冒出来当位置参数。"""
    r = parse(help_text("windows-ping.h.txt"))
    got = {p.value_token: p.required for p in r.positionals}
    assert got.get("target_name") == "required", got
    for junk in ("count", "size", "TTL", "TOS", "timeout", "host-list", "srcaddr", "compartment"):
        assert junk not in got, junk
    assert r.find("-4") is not None and r.find("-6") is not None
    assert r.find("-4").required == "optional"


def test_windows_ping_option_takes_value_single_space_form(help_text):
    """Windows 布局：名字与取值**仅隔 1 个空格**（`-n count       Number...`）——
    -n 必须被判为有取值，否则执行时会生成 `ping -n <主机>` 这种把主机吃掉的坏命令。"""
    r = parse(help_text("windows-ping.h.txt"))
    for name in ("-n", "-l", "-i", "-w"):
        spec = r.find(name)
        assert spec is not None and spec.takes_value is True, name
    assert r.find("-n").value_token == "count"
    assert r.find("-t").takes_value is False, "纯开关不能被误判为有取值"


def test_windows_ping_zh_layout(help_text):
    """中文 Windows 实测（windows-ping.zh.h.txt，取自本机 zh-CN ping.exe.mui）：
    `用法:`/`选项:` 前缀 + 中文描述下，target_name 与取值识别必须照常生效；
    `-c compartment 路由...` 的取值后直接接中文描述（仅 1 空格）也要认。"""
    r = parse(help_text("windows-ping.zh.h.txt"))
    got = {p.value_token: p.required for p in r.positionals}
    assert got.get("target_name") == "required", got
    assert r.find("-n") is not None and r.find("-n").takes_value is True
    assert r.find("-c") is not None and r.find("-c").takes_value is True
    assert r.find("-4") is not None and r.find("-6") is not None


def test_bare_words_never_override_angle_form(help_text):
    """出现尖括号组时裸词一律不算位置参数（`用法：git clone [<选项>] [--] <仓库>`
    里的 clone 是命令词，不能变成参数）。"""
    r = parse(help_text("git-clone.h.txt"))
    tokens = {p.value_token for p in r.positionals}
    assert tokens == {"<仓库>", "<路径>"}, tokens


def test_usage_noise_words_are_not_positionals(help_text):
    """裸词识别必须挡住 usage 噪音（全部来自实测形态）：
    - rsync 多段 usage 的连接词 or 与重复命令名 rsync；
    - ip 的 `{ COMMAND | help }` 里的 help、第二段的 ip；
    - ssh 的 `[-D [bind_address:]port]` 是嵌套取值结构，不是位置参数；
    - tcpdump 的 `-E algo:secret`、`-Q in|out|inout` 是选项取值。"""
    cases = {
        "rsync.help.txt": {"or", "rsync"},
        "ip.help.txt": {"help", "ip"},
        "ssh.help.txt": {"bind_address", "port", "user", "host"},
        "tcpdump.help.txt": {"algo", "secret", "in", "out", "inout"},
    }
    for fixture, junk in cases.items():
        got = {p.value_token for p in parse(help_text(fixture)).positionals}
        assert not (got & junk), (fixture, got)


def test_positional_keeps_required_and_optional(help_text):
    r = parse(help_text("ping.h.txt"))
    got = {p.value_token: p.required for p in r.positionals}
    assert got["<destination>"] == "required"


def test_no_usage_line_means_unknown_not_optional():
    """连 usage 行都没有 ⇒ 如实标「未判定」，不许假装知道。"""
    r = parse("Options:\n  -a    aaa\n  -b    bbb\n")
    assert {o.required for o in r.options} == {"unknown"}
    assert r.usage_marks_required is False
