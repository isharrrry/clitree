"""CLI 配置文件（程序目录 cli/<工具名>.json：一个文件里多个配置 ＋ 解析结果缓存）。"""
import json

import pytest

from clitree.core import parser as P
from clitree.core import profiles as PF
from clitree.core import rules as R
from clitree.core.model import CommandNode, ParamSpec

RULE_SET = R.load_rules()


@pytest.fixture
def root(tmp_path):
    (tmp_path / "cli").mkdir()
    return tmp_path


# ---- 路径与命名 ----

def test_cli_dir_is_under_program_dir(root):
    assert PF.cli_dir(root) == root / "cli"


def test_profile_file_named_after_tool(root):
    assert PF.profile_path("ping", root).name == "ping.json"
    assert PF.profile_path("git", root).name == "git.json"


def test_tool_name_is_sanitized(root):
    assert PF.profile_path("C:/tools/my tool.exe", root).name == "my_tool.json"
    assert PF.profile_path("a/b", root).name == "b.json"


def test_default_root_is_program_dir():
    d = PF.cli_dir()
    assert d.name == "cli" and (d.parent / "pyproject.toml").is_file()


# ---- 一个文件多个配置 ----

def test_empty_file_skeleton(root):
    data = PF.load_profile_file("ping", root)
    assert data["cli"] == "ping" and data["profiles"] == {} and data["targets"] == {}


def test_multiple_profiles_in_one_file(root):
    PF.save_values("ping", "默认", {"-c": "4", "@0": "127.0.0.1"}, root=root)
    PF.save_values("ping", "压测", {"-c": "100", "@0": "10.0.0.1"}, root=root)
    assert PF.list_profiles("ping", root) == ["压测", "默认"] or \
        set(PF.list_profiles("ping", root)) == {"默认", "压测"}
    data = json.loads(PF.profile_path("ping", root).read_text())
    assert set(data["profiles"]) == {"默认", "压测"}
    assert data["profiles"]["压测"]["values"]["-c"] == "100"


def test_create_profile_copies_current_values(root):
    PF.save_values("ping", "默认", {"-c": "4"}, root=root)
    PF.create_profile("ping", "慢速探测", {"-c": "4", "@0": "8.8.8.8"}, root=root, note="外网")
    assert PF.get_profile("ping", "慢速探测", root)["values"]["@0"] == "8.8.8.8"
    assert PF.get_profile("ping", "慢速探测", root)["note"] == "外网"
    assert PF.list_profiles("ping", root)  # 两个都在


def test_active_profile_switches(root):
    PF.save_values("ping", "默认", {"-c": "4"}, root=root)
    PF.create_profile("ping", "b", {"-c": "9"}, root=root)
    PF.set_active("ping", "b", root=root)
    assert PF.active_profile("ping", root) == "b"
    assert PF.get_profile("ping", PF.active_profile("ping", root), root)["values"]["-c"] == "9"


def test_rename_and_delete_profile(root):
    PF.create_profile("ping", "old", {"-c": "1"}, root=root)
    PF.rename_profile("ping", "old", "new", root=root)
    assert "new" in PF.list_profiles("ping", root) and "old" not in PF.list_profiles("ping", root)
    PF.delete_profile("ping", "new", root=root)
    assert "new" not in PF.list_profiles("ping", root)


def test_delete_last_profile_keeps_file_valid(root):
    PF.create_profile("ping", "only", {"-c": "1"}, root=root)
    PF.delete_profile("ping", "only", root=root)
    data = json.loads(PF.profile_path("ping", root).read_text())
    assert data["profiles"] == {} and data["activeProfile"] in ("", None)


# ---- 解析结果缓存（不全量解析也能载入）----

def _ping_options():
    p = P.parse_help(open("tests/fixtures/help/ping.h.txt", encoding="utf-8").read(),
                     RULE_SET, cmd="ping")
    return p.options + p.positionals


def test_param_spec_round_trip():
    spec = ParamSpec(names=["-c", "--count"], takes_value=True, desc="how many",
                     value_token="<count>", required="optional", default="4", example="10",
                     choices=["1", "2"], widget="spin", widget_reason="判为数值",
                     repeatable=True, group="grp0", position=None, negatable=True)
    again = ParamSpec.from_dict(spec.to_dict())
    assert again.to_dict() == spec.to_dict()


def test_save_and_load_node_cache(root):
    node = CommandNode(name="ping", path=["ping"], desc="")
    node.options = _ping_options()
    node.subcommands = [CommandNode(name="sub", path=["ping", "sub"], parent=node)]
    PF.save_node("ping", [], node, {"channel": ["--help"], "rc": 2, "grade": "full",
                                    "dialect": "usage-posix", "raw_text": "usage: ping ..."},
                 root=root)
    cached = PF.cached_node("ping", [], root)
    assert cached is not None
    assert len(cached.options) == len(node.options)
    assert cached.options[0].to_dict() == node.options[0].to_dict()
    assert [s.name for s in cached.subcommands] == ["sub"]
    assert cached.subcommands[0].load_state == "pending"


