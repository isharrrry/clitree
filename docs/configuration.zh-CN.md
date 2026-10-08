# 配置：`cli/<工具名>.json`

[English](configuration.md) | **中文** | [Español](configuration.es.md)

> 属于 **CliTree** 文档的一部分 —— 返回 [README](../README.zh-CN.md)。

每个被你加载过的工具，都会在**程序目录下的 `cli/`** 里留下一个配置文件。
一个文件里同时装三样东西：**解析结果缓存**、**多个配置**、**你自己的参数说明**。

## 文件结构

```jsonc
{
  "schema": 1,
  "cli": "ping",
  "updatedAt": "2026-10-08T16:01:00",

  "targets": {                        // 每个被解析过的命令路径一份缓存；"" = 根命令
    "": {
      "exe": "ping",
      "channel": ["--help"], "rc": 2, "grade": "full", "dialect": "usage-posix",
      "raw_sha256": "ffa24d0b…", "raw_bytes": 1866, "raw_head": "Usage\n  ping …",
      "parsedAt": "2026-10-08T16:01:00",
      "options": [ /* 参数树本体：names/desc/widget/required/… 全在 */ ],
      "subcommands": [ { "name": "sub", "desc": "…" } ]
    },
    "clone": { /* git clone 的那一份（点开它时才会写） */ }
  },

  "notes": {                          // ★ 你自己的参数说明（文件级：对本 CLI 所有配置生效）
    "-c": "我常用 2；外网改 1，别超过 5"
  },

  "activeProfile": "回环两次",
  "profiles": {                       // ★ 一个文件里的多个配置
    "默认":     { "note": "", "createdAt": "…", "updatedAt": "…", "values": {} },
    "回环两次": { "values": { "@0": "127.0.0.1", "-c": "2" } },
    "外网五次": { "note": "外网", "values": { "@0": "8.8.8.8", "-c": "5" },
                  "notes": { "-c": "外网限速，用 1" } }   // 配置级说明（覆盖文件级）
  }
}
```

- **文件名**：工具名去掉扩展名、非法字符换成 `_`（`C:/tools/my tool.exe` ⇒ `my_tool.json`）。
- **位置**：程序目录下的 `cli/`，即 `pyproject.toml` 所在那一层。
  程序目录不可写时（只读安装）**自动回退**到用户配置目录
  （Linux `~/.config/clitree/cli/`，macOS `~/Library/Application Support/clitree/cli/`，Windows `%APPDATA%\clitree\cli\`），不会崩。
- 写文件用**临时文件 ＋ 原子替换**，断电不会留下半截 JSON。

## 缓存：下次不必再跑 help

- 加载一个 CLI 时，先查 `cli/<工具>.json` 的 `targets`：
  **命中就直接渲染参数树与表单，一次 help 都不跑**（状态栏写明「已从缓存载入…解析于 …」）；
- 想刷新，点**「重新解析」**：它才去跑 `--help`，成功后覆盖缓存；
- 没有缓存时（首次加载）自动探测并写入缓存；
- 每次解析成功都会更新缓存：根命令一份，你点开的每个子命令再各一份（`targets["clone"]` 这样）。

缓存里存的是**参数树本体**（15 个字段/参数：`names`、`desc`、`value_token`、`required`、
`default`、`example`、`choices`、`widget`、`widget_reason`、`repeatable`、`group`、`position`…），
所以离线、换机器、工具被卸载，界面照样能把参数列全 —— 只是不能再执行。

`raw_sha256` / `raw_bytes` 是当时 help 文本的指纹（只存前 2 KB 原文 `raw_head` 用于诊断），
用来判断「help 是不是变了」。

## 多个配置（profiles）

界面右侧顶部一行：`配置： [下拉] [保存] [新配置名] [另存为…] [删除] [重新解析]`。

| 操作 | 行为 |
|---|---|
| 下拉切换 | 右侧所有参数值换成那个配置的；**切走前当前值自动存回原配置**（不会丢） |
| 保存 | 把当前表单的值写进当前配置 |
| 另存为 | 把**当前值**复制成一个**新配置并起名**（旧配置不受影响） |
| 删除 | 删掉当前配置（删光也保持文件合法） |

典型用法：`ping` 一个「内网回环」配置（`127.0.0.1` / `-c 2`）＋ 一个「外网」配置（`8.8.8.8` / `-c 5`）；
`tar` 一个「打包」配置 ＋ 一个「解包」配置。

## 参数说明（notes）：文件级 ＋ 配置级

| 层 | 写在哪 | 作用范围 | 怎么产生 |
|---|---|---|---|
| 文件级 | `notes` | 该 CLI 的**所有**配置 | **双击**说明那一行编辑（默认写这里） |
| 配置级 | `profiles.<名字>.notes` | **只对该配置**生效 | `set_note(key, text, scope="profile")` |

优先级：**配置级 > 文件级 > help 原文**。清空输入框即删除该项，回落到下一层，最终回到 help 原文。

界面上你自己的说明显示成 `✎ 你的说明　（原：help 原文）` —— 用深色 ＋ `✎` 标出你写的部分，
help 原文留在括号里，一眼分得清。

## 迁移与隐私

- **带走**：把整个 `cli/` 目录拷到另一台机器的同一位置即可（值、说明、缓存一起走）。
- **隐私**：`values` 里可能有你的主机名、内网 IP、路径 —— 特别是 `@0` 这类位置参数。
  本仓库**故意把 `cli/` 纳入版本管理**（配置跟着仓库走）；如果你的值不适合公开，
  把 `.gitignore` 里关于 `cli/` 的注释那段改回忽略即可（文件里有说明）。
- **schema 变更**：文件顶层有 `schema` 字段；目前是 `1`。
  解析失败或字段缺失时按空骨架继续（**坏文件不会让程序崩**），下次保存会重写为合法结构。

## 复算

```bash
# 看当前有哪些工具配置、里面有什么
python3 - <<'PY'
import json, pathlib
for f in sorted(pathlib.Path("cli").glob("*.json")):
    d = json.loads(f.read_text())
    print(f.name, "| targets:", list(d["targets"]),
          "| profiles:", {k: v.get("values") for k, v in d["profiles"].items()},
          "| notes:", d.get("notes"))
PY
```
