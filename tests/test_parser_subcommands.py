"""子命令段抽取 —— 实测不可靠（计划 §11.5），因此断言"不确定态"而不是编数字。"""
import pytest

from clitree.core import parser as P
from clitree.core import rules as R

RULE_SET = R.load_rules()


def parse(text):
    return P.parse_help(text, RULE_SET, cmd="test")


def test_pnpm_subcommands_not_swallowing_options(help_text):
    r = parse(help_text("pnpm.help.txt"))
    names = [s.name for s in r.subcommands]
    # 实测 pnpm --help 的 Commands 段本身就有 90+ 条（不是假阳），关键是别把 Options 段的词吃进来
    assert 15 <= len(names) <= 120, f"pnpm 子命令数不合理: {len(names)}"
    assert "install" in names and "add" in names
    for bad in ("verbose", "color", "global", "registry"):
        assert bad not in names, f"假阳：{bad} 被当成子命令"


def test_lsblk_columns_are_not_subcommands(help_text):
    """lsblk 的 `Available output columns:` 是列名不是子命令（实测假阳 54 条）。"""
    r = parse(help_text("lsblk.help.txt"))
    assert len(r.subcommands) <= 5, r.subcommands[:5]


def test_git_chinese_grouped_commands(help_text):
    r = parse(help_text("git.help.txt"))
    names = [s.name for s in r.subcommands]
    assert "clone" in names and "init" in names
    assert len(names) >= 10, f"中文分组列表被过早截断: {names}"


def test_git_help_a_full_list(help_text):
    r = parse(help_text("git-help-a.txt"))
    assert len(r.subcommands) >= 140, len(r.subcommands)


def test_no_commands_section_means_empty_not_invented(help_text):
    r = parse(help_text("tcpdump.help.txt"))
    assert r.subcommands == []


def test_uncertainty_is_reported(help_text):
    """抽取不可靠时允许标不确定，但必须如实暴露该状态。"""
    r = parse(help_text("pnpm.help.txt"))
    assert hasattr(r, "subcommands_uncertain")
    assert isinstance(r.subcommands_uncertain, bool)
