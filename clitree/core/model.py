"""数据结构：参数、命令节点、解析结果。"""
from __future__ import annotations

from dataclasses import dataclass, field

WIDGET_KINDS = ("checkbox", "combo", "spin", "text", "path", "tristate", "multi")
REQUIRED_STATES = ("required", "optional", "unknown")
LOAD_STATES = ("pending", "loading", "loaded", "failed")


@dataclass
class ParamSpec:
    names: list[str] = field(default_factory=list)
    takes_value: bool = False
    desc: str = ""
    value_token: str | None = None
    required: str = "unknown"
    default: str | None = None
    example: str | None = None
    choices: list[str] | None = None
    widget: str = "text"
    widget_reason: str = ""
    repeatable: bool = False
    group: str | None = None
    position: int | None = None
    key: str = ""
    negatable: bool = False

    def __post_init__(self):
        if not self.key:
            longs = [n for n in self.names if n.startswith("--")]
            self.key = longs[0] if longs else (self.names[0] if self.names else
                                               ("@%d" % self.position if self.position is not None else "?"))

    @property
    def label(self) -> str:
        if self.names:
            return ", ".join(self.names)
        return "<位置参数 %s>" % (self.position if self.position is not None else "?")

    FIELDS = ("names", "takes_value", "desc", "value_token", "required", "default", "example",
              "choices", "widget", "widget_reason", "repeatable", "group", "position", "key",
              "negatable")

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.FIELDS}

    @classmethod
    def from_dict(cls, d: dict) -> "ParamSpec":
        known = {f: d.get(f) for f in cls.FIELDS if f in d}
        spec = cls(**known)
        if not spec.key:
            spec.__post_init__()
        return spec

    def value_keys(self) -> list[str]:
        keys = [self.key] + list(self.names)
        if self.position is not None:
            keys.append("@%d" % self.position)
        return keys


@dataclass
class Subcommand:
    name: str
    desc: str = ""


@dataclass
class ParseResult:
    options: list[ParamSpec] = field(default_factory=list)
    commands: list[ParamSpec] = field(default_factory=list)   # dashdash-interactive 方言
    positionals: list[ParamSpec] = field(default_factory=list)
    subcommands: list[Subcommand] = field(default_factory=list)
    dialect: str = "unknown"
    grade: str = "usage-only"
    raw_text: str = ""
    usage_line: str = ""
    subcommands_uncertain: bool = False
    usage_marks_required: bool = False   # usage 行是否给出了必填判定依据

    def find(self, name: str) -> ParamSpec | None:
        for o in list(self.options) + list(self.positionals):
            if name in o.names:
                return o
        return None


@dataclass
class CommandNode:
    name: str
    path: list[str] = field(default_factory=list)
    desc: str = ""
    options: list[ParamSpec] = field(default_factory=list)
    subcommands: list["CommandNode"] = field(default_factory=list)
    parent: "CommandNode | None" = None
    load_state: str = "pending"
    error: str | None = None
    dialect: str = ""
    grade: str = ""
    raw_text: str = ""
    parsed_at: str = ""
    probe_meta: dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.path:
            self.path = [self.name]

    @property
    def depth(self) -> int:
        return len(self.path)

    def add_subcommand(self, name: str, desc: str = "") -> "CommandNode":
        child = CommandNode(name=name, path=self.path + [name], desc=desc, parent=self,
                            load_state="pending")
        self.subcommands.append(child)
        return child

    def find_child(self, name: str) -> "CommandNode | None":
        for c in self.subcommands:
            if c.name == name:
                return c
        return None

    def find_option(self, key: str) -> ParamSpec | None:
        for o in self.options:
            if key in o.value_keys():
                return o
        return None

    def walk(self):
        yield self
        for c in self.subcommands:
            yield from c.walk()
