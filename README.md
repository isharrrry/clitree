# CliTree — turn command-line tools into a clickable argument tree

**English** | [中文](README.zh-CN.md) | [Español](README.es.md)

> Drag in an executable (or type a command) → click **Load** → the argument tree appears on the left,
> widgets shaped to each parameter appear on the right, and the three buttons below run it as a
> **new-terminal / background / silent** run. No need to memorize `--help`, no need to type in a shell.

Cross-platform (Windows / Linux / macOS), pure Python + PyQt5; the only dependencies are the system Python and Qt.

![Argument panel after loading ping](screenshots/01-load-ping-widgets.png)

## What problem it solves

A command-line tool's usage hides inside its `help`: parameter names are abbreviations only, the
description is one line, you must read the usage line yourself to tell what is required, and enum
values are scattered through the prose. CliTree **parses all of that into structured data** and
renders it as an operable interface:

- **Argument tree**: the command's own parameters plus its first-level subcommands; **a subcommand's
  help is only probed when you open it**, not all at once;
- **Widgets shaped to each parameter**: a parameter that takes no value gets a **checkbox**, one with a
  fixed value set gets an **editable dropdown**, numbers get a number box, paths get a "Browse…"
  button, repeatable ones get a multi-value list; every parameter shows **full name + short name +
  value placeholder** and the **original help text**;
- **Notes can be rewritten as your own**: double-click the note line to edit it — it is written into
  the configuration file and is still there next time;
- **Three execution modes**: run in a real terminal / run in the background with output streamed back
  into this window / silent run (cursor only, no log). While running, the button turns into
  "■ Stop" and a second click terminates the process; each button's icon remembers its own last result;
- **Profiles are reusable**: one configuration file per tool, holding **multiple profiles**
  (parameter values for different machines or scenarios) and a cached parse result — **loading the
  same tool again does not have to run `help` at all**.

## Quick start

```bash
git clone <your repository URL> clitree && cd clitree

# only the system Python (>=3.9) and PyQt5 are needed
python3 -c "import PyQt5" || python3 -m pip install --user PyQt5

python3 -m clitree                # open the GUI
python3 -m clitree git            # open the GUI and load git right away
```

On a headless machine (no `DISPLAY`), use `xvfb-run -a python3 -m clitree` to open the window;
if you don't want a window at all, use the parse mode directly (see below).

## Interface at a glance

| Only 2 levels after loading | Probing happens when you open a subcommand | Many profiles on one machine | Notes can be rewritten as your own |
|---|---|---|---|
| ![two levels](screenshots/05-git-two-levels-collapsed.png) | ![expanded](screenshots/06-git-clone-expanded.png) | ![profiles](screenshots/11-cli-profiles.png) | ![notes](screenshots/13-custom-note.png) |

| Background output goes into this window | Silent run writes not one line | A running job can be stopped | Dangerous commands are refused |
|---|---|---|---|
| ![background](screenshots/02-run-background-log-ok.png) | ![silent](screenshots/03-run-silent-zero-log.png) | ![stop](screenshots/09-running-stop-button.png) | ![safety](screenshots/08-dangerous-refused.png) |

All 14 screenshots live in [`screenshots/`](screenshots) and can be regenerated with
`xvfb-run -a python3 tools/make_screenshots.py`.

## Command-line usage

Beyond the GUI, CliTree also works as a parser (handy for scripting and for debugging rules):

```bash
python3 -m clitree --parse ping                 # really probe ping and print the parse result
python3 -m clitree --parse --help-file help.txt # parse a help text file directly
python3 -m clitree --tree git                   # also print the tree (root parsed, subcommands pending)
python3 -m clitree --check-rules                # validate the rules file (bad JSON / bad regex is reported)
python3 -m clitree --dump-rules                 # print the effective rules (defaults + your overrides)
```

## Four core concepts

1. **Parsing is a "block model", not a per-line regex.** An option name and its description often live
   on two lines (`pnpm -v, --version` with the description on the next line), and a continuation line
   may even contain a word such as `--delete` (tar) — CliTree merges by *block*, so a continuation
   never becomes a new parameter. Details in [Parsing rules](docs/parsing-rules.md).
   All parsing behaviour lives in `clitree/rules/default.rules.json` (every rule carries the
   measurement behind it), your overrides go to `~/.config/clitree/rules.user.json`, and
   `python3 -m clitree --check-rules` validates the result.

2. **The required/optional rule**: when a usage line exists, **options always count as optional**
   (they can simply be omitted) and only **positional arguments** are split into required/optional;
   only when there is no usage line at all does the UI show "? undetermined". Required parameters and
   positional arguments are sorted to the top of the form.
3. **A profile is a file**: `cli/<tool-name>.json` holds a **parse-result cache** + **multiple profiles** +
   **your own parameter notes** in one file. The next time you load the same tool it is rendered from
   the cache without running `help`. See [Configuration](docs/configuration.md).
4. **Execution goes through argv only**: parameters are handed to the child process as a list and
   **shell strings are never assembled**; the "extra input" box at the bottom of the form is split on
   whitespace and appended to the end of the command. Platform quoting is applied only when opening a
   new terminal. See [Execution modes](docs/execution-modes.md).

## Safety

