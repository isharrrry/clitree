"""落盘位置（按平台约定自算，不依赖 Qt ⇒ core 可无头单测）与最近命令。"""
from __future__ import annotations

import json
import os
import pathlib
import sys

APP = "clitree"
RECENT_CAP = 20


def config_dir() -> pathlib.Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (pathlib.Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = pathlib.Path.home() / "Library" / "Application Support"
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or (pathlib.Path.home() / ".config")
    return pathlib.Path(base) / APP


def user_rules_path() -> pathlib.Path:
    return config_dir() / "rules.user.json"


def recent_path() -> pathlib.Path:
    return config_dir() / "recent.json"


def load_recent(path: pathlib.Path | str | None = None) -> list[str]:
    p = pathlib.Path(path or recent_path())
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    return [x for x in data if isinstance(x, str)] if isinstance(data, list) else []


def push_recent(cmd: str, path: pathlib.Path | str | None = None) -> pathlib.Path:
    p = pathlib.Path(path or recent_path())
    items = [x for x in load_recent(p) if x != cmd]
    items.insert(0, cmd)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(items[:RECENT_CAP], ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return p


def save_widget_override(cli: str, param: str, widget: str,
                         user_path: pathlib.Path | str | None = None) -> pathlib.Path:
    from . import rules as rules_mod

    return rules_mod.save_override(cli, param, widget,
                                   user_path=str(user_path) if user_path else None)
