# Configuration: `cli/<tool-name>.json`

**English** | [中文](configuration.zh-CN.md) | [Español](configuration.es.md)

> Part of the **CliTree** documentation — back to the [README](../README.md).

Every tool you have loaded leaves one configuration file in **`cli/` under the program directory**.
A single file carries three kinds of things at once: the **parse-result cache**, **multiple profiles**
and **your own parameter notes**.

## File structure

```jsonc
{
  "schema": 1,
  "cli": "ping",
  "updatedAt": "2026-10-08T16:01:00",

  "targets": {                        // one cache entry per parsed command path; "" = the root command
    "": {
      "exe": "ping",
      "channel": ["--help"], "rc": 2, "grade": "full", "dialect": "usage-posix",
      "raw_sha256": "ffa24d0b…", "raw_bytes": 1866, "raw_head": "Usage\n  ping …",
      "parsedAt": "2026-10-08T16:01:00",
      "options": [ /* the argument tree itself: names/desc/widget/required/… all present */ ],
      "subcommands": [ { "name": "sub", "desc": "…" } ]
    },
    "clone": { /* the entry for git clone (written only when you open it) */ }
  },

  "notes": {                          // ★ your own parameter notes (file level: applies to every profile of this CLI)
    "-c": "I usually use 2; 1 on the internet, never above 5"
  },

  "activeProfile": "loopback-twice",
  "profiles": {                       // ★ multiple profiles inside one file
    "default":       { "note": "", "createdAt": "…", "updatedAt": "…", "values": {} },
    "loopback-twice": { "values": { "@0": "127.0.0.1", "-c": "2" } },
    "internet-five": { "note": "internet", "values": { "@0": "8.8.8.8", "-c": "5" },
                  "notes": { "-c": "rate-limited on the internet, use 1" } }   // profile-level note (overrides the file level)
  }
}
```

- **File name**: the tool name with its extension stripped and illegal characters replaced by `_`
  (`C:/tools/my tool.exe` ⇒ `my_tool.json`).
- **Location**: `cli/` under the program directory, i.e. the level that holds `pyproject.toml`.
  When the program directory is not writable (a read-only install) it **falls back** automatically to
  the user configuration directory
  (Linux `~/.config/clitree/cli/`, macOS `~/Library/Application Support/clitree/cli/`, Windows `%APPDATA%\clitree\cli/`), without crashing.
- Files are written with a **temporary file plus an atomic replace**, so a power cut cannot leave half a JSON behind.

## Cache: no need to run help again next time

- When a CLI is loaded, `cli/<tool>.json`'s `targets` is consulted first:
  **a hit renders the argument tree and the form directly, without running help even once** (the status
  bar says "loaded from cache… parsed at …");
- To refresh, click **"Reparse"**: only then is `--help` run, and success overwrites the cache;
- With no cache at all (the first load) it probes and writes the cache itself;
- Every successful parse updates the cache: one entry for the root command, and one more for each
  subcommand you open (such as `targets["clone"]`).

What the cache stores is the **argument tree itself** (15 fields per parameter: `names`, `desc`,
`value_token`, `required`, `default`, `example`, `choices`, `widget`, `widget_reason`, `repeatable`,
`group`, `position`…), so offline, on another machine, or with the tool uninstalled, the UI can still
list every parameter — it just cannot execute anything.

`raw_sha256` / `raw_bytes` are the fingerprint of the help text at the time (only the first 2 KB,
`raw_head`, is stored, for diagnosis), used to tell whether "the help has changed".

## Multiple profiles

The row at the top right of the window reads: `配置： [dropdown] [Save] [new profile name] [Save as…] [Delete] [Reparse]`.

| Action | Behaviour |
|---|---|
| Dropdown switch | Every parameter value on the right is replaced by that profile's; **the current values are saved back to the previous profile before switching away** (nothing is lost) |
| Save | Writes the current form values into the current profile |
| Save as | Copies the **current values** into a **new profile with a name you choose** (the old profile is untouched) |
| Delete | Deletes the current profile (deleting everything still leaves the file valid) |

Typical use: for `ping` a "loopback" profile (`127.0.0.1` / `-c 2`) plus an "internet" profile
(`8.8.8.8` / `-c 5`); for `tar` a "pack" profile plus an "unpack" profile.

## Parameter notes: file level + profile level

| Level | Where it is written | Scope | How it is produced |
|---|---|---|---|
| File level | `notes` | **Every** profile of this CLI | **Double-click** the note line to edit (this is where it is written by default) |
| Profile level | `profiles.<name>.notes` | **That profile only** | `set_note(key, text, scope="profile")` |

Precedence: **profile level > file level > the original help text**. Clearing the input box deletes that
entry, falling back to the next level and finally to the original help text.

In the UI your own note is shown as `✎ your note　（原：help text）` — the part you wrote is dark with a
`✎` marker while the original help text stays in the parentheses, so the two are distinguishable at a glance.

## Migration and privacy

- **Taking it with you**: copy the whole `cli/` directory to the same location on another machine
  (values, notes and cache travel together).
- **Privacy**: `values` may contain your host names, intranet IPs and paths — positional arguments such
  as `@0` especially. This repository **deliberately keeps `cli/` under version control** (the
  configuration follows the repository); if your values are not fit to publish, change the `cli/` part
  of `.gitignore` back to ignoring it (the file explains it).
- **Schema changes**: the file has a top-level `schema` field; currently `1`.
  On a parse failure or missing fields it continues with an empty skeleton (**a broken file never
  crashes the program**), and the next save rewrites it as a valid structure.

## Recomputing

```bash
# see which tool configurations exist and what is inside them
python3 - <<'PY'
import json, pathlib
for f in sorted(pathlib.Path("cli").glob("*.json")):
    d = json.loads(f.read_text())
    print(f.name, "| targets:", list(d["targets"]),
          "| profiles:", {k: v.get("values") for k, v in d["profiles"].items()},
          "| notes:", d.get("notes"))
PY
```
