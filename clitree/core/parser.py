"""块模型解析器：把 help 文本变成结构化的参数/子命令。

设计依据（全部来自本机实测，见 plans/clitree.plan.md §11）：
- 单位是「块」不是「行」：选项名可能与其描述分处两行（pnpm/python3/tar 实测）。
- 续行优先：续行里出现的 `-x` 词（tar 的 `--delete, --extract`）绝不能变成新参数。
- 段落标题是开放集合 ⇒ 结构判定优先、词表兜底。
- 方言：usage-posix / dashdash-interactive（gdb）/ man-page / blocks-only。
"""
from __future__ import annotations

import re

from . import widgets as W
from .model import ParamSpec, ParseResult, Subcommand

PLACEHOLDER_SKIP = {"options", "option", "flags", "选项"}

# usage 里「选项名 + 它的取值」片段：这些 `<path>` / `<name>=<value>` 不是位置参数
_OPT_WITH_VALUE = re.compile(
    r"(?<![\w-])(--?[A-Za-z][\w-]*)(\s*[ =]\s*)?(<[^>]*>(=<[^>]*>)?|\[=[^\]]+\])?")


# ---------------------------------------------------------------- 基础工具

def _indent(s: str) -> int:
    return len(s) - len(s.lstrip(" "))


def _nonempty(lines, start):
    for j in range(start + 1, len(lines)):
        if lines[j].strip():
            return lines[j]
    return ""


def _is_man_page(text: str, rules: dict) -> bool:
    lines = text.splitlines()
    if not lines:
        return False
    pats = (rules.get("manPage") or {}).get("detect") or []
    first = lines[0].strip()
    for p in pats:
        try:
            if re.match(p, first):
                return True
        except re.error:
            continue
    return False


def _dialect(text: str, rules: dict) -> str:
    lines = text.splitlines()
    if _is_man_page(text, rules):
        return "man-page"
    cfg = rules.get("dashdashInteractive") or {}
    det = (rules.get("dialects") or {}).get("detect") or []
    for entry in det:
        if entry.get("name") != "dashdash-interactive":
            continue
        if entry.get("anyLineMatches"):
            for l in lines:
                if re.search(entry["anyLineMatches"], l):
                    return "dashdash-interactive"
        cond = entry.get("orLineCount") or {}
        if cond:
            rx = re.compile(cond.get("pattern") or r"$^")
            if sum(1 for l in lines if rx.match(l)) >= int(cond.get("min", 5)):
                return "dashdash-interactive"
    if cfg and re.search(cfg.get("classHeader") or r"$^", text, re.M):
        return "dashdash-interactive"
    for entry in det:
        pat = entry.get("anyLineMatches")
        if pat and re.search(pat, text, re.M | re.I):
            return entry.get("name", "usage-posix")
    return "blocks-only"


def _is_title(line: str, next_line: str, rules: dict) -> bool:
    s = line.strip()
    if not s or s.startswith("-"):
        return False
    if len(s) > 48:
        return False
    if re.match(r"^\s*(usage|用法|使用情况|synopsis)\s*[:：]", line, re.I):
        return False
    if s.endswith((".", ",", ";", "）)")) and not s.endswith(":"):
        return False
    if s.endswith((":", "：")):
        return True
    if _indent(line) == 0 and len(s.split()) <= 8 and next_line and _indent(next_line) > 0:
        return True
    return False


def _section_of(title: str, rules: dict) -> str:
    low = title.lower().rstrip(":：").strip()
    segs = rules.get("segments") or {}
    for key in ("usage", "commands", "options"):
        for word in segs.get(key) or []:
            if word.lower() in low:
                return key
    return "other"


