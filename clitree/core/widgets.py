"""参数 → 控件类型推断（计划 §5.5 的映射表；每条判定都带推断依据）。"""
from __future__ import annotations

import re

_ENUM_SHAPE = re.compile(r"<([A-Za-z0-9_.|-]{3,})>")
_BRACE_SHAPE = re.compile(r"\{([^{}]{3,})\}")
_DEFAULT_PATTERNS = (
    re.compile(r"\[default:\s*([^\]]+)\]", re.I),
    re.compile(r"\(default:\s*([^)]+)\)", re.I),
    re.compile(r"默认(?:值)?\s*[:：]\s*([^\s)）,，。]+)"),
)
_EXAMPLE_PATTERNS = (
    re.compile(r"e\.g\.,?\s*([^;)]+)", re.I),
    re.compile(r"例如\s*[:：]?\s*([^;，。)]+)"),
    re.compile(r"如\s*[:：]\s*([^;，。)]+)"),
)


def _words(rules: dict, key: str) -> list[str]:
    return [w.lower() for w in (rules.get("widgets") or {}).get(key) or []]


def extract_choices(spec_names: list[str], desc: str, value_token: str | None,
                    rules: dict) -> list[str] | None:
    cfg = (rules.get("widgets") or {}).get("enumFromHelp") or {}
    phrases = [p.lower() for p in cfg.get("phrases") or []]
    hay = f"{value_token or ''} {desc}"
    for rej in cfg.get("reject") or []:
        if rej and rej in hay:
            return None
    if not any(p in desc.lower() for p in phrases):
        return None
    for rx in (_ENUM_SHAPE, _BRACE_SHAPE):
        for m in rx.finditer(hay):
            body = m.group(1)
            if "|" in body:
                return [x.strip() for x in body.split("|") if x.strip()]
    return None


def extract_default(desc: str) -> str | None:
    for rx in _DEFAULT_PATTERNS:
        m = rx.search(desc)
        if m:
            return m.group(1).strip()
    return None


def extract_example(desc: str) -> str | None:
    for rx in _EXAMPLE_PATTERNS:
        m = rx.search(desc)
        if m:
            return m.group(1).strip().rstrip(".")
    return None


def infer_widget(spec, rules: dict, cmd: str = "") -> tuple[str, str]:
    """返回 (控件类型, 推断依据)。判定顺序即计划 §5.5 的表。"""
    names = list(spec.names)
    desc = spec.desc or ""

    overrides = ((rules.get("widgets") or {}).get("overrides") or {})
    for candidate in (cmd, (cmd or "").split("/")[-1]):
        table = overrides.get(candidate) or {}
        for name in names + ([spec.key] if spec.key else []):
            if name in table:
                return table[name], f"规则覆盖：用户在 rules.user.json 指定 {name} 为 {table[name]}"

    if getattr(spec, "negatable", False):
        return "tristate", "判为三态：help 写的是 --[no-] 形态（布尔开关）"

    if any(w in desc.lower() for w in _words(rules, "repeatMarkers")):
        return "multi", "判为多值：描述标明可重复（... / multiple times）"

    if not spec.takes_value:
        return "checkbox", "判为开关：该参数在 help 里未标注任何取值"

    choices = extract_choices(names, desc, spec.value_token, rules)
    if choices:
        return "combo", f"判为下拉：描述含 one of 且形态为 <{'|'.join(choices)}>"

    hay = f"{spec.value_token or ''} {desc}".lower()
    if any(w in hay for w in _words(rules, "boolWords")):
        return "tristate", "判为三态：取值/描述是布尔语义（true|false / [no-] 形态）"

    if any(w in hay for w in _words(rules, "numericWords")):
        return "spin", f"判为数值：取值名/描述命中数字语义（{spec.value_token or desc[:20]}）"

    if any(w in hay for w in _words(rules, "pathWords")):
        return "path", f"判为路径：取值名/描述命中路径语义（{spec.value_token or desc[:20]}）"

    fallback = (rules.get("widgets") or {}).get("fallback", "text")
    return fallback, "未确定：help 未给出足够信息，可右键改成其它控件类型"
