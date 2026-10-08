# Parsing rules

**English** | [中文](parsing-rules.zh-CN.md) | [Español](parsing-rules.es.md)

> Part of the **CliTree** documentation — back to the [README](../README.md).

This chapter explains "how help text becomes an argument tree", plus where the rules live, how to edit
them and how to verify them.

## 1. Channels: getting the help text first

Order: `--help` → `-h` → `/?` → `-?` → `help` → `-help`, each one really executed, stopping at the first hit.

**Judgement looks at the output content only; rc is completely untrustworthy** — this is not theory, it
is measured:

| Command | rc | What actually happened |
|---|---|---|
| `git clone -h` | **129** | Printed the complete concise help |
| `ping -h` | **2** | Printed the full help with 20 parameters |
| `ip --help` / `ssh --help` | **255** | Had output (ssh only one usage line) |
| `npm --help` | 1 | Had output |
| `dotnet --help` | 0 | Took 314 ms to return (hence the 5-second per-channel timeout) |

**Quality grading**: once the text is in hand it is graded into three buckets — `full` (≥3 parameter
blocks), `weak` (has content but weak structure), `usage-only` (a usage line and nothing else).
In the UI, `weak` / `usage-only` say explicitly "the help is too terse, the parse result may be
incomplete", and **a 27-byte `nslookup --help` is never treated as "this command has no parameters"**.

Distribution over the 105 real commands on this machine: `full` **76**, `weak` **15**, `usage-only`
**14**; zero blocks (no parameters obtained) 27.

## 2. Safety policy (written into the rules file)

1. **Dangerous commands are never probed and never executed**: `shutdown`, `reboot`, `halt`,
   `poweroff`, `init`, `telinit`, `mkfs*`, `dd`, `fdisk`, `parted`, `mkswap`, `swapon`, `swapoff`,
   `wipefs`, `blkdiscard`, `passwd`, `userdel`, `groupdel`, `chpasswd`, `visudo`, `at`, `batch` —
   24 in total, refused at every entry point.
2. **`-h` must be declared first**: `-h` may only be run when the `--help` text says `-h … help`
   (or the command is on the measured whitelist).
   Why: `sort -h`, `df -h`, `du -h`, `free -h` **are not help** — they run the command unconditionally.
3. **Never page, never interact**: stdin is closed, `PAGER`/`MANPAGER`/`GIT_PAGER`/`SYSTEMD_PAGER` are
   all set to `cat`, the per-channel timeout is 5 seconds and the output cap is 256 KB
   (measured over the 105 commands on this machine: 0 timeouts, 0 hangs).
4. **Interactive CLIs use a dedicated channel**: `gdb --help` is only 3 071 B, while
   `gdb -batch -ex "help all"` is **111 781 B (36 times more)**, and its syntax is completely different
   (`awatch -- Set an access watchpoint…` plus `Command class:` groupings).
   The rules file configures `interactiveChannels` per command name.

## 3. The four dialects

| Dialect | How it is detected | Example | How it is parsed |
|---|---|---|---|
| `man-page` | The first line looks like `GIT-CLONE(1)` | `git clone --help` | Not counted as success; fall back to `-h` |
| `dashdash-interactive` | Contains `Command class:` or ≥5 lines of `name -- description` | `gdb -batch -ex "help all"` | Parsed as gdb syntax (a re-run on this machine matched 170/1531 lines) |
| `usage-posix` | Has `usage:` / `用法:` / `使用情况:` | The vast majority | Block model |
| `blocks-only` | No usage line but there are parameter blocks | `curl --help all` | Block model as well |

## 4. The block model (the core of the parser)

**The unit is a "block", not a "line".** Measured shapes:

```
  -v, --version                       ← the option name sits on a line of its own
          Print the pnpm version      ← the description is on the next line, indented deeper ⇒ merged into the same block

  -A, --catenate, --concatenate   追加 tar 文件至归档     ← one option with three aliases
      --occurrence[=NUMBER]  仅处理归档中每个文件的第 NUMBER
                             --diff, --extract 或是 --list   ← a word on a continuation line is **not** a new parameter
```

Rule highlights (all in the `optionBlock` section of `clitree/rules/default.rules.json`):

- `joinContinuation: true` plus `continuationMinExtraIndent: 2`: lines indented deeper merge into the
  previous block;
