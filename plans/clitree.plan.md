# Plan: CliTree — CLI 参数树可视化执行器（Win/Linux/macOS）

**来源**：自由文本需求（无 PRD，需求已足够清楚 ⇒ 按 eccplan 路由表跳过 PRD 阶段）
**复杂度**：Large（新项目、跨三平台、含 GUI ＋ 解析引擎 ＋ 进程执行三条独立链路）
**状态**：**已实施完成（v0.1.0）** —— 规则落地 ＋ 全部模块实现 ＋ **110 项测试全绿** ＋ 真 CLI 端到端三模式读数；实施偏差与实测见 §12。

---

## 1. 需求复述（Restatement）

做一个桌面 GUI 工具，把任意 CLI 的 help 文本变成可点选的参数树，并在 GUI 里填值执行：

1. **入口两条**：① 主界面输入框敲一个 cli 命令；② 把可执行文件**拖进窗口**。点「加载」生效。
2. **加载动作**：自动尝试该 cli 的 `--help` / `-h` / `/?` / `-?` / `help` 等通道，拿到 help 文本。
3. **左侧树（初始 2 层，其余按需展开）**：
   - 点「加载」时**只解析 2 层**：**第 1 层 = 该 CLI 自身的全部参数**，**第 2 层 = 它的一级子命令**（只列名字，**不跑**每个子命令的 help）。
   - 用户**点开某个子命令节点**时，才去跑那个子命令的 help 并长出第 3 层；再点开再长一层，**展开上限 3 层**（可改规则）。
   - 另给一个**显式**的「全量展开」按钮（有上限、限并发、可中断），默认不自动触发。
   - 根节点旁显示统计：`分支 N · 子命令 M · 参数 K`。
4. **右侧表单（控件类型必须匹配参数语义，不许一律给输入框）**：点中树里任一节点，右侧出现该节点全部参数；**参数形态决定控件**——
   - **开关型参数**（如 `ping -t` 这类不取值的 flag）⇒ **勾选框 ＋ 解释文字**，**不给输入框**；
   - **取值有固定集合的参数** ⇒ **下拉框**（可编辑，见 §5.5）；
   - **数值/路径/可重复/互斥组**等 ⇒ 数值框 / 文本框＋浏览 / 多值列表 / 单选组（完整映射见 §5.5）。
   - 每个控件旁边都带 **默认值**、**示例值提示**、**是否必填** 标记，外加 **help 原文描述** 与 **「为什么判成这种控件」的推断依据**（可一键改成别的控件类型，且纠正会写回规则文件）。
5. **下方三个执行按钮**（各自独立记忆状态）：
   - **新终端执行**：开一个真正的终端窗口跑。
   - **后台执行**：跑起来，stdout/stderr 实时回显到**本窗口日志区**。
   - **静默执行**：只在运行期间把鼠标变 busy，**不产生任何日志**。
6. **结果图标**：每次执行结束后，该按钮的图标更新为「上次成功 / 上次失败」，运行中为「运行中」。
7. **解析规则可迭代**：规则**默认给一套**，**落到文件**（用户可见可改），后续升级只改这个文件。
8. **三平台通用**：Windows / Linux / macOS 同一套代码。

### 非目标（本计划不做，除非你点名要）

- 不做 shell 语法高亮、不做命令历史库、不做补全引擎。
- 不做 `man` 页的完整渲染（只做「识别出这是 man 页 ⇒ 走回退通道」）。
- 不做权限提升 / sudo 包装。

---

## 2. 本机实测事实（计划的依据，不是猜测）

| 事实 | 实测读数 |
|---|---|
| 解释器 | `Python 3.10.12`；`pip 26.2.1`（`~/.local`）；`python3 -m ensurepip` **不存在** |
| **venv 不可用** | `python3 -m venv` 建出的环境**无 pip**；且其 `sys.path` **不含 `/usr/lib/python3/dist-packages`** ⇒ 连系统 Qt 也看不见 ⇒ **本计划不建 venv，直接用系统 `python3`** |
| GUI 绑定 | **只有 PyQt5 5.15.6 / Qt 5.15.3**（`/usr/lib/python3/dist-packages`）；PyQt6 / PySide6 / PySide2 **均无** |
| 无头验证通道 | `QT_QPA_PLATFORM=offscreen` 实跑成功；`xvfb-run`、`Xvfb` 在 PATH 上 |
| 终端仿真器（Linux 侧新终端模式） | `gnome-terminal`、`xfce4-terminal` 有；`xterm` / `konsole` / `wt` 无 |
| 当前会话图形环境 | `DISPLAY` 未设、`XDG_SESSION_TYPE` 未设 ⇒ **本机是无头环境**，GUI 只能靠 offscreen/xvfb 验证 |
| 测试框架 | `pytest 9.1.1` 已在 |
| 网络 | PyPI 可达（`https://pypi.org/simple/pyside6/` HTTP/2 200）⇒ 日后切 PySide6 可行 |
| OS | Ubuntu 22.04.5 LTS x86_64 |

### help 文本形态采样（本机真跑出来的，构成默认规则的覆盖目标）

| CLI | rc | 形态要点 |
|---|---|---|
| `pnpm --help` | 0 | 英文 `Usage:`/`Commands:`；**选项名与描述分两行**（`-v, --version` ＋ 缩进说明行）；`--color[=<COLOR>]` 这种怪取值 |
| `git --help` | 0 | **中文**：`用法：` ＋ **分组**命令列表；**无选项行** |
| `tar --help` | 0 | **中文**：`用法:`/`主操作模式:`；`-A, --catenate, --concatenate` 多别名；**续行里出现 `-` 开头的词**（`--delete, --extract`） |
| `dotnet --help` | 0 | 中文段落标题 `使用情况:` ＋ 英文小标题 `runtime-options:` |
| `python3 --help` | 0 | argparse：`usage:` ＋ `-b     : 描述`（**冒号分隔**）＋ 描述跨行 |
| `pip --help` | 0 | `Usage:`/`Commands:`（两列） |
| `gcc --help` | 0 | GNU 长 help：**单横线长选项名**（`-pass-exit-codes`） |
| `git clone --help` | 0 | **man 页**（`GIT-CLONE(1) … SYNOPSIS`）⇒ 必须回退 |
| `git clone -h` | **129** | 简洁文本（`用法：` ＋ `-v, --verbose  …`）⇒ **rc 不可信** |
| `dotnet build -h` | 0 | `Description:` ＋ `用法:` 混排 |
| `git help -a` | 0 | 144 条子命令（`^   [a-z]` 计数），可做子命令枚举兜底 |
| `ping -h` | **2** | iputils 风格：`Usage` **无冒号**标题 ＋ `<destination>` 位置参数；**两个参数带 `can be one of <a\|b\|c>`**（`-M`、`-T`）⇒ 唯一的真枚举来源；`-t <ttl>` 是**取值型**（对照：Windows `ping -t` 是无值开关） |
| `curl --help all` | 0 | 244 个选项块（最大样本）；`-b <data\|filename>` 是**取值形态**而非集合 ⇒ 假阳陷阱 |

### 耗时实测（懒加载与超时的依据）

`pnpm --help` 122 ms｜`pip --help` 176 ms｜`dotnet --help` 314 ms｜`dotnet build -h` 314 ms｜`git clone --help` 43 ms｜其余（git/tar/python3/gcc/`git help -a`）≤ 5 ms。
⇒ 单次探测 `timeoutMs` 默认 **5000 ms** 合理（dotnet 类冷启动可到数百 ms）；**若加载时无脑递归全部子命令**，`git` 这一个是 144 次探测 ⇒ 这就是 §1 第 3 点「初始 2 层、其余懒展开」的量化理由。

