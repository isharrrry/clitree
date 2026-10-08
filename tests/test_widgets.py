"""参数 → 控件类型映射（计划 §5.5 + §11.7/§11.8 实测）。"""
import pytest

from clitree.core import parser as P
from clitree.core import rules as R
from clitree.core import widgets as W

RULE_SET = R.load_rules()


def opts(text):
    return P.parse_help(text, RULE_SET, cmd="test").options


def widget_of(options, name):
    for o in options:
        if name in o.names:
            return o.widget, o.widget_reason
    raise AssertionError(f"未解析出 {name}")


# ---- 来自真 CLI 的实测形态 ----

def test_flag_becomes_checkbox(help_text):
    o = opts(help_text("ping.h.txt"))
    kind, why = widget_of(o, "-D")
    assert kind == "checkbox"
    assert why, "每个判定都必须带推断依据"


def test_numeric_value_becomes_spin(help_text):
    o = opts(help_text("ping.h.txt"))
    assert widget_of(o, "-c")[0] == "spin"


def test_one_of_enum_becomes_combo(help_text):
    o = opts(help_text("ping.h.txt"))
    kind, why = widget_of(o, "-M")
    assert kind == "combo"
    spec = next(x for x in o if "-M" in x.names)
    assert spec.choices == ["do", "dont", "want"]
    assert "one of" in why


def test_path_value_gets_browse(help_text):
    o = opts(help_text("ping.h.txt"))
    assert widget_of(o, "-I")[0] == "path"


def test_data_or_filename_is_not_an_enum(help_text):
    """curl -b <data|filename> 是取值形态，不是枚举集合（实测假阳）。"""
    o = opts(help_text("curl.help-all.txt"))
    kind, _ = widget_of(o, "--cookie")
    assert kind != "combo", "禁止把 <data|filename> 当成下拉候选"


def test_bool_syntax_becomes_tristate():
    o = opts("Usage: t [options]\n\nOptions:\n  --[no-]color     toggle color\n")
    assert widget_of(o, "--color")[0] == "tristate"


def test_repeatable_becomes_multi():
    o = opts("Usage: t [options]\n\nOptions:\n  -v, --verbose    repeatable, use multiple times\n")
    assert widget_of(o, "-v")[0] == "multi"


def test_exclusive_group_from_usage():
    text = "Usage: t [-p | --paginate | -P | --no-pager]\n\nOptions:\n  -p, --paginate   page\n  -P, --no-pager   no page\n"
    o = opts(text)
    groups = {x.group for x in o if x.group}
    assert groups, "usage 里的互斥组必须被识别"


def test_unknown_falls_back_to_text_with_reason():
    o = opts("Usage: t [options]\n\nOptions:\n  -Z <whatzit>     unclear thing\n")
    kind, why = widget_of(o, "-Z")
    assert kind in {"text", "path", "spin"}
    assert why


def test_every_option_has_widget_and_reason(help_text):
    for fixture in ("ping.h.txt", "tar.help.txt", "pnpm.help.txt", "gcc.help.txt", "curl.help-all.txt"):
        for x in opts(help_text(fixture)):
            assert x.widget in {"checkbox", "combo", "spin", "text", "path", "tristate", "multi"}
            assert x.widget_reason, f"{fixture}: {x.names} 缺推断依据"


def test_user_override_wins(tmp_path):
    rules = R.load_rules()
    rules["widgets"]["overrides"] = {"test": {"-D": "spin"}}
    o = P.parse_help("Usage: t [options]\n\nOptions:\n  -D     flag\n", rules, cmd="test").options
    assert o[0].widget == "spin"
    assert "规则覆盖" in o[0].widget_reason
