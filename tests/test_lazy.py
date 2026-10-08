"""懒加载：点加载只 2 层，展开才探测（D3 / 计划 §5.2）。"""
import pytest

from clitree.core import lazy as L
from clitree.core import rules as R

RULE_SET = R.load_rules()

ROOT_HELP = """Usage: fakecli [options] <target>

Commands:
  sub1            first subcommand
  sub2            second subcommand
  sub3            third subcommand

Options:
  -v, --verbose    verbose
"""
SUB_HELP = """Usage: fakecli sub1 [options]

Commands:
  deep            a deeper command

Options:
  -x, --extra <VALUE>   extra
"""


class FakeProbe:
    def __init__(self, table):
        self.table = table
        self.calls = []

    def __call__(self, exe, rules, node_path=()):
        self.calls.append((exe, tuple(node_path)))
        key = tuple(node_path)
        if key in self.table:
            return self.table[key]
        raise AssertionError(f"不该探测 {key}")


def make_probe():
    from clitree.core.discovery import ProbeResult

    def ok(text):
        return ProbeResult(ok=True, raw_text=text, channel=["--help"], rc=0, grade="full",
                           dialect="usage-posix", reason="ok", man_page_seen=False)

    return FakeProbe({
        (): ok(ROOT_HELP),
        ("sub1",): ok(SUB_HELP),
        ("sub2",): ok(ROOT_HELP),
        ("sub3",): ok(ROOT_HELP),
    })


def test_load_root_probes_once_and_stops_at_two_levels():
    probe = make_probe()
    loader = L.TreeLoader(RULE_SET, probe_fn=probe)
    root = loader.load_root("/usr/bin/fakecli")
    assert len(probe.calls) == 1, "点加载只许探测 1 次"
    assert [s.name for s in root.subcommands] == ["sub1", "sub2", "sub3"]
    for s in root.subcommands:
        assert s.load_state == "pending"
        assert s.options == [], "第 2 层不许带参数（还没探测）"


def test_expand_probes_only_that_subcommand():
    probe = make_probe()
    loader = L.TreeLoader(RULE_SET, probe_fn=probe)
    root = loader.load_root("/usr/bin/fakecli")
    sub1 = root.subcommands[0]
    loader.expand(sub1)
    assert len(probe.calls) == 2
    assert sub1.load_state == "loaded"
    assert any("--extra" in o.names for o in sub1.options)


def test_expand_is_cached():
    probe = make_probe()
    loader = L.TreeLoader(RULE_SET, probe_fn=probe)
    root = loader.load_root("/usr/bin/fakecli")
    sub1 = root.subcommands[0]
    loader.expand(sub1)
    loader.expand(sub1)
    loader.expand(sub1)
    assert len(probe.calls) == 2, "重复展开不许重复探测"


def test_max_depth_stops_expansion():
    probe = make_probe()
    loader = L.TreeLoader(RULE_SET, probe_fn=probe)
    root = loader.load_root("/usr/bin/fakecli")
    sub1 = root.subcommands[0]
    loader.expand(sub1)
    deep = sub1.subcommands[0]
    assert deep.path == ["fakecli", "sub1", "deep"]
    loader.expand(deep)  # 已到 maxDepth=3 ⇒ 不再探测
    assert all(c[1] != ("sub1", "deep") for c in probe.calls)


def test_expand_all_probes_each_pending_once():
    probe = make_probe()
    loader = L.TreeLoader(RULE_SET, probe_fn=probe)
    root = loader.load_root("/usr/bin/fakecli")
    loader.expand_all(root)
    assert len(probe.calls) == 4  # root + sub1/2/3


def test_failed_probe_marks_node_and_is_retryable():
    from clitree.core.discovery import ProbeResult

    calls = []

    def bad(exe, rules, node_path=()):
        calls.append(tuple(node_path))
        if len(calls) == 1:
            return ProbeResult(ok=True, raw_text=ROOT_HELP, channel=["--help"], rc=0, grade="full",
                               dialect="usage-posix", reason="ok", man_page_seen=False)
        return ProbeResult(ok=False, raw_text="", channel=["--help"], rc=1, grade="usage-only",
                           dialect="unknown", reason="拿不到 help", man_page_seen=False)

    loader = L.TreeLoader(RULE_SET, probe_fn=bad)
    root = loader.load_root("/usr/bin/fakecli")
    sub1 = root.subcommands[0]
    loader.expand(sub1)
    assert sub1.load_state == "failed" and sub1.error
    loader.expand(sub1, retry=True)
    assert len(calls) == 3, "失败节点必须可重试"


def test_depth_limit_configurable():
    probe = make_probe()
    loader = L.TreeLoader(RULE_SET, probe_fn=probe, max_depth=2)
    root = loader.load_root("/usr/bin/fakecli")
    sub1 = root.subcommands[0]
    loader.expand(sub1)
    assert sub1.load_state == "pending", "maxDepth=2 时第 2 层不许再展开"