def _blocks(lines, rules: dict):
    """把行合并成块：块首 = 以 '-' 开头的选项定义行；更深的缩进行是它的续行。

    注意块首判定**不能**依赖名字正则：`--[no-]color` 这类形态名字里带 `[`，实测存在。
    """
    out, cur = [], None
    for raw in lines:
        s = raw.rstrip()
        if not s.strip():
            continue
        st = s.strip()
        if st.startswith("-") and len(st) > 1:
            if cur:
                out.append(cur)
            cur = [s]
        elif cur is not None and _indent(s) > _indent(cur[0]):
            cur.append(s)
        else:
            if cur:
                out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    return out


# ---------------------------------------------------------------- 选项块

_NEG_FORM = re.compile(r"--\[no-\]([A-Za-z][\w-]*)")


def _parse_option_block(block, rules: dict, cmd: str) -> ParamSpec | None:
    head = block[0]
    continuations = [x.strip() for x in block[1:]]
    normalized = _NEG_FORM.sub(lambda m: "--" + m.group(1), head)
    negatable = normalized != head

    tok = re.compile((rules.get("optionBlock") or {}).get("nameToken") or r"(?<![-\w])--[\w-]+")
    names = [m.group(0) for m in tok.finditer(normalized)]
    if not names:
        return None

    tail_start = max(m.end() for m in tok.finditer(normalized))
    tail = normalized[tail_start:]

    val_pat = ((rules.get("optionBlock") or {}).get("valueToken")
               or r"(<[^>]+>|\[=[^\]]+\]|[A-Z][A-Z0-9_]{1,})")
    takes_value = False
    value_token = None
    # 取值 token 必须**紧贴**参数名（实测：`-c <count>` 是取值，而
    # `-d      use SO_DEBUG socket option` 里的 SO_DEBUG 只是描述里的词，不是取值）
    adjacent = rules.get("optionBlock", {}).get("valueMustBeAdjacentToName", True)
    m = re.match(r"[ \t]{0,2}(" + val_pat + r")", tail) if adjacent else re.search(val_pat, tail)
    if m:
        takes_value = True
        value_token = m.group(1)
        tail = tail[:m.start()] + " " + tail[m.end():]
    else:
        m2 = re.match(r"\s*([A-Za-z][\w.-]*)\s*[:：]", tail)
        if m2 and m2.group(1).lower() not in PLACEHOLDER_SKIP:
            takes_value = True
            value_token = m2.group(1)
            tail = tail[m2.end():]
        elif re.search(r"=\S|\{[^}]*\}", tail):
            takes_value = True
            em = re.search(r"=\s*(\S+)", tail)
            value_token = em.group(1) if em else None

    desc = " ".join(x for x in [tail.strip().strip(":").strip()] + continuations if x).strip()
    spec = ParamSpec(names=names, takes_value=takes_value, desc=desc, value_token=value_token,
                     negatable=negatable)
    return spec


# ---------------------------------------------------------------- 子命令段

_SUB_RE = re.compile(r"^\s{2,}([A-Za-z][\w.+-]*)\s{2,}(\S.*)$")


def _parse_subcommands(lines, rules: dict):
    subs, seen = [], set()
    for l in lines:
        if l.lstrip().startswith("-"):
            continue
        m = _SUB_RE.match(l)
        if not m:
            continue
        name, desc = m.group(1), m.group(2).strip()
        if name in seen or name.lower() in PLACEHOLDER_SKIP:
            continue
        seen.add(name)
        subs.append(Subcommand(name=name, desc=desc))
    return subs


# ---------------------------------------------------------------- usage 行

def _usage_line(text: str) -> str:
    """usage 行的两种实测形态：
    ① `usage: prog [options] <target>`（同行）
    ② `Usage` 单独一行，下一缩进行才是用法（iputils ping 实测）
    """
    parts: list[str] = []
    lines = text.splitlines()
    same_line = re.compile(r"(?i)^\s*(usage|用法|使用情况|synopsis)\s*[:：]\s*\S")
    title_only = re.compile(r"(?i)^\s*(usage|用法|使用情况|synopsis)\s*[:：]?\s*$")
    for i, l in enumerate(lines):
        if same_line.match(l):
            parts.append(l.strip())
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j]
                if nxt.strip() and nxt.startswith((" ", "\t")) and not nxt.strip().startswith("-"):
                    parts.append(nxt.strip())
                else:
                    break
            break
        if title_only.match(l):
            for j in range(i + 1, min(i + 4, len(lines))):
                nxt = lines[j]
                if nxt.strip() and nxt.startswith((" ", "\t")) and not nxt.strip().startswith("-"):
                    parts.append(nxt.strip())
                elif nxt.strip():
                    break
            break
    return " ".join(parts)


