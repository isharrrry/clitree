# Architecture

**English** | [中文](architecture.zh-CN.md) | [Español](architecture.es.md)

> Part of the **CliTree** documentation — back to the [README](../README.md).

## Three layers, one hard rule

```
clitree/
├── core/      pure logic: parsing, rules, widget inference, probing, lazy loading, execution, persistence   ← does not import Qt
├── ui/        the Qt interface; **ui/qt.py is the only file that imports Qt**
├── rules/     default.rules.json (the single source of truth for parsing rules)
tests/         165 tests (including the offscreen GUI smoke tests)
tools/         scripts that generate the dependency tree / the screenshots
cli/           one configuration file per tool (cache + multiple profiles + your notes)
```

**The hard rule**: `PyQt5` / `PySide6` must never appear inside `core`. That buys two practical things:
① the parsing and execution logic can be unit-tested without a graphical environment (the CI on this
machine is exactly `QT_QPA_PLATFORM=offscreen` plus plain pytest);
② if you later want to move from PyQt5 to PySide6 (for LGPL, say), **you only touch `ui/qt.py`**.

## Module responsibilities

| Module | Responsibility | Key point |
|---|---|---|
| `core/model.py` | The data structures `ParamSpec` / `CommandNode` / `ParseResult` | Ships `to_dict/from_dict`; the cache in the configuration file is exactly this |
| `core/rules.py` | Load / validate / deep-merge the rules file | User overrides go to `rules.user.json`, **the packaged rules are never modified** |
| `core/parser.py` | Help text → structured parameters and subcommands | Block model; dialect detection; required/optional rule |
| `core/widgets.py` | Parameter → widget type inference | Every decision produces a `widget_reason` (visible in the UI) |
| `core/discovery.py` | Probe the help channels (including the safety policy) | Dangerous commands are refused outright; `-h` must be declared first; rc is ignored, only content counts |
| `core/lazy.py` | The lazy-loading tree | Loading produces 2 levels only; a node is probed when it is expanded |
| `core/executor.py` | The three execution modes + stop | argv lists are passed straight through, a shell is never assembled |
| `core/terminals.py` | "Open a new terminal" adapters for three platforms | One command set each for Linux / macOS / Windows |
| `core/store.py` | Configuration directory, recent commands | Paths are computed per platform convention (`XDG_CONFIG_HOME` / `APPDATA` / `Library/Application Support`) |
| `core/profiles.py` | Read/write `cli/<tool-name>.json` | Parse cache + multiple profiles + parameter notes |
| `ui/qt.py` | Thin Qt adapter layer | The only place in the project that imports Qt |
| `ui/main_window.py` | Main window assembly, drag & drop, loading, the profile row, execution | Thread callbacks return to the main thread through a queue to refresh the UI |
| `ui/tree_panel.py` | The left tree | Subcommands are marked "not expanded"; probing is triggered only by opening one |
| `ui/param_form.py` | The parameter form on the right | Sorting, the widget factory, always-visible notes with double-click editing |
| `ui/run_bar.py` / `ui/icons.py` | The three run buttons and the state icons | While running it becomes "■ Stop"; each button remembers its own last result |
| `ui/log_panel.py` | The log area | **Only the background mode writes into it** |

## The full data flow of one "load → run"

```
The user types / drags in a CLI
        │
        ├─ profiles.cached_node(cli)  ── hit ⇒ render the tree and the form directly (**no probing**)
        │                                  the status bar says "loaded from cache… parsed at …"
        │
        └─ miss ⇒ discovery.probe(exe, rules, node_path)
                     ├─ dangerous command? ⇒ refuse immediately (the reason goes to the status bar)
                     ├─ interactive command (gdb and friends) ⇒ dedicated channel `-batch -ex "help all"`
                     └─ otherwise follow the channel order --help → -h → /? → -? → help → -help
                          running each one for real, **judging success by the output content**
                          (rc is completely untrustworthy)
                          │
                          ▼
                    parser.parse_help(text, rules)  →  a list of ParamSpec + the subcommand list
                          │
                          ▼
                    widgets.infer_widget(spec)      →  widget type + inference reason
                          │
                          ├─ profiles.save_node(...)     write the parse result into cli/<tool>.json
                          └─ lazy.TreeLoader._fill(...)  grow only 2 levels, the rest stays pending
                          │
                          ▼
                    TreePanel.show_root()  +  ParamForm.build()  (positionals first → required → the rest)
                          │
                          the user fills in values / picks a profile (profiles.get_profile → form.set_value)
                          ▼
                    executor.build_argv(exe, node, values)   ← an argv list, never through a shell
                          │
        ┌─────────────────┼──────────────────────────┐
        ▼                 ▼                          ▼
   new terminal        background                 silent
   (terminals)         (Popen + a thread pump)    (Popen, output not read)
   no rc ⇒             stdout/stderr line by      zero new lines in the log area
   "launched"          line into the log          rc decides ok / fail when it ends
                       rc decides ok / fail
```

## Why the cache and the profiles live in the same file

`cli/<tool-name>.json` holds three kinds of things at once:

- `targets`: one parse result **per command path that has been parsed** (the root command is `""`,
  `git clone` is `"clone"`);
- `profiles`: **multiple profiles** of the same tool (parameter values for different machines/scenarios);
- `notes`: **your own parameter notes** (file level) plus an optional override per profile.

The reason is that they naturally share a lifetime: a tool's argument tree, the values you fill in for
it, and your understanding of it should travel together when you change machines. Details in
[Configuration](configuration.md).

## Want to see the real dependencies between modules?

`tools/deps_tree.py` parses imports with AST and generates a dependency tree carrying
**hierarchical letter numbering**:

```bash
python3 tools/deps_tree.py            # print it
python3 tools/deps_tree.py --out docs/DEPENDENCY-TREE.md
```

The numbering looks like `[BACD]` = 2nd item of level 1 → 1st of level 2 → 3rd of level 3 → 4th of
level 4; when the same file appears a second time it is written as `↩ see [first number]` and not
expanded again. The current snapshot is in [DEPENDENCY-TREE.md](DEPENDENCY-TREE.md).
