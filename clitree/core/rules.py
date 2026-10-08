"""规则加载 / 校验 / 覆盖写回。默认规则是随包的 default.rules.json（唯一真相源）。"""
from __future__ import annotations

import copy
import json
import pathlib
import re

RULES_DIR = pathlib.Path(__file__).resolve().parent.parent / "rules"
DEFAULT_RULES = RULES_DIR / "default.rules.json"

_REGEX_FIELDS = (
    ("optionBlock", "nameToken"),
    ("optionBlock", "valueToken"),
    ("helpChannels", "dashHDeclarationPattern"),
    ("dashdashInteractive", "definitionLine"),
    ("dashdashInteractive", "classHeader"),
)


def default_rules_path() -> str:
    return str(DEFAULT_RULES)


def user_rules_path() -> str:
    from . import store

    return str(store.user_rules_path())


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_rules(user_path: str | None = None) -> dict:
    with open(DEFAULT_RULES, encoding="utf-8") as fh:
        rules = json.load(fh)
    up = user_path if user_path is not None else user_rules_path()
    p = pathlib.Path(up)
    if p.is_file():
        try:
            over = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            over = {}
        if isinstance(over, dict):
            rules = _deep_merge(rules, over)
    return rules


def check_rules(path: str | None = None) -> list[str]:
    """返回错误列表；空列表 = 规则可用。"""
    p = pathlib.Path(path or default_rules_path())
    errs: list[str] = []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"JSON 解析失败: {exc}"]
    if not isinstance(data, dict):
        return ["规则根必须是对象"]
    for section, field in _REGEX_FIELDS:
        pat = (data.get(section) or {}).get(field)
        if not pat:
            continue
        try:
            re.compile(pat)
        except re.error as exc:
            errs.append(f"{section}.{field} 正则非法: {exc}")
    for i, pat in enumerate((data.get("optionBlock") or {}).get("separators") or []):
        try:
            re.compile(pat)
        except re.error as exc:
            errs.append(f"optionBlock.separators[{i}] 正则非法: {exc}")
    for i, pat in enumerate((data.get("manPage") or {}).get("detect") or []):
        try:
            re.compile(pat)
        except re.error as exc:
            errs.append(f"manPage.detect[{i}] 正则非法: {exc}")
    for entry in (data.get("dialects") or {}).get("detect") or []:
        for key in ("firstLineMatches", "anyLineMatches"):
            if entry.get(key):
                try:
                    re.compile(entry[key])
                except re.error as exc:
                    errs.append(f"dialects.detect[{entry.get('name')}].{key} 正则非法: {exc}")
    return errs


def save_override(cli: str, param: str, widget: str, user_path: str | None = None) -> pathlib.Path:
    """把用户的控件类型纠正写进用户覆盖文件（不碰随包默认规则）。"""
    p = pathlib.Path(user_path or user_rules_path())
    data: dict = {}
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    if not isinstance(data, dict):
        data = {}
    widgets = data.setdefault("widgets", {})
    overrides = widgets.setdefault("overrides", {})
    overrides.setdefault(cli, {})[param] = widget
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p
