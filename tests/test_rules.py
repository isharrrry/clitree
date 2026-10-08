import json
import pathlib

import pytest

from clitree.core import rules as R


def test_default_rules_load_and_version(rules):
    assert rules["rulesVersion"] >= 3
    assert rules["subcommands"]["initialDepth"] == 2
    assert rules["subcommands"]["lazyExpand"] is True
    assert rules["widgets"]["comboEditable"] is True


def test_default_rules_file_is_checked_clean():
    assert R.check_rules(R.default_rules_path()) == []


def test_check_rules_flags_bad_json_and_bad_regex(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{ not json")
    assert R.check_rules(p)
    p2 = tmp_path / "badregex.json"
    p2.write_text(json.dumps({"optionBlock": {"nameToken": "([unclosed"}}))
    errs = R.check_rules(p2)
    assert errs and "nameToken" in " ".join(errs)


def test_deny_list_covers_dangerous_commands(rules):
    deny = set(rules["helpChannels"]["denyNeverProbe"])
    for cmd in ("shutdown", "reboot", "dd", "mkfs", "fdisk", "passwd"):
        assert cmd in deny


def test_user_overrides_merge_shallow(tmp_path, monkeypatch):
    user = tmp_path / "rules.user.json"
    user.write_text(json.dumps({"widgets": {"overrides": {"git": {"--bare": "tristate"}}}}))
    merged = R.load_rules(user_path=user)
    assert merged["widgets"]["overrides"]["git"]["--bare"] == "tristate"
    # 未覆盖的部分必须保持默认
    assert merged["widgets"]["fallback"] == "text"
    assert merged["subcommands"]["initialDepth"] == 2


def test_save_override_round_trip(tmp_path):
    user = tmp_path / "rules.user.json"
    R.save_override("git", "--bare", "tristate", user_path=user)
    R.save_override("tar", "-A", "spin", user_path=user)
    data = json.loads(user.read_text())
    assert data["widgets"]["overrides"]["git"]["--bare"] == "tristate"
    assert data["widgets"]["overrides"]["tar"]["-A"] == "spin"
    assert R.load_rules(user_path=user)["widgets"]["overrides"]["tar"]["-A"] == "spin"


def test_default_rules_path_exists():
    p = pathlib.Path(R.default_rules_path())
    assert p.is_file() and p.name == "default.rules.json"
