# Contributing

**English** | [中文](contributing.zh-CN.md) | [Español](contributing.es.md)

> Part of the **CliTree** documentation — back to the [README](../README.md).

## Environment

| Item | Value (measured on this machine) |
|---|---|
| Interpreter | the system `python3` (3.10.12 measured; `requires-python >= 3.9`) |
| GUI | PyQt5 5.15.6 / Qt 5.15.3 (system packages) |
| Tests | pytest 9.1.1 |

```bash
python3 -c "import PyQt5" || python3 -m pip install --user PyQt5
python3 -m pytest -q                 # 169 items (164 pass; 5 platform-specific)
```

**Do not create a venv** (measured here: `python3 -m ensurepip` does not exist ⇒ a venv has no pip,
and the venv's `sys.path` cannot see `/usr/lib/python3/dist-packages`, so it cannot even import the
system PyQt5). When you need an extra dependency use `python3 -m pip install --user <package>`.

Without a graphical environment (no `DISPLAY` / `WAYLAND_DISPLAY`):

- run the tests: `QT_QPA_PLATFORM=offscreen python3 -m pytest -q` (`tests/conftest.py` already sets this by default);
- look at the window: `xvfb-run -a python3 -m clitree`;
- produce screenshots: `xvfb-run -a python3 tools/make_screenshots.py` (writes into `screenshots/`).

## Test map

| File | Coverage |
|---|---|
| `tests/test_rules.py` | Rule loading, deep-merging user overrides, reporting bad JSON/bad regex |
| `tests/test_parser_blocks.py` | The block model, the four dialects, the required/optional rule, parsing all 29 fixtures one by one |
| `tests/test_parser_subcommands.py` | The subcommand section (including the `lsblk` column-name false positive and the `git help -a` real count) |
| `tests/test_widgets.py` | The widget inference order and every exception (`--[no-]`, repeatable, `curl -b` must not become an enum) |
| `tests/test_discovery.py` | Channel order, untrustworthy rc, dangerous commands refused, man-page fallback, interactive channels |
| `tests/test_lazy.py` | One probe on load, one more on expansion, zero on repeat, the depth cap, retry after failure |
| `tests/test_executor.py` | argv safety, the three modes, stop, terminal adapters |
| `tests/test_profiles.py` | `cli/<tool>.json` caching, multiple profiles, the two note levels, fallback, broken files |
| `tests/test_gui_smoke.py` | Building the window offscreen, load/expand, widget types, double-clicking a note, switching profiles, stop |

`tests/fixtures/help/*.txt` are **29 real help texts** (including Chinese, man pages, argparse,
two-line blocks, GNU long options, and Windows English/Chinese ping); `tests/fixtures/fakecli.py` is a
controllable fake CLI (it can prescribe exit codes, write to stderr and sleep for a long time). The
executor and GUI tests use it — **real commands are never used for destructive verification**.

## Editing the parsing rules

See [Parsing rules § how to iterate on the rules](parsing-rules.md). Three rules of discipline:

1. Verify with `--parse --help-file` against real text instead of editing regexes from memory;
2. Always run `python3 -m clitree --check-rules` afterwards (non-zero means broken);
3. Add or update the corresponding tests; the expected values in `fixtures` must be **recomputed on the
   spot** — never copy an old reading into a "pass".

## Adding a fixture

```bash
<pick-a-real-cli> --help > tests/fixtures/help/<name>.help.txt
# for commands with spaces or subcommands, spell out the channel, e.g. git clone -h
```

and add an assertion in the tests (count, shape or widget type). The sample must be **verbatim text
captured from a real machine** — do not hand-write it and do not polish it.

## Changing the UI

- Qt may only appear inside `clitree/ui/`, and **`ui/qt.py` is the only file that imports Qt** (so a
  binding swap touches that one file);
- `core/` must not import Qt (that would make headless unit tests impossible);
- New UI behaviour deserves an assertion in `test_gui_smoke.py` — it already has a reusable
  `MainWindow(probe_fn=..., profile_root=tmp_path)` fixture that never pollutes the real `cli/`.

## Documentation conventions

- Every document comes in three languages: `X.md` (English), `X.zh-CN.md` (Chinese), `X.es.md`
  (Spanish), with the language-switch line kept at the top:
  `[English](X.md) | [中文](X.zh-CN.md) | [Español](X.es.md)`;
- **Change behaviour ⇒ update all three languages in the same pass** (if you truly cannot, at least
  leave a TODO instead of letting the three languages contradict each other);
- Every number in the documentation must either come with a command to recompute it or be labelled
  "not verified".

## Commit conventions

- Commit messages use a one-line prefixed subject (`feat:` / `fix:` / `docs:` / `test:` / `refactor:` /
  `chore:`) with the "why" in the body;
- **Do not commit** `__pycache__/`, `.pytest_cache/`, `*-session.jsonl` (already in `.gitignore`);
- `cli/` **is** tracked (the configuration follows the repository); if the values inside are not fit to
  publish, change `.gitignore` before committing;
- Big changes should come with readings (the tests you ran, screenshots, `--parse` output) rather than
  "it should be fine".

## The not-yet-verified list (NOINFO)

This list exists so that nobody assumes these already hold:

- **Windows / macOS**: `ping` parsing/execution and the test suite have been exercised on Windows 11
  (2026-10, see the README table); the `-?` channel, opening a terminal via `cmd start` / `osascript`,
  and PyInstaller packaging are still **untested**;
- **Whether the new-terminal mode really pops up a window**: this machine has no graphical
  environment, so all we can read is the button state `launched`;
- **Packaging**: no PyInstaller packaging verification has been done;
- **Long-term stability under locales other than Chinese**: only this machine's locale and the
  `LC_ALL=C` switch have been tested.

If you close one of these gaps, **delete the corresponding entry here and attach the readings** —
leaving a false statement in the documentation is far worse than leaving "not verified".