def test_cached_node_none_when_never_parsed(root):
    assert PF.cached_node("ping", [], root) is None
    assert PF.cached_node("ping", ["clone"], root) is None


def test_cache_records_help_sha_and_meta(root):
    node = CommandNode(name="ping", path=["ping"])
    node.options = _ping_options()
    PF.save_node("ping", [], node, {"channel": ["--help"], "rc": 2, "grade": "full",
                                    "dialect": "usage-posix", "raw_text": "abc"}, root=root)
    meta = PF.node_meta("ping", [], root)
    assert meta["grade"] == "full" and meta["channel"] == ["--help"]
    assert len(meta["raw_sha256"]) == 64 and meta["raw_bytes"] == 3
    assert "raw_head" in meta


def test_subcommand_cache_is_separate(root):
    root_node = CommandNode(name="git", path=["git"])
    root_node.options = [ParamSpec(names=["-v"], desc="verbose", widget="checkbox")]
    sub = CommandNode(name="git", path=["git", "clone"], parent=root_node)
    sub.options = [ParamSpec(names=["--bare"], desc="bare", widget="checkbox")]
    PF.save_node("git", ["clone"], sub, {"raw_text": "x"}, root=root)
    assert PF.cached_node("git", [], root) is None
    got = PF.cached_node("git", ["clone"], root)
    assert got is not None and got.options[0].names == ["--bare"]


def test_profiles_and_cache_live_in_same_file(root):
    node = CommandNode(name="ping", path=["ping"])
    node.options = _ping_options()
    PF.save_node("ping", [], node, {"raw_text": "x"}, root=root)
    PF.save_values("ping", "默认", {"-c": "4"}, root=root)
    data = json.loads(PF.profile_path("ping", root).read_text())
    assert "" in data["targets"] and "默认" in data["profiles"]


def test_corrupt_file_is_not_fatal(root):
    PF.profile_path("ping", root).write_text("{ this is not json")
    data = PF.load_profile_file("ping", root)
    assert data["profiles"] == {}          # 坏文件不抛异常，按空骨架继续
    PF.save_values("ping", "默认", {"-c": "4"}, root=root)
    assert PF.list_profiles("ping", root) == ["默认"]


def test_unwritable_dir_falls_back(tmp_path, monkeypatch):
    """程序目录不可写时，回退到用户配置目录（不抛异常）。"""
    ro = tmp_path / "ro"
    ro.mkdir()
    (ro / "cli").mkdir()
    (ro / "cli").chmod(0o500)
    fallback = tmp_path / "cfg"
    monkeypatch.setattr(PF, "_fallback_dir", lambda: fallback)
    p = PF.save_values("ping", "默认", {"-c": "4"}, root=ro)
    assert p.parent == fallback
    assert PF.get_profile("ping", "默认", root=ro)["values"]["-c"] == "4"
    (ro / "cli").chmod(0o700)


# ---- 参数说明：文件级 ＋ 配置级覆盖（2026-10）----

def test_file_level_note_round_trip(root):
    PF.set_note("ping", "-c", "我常用 2，别超过 5", root=root)
    text, source = PF.get_note("ping", "-c", root)
    assert text == "我常用 2，别超过 5" and source == "file"
    assert json.loads(PF.profile_path("ping", root).read_text())["notes"]["-c"] == "我常用 2，别超过 5"


def test_profile_note_overrides_file_note(root):
    PF.set_note("ping", "-c", "文件级说明", root=root)
    PF.create_profile("ping", "外网", {"-c": "1"}, root=root)
    PF.set_note("ping", "-c", "外网要限速", root=root, profile="外网")
    assert PF.get_note("ping", "-c", root, profile="外网") == ("外网要限速", "profile")
    assert PF.get_note("ping", "-c", root, profile="默认") == ("文件级说明", "file")


def test_empty_note_clears_and_falls_back(root):
    PF.set_note("ping", "-c", "文件级", root=root)
    PF.create_profile("ping", "b", {}, root=root)
    PF.set_note("ping", "-c", "配置级", root=root, profile="b")
    PF.set_note("ping", "-c", "", root=root, profile="b")      # 清掉配置级 ⇒ 回落到文件级
    assert PF.get_note("ping", "-c", root, profile="b") == ("文件级", "file")
    PF.set_note("ping", "-c", "", root=root)                    # 清掉文件级 ⇒ 回到 help 原文
    assert PF.get_note("ping", "-c", root) == ("", "")


def test_notes_do_not_disturb_values(root):
    PF.save_values("ping", "默认", {"-c": "4"}, root=root)
    PF.set_note("ping", "-c", "说明", root=root)
    assert PF.get_profile("ping", "默认", root)["values"]["-c"] == "4"
