# Changelog

All notable changes to this project are recorded here.

## 0.2.0

Per-tool configuration files, editable parameter notes, stop support, and a documentation set in three languages.

### Added

| Item | What it does |
|---|---|
| `cli/<tool>.json` | One file per tool holding the **parse cache** (`targets`), **multiple profiles** (`profiles`) and **your own parameter notes** (`notes`). Loading a tool that has a cache renders the whole tree without running `help` again; the **Reparse** button refreshes it. |
| Profile bar | Right-hand dropdown to switch between profiles, **Save**, **Save as…** (copy the current values into a new named profile) and **Delete**. Switching profiles saves the current values back first. |
| Editable parameter notes | **Double-click** the description line to replace the help text with your own note. Shown as `✎ your note　(original: help text)`. Notes exist at file level and can be overridden per profile. |
| Stop a run | While a run is active its button becomes **■ Stop**; clicking again terminates the process (`terminate → 3 s → kill`) and the button records `stopped`. Background and silent runs can be stopped; the new-terminal mode cannot (no process handle). |
| Long and short names | Parameter labels show `-c, --count <count>`, and every parameter has its help description **always visible** underneath instead of hiding in a tooltip. |

### Changed

- **Required-argument semantics**: when a usage line exists, options are **optional by default** — only positional
  arguments are classified required/optional. `？Undetermined` is now shown only when there is no usage line at all.
  (Before this, all 32 options of `ping` were labelled "unannotated", which was noise.)
- **Form order**: positional arguments first, then required ones, then the rest in help order.
- Screenshots, README and the `docs/` set are now shipped in English, Chinese and Spanish.

### Fixed

- `QSpinBox` showed `-1000000` for an empty value (Qt ignores an empty `specialValueText`) — now shows `（not set）`.
- `QComboBox` had a leading empty item, which broke selection of the first real choice.
- Stop-button text nested the mode label inside parentheses (`■ Stop (Background run (log in this window))`).

## 0.1.0

First working version: help parsing, the argument tree, the inferred widgets and the three execution modes.

| Item | What it does |
|---|---|
| `core/parser.py` | Block-model parser for help text: continuation lines are merged into the option they belong to, so `--diff, --extract` inside a description never becomes a separate option. |
| `core/discovery.py` | Probes `--help → -h → /? → -? → help → -help`, decides by **content rather than exit code** (measured: `git clone -h` returns 129 and `ping -h` returns 2 while both print complete help). |
| `core/widgets.py` | Infers the widget per parameter: checkbox for valueless flags, editable dropdown for explicit choice sets, numeric box, path box with a browse button, tri-state for `--[no-]x`, multi-value list for repeatable options. |
| `core/lazy.py` | Loading a tool renders only two levels; a subcommand's help is probed when you expand it, and the result is cached. |
| `core/executor.py` | Runs the built command as an **argv list, never through a shell**, in one of three modes. |
| `core/rules.py` + `rules/default.rules.json` | All parsing behaviour lives in one editable, versioned rules file with measured evidence recorded inside it. |
| Safety | 24 dangerous commands are never probed or executed; `-h` is only tried when `--help` declares it; probing closes stdin, disables pagers, times out after 5 s and caps output at 256 KB. |
