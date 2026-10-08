"""落盘：配置目录 / 最近命令 / 控件类型覆盖写回（D2）。"""
import json

import pytest

from clitree.core import rules as R
from clitree.core import store as S


def test_config_dir_respects_xdg(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("APPDATA", raising=False)
    assert str(tmp_path / "clitree") == str(S.config_dir())


def test_config_dir_respects_appdata_on_windows(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    monkeypatch.setattr(S.sys, "platform", "win32")
    assert "clitree" in str(S.config_dir())


def test_recent_commands_dedup_and_cap(tmp_path):
    p = tmp_path / "recent.json"
    for i in range(30):
        S.push_recent(f"cmd{i}", path=p)
    S.push_recent("cmd5", path=p)
    recent = S.load_recent(path=p)
    assert recent[0] == "cmd5", "最近的排最前（去重）"
    assert len(recent) <= 20


def test_widget_override_round_trip(tmp_path):
    user = tmp_path / "rules.user.json"
    S.save_widget_override("ping", "-D", "spin", user_path=user)
    merged = R.load_rules(user_path=user)
    assert merged["widgets"]["overrides"]["ping"]["-D"] == "spin"
    data = json.loads(user.read_text())
    assert data["widgets"]["overrides"]["ping"]["-D"] == "spin"
