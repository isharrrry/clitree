# CliTree —— 把命令行工具变成可点选的参数树

[English](README.md) | **中文** | [Español](README.es.md)

> 拖进一个可执行文件（或输入一个命令）→ 点「加载」→ 左边出参数树、右边按参数形态出控件、
> 下面三个按钮分别用「新终端 / 后台 / 静默」方式执行。不用记 `--help`，也不用在命令行里敲。

跨平台（Windows / Linux / macOS）、纯 Python ＋ PyQt5、依赖只有系统 Python 与 Qt。

![加载 ping 后的参数面板](screenshots/01-load-ping-widgets.png)

## 它解决什么问题

命令行工具的用法都藏在 `help` 里：参数名只有缩写、说明只有一行、哪个必填要自己看 usage 行、
枚举值散落在描述文字里。CliTree 把这些**解析成结构化数据**并渲染成可操作的界面：

- **参数树**：本命令的参数 ＋ 一级子命令；**点开某个子命令才会去跑它的 help**，不是一次性全解析；
- **按形态出控件**：不取值的参数给**勾选框**、有固定取值的给**可编辑下拉**、数值给数值框、路径给「浏览…」、
  可重复的给多值列表；每条参数都显示**全称＋简称＋取值占位**和 **help 原文说明**；
- **说明可以改成你自己的**：双击说明那一行即可改写，写进配置文件，下次还在；
- **三种执行方式**：开真终端跑 / 后台跑并把输出实时回显到本窗口 / 静默跑（只转鼠标、不写日志）；
  执行中按钮变「■ 停止」，再点一次即终止进程；按钮图标记住各自上次的结果；
- **配置可复用**：每个工具一个配置文件，里面能放**多个配置**（不同机器、不同场景的参数值），
  也能缓存解析结果 —— **下次加载同一个工具不必再跑 help**。

## 快速开始

```bash
git clone <你的仓库地址> clitree && cd clitree

# 只依赖系统 Python（>=3.9）与 PyQt5
python3 -c "import PyQt5" || python3 -m pip install --user PyQt5

python3 -m clitree                # 打开界面
python3 -m clitree git            # 打开界面并直接加载 git
```

无头机器（没有 `DISPLAY`）上开窗可以用 `xvfb-run -a python3 -m clitree`；
不想开窗就直接用解析模式（见下）。

## 界面速览

| 加载后只有 2 层 | 点开子命令才探测 | 一台机器多个配置 | 说明可以改成自己的 |
|---|---|---|---|
| ![两层](screenshots/05-git-two-levels-collapsed.png) | ![展开](screenshots/06-git-clone-expanded.png) | ![配置](screenshots/11-cli-profiles.png) | ![说明](screenshots/13-custom-note.png) |

| 后台执行的输出进本窗 | 静默执行不写一行日志 | 执行中可停止 | 危险命令被拦住 |
|---|---|---|---|
| ![后台](screenshots/02-run-background-log-ok.png) | ![静默](screenshots/03-run-silent-zero-log.png) | ![停止](screenshots/09-running-stop-button.png) | ![安全](screenshots/08-dangerous-refused.png) |

全部 14 张截图在 [`screenshots/`](screenshots)，可用
`xvfb-run -a python3 tools/make_screenshots.py` 重新生成。

## 命令行用法

界面之外，CliTree 也能当解析器用（便于脚本化与调试规则）：

```bash
python3 -m clitree --parse ping                 # 真去探测 ping 并打印解析结果
python3 -m clitree --parse --help-file help.txt # 直接解析一个 help 文本文件
python3 -m clitree --tree git                   # 连树一起打印（根已解析、子命令待展开）
python3 -m clitree --check-rules                # 校验规则文件（坏 JSON / 坏正则会报出来）
python3 -m clitree --dump-rules                 # 打印生效规则（默认规则 ＋ 你的覆盖）
```

## 四个核心概念

1. **解析是「块模型」，不是逐行正则。** 选项名和说明常常分处两行（`pnpm -v, --version` 与下一行的说明），
   续行里还可能再出现 `--delete` 这种词（tar）——CliTree 按「块」合并，续行不会变成新参数。
   细节见 [解析规则](docs/parsing-rules.zh-CN.md)。
   所有解析行为都写在 `clitree/rules/default.rules.json` 里（每条规则旁记录它的实测依据），
   你自己的覆盖写 `~/.config/clitree/rules.user.json`，改完用 `python3 -m clitree --check-rules` 自检。
2. **必填口径**：usage 行存在时，**选项一律算可选**（不传也能跑），只有**位置参数**分必填/可选；
   连 usage 都没有时才显示「？未判定」。必填项与位置参数会被排在表单最前面。
3. **配置即文件**：`cli/<工具名>.json` 一个文件里装**解析结果缓存** ＋ **多个配置** ＋ **你自己的参数说明**。
   下次加载同一工具直接用缓存，不跑 help。详见 [配置](docs/configuration.zh-CN.md)。
4. **执行只走 argv**：参数以列表直接交给子进程，**绝不拼 shell 字符串**；
   表单末尾的「其他输入」会按空格拆开、追加到命令末尾；开新终端时才做平台引号转义。
   详见 [执行模式](docs/execution-modes.zh-CN.md)。

## 安全

- **危险命令永不探测、永不执行**：`shutdown` / `reboot` / `mkfs*` / `dd` / `fdisk` / `passwd` 等 24 条，
  在任何入口（拖入、输入、缓存、执行）都会被拦住并说明原因；