def _positionals(usage: str) -> list[ParamSpec]:
    """位置参数 = usage 里**裸的** `<占位符>`（选项的取值不算）。

    支持中文占位符（`用法：git clone [<选项>] [--] <仓库> [<路径>]` 实测），
    并先剔掉 `-C <path>` / `-c <name>=<value>` 这类选项取值。
    """
    out, idx = [], 0
    if not usage:
        return out
    bare = _OPT_WITH_VALUE.sub(" ", usage)
    required_part = re.sub(r"\[[^\]]*\]", " ", bare)
    for m in re.finditer(r"<([^>\s]+)>", bare):
        name = m.group(1)
        if name.lower() in PLACEHOLDER_SKIP:
            continue
        required = "required" if m.group(0) in required_part else "optional"
        out.append(ParamSpec(names=[], takes_value=True, desc=f"位置参数 <{name}>",
                             value_token=m.group(0), required=required, position=idx,
                             widget="text", widget_reason="位置参数：usage 行里出现，必按顺序传"))
        idx += 1
    return out


def _exclusive_groups(usage: str, options: list[ParamSpec]) -> None:
    for gi, m in enumerate(re.finditer(r"\[([^\]]*\|[^\]]*)\]", usage or "")):
        body = m.group(1)
        members = [x.strip() for x in body.split("|")]
        members = [x for x in members if x.startswith("-")]
        if len(members) < 2:
            continue
        gid = f"grp{gi}"
        for opt in options:
            if any(n in members for n in opt.names):
                opt.group = gid


def _apply_usage(usage: str, options: list[ParamSpec]) -> bool:
    """按 usage 行定必填。返回 True 表示「usage 行确实给了判定依据」。

    实测口径（2026-10 修订）：`ping [options] <destination>` 这类 usage 里，
    **选项一律是可选**（不传也能跑），只有位置参数才分必填/可选；
    连 usage 行都没有时保持 unknown（如实标「未判定」，不假装知道）。
    """
    if not usage:
        return False
    for opt in options:
        opt.required = "optional"          # 默认：选项就是可选
    for opt in options:
        hit = [n for n in opt.names if re.search(r"(?<![\w-])" + re.escape(n) + r"(?![\w-])", usage)]
        if not hit:
            continue
        name = hit[0]
        inside = re.search(r"\[[^\]]*" + re.escape(name) + r"[^\]]*\]", usage)
        opt.required = "optional" if inside else "required"
    return True


# ---------------------------------------------------------------- 方言解析

def _parse_dashdash(text: str, rules: dict) -> list[ParamSpec]:
    cfg = rules.get("dashdashInteractive") or {}
    rx = re.compile(cfg.get("definitionLine") or r"^\s*([A-Za-z][\w-]*)\s+--\s+(.+)$")
    splitter = cfg.get("aliasesSplit") or r",\s*"
    out = []
    for line in text.splitlines():
        m = rx.match(line)
        if not m:
            continue
        names = [x.strip() for x in re.split(splitter, m.group(1).strip()) if x.strip()]
        desc = m.group(2).strip()
        spec = ParamSpec(names=names, takes_value=False, desc=desc,
                         widget="checkbox", widget_reason="交互式子命令：无取值，选中即执行")
        out.append(spec)
    return out


# ---------------------------------------------------------------- 分级 / 入口