- `nameToken`: `--[A-Za-z][\w-]*` or `-[A-Za-z][\w-]*` — **single-dash long names must be supported**
  (GNU's `-pass-exit-codes`);
- `valueToken` must be **adjacent to the parameter name**: `-c <count>` takes a value, whereas the
  `SO_DEBUG` in `-d      use SO_DEBUG socket option` is merely a word in the description
  (it used to be misread as a value; fixed);
- The `--[no-]color` shape is normalised to `--color` and flagged as "tri-state".

Section titles use **structural detection first, word list as a fallback**: titles are an open set
(measured on this machine, besides `options`/`usage` there are one-off titles such as
`main operation mode` and `valid arguments for -d`), so a word list cannot enumerate them.

## 5. Subcommands: unreliable, hence lazy loading

| Sample | Extracted count | Real or not |
|---|---|---|
| `pnpm --help` | 91 | **Real** (pnpm does have many commands, and no false positives such as `verbose`/`color`) |
| `git help -a` | 141 | Real |
| `git --help` (Chinese) | 22 | Real (a grouped list; group titles do not end the section) |
| `lsblk --help` | 0 | Real (`Available output columns:` is a list of **column names**, once mis-extracted as 54 subcommands; a fallback condition now blocks it) |

Hence: **loading produces 2 levels only** (this command's parameters plus the first-level subcommand
list, with the subcommands marked "not expanded"), and a subcommand's help is probed only when you
open it; there is also an "Expand all" button (capped at 3 levels).

## 6. The required/optional rule

- **A usage line exists** ⇒ options **always count as optional** (they can simply be omitted) and only
  **positional arguments** are split into required/optional
  (written outside `[]` in the usage line ⇒ required);
- **No usage line at all** ⇒ show "? undetermined" instead of pretending to know;
- UI sorting: **positional arguments first → then required → the rest in the original help order**.

This rule was earned by fixing a bug: in `ping [options] <destination>` only the positional argument
falls in the required position, and an early implementation treated "the option is not mentioned in
usage" as "unmarked", so all 32 ping options ended up carrying `[unmarked]`.

## 7. Widget inference order

Judged top to bottom, stopping at the first hit (implemented in `core/widgets.py`; **every decision
produces an inference reason**, and the type can be changed with a right-click in the UI):

| Order | Condition | Widget |
|---|---|---|
| 1 | A user override (`widgets.overrides`) | Whatever the user chose |
| 2 | Help spells it as `--[no-]xyz` | Tri-state dropdown |
| 3 | The description contains `...` / `multiple times` | Multi-value list |
| 4 | The block has **no value marker** | **Checkbox** (+ the help explanation) |
| 5 | The description contains `one of` and the shape is `<a\|b\|c>` | **Editable dropdown** |
| 6 | The value name/description hits `numericWords` (`count`/`ttl`/`timeout`…) | Number box |
| 7 | It hits `pathWords` (`file`/`dir`/`interface`…) | Text box + "Browse…" |
| 8 | Anything else | Text box (marked "undetermined", changeable) |

⚠️ **Do not treat `curl -b <data|filename>` as an enum**: that is a "value shape", not a set; the rules
carry a `reject` blacklist for it.
Measured: out of 105 real commands, help gives an explicit value set in **only two places, `ping -M` /
`-T`** — hence dropdowns are always **editable** and no candidates are invented when nothing is found.

## 8. Rules file reference

`clitree/rules/default.rules.json` (strict JSON, `rulesVersion: 3`):

| Section | Purpose |
|---|---|
| `evidence` | The measured numbers the rules rest on (the distribution over 105 commands and so on), kept for later comparison |
| `dialects.detect` | Dialect detection order and regexes |
| `helpChannels` | Channel order, the `-h` declaration requirement, the measured whitelist, interactive channels, the 24 dangerous commands, timeouts and caps |
| `segments` | The section word list (structural detection first, the list is only a fallback) |
| `optionBlock` | Block merging and the name/value regexes |
| `widgets` | Widget inference word lists, the enum table, overrides |
| `subcommands` | `initialDepth: 2`, `lazyExpand`, `maxDepth: 3`, the fallback condition |
| `manPage` / `locale` / `limits` | man-page fallback, `LC_ALL=C` probing first, concurrency and log caps |

**Do not edit the packaged file with your own changes**: write
`~/.config/clitree/rules.user.json` (or the platform equivalent) instead — it is **deep-merged** on top
of the default rules (right-clicking a widget type in the GUI goes down exactly this path).

## 9. How to iterate on the rules

```bash
# 1) edit the rules
$EDITOR clitree/rules/default.rules.json
python3 -m clitree --check-rules          # bad JSON / bad regex is reported at once (non-zero exit)

# 2) look at the effect on a real command
python3 -m clitree --parse ping
python3 -m clitree --parse --help-file /tmp/some-tool--help.txt

# 3) run the regression (the fixtures are 27 real help texts)
python3 -m pytest tests/test_parser_blocks.py tests/test_widgets.py -q
```

To add a fixture: `<command> --help > tests/fixtures/help/<command>.help.txt`, keeping the file name
shape `<tool>.help.txt`, and add an assertion in the tests (shape, count, or widget type).
