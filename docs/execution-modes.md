# Execution modes

**English** | [中文](execution-modes.zh-CN.md) | [Español](execution-modes.es.md)

> Part of the **CliTree** documentation — back to the [README](../README.md).

## The three modes

| Mode | Implementation | Log area | Exit code | Can it be stopped |
|---|---|---|---|---|
| **new-terminal run** | `terminals.build_terminal_argv()` picks the platform terminal (Linux: `gnome-terminal`/`xfce4-terminal`/`konsole`/`xterm`/`x-terminal-emulator`; macOS: `osascript` driving Terminal.app; Windows: `wt.exe` or `cmd /c start`) | Not returned (the terminal shows it itself) | **Not available** | **No** (an external window) |
| **background run** | `subprocess.Popen` plus a thread reading stdout+stderr line by line | Written in real time, line by line | Yes | Yes |
| **silent run** | `Popen` with stdout/stderr sent to `/dev/null` | **Not one line is written** | Yes | Yes |

The design stance: **no exit code means no verdict on success or failure**. The new-terminal mode only
marks the button as "launched in terminal" — it never pretends success (nor failure).

## Stop

While a run is in flight, that mode's button text becomes **`■ Stop`**; a second click terminates it:

```
RunHandle.stop()  →  terminate()  →  wait up to 3 seconds  →  still alive ⇒ kill()
```

- The result state is recorded as **`stopped`** (neutral, not a failure) and the button icon becomes a stop square;
- After stopping a background run the log area keeps the output already produced;
- Stopping a silent run writes no log either;
- Calling `stop()` on a run that has already finished is a **no-op** (it changes no state and raises nothing).

## The result-icon state machine

Each button **independently** remembers its own last result:

| State | When | Icon |
|---|---|---|
| `idle` | Never run | ▶ |
| `running` | Currently running (the button text becomes "■ Stop") | ↻ |
| `ok` | Exit code 0 | ✓ |
| `fail` | Exit code non-zero | ✗ |
| `launched` | A new terminal was launched (no exit code) | a square |
| `stopped` | The user clicked stop | ■ |
| `error` | The launch failed (no terminal emulator found, for example) | ⚠ |

## argv pass-through: never through a shell

Parameters are always handed to the child process as a **list**:

```python
argv = build_argv(exe, node, values)
# example: {"--verbose": True, "--count": "3", "--output": "a b; rm -rf /", "@0": "host"}
#   ⇒ ["ping", "--verbose", "--count", "3", "--output", "a b; rm -rf /", "host"]
```

A value such as `a b; rm -rf /` **stays one single argv element** and is never interpreted as a command
separator (a test pins this down).

Only the "open a new terminal" path needs a command line, and that is the only place where escaping
happens: POSIX uses `shlex.join`, Windows wraps in `"…"` and escapes inner quotes.

How `build_argv` turns form state into argv:

| Form state | Result |
|---|---|
| Checkbox unchecked / dropdown empty / number box showing "（不传）" | **The parameter is not passed** |
| Checkbox checked | The long name is passed (the short name if there is no long name) |
| Has a value | Two elements, `name value`, are passed |
| Repeatable (multi-value list) | Each value is passed once as `name value` |
| Positional argument | Appended at the end in order (without a name) |

## Dangerous commands: two interception points

1. **Before probing**: when `discovery.probe()` sees one of the 24 — `shutdown`/`dd`/`mkfs*` and
   friends — it returns a refusal immediately and **starts no process at all**;
2. **Before execution**: `MainWindow.run()` checks the same list once more (so that a probe result
   coming from the cache, or an injected fake probe, cannot slip through) and writes the reason into
   the status bar.

Measured in the UI: loading `/sbin/shutdown` ⇒ the tree and the form are empty and the status bar reads
"Security policy: shutdown is a dangerous command, CliTree neither probes nor executes it"
(screenshot `08-dangerous-refused.png`).

## Recomputing

```bash
python3 -m pytest tests/test_executor.py -q      # three modes + stop + argv safety
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from clitree.core import executor, terminals
print(terminals.build_terminal_argv(["echo", "hi there"], platform="linux"))
print(executor.build_argv("ping", __import__("clitree.core.model", fromlist=["CommandNode"]).CommandNode(
    name="ping", path=["ping"], options=[]), {}))
PY
```