def grade_of(text: str, rules: dict) -> str:
    if _is_man_page(text, rules):
        return "man-page"
    if _dialect(text, rules) == "dashdash-interactive":
        n = sum(1 for l in text.splitlines()
                if re.match(r"^[A-Za-z][\w-]*(?:, ?[\w-]+)* -- \S", l))
        return "full" if n >= 3 else "usage-only"
    lines = [l for l in text.splitlines() if l.strip()]
    if not lines:
        return "usage-only"
    blocks = _blocks(lines, rules)
    if len(blocks) >= 3:
        return "full"
    if len(lines) <= 3 or len(blocks) <= 1:
        return "usage-only"
    return "weak"


def parse_help(text: str, rules: dict, cmd: str = "") -> ParseResult:
    text = text or ""
    dialect = _dialect(text, rules)
    grade = grade_of(text, rules)
    res = ParseResult(dialect=dialect, grade=grade, raw_text=text)

    if dialect == "man-page":
        return res

    if dialect == "dashdash-interactive":
        res.commands = _parse_dashdash(text, rules)
        return res

    lines = [l.rstrip() for l in text.splitlines()]
    sections: list[tuple[str, list[str]]] = []
    cur_name, cur_lines = "preamble", []
    for i, line in enumerate(lines):
        if _is_title(line, _nonempty(lines, i), rules):
            sec = _section_of(line, rules)
            if sec in ("usage", "commands", "options"):
                sections.append((cur_name, cur_lines))
                cur_name, cur_lines = sec, []
                continue
            if cur_name in ("commands", "options"):
                cur_lines.append(line)          # 组内小标题，不结束本段（实测 git 中文分组）
                continue
            sections.append((cur_name, cur_lines))
            cur_name, cur_lines = sec, []
            continue
        cur_lines.append(line)
    sections.append((cur_name, cur_lines))

    usage = _usage_line(text)
    res.usage_line = usage

    subs: list[Subcommand] = []
    options: list[ParamSpec] = []
    commands_section_lines: list[str] = []
    for name, body in sections:
        if name == "commands":
            commands_section_lines += body
        elif name == "options":
            for block in _blocks(body, rules):
                spec = _parse_option_block(block, rules, cmd)
                if spec:
                    options.append(spec)

    if commands_section_lines:
        subs = _parse_subcommands(commands_section_lines, rules)
    elif re.search(r"(?i)\bcommand(s)?\b|命令", text):
        # 只有文本里真的出现过「命令」字样才做全文兜底（git help -a 这类）；
        # 否则 lsblk 会把 "Available output columns" 的列名当成 54 个子命令。
        subs = _parse_subcommands([l for l in lines if not l.lstrip().startswith("-")], rules)
        res.subcommands_uncertain = not subs

    # 兜底：不少工具的 help 没有 "Options:" 标题（curl --help all 实测），
    # 这时对整段做块解析，否则参数树会整个空掉。
    if not options:
        pool = [l for name, body in sections if name != "commands" for l in body]
        for block in _blocks(pool or lines, rules):
            spec = _parse_option_block(block, rules, cmd)
            if spec:
                options.append(spec)

    res.subcommands = subs
    res.subcommands_uncertain = res.subcommands_uncertain or (
        bool(commands_section_lines) and len(subs) < 2)

    for spec in options:
        kind, why = W.infer_widget(spec, rules, cmd=cmd)
        spec.widget, spec.widget_reason = kind, why
        if spec.choices is None:
            spec.choices = W.extract_choices(spec.names, spec.desc, spec.value_token, rules)
        spec.default = spec.default or W.extract_default(spec.desc)
        spec.example = spec.example or W.extract_example(spec.desc)
        if any(w in spec.desc.lower() for w in
               [x.lower() for x in (rules.get("widgets") or {}).get("repeatMarkers") or []]):
            spec.repeatable = True

    positionals = _positionals(usage)
    res.usage_marks_required = _apply_usage(usage, options)
    _exclusive_groups(usage, options)

    res.options = options
    res.positionals = positionals
    return res