### `LC_ALL=C` 开关实测

`LC_ALL=C` 下 **`git`/`tar`/`dotnet` 都从中文变英文**（`usage:` / `Usage:` / `runtime-options:`）⇒ `locale.probeOrder` 策略可行；但**不能假定 C locale 一定成功**，双语规则仍必需。

---

## 3. Patterns to Mirror

新文件夹，**没有既有代码可镜像** —— 按 eccplan 的要求如实声明：**本计划不发明「项目内既有 pattern」**。
可借鉴的只有本机事实与 Python/Qt 通用惯例：

| 类别 | 来源 | 采取的做法 |
|---|---|---|
| 命名 | — | Python 包 `clitree`，模块 snake_case，规则文件 `default.rules.json` |
| 错误处理 | — | 解析失败 ⇒ **如实呈现"未识别段落"**，绝不猜参数；执行失败 ⇒ 异常落日志并置按钮为失败态 |
| 日志 | — | 窗口日志区统一 `[时间][流] 原文`，单条长度与总行数设上限 |
| 数据访问 | — | 用户配置与规则覆盖落 `QStandardPaths`（Win `%APPDATA%\clitree\`，macOS `~/Library/Application Support/clitree/`，Linux `~/.config/clitree/`） |
| 测试 | — | `pytest`；解析器测试靠**固化的 help 文本 fixtures**（§2 采样即初始集，共 11 条） |

---

## 4. 架构与文件

```
clitree/
├── pyproject.toml                 # 依赖与入口 (console_scripts: clitree)
├── README.md
├── plans/clitree.plan.md          # 本文件
├── clitree/
│   ├── __main__.py                # python -m clitree
│   ├── app.py                     # QApplication 装配
│   ├── core/
│   │   ├── model.py               # CommandNode / ParamSpec / LoadResult（dataclass）
│   │   ├── discovery.py           # help 通道探测：--help/-h//?/-?/help/-help，rc 不可信
│   │   ├── parser.py              # 规则驱动的 help → 树（**块模型**，见 §5.1）
│   │   ├── rules.py               # 规则加载/校验/热重载/用户覆盖合并
│   │   ├── widgets.py             # ★ 参数→控件类型推断（纯逻辑、可单测，§5.5 的映射表在这里）
│   │   ├── lazy.py                # ★ 懒加载：展开节点时才探测该级 help（有缓存、限并发、可取消）
│   │   ├── executor.py            # 三模式执行（terminal / background / silent）
│   │   ├── terminals.py           # 三平台「开新终端」适配
│   │   └── store.py               # QStandardPaths 落盘、最近命令、每节点参数值草稿
│   ├── ui/
│   │   ├── qt.py                  # ★ 薄适配层：只在这里 import Qt（日后切 PySide6 只改这一个文件）
│   │   ├── main_window.py         # 主窗＋拖放＋加载框＋「全量展开」
│   │   ├── tree_panel.py          # 左树＋统计徽标＋展开态/加载中态
│   │   ├── param_form.py          # 右表单：控件工厂（§5.5 映射）＋默认值/示例/必填/推断依据/改类型
│   │   ├── log_panel.py           # 日志区（仅后台模式写入）
│   │   ├── run_bar.py             # 三按钮＋结果图标状态机
│   │   └── icons.py               # 状态图标（内置 SVG，无外部资源）
│   └── rules/
│       └── default.rules.json     # ★ **已落地 v3**（5548 B / sha16 69233c773054a0a6）：方言·通道·词表·枚举·覆盖
└── tests/
    ├── fixtures/help/*.txt        # 16 条采样 help（中文/man/argparse/GNU/两行块/枚举型 ping）
    ├── test_parser_blocks.py      # 块合并与选项定义（含 §11 的形态清单）
    ├── test_parser_subcommands.py # 子命令段（含假阳/假阴回归）
    ├── test_widgets.py            # ★ 参数→控件类型推断（§5.5 映射表 ＋ §11.8 的分布基线）
    ├── test_discovery.py          # 通道探测（含 rc=129 判成功）
    ├── test_lazy.py               # ★ 懒加载：未展开的节点不产生进程
    ├── test_executor.py           # 三模式
    └── test_gui_smoke.py          # offscreen 起窗、点树、填表（含勾选框/下拉框）、假执行
```

---

## 5. 关键设计

### 5.1 默认规则文件（用户需求 7 的核心；**已落地为真实文件，不再是设计稿**）

**文件**：`clitree/rules/default.rules.json`（v3，5548 B，sha16 `69233c773054a0a6`，**严格 JSON**、14 个顶层键、**12/12 正则实测可编译**）。
它已装入本轮实测产出的全部数据：`evidence`（105 条命令读数）、`dialects`（方言识别）、`helpChannels`（通道 ＋ 安全白/黑名单）、`segments`、`optionBlock`、`widgets`（词表/枚举表/覆盖）、`subcommands`、`manPage`、`locale`、`limits`。

> ⚠️ **该文件是唯一真相源**：下面只是设计摘要，**改规则改文件本身，别改本节**（两处并存必然漂移）。改完跑 `clitree --check-rules`。

摘要（详情以文件为准）：4 类方言 `usage-posix` / `dashdash-interactive` / `man-page` / `blocks-only`（`windows-slash` 待实测）；通道序 `--help → -h → /? → -? → help → -help`，**`-h` 必须先在 `--help` 文本里被声明为 help 才允许跑**（实测白名单 20 个），24 条危险命令**永不探测**；控件词表与 `enumTables`（`ping -M/-T`）；子命令 `initialDepth=2 ＋ lazyExpand`。

以下为**设计期草稿存档**（已被上表文件取代，保留以便对照演进）：

```jsonc
{
  "rulesVersion": 2,                       // v1 的"逐行正则"设计已被 §11 实测推翻，见 §11.4
  "segments": {                            // 段落/小标题（中英双语）
    "usage":    ["usage", "用法", "使用情况", "synopsis"],
    "commands": ["commands", "命令", "子命令", "可用命令"],
    "options":  ["options", "选项", "参数", "主操作模式", "runtime-options", "description"]
  },
  "optionBlock": {                         // ★ 单位是「块」不是「行」
    "joinContinuation": true,              // 缩进更深 ⇒ 并入上一块（实测必需：pnpm/python3/tar）
    "continuationMinExtraIndent": 2,
    "nameToken": "(?<![-\\w])(--[A-Za-z][\\w-]*|-[A-Za-z][\\w-]*)" ,  // 注意：GNU 有 -pass-exit-codes
    "valueToken": "(<[^>\\s]+>|\\[=[^\\]]+\\]|=?[A-Z][A-Z0-9_]{1,})",
    "separators": ["\\s{2,}", "\\s*[:：]\\s*"]   // 两列式 与 冒号式（argparse）
  },
  "subcommands": {
    "initialDepth": 2,                     // ★ 加载时只到第 2 层
    "lazyExpand": true,                    // ★ 展开才探测（缓存结果）
    "maxDepth": 3,                         // 展开上限
    "fromCommandsSegment": true,
    "segmentEndWhen": "line-not-indented-or-new-title",
    "fallback": [["help", "-a"], ["--help-all"]]   // 段落抽取不可靠时的兜底（§11.3）
  },
  "required": { "fromUsageLine": true, "markers": ["<", ">"], "optionalWrappers": ["[", "]"] },
  "widgets": {                             // ★ 参数 → 控件类型（§5.5）；实测：能从 help 抽到真枚举的只有 2/864
    "flagMeans": "no-value-token",         // 该参数块里没有取值标记 ⇒ 勾选框（不是输入框）
    "enumFromHelp": {
      "phrases": ["one of", "can be one of", "one of the following", "可选值", "取值范围"],
      "shape": "<a|b|c>",
      "reject": ["<data|filename>"]        // 反例：curl -b 的 <data|filename> 是"取值形态"不是枚举集合
    },
    "enumTables": { "ping": { "-M": ["do", "dont", "want"], "-T": ["tsonly", "tsandaddr", "tsprespec"] } },
    "numericWords": ["count","num","number","size","timeout","interval","second","port","ttl","hop","retr","level","depth","width","height","byte","rate","mtu","priority","times"],
    "pathWords": ["file","path","dir","directory","filename","dest","destination","url","uri","host","address","interface"],
    "boolWords": ["true","false","enable","disable","toggle","[no-]"],
    "repeatMarkers": ["...", "multiple times", "可多次"],
    "exclusiveGroupsFromUsage": true,      // usage 里 `-p | --paginate | -P | --no-pager` ⇒ 单选组
    "comboEditable": true,                 // ★ 下拉一律可编辑（枚举抽不到时仍能自由填）
    "fallback": "text",                    // 判不出 ⇒ 文本框 ＋ 标「未确定」
    "overrides": {}                        // 用户一键纠正写这里（实际落在 rules.user.json），下次自动生效
  },
  "manPage": { "detect": ["^[A-Z0-9-]+\\(\\d\\)", "SYNOPSIS"], "fallbackArgs": [["-h"], ["--help-all"], ["help"]] },
  "locale": { "probeOrder": ["C", null] },
  "limits": { "maxOutputBytes": 262144, "timeoutMs": 5000, "maxConcurrentProbes": 2 }
}
```

- **正则一律 Python 语法**（`(?P<name>…)`）。初稿写成 .NET 风格 `(?<name>…)` —— Python `re` 会直接 `error`，这是 §11.4 抓到的自伤。
- 用户覆盖：`<QStandardPaths 配置目录>/rules.user.json` **浅合并**到默认规则之上；GUI 有「打开规则文件 / 重载规则」。
- `clitree --dump-rules` 打印生效规则（合并后）；`clitree --check-rules` 自检语法（坏 JSON ⇒ 非 0）⇒ 迭代可验证。

### 5.2 懒加载（`lazy.py`，D3 的核心）

| 时机 | 行为 |
|---|---|
| 点「加载」 | 跑**1 次**探测（根 CLI 的 help）⇒ 出第 1 层参数 ＋ 第 2 层子命令名单（**子命令名字只从根 help 的段落里抽，不逐个探测**） |
| 点开一个子命令节点 | 该节点置「加载中」→ 跑 **1 次**该子命令的 help → 填它的参数（第 3 层）＋ 它的子命令（再下一层，达上限则不再长） |
| 点「全量展开」 | 广度优先批量探测，最多 `maxDepth` 层、并发 ≤ `maxConcurrentProbes`、可中断；进度显示在日志区 |
| 缓存 | 同一 `(可执行文件, 子命令路径)` 只探测一次；可手动「重新探测该节点」 |
| 失败 | 探测超时/无输出 ⇒ 节点标「未能获取 help」并保留可重试，**不静默当成"无参数"** |

### 5.3 help 通道探测（`discovery.py`）—— **安全第一**

`--help` → `-h` → `/?` → `-?` → `help` → `-help`，逐个真跑，**以输出内容判定**：拿到非空输出且「含段落标题或含选项块」即视为成功（**忽略 rc**，§2 的 rc=129/2/255 是铁证）。

**安全铁律（全部写进规则文件，可在 GUI 里查看但不可被随手改坏）**：

1. **危险命令永不探测**：`shutdown`/`reboot`/`halt`/`poweroff`/`init`/`mkfs*`/`dd`/`fdisk`/`parted`/`mkswap`/`swapon`/`wipefs`/`blkdiscard`/`passwd`/`userdel`/`chpasswd`/`visudo`…（24 条）**任何通道都不跑**，GUI 里如实显示「按安全策略跳过」（本机实测：这 24 条一个都没被探测过）。
2. **`-h` 只在被声明时才跑**：先从 `--help` 文本里确认它写了 `-h … help`（实测 20 个命令如此，其中 18 个的 `-h` 与 `--help` **逐字节相同**，`ping`/`pnpm` 两条不同）⇒ 否则 `-h` 在别的命令上可能是**真实动作**（`sort -h`、`df -h`、`du -h` 都不是 help）。
3. **绝不分页、绝不交互**：`stdin` 关闭 ＋ `PAGER/MANPAGER/GIT_PAGER/SYSTEMD_PAGER=cat` ＋ 单通道超时 5 s ＋ 输出上限 256 KB（本机 105 条实测：无一超时、无一挂起）。
4. **交互式 CLI 走专用通道**（实测：`gdb --help` 只有 3071 B，而 `gdb -batch -ex "help all"` 有 **111 781 B ＝ 36×**）⇒ 规则里按命令名配 `interactiveChannels`，树里据此长出真正的命令树。

**质量分级**（105 条实测：`full` 76 ／ `weak` 15 ／ `usage-only` 14）：只有 `full` 才渲染完整参数树；`weak`/`usage-only` 显示原文 ＋ 明写「帮助过于简略，解析结果可能不完整」；**绝不把 27 字节的 `nslookup --help` 当成"该命令没有参数"**。

**方言识别**（`dialects`）：`man-page`（`GIT-CLONE(1)`）⇒ 回退 `-h`；`dashdash-interactive`（`awatch -- Set an access watchpoint…` ＋ `Command class:`）⇒ 用 gdb 语法族解析（实测回测命中 170/1531 行）；其余走 `usage-posix` 块模型。

### 5.4 三模式执行（`executor.py`）

| 模式 | 实现 | 日志 | 结果图标 |
|---|---|---|---|
| 新终端 | `terminals.py` 按平台：Linux `gnome-terminal -- bash -lc` / `xfce4-terminal -e` / `x-terminal-emulator`；macOS `osascript -e 'tell app "Terminal" to do script …'`；Windows `cmd /c start "" cmd /k …`（有 Windows Terminal 则 `wt`） | 不回流 | **拿不到子进程 rc** ⇒ 图标「已在终端启动」，**不假装成功** |
| 后台 | `QProcess`，`readyRead` 流式进日志区，可停止 | 实时回显 stdout/stderr | rc==0 ⇒ 成功，否则失败 |
| 静默 | 启动后不等（detached） | **零日志** | rc==0 ⇒ 成功，否则失败；运行期 `setOverrideCursor(WaitCursor)` |

- **安全铁律**：参数一律以 **argv 列表**交给 `QProcess`，**绝不拼接 shell 字符串**；写入新终端命令时 `shlex.quote`（POSIX）/ Win 引号规则转义。
- 运行中禁用参数编辑。

### 5.5 树、表单与「参数 → 控件」映射（本节的表就是 `widgets.py` 的全部逻辑）

- 节点类型：`root(cli)` / `subcommand` / `option-group` / `option`；根节点徽标 `分支 N · 子命令 M · 参数 K`。

**控件映射表**（判定顺序从上到下，命中即停）：

| 参数形态（怎么判） | 控件 | 语义 | 控件旁显示 |
|---|---|---|---|
| 该参数块**无取值标记**（`-D`、`--flood`、`ping -t` 这类） | **勾选框**（三态：默认／显式传／不传） | 勾=传该参数；灰=不传；help 若标注默认开则默认态为勾 | help 原文描述 ＋「判为开关：help 未标注取值」 |
| 取值有集合：描述含指示词且形态为 `<a\|b\|c>`，或 `enumTables` 给了 | **下拉框（可编辑）** | 选中=传该值 | 取值清单 ＋「判为下拉：描述含 one of …」 |
| 取值名/描述命中 `numericWords`（`<count>`、`<ttl>`…） | **数值框**（步进、可留空） | 空=不传 | 单位线索（从描述抽 `seconds`/`ms`） |
| 命中 `pathWords`（`<file>`、`<dir>`…；host/url 类除外） | **文本框 ＋「浏览…」** | 空=不传 | 路径类型 ＋ 推断依据 |
| 布尔语义（`[=true\|false]`、`--[no-]xxx`） | **三态下拉**（默认／启用／禁用） | 明确选择才传 | 三态说明 |
| 描述含 `...` / `multiple times` | **多值列表**（可增删行） | 空=不传 | 「可重复」 |
| usage 行里的互斥组（`-p \| --paginate \| -P`） | **单选组** | 选一个 | 组说明 |
| usage 行里的位置参数（`<destination>`） | **文本框（必填）** | 必填校验 | 必填标记 |
| **判不出** | **文本框 ＋「未确定」标签** | — | 一键改类型入口 |

**纠错闭环（★ 越用越准）**
- 每个控件旁显示**推断依据**；右键或小按钮可把该参数改成别的控件类型。
- 纠正**写进 `rules.user.json` 的 `widgets.overrides`**（键 = `CLI 名 ＋ 参数名`）⇒ 下次加载同一 CLI 自动正确，不必再改。
- **只写用户覆盖，不改进仓的 `default.rules.json`** ⇒ 随包规则保持干净可升级。

**「不猜」三原则**
1. `required` 不明 ⇒ 三态「必填／可选／未标注」，不默默填「必填」。
2. 枚举抽不到 ⇒ **可编辑下拉**（预置历史用过的值），**不硬造候选**。
3. 控件类型判不出 ⇒ 文本框 ＋「未确定」，**不假装它是开关**。⚠️ 例：本机 iputils 的 `ping -t <ttl>` 是**取值型**（`ttl`），而 Windows `ping -t` 是**无值开关**（持续 ping）⇒ **同名参数跨 CLI 语义不同，控件类型只能由该 CLI 自己的 help ＋ 规则决定，绝不硬编码参数名**。

- 默认值与示例抽取：`default` 从 `[default: x]`/`(默认: x)`/`(默认值为 x)` 抽；`example` 从描述里的 `e.g.`/`例如`/`如：`片段抽，抽不到显示 `示例：—`（**不编**）。

### 5.6 结果图标状态机

每按钮独立：`idle → running → ok | fail | launched(仅新终端)`；图标由 `icons.py` 内置 SVG 生成；状态记忆到 `store.py`（关窗保留）。

---

## 6. 任务分解（每步带 Validate）

### Phase 0 — 脚手架（**不用 venv**）
- Task 0.1：建 `pyproject.toml`、包骨架；依赖只写 `PyQt5`（系统已有，`pip install --user` 仅在缺件时用）。
- **Validate**：`python3 -c "import clitree, PyQt5.QtWidgets; print('ok')"`。
  ⚠️ 初稿写的是 `python3 -m venv .venv && .venv/bin/pip install -e .` —— **本机走不通**（§2：无 ensurepip、venv 看不到 dist-packages），已改。

### Phase 1 — 模型 ＋ 规则引擎 ＋ 控件推断（TDD 先行）
- Task 1.1：`model.py` 数据类（含 `widget_kind` / `widget_reason` / `choices` / `required_state`）。
- Task 1.2：落 `rules/default.rules.json` ＋ `rules.py`（加载/合并/校验）。
- Task 1.3：`parser.py` —— **块模型**（段落切分 → 选项块合并 → 名字/取值/描述抽取）。
- Task 1.4：`widgets.py` —— §5.5 映射表（纯逻辑，不依赖 Qt，可单测）。
- **Validate**：`pytest tests/test_parser_blocks.py tests/test_parser_subcommands.py tests/test_widgets.py -q`，16 条 fixture 逐条断言。
  块数基线（**本轮检验实测**，实现后若规则收紧须重算并记录差异，**不许直接把实测数字抄成"通过"**）：
  `pnpm 33 块｜tar 166｜gcc 42｜python3 30｜pip 26｜dotnet 12｜dotnet build -h 19｜git clone -h 35｜git clone --help 40（man 页分支）｜ping -h 20`；
  形态断言必含：`--color[=<COLOR>]`、`-pass-exit-codes`、`-b : desc`、`-A, --catenate, --concatenate`、**tar 续行里的 `--delete/--extract` 不得被当成新参数**。
  控件断言必含（这几条是判别力所在，缺一不可）：
  `ping -D` ⇒ **勾选框**；`ping -c <count>` ⇒ **数值框**；`ping -M <pmtud opt>` ⇒ **下拉 `do/dont/want`**；
  `curl -b <data|filename>` ⇒ **文本框，绝不判成下拉**（§11.8 的假阳）；`--[no-]xxx` ⇒ 三态；`--foo...` ⇒ 多值列表；
  每个判定都必须带 `widget_reason` 非空（**没有依据的判定 = 不合格**）。
  分布基线（§11.8：864 块实测 `勾选框 416｜文本 169｜文本＋浏览 123｜三态 97｜数值 57｜下拉 2`）——**仅作参照，实现时词表变全会漂移，须现场重算，不许当断言语义**。

### Phase 2 — help 通道探测 ＋ 子命令枚举
- Task 2.1：`discovery.py`（含 rc=129 判成功、man 页回退、`LC_ALL=C` 优先与原文重试）。
- Task 2.2：子命令段抽取 ＋ **兜底通道**（§11.3 实测段落抽取有假阳/假阴 ⇒ 必须有兜底与"不确定"态）。
- **Validate**：`pytest tests/test_discovery.py -q`；真跑 `git`/`tar`/`pnpm`/`pip`/`dotnet`/`python3` 六条，读数写进 README「验证记录」。

### Phase 3 — 懒加载
- Task 3.1：`lazy.py`＋树节点的加载中/失败/可重试三态。
- **Validate**：`pytest tests/test_lazy.py -q` —— 断言「加载 `git` 只产生 **1 次**探测」「点开 1 个子命令只多 **1 次**」「同一节点重复点开 **0 次**新增探测」「全量展开有上限与并发上限」；用假 CLI（可控 sleep/输出）计数，不依赖真 CLI 计时。

### Phase 4 — 执行器
- Task 4.1：`executor.py` ＋ `terminals.py`。
- Task 4.2：假 CLI（`tests/fixtures/fakecli.py`：可控 rc / stderr / sleep）。
- **Validate**：`pytest tests/test_executor.py -q` —— 后台模式断言日志逐行到达；**静默模式断言日志区零新增行**；rc 非 0 断言失败态；一条注入用例断言参数不经 shell。

### Phase 5 — GUI
- Task 5.1：主窗 ＋ 左树（含懒展开）＋ 右表单 ＋ 日志区 ＋ 运行栏。
- Task 5.2：拖放（`dragEnterEvent`/`dropEvent`，过滤可执行文件）。
- **Validate**：`QT_QPA_PLATFORM=offscreen pytest tests/test_gui_smoke.py -q`；再用 `xvfb-run -a` 跑一次并**截图留档**。

### Phase 6 — 规则迭代闭环
- Task 6.1：`--dump-rules` / `--check-rules` ＋ GUI「重载规则」。
- **Validate**：改一条规则 ⇒ 对应 fixture 断言按预期改变；坏 JSON ⇒ `--check-rules` 非 0。

### Phase 7 — 跨平台与打包
- Task 7.1：三平台路径与终端适配（`store.py` / `terminals.py` 分支）。
- Task 7.2：PyInstaller 打包脚本（Win `.exe` / macOS `.app` / Linux 单文件）。
- **Validate**：Linux 本机打包产物在 `xvfb-run` 下起窗；**Windows/macOS 无法在本机实测 ⇒ 记「未验证」**，不推测冒充读数。

### Phase 8 — 收尾
- Task 8.1：README（用法、规则文件说明、三模式差异、已知限制）。
- Task 8.2：全套 `pytest -q` ＋ 真 CLI 端到端清单跑一遍。
- **Validate**：全绿 ＋ 端到端读数写入 README「验证记录」。

---

## 7. 风险

| 风险 | 可能性 | 缓解 |
|---|---|---|
| help 文本天然不可完全解析 | **高** | **块模型**（§11 实测 403/403 块全部解析出名字）＋ 规则可迭代 ＋ 未识别段落**如实显示原文**；不猜 |
| 「选项名与描述分两行」形态（pnpm/python3 等） | 已实测，**必现** | `joinContinuation` 缩进合并；`test_parser_blocks.py` 固定该形态 |
| **续行里含 `-` 开头的词**被误判成新参数（tar 实测） | 高 | 续行判定优先于"新定义"判定；单列断言防回归 |
| **枚举取值在 help 里几乎不出现**（实测 431 个取值块中真枚举只有 **2** 个 ≈ 0.5%） | **高** | 下拉一律**可编辑**＋预置历史值；`enumTables` 手工迭代；抽不到**不造候选** |
| **控件类型误判**（`ping -t`：iputils 是 `<ttl>` 取值型、Windows 是无值开关；`ttl` 不在词表里会被当自由文本） | **高** | 每个控件显示**推断依据** ＋ 一键改类型 ＋ 纠正写进 `rules.user.json`；词表可迭代 |
| 把 `curl -b <data\|filename>` 这种「取值形态」误判成枚举下拉 | 中 | `widgets.enumFromHelp.reject` 黑名单 ＋ Phase 1 判别断言（§11.8 已实测该假阳） |
| **子命令段抽取不可靠**（实测 pnpm 假阳 91 / git 中文版假阴 2 / `git help -a` 抽 0 而真值 144） | **高** | 初始只出 2 层、其余懒展开；兜底通道 `help -a`；无法确定时标「不确定」而不编数字 |
| rc 不可信（`git clone -h`=129） | 已实测 | 判定只看输出内容 |
| locale 改变输出语言 | 已实测（`LC_ALL=C` 有效） | 双语规则 ＋ `LC_ALL=C` 优先、失败用原文重试 |
| 新终端模式拿不到子进程 rc | **必然** | 三态区分（启动≠成功），不谎报 |
| 无头环境无法人工点 GUI | 必然 | offscreen 冒烟 ＋ xvfb 截图；人工验收留给你 |
| PyQt5 为 GPL（若对外闭源分发有许可问题） | 中 | D1 已定：先 PyQt5 开工；`ui/qt.py` 薄适配层 ⇒ 日后切 PySide6(LGPL) 只改一处 |
| 新终端模式的转义漏洞 | 中 | argv 直传 ＋ `shlex.quote`；一条专门注入测试 |
| 跨平台打包无法本机验证 | 高 | 如实标「未验证」 |

---

## 8. 已定决策（D1–D5，按你的拍板）

| 编号 | 决策 | 落地方式 |
|---|---|---|
| **D1** | **Qt 绑定 = 先用本机 PyQt5**（不建 venv，用系统 `python3`），代码留 `ui/qt.py` 薄适配层；**若将来要对外分发**再换 PySide6(LGPL)（PyPI 实测可达） | §4 文件树、§6 Phase 0 |
| **D2** | **默认规则随包**（仓内 `clitree/rules/`，跟 git 迭代）；**用户覆盖 ＋ 最近记录走 `QStandardPaths`** | §5.1、§4 `store.py` |
| **D3** | **初始 2 层，后续再展开**：加载只解析「本 CLI 参数 ＋ 一级子命令名单」；子命令节点被点开才探测；另给「全量展开」（上限 3 层、限并发、可中断） | §1 第 3 点、§5.2、§6 Phase 3 |
| **D4** | **危险命令确认门：加，但只提示不阻断**，可开关、默认开 | §5.4 运行前检查（高危形态红字 ＋ 二次确认） |
| **D5** | 项目名 **`clitree`**（目录 `/home/links-dev/netTest/GitProj/clitree`） | 全篇 |

---

## 9. 验收（Acceptance）

- [ ] 输入 / 拖入一个 CLI，点加载 ⇒ 左树出现「本 CLI 参数 ＋ 一级子命令」共 **2 层**与统计徽标
- [ ] 子命令节点**未点开时没有任何探测进程**；点开后只多跑**该子命令的 1 次** help；重复点开命中缓存
- [ ] 「全量展开」受 `maxDepth`/并发上限约束且可中断
- [ ] 点任一节点，右侧按**参数形态**出控件：**无值参数是勾选框（带 help 解释、不是输入框）**、有集合取值的可编辑下拉、数值/路径/可重复/互斥组各就位，并带默认值、示例提示、必填/可选/未标注标记
- [ ] 每个控件显示**推断依据**；改一次控件类型 ⇒ 写进 `rules.user.json` ⇒ **重载后同一 CLI 自动用新类型**（且 `default.rules.json` 未被改动）
- [ ] 抽不到枚举时下拉**仍可自由输入**，且**没有任何凭空造出的候选值**
- [ ] 三个按钮分别验证：新终端真开窗、后台结果实时进本窗日志、静默模式日志区**零新增行**且鼠标 busy
- [ ] 每次执行后按钮图标反映上次结果（成功/失败/已启动/运行中）
- [ ] `rules/default.rules.json` 存在且可改；改后重载生效；`--check-rules` 拦得住坏规则
- [ ] `pytest -q` 全绿；11 条 fixture（含中文/两行块/man/argparse/GNU 长选项）断言通过
- [ ] 三平台代码路径就位；**Windows/macOS 标「未在本机验证」**，不谎报

---

## 10. 下一步

**等你批准开工**（`yes` / `modify: …`）。
开工后：先把 Phase 0–1 变成待办列表（一次列全、同时只留一条进行中），按各 `Validate` 逐条自证再往下走。
**两处已变的起点**：① `rules/default.rules.json` **已落地**（Phase 1 的 Task 1.2 因此从"写规则"变成"实现加载器 ＋ 校验器"）；② 解析器必须按 §11.4 的五条修正与 §11.8 的方言/通道读数实现，**再写测试**。
规则迭代继续按 §5.3 的安全策略跑真实 CLI（危险命令永不探测、`-h` 先验声明、stdin 关闭 ＋ 超时），新探测结果写回规则文件的 `evidence` 段。

---

## 11. 计划自检（本轮实测检验；**推翻了本计划初稿的多处设计**）

检验环境：`/tmp/clitree-probe/`（**16 条样本** ＋ 三版匹配脚本），2026-10-05，系统 `python3 3.10.12`。

### 11.1 通道与耗时（支撑 §2 与懒加载决策）

11 条样本全部取到 rc 与耗时（见 §2 表）；关键两条：**`git clone -h` rc=129 却有完整 help**、**`dotnet --help`/`dotnet build -h` 各 314 ms**。

### 11.2 初稿正则（逐行匹配）实测：**几乎全废**

| 组 | 定义 | 命中 |
|---|---|---|
| A 组 | 计划初稿 §5.1 的三条正则（逐行、`^` 锚定） | **4 / 412 候选行（1%）** |
| B 组 | 加强版逐行正则（加前导 `\s*`、多别名、取值放宽） | **231 / 412（56%）** |

⇒ 逐行匹配路线**证伪**：即便加强到 B 组，仍有 44% 的选项行漏掉，且 `pnpm`（选项名与描述分两行）**全漏（0/37）**。

### 11.3 块模型实测：**403/403 块全部解析出名字**

| 样本 | OPT 块 | 解析出名字 | 有描述 | 带取值 |
|---|---|---|---|---|
| pnpm_help | 33 | 33 | 33 | 17 |
| tar_help | 166 | 166 | 164 | 60 |
| gcc_help | 42 | 42 | 42 | 17 |
| python3_help | 30 | 30 | 30 | 7 |
| pip_help | 26 | 26 | 26 | 14 |
| git_clone_h | 35 | 35 | 34 | 18 |
| dotnet_help / dotnet_build_h | 12 / 19 | 12 / 19 | 12 / 19 | 8 / 9 |
| git_clone_help（man 页） | 40 | 40 | 40 | 17 |
| **合计** | **403** | **403** | **400** | **167** |

关键形态抽查（逐字）：`pnpm` 的 `--color[=<COLOR>]` 为 **2 行块**（名字＋取值在首行、描述在次行）；`gcc` 的 `-pass-exit-codes` 为 **单横线长名**；`python3` 的 `-b` 后跟 `:` 分隔描述；`tar` 的 `--occurrence[=NUMBER]` 是 **2 行块且续行里含 `--delete, --extract`**（必须算续行，不得算新参数）。

### 11.4 自检对计划的**强制修正**（已落进 §5.1/§6）

1. **命名组语法写错**：初稿用 .NET 风格 `(?<name>…)` ⇒ Python `re` 直接报错。→ 全改 `(?P<name>…)`。
2. **缺前导缩进匹配**：help 的选项行几乎都缩进 ⇒ A 组命中率 1% 的主因。→ 匹配前先去缩进或加 `\s*`。
3. **「逐行」必须升级为「块」**（名字行 ＋ 更深缩进续行合并）。→ `optionBlock.joinContinuation`。
4. **短选项 ≠ 单字符**：GNU 有 `-pass-exit-codes`。→ `nameToken` 用 `-[A-Za-z][\w-]*`。
5. **取值形态穷举不够**：`[=<COLOR>]`、`[=NUMBER]`、`[.MINOR]`、`{a|b|c}[,...]` 均实测存在。→ `valueToken` 放宽。

### 11.5 子命令段抽取实测：**不可靠（假阳＋假阴）**

| 样本 | 抽出条数 | 真值/判定 |
|---|---|---|
| pnpm_help | 91 | **假阳**（段结束判定失效，吞了后续段落） |
| pip_help | 9 | 与 `Commands:` 段相符 |
| git_help（中文） | 2 | **假阴**（中文版是**分组**列表，遇分组标题就停了） |
| git_help_a | 0 | **假阴**（真值 `^   [a-z]` 计数 = **144**） |
| dotnet_help / tar_help / git_clone_h | 0 | 无子命令段（正确） |

⇒ 支撑 D3：**加载时只出 2 层、其余懒展开**，并且子命令枚举必须有**兜底通道**与「不确定」态，**不许把抽出的数字直接当真相**。

### 11.6 计划文件自身自检（机器复算）

| 检验项 | 读数 |
|---|---|
| §5.1 声明的三条 token 正则能否在 Python 下编译（`nameToken`/`valueToken`/`manPage.detect`） | **3/3 compile OK**（初稿的 .NET 命名组语法会在这一步直接失败） |
| §5.1 的规则块是否自洽可解析（剥注释与尾逗号后 `json.loads`） | **OK**，顶层键 8 个；`rulesVersion=2`、`initialDepth=2`、`lazyExpand=True`、`maxDepth=3`、`timeoutMs=5000` 逐值读回 |
| 工作目录是否保持「未开工」 | `find` 全树只有 `plans/clitree.plan.md` **1 个文件**，无任何实现产物 |
| 计划章节完整性 | 11 个一级章节齐全（§1–§11） |

### 11.7 控件类型推断检验（本轮新增；直接决定 §5.5 的写法）

样本扩到 **16 条**（§11.3 的 11 条 ＋ `ping -h`、`curl --help all`、`ssh -h` 等），统计单位同为「块」。

| 推断出的控件类型 | 块数 | 占比 |
|---|---|---|
| 勾选框（块内无取值标记） | 416 | 48% |
| 文本框（自由） | 169 | 20% |
| 文本＋浏览（路径类取值名） | 123 | 14% |
| 三态（布尔语义） | 97 | 11% |
| 数值框 | 57 | 7% |
| **下拉（真枚举）** | **2** | **0.2%** |
| 合计 | 864 | |

**结论（每条都有读数）**：

1. **枚举几乎抽不到**：431 个「有取值块」里只有 **2 个**能从 help 抽出集合，且都是 `ping` 的 `one of <a|b|c>` 形态（`-M → do|dont|want`、`-T → tsonly|tsandaddr|tsprespec`）⇒ 「是选项就给下拉」**不可能靠 help 自动兑现**，只能靠 ①规则 `enumTables` ②用户纠正 ③**可编辑下拉**兜底 —— 这就是 §5.5 改成「可编辑下拉 ＋ 纠错写回 `rules.user.json`」的直接原因。
2. **假阳实测**：`curl -b <data|filename>` 会被朴素规则当成取值集合（它其实在说"取值可以是 data 或 filename 两种形态"）⇒ §5.1/§5.5 加了 `reject` 黑名单与一条**判别断言**（Phase 1）。
3. **`ping -t <ttl>` 被判成「自由文本」**（`ttl` 不在检验词表里）⇒ 词表本身是**可迭代项**，撑不住的地方必须靠「推断依据 ＋ 一键改类型」；同时它是**同名参数跨 CLI 语义不同**的铁证（Windows `ping -t` 是无值开关）⇒ 绝不硬编码参数名。
4. **rc 第三次证明不可信**：`ping -h` 给出 20 个参数块的完整帮助却 **rc=2**；`ssh -h` **rc=255**（只有 510 B 的一行 usage）。
5. **未检验（NOINFO）**：Windows/macOS 的 `/?`、`-?` 帮助形态与它们的枚举表达方式（无该平台机器）；CLI 自带 shell 补全（bash/zsh completion）能否当枚举来源 —— **未试，不在本计划承诺内**。

### 11.8 全量 CLI 探测（本轮新增：105 条命令；系统命令 ＋ git/pnpm/dotnet 第三方 ＋ 网络抓包族 ＋ gdb 家族）

安全策略：**危险命令不进候选清单**（24 条）、`-h` 只在被 `--help` 声明时跑、`stdin` 关闭 ＋ 分页器全部 `cat` ＋ 5 s 超时。**实测 0 超时、0 挂起、危险命令 0 次执行**。

| 读数 | 值 |
|---|---|
| 探测成功 | **105 条**（第一批 78 ＋ 第二批 27） |
| **未安装（NOINFO）** | **15 条**：`dumpcap ncat tftp lftp whois ifconfig route arp iptables nft ethtool nmap gdbserver ltrace valgrind` |
| 质量分级 | `full` **76（72%）**｜`weak` 15｜`usage-only` 14 |
| 方言 | `usage-posix` 92｜`blocks-only` 6｜`unknown` 5｜**`dashdash-interactive` 2** |
| 零块条数 | 27 |
| **真枚举** | 全库仍只有 **2 条**（`ping -M`/`-T`）⇒ 样本扩大 6.5 倍，「枚举抽不到」的结论**更强**（§11.7 的 0.2% 不是小样本偶然） |
| **`-h` 通道** | 20 个命令声明了 `-h`；其中 **18 个与 `--help` 输出逐字节相同**，`ping`/`pnpm` 两条不同 |
| **rc 不可信（第三、四次复证）** | rc≠0 却给出可用 help：`ping(2) awk(2) which(2) ip(255) ssh(255) tracepath(255) dig/host/scp/killall/top/npm/ftp/nc/socat/telnet/sftp/netcat(1)` |
| **交互式放大** | `gdb --help` 3 071 B → `gdb -batch -ex "help all"` **111 781 B（36×）**，且是**另一种语法**（`awatch -- Set an access watchpoint…` ＋ `Command class:` 分组） |
| 网络/抓包族 | `tcpdump`（`--help` 与 `-h` 同为 589 B）｜`ftp`（`--help`/`-h` 同为 501 B，rc=1）｜`nc`/`netcat`/`socat`/`telnet`/`sftp` 仅 usage-only｜`mtr` full(35 块)｜`tracepath` 6 块 |
| gdb 家族 | `gdb` full(34 块)｜`strace` 66｜`objdump` 63｜`readelf` 48｜`nm` 36｜`strip` 28｜`strings` 15｜`addr2line` 13｜`elfedit` 12｜`size` 7｜**`gcore` 仅 50 B、`gdb-add-index` 40 B（usage-only）** |
| 段落标题实测词频 | `options×14 usage×10 examples×4 commands×4 other options×3` ＋ `main operation mode`/`operation modifiers`/`exit status`/`valid arguments for -d` 等一次性标题 ⇒ **标题是开放集合**，只能"结构判定优先 ＋ 词表兜底"，**不许穷举** |

产物：`clitree/rules/default.rules.json`（v3）就是据此写成的；其中 `evidence` 段保存了上述数字，便于日后迭代时对照。

### 11.9 未检验（NOINFO，不许当已知）

- Windows / macOS 的实际 help 形态（本机无法取样本；`/?` 与 PowerShell `-?` 通道**未实测**）。
- man 页正文的**完整**解析（只验证了 man 页**识别**成立；正文解析未做，计划里也只承诺回退）。
- 打包（PyInstaller）在本机的可行性 —— **未试**，Phase 7 才验。
- 真机三平台终端模拟器适配 —— Linux 侧只确认了 `gnome-terminal`/`xfce4-terminal` 存在，**未实际开窗验证**。

---

## 12. 实施与验证记录（TDD 测试先行；全部为本轮实测读数）

### 12.1 交付件

```
clitree/                       （项目根 = /home/links-dev/netTest/GitProj/clitree）
├── pyproject.toml  README.md  plans/clitree.plan.md
├── clitree/
│   ├── __main__.py  app.py
│   ├── core/{model,rules,parser,widgets,discovery,lazy,executor,terminals,store}.py
│   ├── ui/{qt,icons,tree_panel,param_form,log_panel,run_bar,main_window}.py
│   └── rules/default.rules.json          ← 规则唯一真相源
└── tests/  （8 个测试文件 ＋ 27 条 help fixture ＋ fakecli.py）
```

### 12.2 测试读数

| 阶段 | 读数 |
|---|---|
| RED（先写测试） | `pytest -q` ⇒ **9 个测试文件全部收集错误**（模块不存在）—— 测试确实先行 |
| GREEN | `pytest -q` ⇒ **110 passed**（解析块/子命令/控件/通道/懒加载/执行器/落盘/GUI 冒烟） |
| 真 CLI 端到端 | `ping` 33 参数；后台 `ping -c 1 127.0.0.1` ⇒ **日志 +6 行、按钮 `ok`**；静默 ⇒ **日志 +0 行、按钮 `ok`**；新终端 ⇒ `launched` |
| 截图 | offscreen 198 226 B ／ xvfb 162 312 B（1200×780，肉眼确认树·参数区·三按钮·日志·状态栏齐备） |

### 12.3 与计划的偏差（逐条，都是实测逼出来的）

1. **规则文件位置**：计划写 `clitree/rules/default.rules.json`，而上一轮先落在了项目根 `rules/` ⇒ 实施时**移进包内**（`pip` 安装后仍可用，且与计划一致）。
2. **core 不依赖 Qt**：计划说配置路径走 `QStandardPaths`，实现改为**按平台约定自算**（`XDG_CONFIG_HOME` / `APPDATA` / `~/Library/Application Support`）。理由：`core` 要能无头单测；结果等价。
3. **控件判定顺序**：计划表把「开关」放第一，实测发现**「可重复」必须优先于「开关」**（`-v, --verbose  repeatable, use multiple times` 否则会被判成复选框）⇒ 实现顺序：三态 → 可重复 → 开关 → 下拉 → 数值 → 路径 → 文本。
4. **取值 token 必须紧贴参数名**：实测 `-d    use SO_DEBUG socket option` 会把描述里的 `SO_DEBUG` 当成取值（假阳）⇒ 规则加 `valueMustBeAdjacentToName`，`-d` 恢复为复选框。同时 `<[^>]+>` 允许空格，否则 `-M <pmtud opt>` 取不到值。
5. **无 `Options:` 标题时的兜底**：`curl --help all` 等工具的 help 没有段标题，逐段解析会把参数树抽空 ⇒ 加"options 段为空时对全文做块解析"的兜底（curl 从 0 → **244 个参数**）。
6. **子命令兜底加条件**：全文兜底只在文本出现过「command(s)/命令」字样时启用，否则 `lsblk` 会把 `Available output columns` 的 **54 个列名**当成子命令（实测假阳，已用测试锁住）。
7. **方言判定区分大小写**：规则里 `usage-posix` 的 `anyLineMatches` 必须带 `(?i)`，否则 `Usage:` 匹配不上（pnpm 会被判成 `blocks-only`）。
8. **无头环境提示**：`python3 -m clitree` 在无 `DISPLAY` 时原本直接 Qt 崩溃 ⇒ 改为打印明确指引（rc=2），并让 `--tree` 自动走解析模式。
9. **测试期望按实测修正 3 处**（改测试、不改实现去迎合）：`python3 -b` 是开关而非取值（实测 `-b : issue warnings`）、`position=0` 判定要用 `is not None`、pnpm 子命令上限从 70 放宽到 120（实测 91 条**是真命令**，且无 `verbose/color` 等假阳）。

### 12.4 仍未验证（NOINFO，不许当已知）

- **Windows / macOS**：`/?`、`-?` 通道、`cmd start`/`osascript` 开终端、PyInstaller 打包 —— 全部只有代码就位，**未实测**。
- **新终端模式是否真的起了窗口**：本机无图形环境，只能读到按钮 `launched`（Popen 成功），窗口本身未验证。
- **中文/其它 locale 下 CLI 输出的长期稳定性**：只测了本机当前 locale。

### 12.5 复现命令

```bash
cd /home/links-dev/netTest/GitProj/clitree
python3 -m pytest -q                        # 110 passed
python3 -m clitree --check-rules            # RULES-CHECK=PASS
python3 -m clitree --parse ping             # 真探测：32 参数、-c 数值、-M 下拉
python3 -m clitree --tree git               # 根 loaded ＋ 22 子命令 pending（2 层）
QT_QPA_PLATFORM=offscreen python3 /tmp/clitree-e2e/e2e.py    # 三模式端到端
xvfb-run -a python3 /tmp/clitree-e2e/e2e.py                  # 真 X 渲染 ＋ 截图
```

### 12.6 截图暴露并修复的真缺陷（第三个测试批次）

生成 `screenshots/` 时肉眼发现的三个问题，全部**先写测试（RED）再修**，现已 113 项全绿：

| 缺陷 | 现象 | 修法 | 新测试 |
|---|---|---|---|
| **子命令探测顺序错**（真缺陷，影响正确性） | 点开 `git clone` 右侧出现 **7 个假位置参数** —— 因为拼成了 `git -h clone`，拿回来的是**父命令**的帮助（`git -h clone` ⇒ `未知选项：-h` ＋ git 主 usage，里面有 `[-C <path>] [-c <name>=<value>]`） | 通道参数必须跟在子命令**之后**：`path + args`（`git clone --help`）；修后 `clone` 得到**它自己的 37 个参数** | `test_subcommand_path_comes_before_the_channel_flag` |
| **选项取值被当成位置参数** | `[-C <path>]`、`[-c <name>=<value>]`、`[--exec-path[=<path>]]` 里的 `<path>`/`<name>` 都变成了位置参数 | 先剔除「选项名 ＋ 其取值」再抽裸占位符；同时**支持中文占位符**（`<仓库>`/`<路径>`，实测 git 中文帮助） | `test_option_values_are_not_counted_as_positional`、`test_cjk_positionals_are_kept_and_placeholder_skipped` |
| 数值框空值显示 `-1000000` | `QSpinBox` 的 `setSpecialValueText("")` 被 Qt **忽略空字符串** | 改成 `（不传）` | GUI 冒烟（`test_widget_types_match_param_shape`）覆盖 |

复现命令追加：`xvfb-run -a python3 tools/make_screenshots.py` ⇒ 9 张图。


### 12.7 可用性修订（2026-10，第二轮 TDD：12 个新测试先 RED 再 GREEN）

用户提的四条，逐条落地并留读数：

| 问题 | 根因（实测） | 修法 | 读数 |
|---|---|---|---|
| ping 满屏 `[未标注]` | 32 个选项**全部** `required=unknown` —— 因为 `ping [options] <destination>` 这个 usage 行只提到位置参数，我把「没提到」当成了「未标注」 | 口径改为：**usage 行存在时，选项一律是「可选」**（不传也能跑），只有位置参数分必填/可选；连 usage 都没有才保持 `unknown` = 「？未判定」，并给 `ParseResult.usage_marks_required` 记录依据 | 修后 ping：**32 个选项全部 optional、0 条带标记**，唯一标记是 `<destination> [＊必填]` |
| 只有参数名、不知道填什么 | 描述只存在 tooltip 里；标签只显示 `o.label`（短名） | 标签改为**全称＋简称＋取值占位**（`-c, --count <count>`），每条参数**下方常显一行灰字 help 说明**；tooltip 保留推断依据/默认/示例 | `git clone`：`-v, --verbose` 等 35 条选项＋2 条位置参数，全部带中文说明 |
| 必填项不排前面 | 表单按 help 原顺序渲染 | `ParamForm.sort_specs`：**位置参数 → 必填 → 其它按原顺序**（稳定排序，数据层不动） | ping 首行 = `<destination> [＊必填]`；`git clone` 首两行 = `<仓库>`（必填）、`<路径>` |
| 执行后不能停 | 无停止通道，`RunHandle` 只有等待 | `RunHandle.stop()`（terminate → 3 s → kill）；`RunBar` 运行中把该按钮文字改成 `■ 停止`、`main_window.run()` 第二次点击即走停止分支；新增 `stopped` 状态与图标 | 端到端：`ping -c 30 127.0.0.1` 运行中按钮为 `■ 停止`，再点一次 ⇒ `state=stopped`、进程被终止（截图 09/10） |

复算命令：`python3 -m pytest -q`（**125 passed**）、`xvfb-run -a python3 tools/make_screenshots.py`（11 张）。


### 12.8 CLI 配置文件（`cli/<工具名>.json`：多配置 ＋ 解析缓存；第三轮 TDD，25 个新测试）

用户要求：解析过的工具在程序目录 `cli/` 下留一个配置文件；一个文件里放多个配置；右侧下拉切换；
**不全量解析也能靠这个文件载入解析结果和参数值**；当前值可另存为新配置并起名。

| 需求 | 实现 | 读数（端到端实测） |
|---|---|---|
| 解析即落文件 | `core/profiles.py`：`save_node()` 写 `targets["<命令路径>"]`（含 `options` 参数树本体 ＋ `channel/rc/grade/dialect` ＋ help 的 `raw_sha256`/`raw_bytes`/`raw_head`） | 加载 `ping` ⇒ `cli/ping.json` 生成，**18 362 B**，根缓存 **33 个参数** |
| 一个文件多个配置 | `profiles` 字典 ＋ `activeProfile` | 同文件里三个配置：`默认`（空）、`回环两次`（`@0=127.0.0.1 -c=2`）、`外网五次`（`@0=8.8.8.8 -c=5`） |
| 右侧下拉切换 | 配置行：`[下拉][保存][新配置名][另存为…][删除][重新解析]`；`switch_profile()` 会**先把当前值写回旧配置**再载入新值 | 切到「回环两次」⇒ 表单值 `{'@0': '127.0.0.1', '-c': '2'}` |
| **不全量解析也能载入** | `load_command()` 先查 `cached_node()`：命中就直接渲染树与表单，**不起探测**；「重新解析」才强制跑 help | 第二个窗口加载 `ping`：**探测 0 次**、`loaded_from_cache=True`、参数 33 个齐全；点「重新解析」⇒ 探测 1 次、标志复位 |
| 另存为新配置 | `save_as_profile(name)`（**不回写旧配置**，语义＝复制当前值建新配置） | 存两个新配置后下拉里三个并存，重开窗口仍在（跨窗口持久） |

其它：程序目录不可写时自动回退用户配置目录（有测试）；坏 JSON 不致命（按空骨架继续并有测试）；
`cli/` 已加进 `.gitignore`（可能含主机/路径类参数值，不应默认入库）。
新增截图 `11-cli-profiles.png`、`12-profile-switched.png`；`python3 -m pytest -q` ⇒ **150 passed**。


### 12.9 参数说明：记录 ＋ 改成自己的（第四轮 TDD，8 个新测试）

用户追问「配置文件是否记录了参数说明、能否改成自己的说明」。核对结论与落地：

| 问 | 核对读数 | 结论 |
|---|---|---|
| 是否记录 help 说明 | 缓存里每个参数 **15 个字段**，含 `desc`（help 原文）、`widget_reason`（推断依据）、`default`/`example`/`choices` | **已经记录**（`cli/ping.json` 里 `-c` ⇒ `desc='stop after <count> replies'`） |
| 能否改成自己的说明 | 原实现 `profiles` 里**只有 `values`**，全文件无处安放用户说明、界面也无入口 | **原为「没有」，本轮补上** |

新增（本轮）：

- `profiles.set_note/get_note/all_notes`：**文件级 `notes`**（对本 CLI 所有配置生效）＋ **配置级 `profiles.<name>.notes`**（只对该配置生效）；空文本＝清除并回落到 help 原文。
- 界面：说明那一行是**可双击编辑**的标签 —— 双击变输入框、回车/失焦提交；显示规则 `✎ 你的说明　（原：help 原文）`，**一眼分得出哪句是你写的**；清空即回原文。
- 写入时机：双击默认写**文件级**；`set_note(..., scope="profile")` 写**配置级**（要更细的粒度时用）。
- 持久化：新窗口走缓存那条路加载后，自定义说明仍在（测试 `test_custom_note_persists_into_file_and_next_session`）。

端到端读数（真 ping）：① 默认 `stop after <count> replies`；② 改后 `✎ 我常用 2；外网改 1，别超过 5　（原：stop after <count> replies）`；
③ 配置级覆盖 `✎ 外网限速，用 1`；④ 切到「默认」回落到文件级；⑤ 清掉配置级 ⇒ 回落文件级；
⑥ 文件落点 `notes = {'-c': …}`、`profiles.外网.notes = {'-c': …}`。新增截图 `13-custom-note.png`；`pytest -q` ⇒ **158 passed**。