- **`-h` 只在 `--help` 文本里声明过它时才跑**（因为 `sort -h`、`df -h` 不是 help）；
- 探测一律：关闭 stdin ＋ `PAGER/MANPAGER/GIT_PAGER/SYSTEMD_PAGER=cat`（防分页挂起）＋ 单通道 5 秒超时 ＋ 256 KB 输出上限；
- 执行新终端时用 `shlex.quote`（POSIX）或 Windows 引号规则转义。

## 文档

文档与 README 一样有**英文 / 中文 / 西班牙文**三语版本，入口见 [文档索引](docs/index.zh-CN.md)。

| 想了解 | 看 |
|---|---|
| 架构、模块职责、数据流 | [architecture](docs/architecture.zh-CN.md) |
| help 怎么解析、规则文件怎么改 | [parsing-rules](docs/parsing-rules.zh-CN.md) |
| `cli/<工具名>.json` 的完整格式 | [configuration](docs/configuration.zh-CN.md) |
| 三种执行方式与停止语义 | [execution-modes](docs/execution-modes.zh-CN.md) |
| 参与开发、跑测试、出截图 | [contributing](docs/contributing.zh-CN.md) |
| 模块依赖关系（自动生成） | [DEPENDENCY-TREE](docs/DEPENDENCY-TREE.md) |

## 开发

```bash
python3 -m pytest -q                              # 165 项测试（160 通过；5 项平台差异项见「已知限制」）
python3 tools/deps_tree.py                        # 重新生成依赖关系树
xvfb-run -a python3 tools/make_screenshots.py     # 重新生成 14 张界面截图
```

本机实测环境：Linux 部分 Python 3.10.12 ＋ PyQt5 5.15.6，Windows 部分 Python 3.14.6 ＋ PyQt5 5.15.11；测试在 `QT_QPA_PLATFORM=offscreen` 下运行。
开发约定与「哪些东西没验证」写在 [contributing](docs/contributing.zh-CN.md)。

## 本机验证记录（实测）

| 项 | 读数 |
|---|---|
| 测试 | `python3 -m pytest -q` ⇒ **160 passed**（解析 29 条真机 fixture、控件推断、通道安全、懒加载、执行器、配置文件、GUI 冒烟；其余 5 项为平台差异项，见「已知限制」） |
| 真 CLI 解析 | `ping` 33 项参数（`-c` 数值、`-M` 下拉 `do/dont/want`、`-I` 路径、`-D` 开关）｜`git` 22 个子命令｜`tar` 166 个参数｜`curl --help all` 244 个参数｜`gdb` 走交互通道拿到 **111 781 B**（它的 `--help` 只有 3 071 B） |
| Windows 实测（2026-10） | Windows 11 ＋ Python 3.14.6 ＋ PyQt5 5.15.11：`ping` 解析出 18 项参数（裸词位置参数 `target_name` 必填、数字选项 `-4`/`-6`、`-n` 数值框）；`ping -n 2 127.0.0.1` 端到端执行 ⇒ rc=0 收到回显；英文与中文（zh-CN）两版帮助都已入库为 fixture |
| 懒加载 | `--tree git` ⇒ 根已解析、22 个子命令全部 `pending`；同一节点重复展开 **0 次**新增探测 |
| 缓存与配置 | 第二个窗口加载 `ping` ⇒ **探测 0 次**（直接走缓存）；配置切换、另存为、说明两层均实测，见 [配置](docs/configuration.zh-CN.md) |
| 三模式 | 后台 `ping -c 2 127.0.0.1` ⇒ 日志 **+6 行**、按钮 `ok`；静默执行同一命令 ⇒ 日志 **+0 行**、按钮 `ok`；执行中 `ping -c 30` 再点一次 ⇒ 状态 `stopped` |
| 安全 | 24 条危险命令在任何入口被拒（加载 `/sbin/shutdown` ⇒ 树与表单为空 ＋ 状态栏写明理由） |
| 规则自检 | `python3 -m clitree --check-rules` ⇒ `RULES-CHECK=PASS`（12/12 正则可在 Python 下编译） |
| 全部截图 | `xvfb-run -a python3 tools/make_screenshots.py` ⇒ **14 张**（offscreen 与真 X 渲染两种都跑过） |

取数环境：Ubuntu 22.04 ＋ Python 3.10.12 ＋ PyQt5 5.15.6（Linux 部分）；Windows 11 ＋ Python 3.14.6 ＋ PyQt5 5.15.11（Windows 部分）。**表格里没有一行是估计值**；取不到的项一律写进 [已知限制](#已知限制如实列出) 与 [参与开发](docs/contributing.zh-CN.md)。

## 已知限制（如实列出）

- **Windows 仅部分实测（2026-10），macOS 未验证**：`ping` 的解析与执行、本机测试套件已在 Windows 11 上跑过（见上表）；`-?` 通道、`cmd start` 开终端、打包仍未验证；
- **枚举取值多数抽不到**：105 个真实命令里，help 里显式写取值集合的只有 `ping` 两处 ⇒ 下拉框一律可编辑，抽不到就不造候选；
- **子命令段抽取不可靠**：`pnpm` 91 条为真、`lsblk` 的列名段必须靠兜底条件挡掉，所以初始只出 2 层、展开才探测；
- **新终端模式拿不到子进程返回码**：因此它只显示「已在终端启动」，不判成败，也不能停止。

## 许可证

[MIT](LICENSE)。