- **Dangerous commands are never probed and never executed**: `shutdown` / `reboot` / `mkfs*` / `dd` /
  `fdisk` / `passwd` and 24 commands in total are refused at every entry point (drag-in, typed input,
  cache, execution) with the reason spelled out;
- **`-h` is only run when the `--help` text declares it** (because `sort -h` and `df -h` are not help);
- Every probe closes stdin and sets `PAGER/MANPAGER/GIT_PAGER/SYSTEMD_PAGER=cat` (so paging can never
  hang it), with a 5-second timeout per channel and a 256 KB output cap;
- Opening a new terminal escapes with `shlex.quote` (POSIX) or the Windows quoting rules.

## Documentation

Like the README, the documentation comes in **English / Chinese / Spanish**. Entry point:
[documentation index](docs/index.md).

| To learn about | Read |
|---|---|
| Architecture, module responsibilities, data flow | [architecture](docs/architecture.md) |
| How help is parsed, how to edit the rules file | [parsing-rules](docs/parsing-rules.md) |
| The complete format of `cli/<tool-name>.json` | [configuration](docs/configuration.md) |
| The three execution modes and stop semantics | [execution-modes](docs/execution-modes.md) |
| Contributing, running tests, generating screenshots | [contributing](docs/contributing.md) |
| Module dependencies (auto-generated) | [DEPENDENCY-TREE](docs/DEPENDENCY-TREE.md) |

## Development

```bash
python3 -m pytest -q                              # 165 tests (160 pass; 5 are platform-specific — see Known limitations)
python3 tools/deps_tree.py                        # regenerate the dependency tree
xvfb-run -a python3 tools/make_screenshots.py     # regenerate the 14 screenshots
```

Measured environments: Python 3.10.12 + PyQt5 5.15.6 (Linux) and Python 3.14.6 + PyQt5 5.15.11 (Windows); the tests run under
`QT_QPA_PLATFORM=offscreen`. Development conventions and "what has not been verified" are in
[contributing](docs/contributing.md).

## Measured verification

| Item | Reading |
|---|---|
| Tests | `python3 -m pytest -q` ⇒ **160 passed** (29 real help fixtures, widget inference, probe safety, lazy loading, executor, configuration files, GUI smoke; the other 5 are platform-specific — see [Known limitations](#known-limitations-listed-honestly)) |
| Real CLI parsing | `ping` 33 parameters (`-c` numeric, `-M` dropdown `do/dont/want`, `-I` path, `-D` checkbox)｜`git` 22 subcommands｜`tar` 166 parameters｜`curl --help all` 244 parameters｜`gdb` through its interactive channel: **111 781 B** (its `--help` is only 3 071 B) |
| Windows, measured locally (2026-10) | Windows 11 + Python 3.14.6 + PyQt5 5.15.11: `ping` parses to 18 parameters (bare-word positional `target_name` required, numeric `-4`/`-6`, `-n` as a number box); `ping -n 2 127.0.0.1` runs end-to-end ⇒ rc=0, replies received; both the English and the Chinese (`zh-CN`) help are covered by fixtures |
| Lazy loading | `--tree git` ⇒ root parsed, all 22 subcommands `pending`; expanding the same node twice adds **0** extra probes |
| Cache and profiles | A second window loading `ping` performs **0 probes** (straight from the cache); profile switching, save-as and both note levels are covered in [configuration](docs/configuration.md) |
| Three modes | Background `ping -c 2 127.0.0.1` ⇒ **+6 log lines**, button `ok`; silent run of the same command ⇒ **+0 log lines**, button `ok`; clicking again during `ping -c 30` ⇒ state `stopped` |
| Safety | All 24 dangerous commands are refused at every entry point (loading `/sbin/shutdown` leaves the tree and form empty and states the reason in the status bar) |
| Rules self-check | `python3 -m clitree --check-rules` ⇒ `RULES-CHECK=PASS` (12/12 regexes compile under Python) |
| Screenshots | `xvfb-run -a python3 tools/make_screenshots.py` ⇒ **14 images** (both offscreen and real-X rendering were used) |

Environment: Ubuntu 22.04, Python 3.10.12, PyQt5 5.15.6 (Linux part), plus Windows 11, Python 3.14.6, PyQt5 5.15.11 (Windows part). **No row in this table is an estimate**; anything not measured is listed under [Known limitations](#known-limitations-listed-honestly) and in [contributing](docs/contributing.md).

## Known limitations (listed honestly)

- **Windows is only partially verified (2026-10), macOS not at all**: `ping` parsing/execution and the
  local test suite have been exercised on Windows 11 (see the table above); the `-?` channel, opening a
  terminal via `cmd start`, and packaging are still code-only;
- **Most enum values cannot be extracted**: out of 105 real commands, only `ping` spells a value set
  out in its help (two places) — so dropdowns are always editable and no candidates are invented;
- **Subcommand-section extraction is unreliable**: `pnpm`'s 91 entries are real, while `lsblk`'s column
  section has to be blocked by a fallback condition — that is why only 2 levels are produced on load
  and probing happens on expansion;
- **The new-terminal mode cannot obtain the child's exit code**: it therefore only shows "launched in
  terminal", never judges success or failure, and cannot be stopped.

## License

[MIT](LICENSE).
