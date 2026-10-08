"""CLI 配置文件：程序目录 `cli/<工具名>.json`，一个文件里装**多个配置** ＋ 解析结果缓存。

文件结构（schema 1）：

    {
      "schema": 1,
      "cli": "ping",
      "updatedAt": "2026-10-05T22:40:00",
      "targets": {                       // 每个「被解析过的命令路径」一份缓存，"" = 根
        "": { "exe": "ping", "channel": ["--help"], "rc": 2, "grade": "full",
              "dialect": "usage-posix", "raw_sha256": "…", "raw_bytes": 1866, "raw_head": "…",
              "options": [ …ParamSpec… ], "subcommands": [{"name": "clone", "desc": "…"}] }
      },
      "activeProfile": "默认",
      "profiles": {                      // ★ 一个文件里多个配置
        "默认": {"note": "", "createdAt": "…", "updatedAt": "…",
                 "values": {"-c": "4", "@0": "127.0.0.1"}}
      }
    }

设计要点：
- 缓存里有**参数树本体**，所以下次不跑 help 也能直接把树和表单渲染出来。
- 只存 help 的前 2 KB（`raw_head`）＋ 全量 sha256：够诊断，不会让文件膨胀。
- 程序目录写不进去（只读安装）时自动回退到用户配置目录，不抛异常。
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import pathlib
import re

from . import store
from .model import CommandNode, ParamSpec, Subcommand

SCHEMA = 1
RAW_HEAD_LIMIT = 2048


# ---------------------------------------------------------------- 路径

def _fallback_dir() -> pathlib.Path:
    return store.config_dir() / "cli"


def cli_dir(root: pathlib.Path | str | None = None) -> pathlib.Path:
    """程序目录下的 cli/；没有 root 时用包的上上层（＝ pyproject.toml 所在目录）。"""
    if root is not None:
        return pathlib.Path(root) / "cli"
    return pathlib.Path(__file__).resolve().parents[2] / "cli"


def _safe_name(cli_name: str) -> str:
    name = (cli_name or "cli").strip().replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"\.(exe|py|sh|bat|cmd)$", "", name, flags=re.I)
    name = re.sub(r"[^\w.-]+", "_", name)
    return name or "cli"


def profile_path(cli_name: str, root: pathlib.Path | str | None = None) -> pathlib.Path:
    return cli_dir(root) / f"{_safe_name(cli_name)}.json"


def _writable(path: pathlib.Path) -> pathlib.Path:
    """返回真正可写的目录：程序目录优先，写不进去就回退到用户配置目录。"""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".clitree-write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return path
    except Exception:
        fb = _fallback_dir()
        fb.mkdir(parents=True, exist_ok=True)
        return fb


def _read_path(cli_name: str, root: pathlib.Path | str | None) -> pathlib.Path:
    p = profile_path(cli_name, root)
    if p.is_file():
        return p
    fb = _fallback_dir() / p.name
    return fb if fb.is_file() else p


# ---------------------------------------------------------------- 读写

def _now() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _skeleton(cli_name: str) -> dict:
    return {"schema": SCHEMA, "cli": _safe_name(cli_name), "updatedAt": _now(),
            "targets": {}, "notes": {}, "activeProfile": "", "profiles": {}}


def load_profile_file(cli_name: str, root: pathlib.Path | str | None = None) -> dict:
    p = _read_path(cli_name, root)
    data = None
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = None
    if not isinstance(data, dict):
        return _skeleton(cli_name)
    out = _skeleton(cli_name)
    out.update({k: v for k, v in data.items() if k in out})
    for key in ("targets", "profiles", "notes"):
        if not isinstance(out.get(key), dict):
            out[key] = {}
    return out


def _write(cli_name: str, data: dict, root: pathlib.Path | str | None) -> pathlib.Path:
    data["schema"] = SCHEMA
    data["cli"] = _safe_name(cli_name)
    data["updatedAt"] = _now()
    target = _writable(profile_path(cli_name, root).parent) / profile_path(cli_name, root).name
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(target)                      # 原子替换，避免半截文件
    return target


# ---------------------------------------------------------------- 解析结果缓存

def save_node(cli_name: str, node_path: list, node: CommandNode, probe_meta: dict | None = None,
              root: pathlib.Path | str | None = None) -> pathlib.Path:
    """把某个命令路径的解析结果写进缓存（`node_path=[]` 是根）。"""
    data = load_profile_file(cli_name, root)
    key = "/".join(node_path or [])
    meta = dict(probe_meta or {})
    raw = meta.pop("raw_text", "") or ""
    entry = {
        "exe": (meta.pop("exe", "") or ""),
        "channel": meta.get("channel") or [],
        "rc": meta.get("rc"),
        "grade": meta.get("grade") or node.grade or "",
        "dialect": meta.get("dialect") or node.dialect or "",
        "raw_sha256": hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest() if raw else "",
        "raw_bytes": len(raw.encode("utf-8", "replace")),
        "raw_head": raw[:RAW_HEAD_LIMIT],
        "parsedAt": _now(),
        "options": [o.to_dict() for o in node.options],
        "subcommands": [{"name": s.name, "desc": s.desc} for s in node.subcommands],
    }
    data["targets"][key] = entry
    return _write(cli_name, data, root)


def node_meta(cli_name: str, node_path: list, root: pathlib.Path | str | None = None) -> dict | None:
    data = load_profile_file(cli_name, root)
    entry = data["targets"].get("/".join(node_path or []))
    if not isinstance(entry, dict):
        return None
    return {k: v for k, v in entry.items() if k not in ("options", "subcommands")}


def cached_node(cli_name: str, node_path: list, root: pathlib.Path | str | None = None):
    """从缓存还原一个 CommandNode（没缓存过就返回 None）。"""
    data = load_profile_file(cli_name, root)
    entry = data["targets"].get("/".join(node_path or []))
    if not isinstance(entry, dict):
        return None
    path = list(node_path or [])
    name = path[-1] if path else _safe_name(cli_name)
    node = CommandNode(name=name, path=([_safe_name(cli_name)] + path) if path else [_safe_name(cli_name)])
    node.options = [ParamSpec.from_dict(d) for d in entry.get("options") or []]
    node.load_state = "loaded"
    node.grade = entry.get("grade") or ""
    node.dialect = entry.get("dialect") or ""
    node.parsed_at = entry.get("parsedAt") or ""
    for s in entry.get("subcommands") or []:
        node.add_subcommand(s.get("name", ""), s.get("desc", ""))
    node.probe_meta = dict(entry)
    return node


# ---------------------------------------------------------------- 配置（profiles）

def list_profiles(cli_name: str, root: pathlib.Path | str | None = None) -> list:
    return sorted(load_profile_file(cli_name, root)["profiles"])


def has_profiles(cli_name: str, root: pathlib.Path | str | None = None) -> bool:
    return bool(load_profile_file(cli_name, root)["profiles"])


def get_profile(cli_name: str, name: str, root: pathlib.Path | str | None = None) -> dict:
    data = load_profile_file(cli_name, root)
    prof = data["profiles"].get(name)
    if not isinstance(prof, dict):
        return {"note": "", "values": {}}
    prof.setdefault("values", {})
    return prof


def active_profile(cli_name: str, root: pathlib.Path | str | None = None) -> str:
    data = load_profile_file(cli_name, root)
    active = data.get("activeProfile") or ""
    if active and active in data["profiles"]:
        return active
    return sorted(data["profiles"])[0] if data["profiles"] else ""


def save_values(cli_name: str, name: str, values: dict, root: pathlib.Path | str | None = None,
                note: str | None = None) -> pathlib.Path:
    data = load_profile_file(cli_name, root)
    prof = data["profiles"].setdefault(name, {"note": "", "createdAt": _now(), "values": {}})
    prof["values"] = {k: v for k, v in (values or {}).items() if v is not None}
    prof["updatedAt"] = _now()
    if note is not None:
        prof["note"] = note
    prof.setdefault("createdAt", _now())
    data["activeProfile"] = name
    return _write(cli_name, data, root)


def create_profile(cli_name: str, name: str, values: dict, root: pathlib.Path | str | None = None,
                   note: str = "") -> pathlib.Path:
    """「另存为」：把当前参数值存成一个新配置并起名。"""
    return save_values(cli_name, name, values, root=root, note=note)


def rename_profile(cli_name: str, old: str, new: str, root: pathlib.Path | str | None = None):
    data = load_profile_file(cli_name, root)
    if old in data["profiles"] and new and new not in data["profiles"]:
        data["profiles"][new] = data["profiles"].pop(old)
        if data.get("activeProfile") == old:
            data["activeProfile"] = new
        _write(cli_name, data, root)
    return data


def delete_profile(cli_name: str, name: str, root: pathlib.Path | str | None = None):
    data = load_profile_file(cli_name, root)
    data["profiles"].pop(name, None)
    if data.get("activeProfile") == name:
        data["activeProfile"] = sorted(data["profiles"])[0] if data["profiles"] else ""
    _write(cli_name, data, root)
    return data


def set_active(cli_name: str, name: str, root: pathlib.Path | str | None = None):
    data = load_profile_file(cli_name, root)
    data["activeProfile"] = name
    _write(cli_name, data, root)
    return data


# ---------------------------------------------------------------- 参数说明（notes）

def set_note(cli_name: str, key: str, text: str, root: pathlib.Path | str | None = None,
             profile: str | None = None) -> pathlib.Path:
    """写「自己的参数说明」。profile=None ⇒ 文件级（对本 CLI 所有配置生效）；
    给了 profile ⇒ 只对该配置生效。空文本 = 清除，回到 help 原文。"""
    data = load_profile_file(cli_name, root)
    text = (text or "").strip()
    if profile:
        prof = data["profiles"].setdefault(profile, {"note": "", "createdAt": _now(), "values": {}})
        notes = prof.setdefault("notes", {})
        if text:
            notes[key] = text
        else:
            notes.pop(key, None)
        if not notes:
            prof.pop("notes", None)
    else:
        notes = data.setdefault("notes", {})
        if text:
            notes[key] = text
        else:
            notes.pop(key, None)
    return _write(cli_name, data, root)


def get_note(cli_name: str, key: str, root: pathlib.Path | str | None = None,
             profile: str | None = None) -> tuple:
    """返回 (说明文本, 来源)，来源 ∈ {"profile", "file", ""}。"""
    data = load_profile_file(cli_name, root)
    if profile:
        n = ((data["profiles"].get(profile) or {}).get("notes") or {}).get(key)
        if n:
            return n, "profile"
    n = (data.get("notes") or {}).get(key)
    if n:
        return n, "file"
    return "", ""


def all_notes(cli_name: str, root: pathlib.Path | str | None = None,
              profile: str | None = None) -> dict:
    data = load_profile_file(cli_name, root)
    out = {k: (v, "file") for k, v in (data.get("notes") or {}).items()}
    if profile:
        for k, v in ((data["profiles"].get(profile) or {}).get("notes") or {}).items():
            out[k] = (v, "profile")
    return out
