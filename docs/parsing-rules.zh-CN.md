# 解析规则

[English](parsing-rules.md) | **中文** | [Español](parsing-rules.es.md)

> 属于 **CliTree** 文档的一部分 —— 返回 [README](../README.zh-CN.md)。

这一篇讲「help 文本怎么变成参数树」，以及规则写在哪、怎么改、怎么验证。

## 1. 通道：先拿到 help 文本

顺序：`--help` → `-h` → `/?` → `-?` → `help` → `-help`，逐条真跑，命中即停。

**判定只看输出内容，rc 完全不可信**——这不是理论，是实测：

| 命令 | rc | 实际情况 |
|---|---|---|
| `git clone -h` | **129** | 输出了完整的简洁帮助 |
| `ping -h` | **2** | 输出 20 个参数的完整帮助 |
| `ip --help` / `ssh --help` | **255** | 有输出（ssh 只有一行 usage） |
| `npm --help` | 1 | 有输出 |
| `dotnet --help` | 0 | 314 ms 才返回（所以单通道超时给 5 秒） |

**质量分级**：拿到文本后分三档 —— `full`（≥3 个参数块）、`weak`（有内容但结构弱）、`usage-only`（只有用法行）。
界面上 `weak` / `usage-only` 会明确提示「帮助过于简略，解析结果可能不完整」，
**绝不把 27 字节的 `nslookup --help` 当成「该命令没有参数」**。

本机 105 个真实命令的分布：`full` **76**、`weak` **15**、`usage-only` **14**；零块（拿不到参数）27 条。

## 2. 安全策略（写在规则文件里）

1. **危险命令永不探测、永不执行**：`shutdown`、`reboot`、`halt`、`poweroff`、`init`、`telinit`、
   `mkfs*`、`dd`、`fdisk`、`parted`、`mkswap`、`swapon`、`swapoff`、`wipefs`、`blkdiscard`、
   `passwd`、`userdel`、`groupdel`、`chpasswd`、`visudo`、`at`、`batch` —— 共 24 条，任何入口都拒绝。
2. **`-h` 必须先被声明**：只有当 `--help` 文本里写了 `-h … help`（或该命令在实测白名单里）才允许跑 `-h`。
   原因：`sort -h`、`df -h`、`du -h`、`free -h` **都不是 help**，是无条件跑命令。
3. **绝不分页、绝不交互**：关闭 stdin，`PAGER`/`MANPAGER`/`GIT_PAGER`/`SYSTEMD_PAGER` 全部设为 `cat`，
   单通道超时 5 秒，输出上限 256 KB（本机 105 条实测：0 超时、0 挂起）。
4. **交互式 CLI 走专用通道**：`gdb --help` 只有 3 071 B，而 `gdb -batch -ex "help all"` 有 **111 781 B（36 倍）**，
   而且语法完全不同（`awatch -- Set an access watchpoint…` ＋ `Command class:` 分组）。
   规则文件里按命令名配 `interactiveChannels`。

## 3. 四种方言

| 方言 | 识别依据 | 例子 | 解析方式 |
|---|---|---|---|
| `man-page` | 首行形如 `GIT-CLONE(1)` | `git clone --help` | 不算成功，回退到 `-h` |
| `dashdash-interactive` | 含 `Command class:` 或 ≥5 行 `名字 -- 说明` | `gdb -batch -ex "help all"` | 按 gdb 语法解析（本机回测命中 170/1531 行） |
| `usage-posix` | 有 `usage:` / `用法:` / `使用情况:` | 绝大多数 | 块模型 |
| `blocks-only` | 没有 usage 行但有参数块 | `curl --help all` | 同样走块模型 |

## 4. 块模型（这是解析器的核心）

**单位是「块」，不是「行」。** 实测形态：

```
  -v, --version                       ← 选项名单独一行
          Print the pnpm version      ← 说明在下一行、缩进更深 ⇒ 并入同一块

  -A, --catenate, --concatenate   追加 tar 文件至归档     ← 一个选项三个别名
      --occurrence[=NUMBER]  仅处理归档中每个文件的第 NUMBER
                             --diff, --extract 或是 --list   ← 续行里的词**不是**新参数
```

规则要点（都在 `clitree/rules/default.rules.json` 的 `optionBlock` 段）：

- `joinContinuation: true` ＋ `continuationMinExtraIndent: 2`：缩进更深的行并入上一块；
- `nameToken`：`--[A-Za-z][\w-]*` 或 `-[A-Za-z0-9][\w-]*` —— **必须支持单横线长名**（GNU 的 `-pass-exit-codes`）
  与**数字短选项**（Windows ping 的 `-4`/`-6`、curl 的 `-0`…`-3`）；
- `valueToken` 要求**紧贴参数名**：`-c <count>` 是取值，而
  `-d      use SO_DEBUG socket option` 里的 `SO_DEBUG` 只是描述里的词（曾误判成取值，已修）；
- **Windows 布局的取值**：名字与取值**仅隔 1 个空格**、取值后是 2+ 空格或「1 空格＋大写/中文开头的描述」
  （`-n count       Number…`、`-c compartment Routing…`、`-c compartment 路由…`）——这才让 `-n` 成为数值框
  而不是无值开关、拼出的命令才是对的；`-v verbose output` 这类紧凑描述不满足条件 ⇒ 不会被误吃；
- `--[no-]color` 形态会被归一成 `--color` 并标记为「三态」。

段落标题用**结构判定优先 ＋ 词表兜底**：标题是开放集合（实测除了 `options`/`usage` 还有
`main operation mode`、`valid arguments for -d` 这种一次性标题），所以不能穷举词表。

## 5. 子命令：不可靠，所以要懒加载

| 样本 | 抽出条数 | 真假 |
|---|---|---|
| `pnpm --help` | 91 | **真**（pnpm 命令确实多，且不含 `verbose`/`color` 之类假阳） |
| `git help -a` | 141 | 真 |
| `git --help`（中文） | 22 | 真（分组列表，组标题不结束段） |
| `lsblk --help` | 0 | 真（`Available output columns:` 是**列名**，曾被误抽成 54 个子命令，已加兜底条件挡掉） |

所以：**加载只出 2 层**（本命令参数 ＋ 一级子命令名单，子命令标「未展开」），
点开某个子命令才去跑它的 help；另有「全量展开」按钮（上限 3 层）。

## 6. 必填口径

- **有 usage 行** ⇒ 选项**一律按可选**处理（不传也能跑），只有**位置参数**分必填/可选
  （usage 里写在 `[]` 外 ⇒ 必填）；
- **没有 usage 行** ⇒ 显示「？未判定」，不假装知道；
- 界面排序：**位置参数置顶 → 其余必填 → 其它按 help 原顺序**。

这条口径是修出来的：`ping [options] <destination>` 只有位置参数落在必填位置，
早期实现把「选项没被 usage 提到」当成「未标注」，结果 ping 的 32 个选项全挂 `[未标注]`。

**位置参数有两种写法**（都是实测）：① 尖括号占位（`<destination>`、中文 `[<路径>]`，POSIX 惯例）；
② 整条 usage 里**没有尖括号**时，**裸词**也算（Windows ping 的 `… [-4] [-6] target_name`、nc 的
`[proxy_address] [port]`、mtr 的 `hostname`）。裸词口径会主动挡掉实测过的噪音：与尖括号形态互斥
（`git clone … [<选项>]` 里的 `clone`）、与命令名同形的词、连接词与 help 子词（rsync 的 `or`、
ip 的 `{ COMMAND | help }`）、全大写集合占位（`[OPTION...]` 里的 `OPTION`）、以及嵌在
「内含方括号的方括号组」里的取值结构（ssh 的 `[-D [bind_address:]port]`）。

## 7. 控件推断顺序

判定自上而下，命中即停（实现在 `core/widgets.py`，**每条都产出推断依据**，界面上可右键改类型）：

| 顺序 | 条件 | 控件 |
|---|---|---|
| 1 | 用户覆盖（`widgets.overrides`） | 用户指定 |
| 2 | help 写的是 `--[no-]xyz` 形态 | 三态下拉 |
| 3 | 描述含 `...` / `multiple times` | 多值列表 |
| 4 | 块内**没有取值标记** | **勾选框**（＋ help 解释） |
| 5 | 描述含 `one of` 且形态为 `<a\|b\|c>` | **可编辑下拉** |
| 6 | 取值名/描述命中 `numericWords`（`count`/`ttl`/`timeout`…） | 数值框 |
| 7 | 命中 `pathWords`（`file`/`dir`/`interface`…） | 文本框 ＋「浏览…」 |
| 8 | 其它 | 文本框（标「未确定」，可改） |

⚠️ **不要把 `curl -b <data|filename>` 当成枚举**：那是「取值形态」不是集合，规则里有 `reject` 黑名单。
实测：105 个真实命令里，help 显式给出取值集合的**只有 `ping -M` / `-T` 两处** ——
所以下拉框一律**可编辑**，抽不到就不造候选。

## 8. 规则文件参考

`clitree/rules/default.rules.json`（严格 JSON，`rulesVersion: 3`）：

| 段 | 作用 |
|---|---|
| `evidence` | 规则依据的实测数字（105 条命令的分布等），便于日后对照 |
| `dialects.detect` | 方言识别顺序与正则 |
| `helpChannels` | 通道顺序、`-h` 声明要求、实测白名单、交互式通道、24 条危险命令、超时与上限 |
| `segments` | 段落词表（结构判定优先，词表只做兜底） |
| `optionBlock` | 块合并与名字/取值正则 |
| `widgets` | 控件推断词表、枚举表、覆盖 |
| `subcommands` | `initialDepth: 2`、`lazyExpand`、`maxDepth: 3`、兜底条件 |
| `manPage` / `locale` / `limits` | man 页回退、`LC_ALL=C` 优先探测、并发与日志上限 |

**你的改动不要改进仓文件**：写 `~/.config/clitree/rules.user.json`（或平台等价目录），
它会**深合并**到默认规则之上（GUI 里右键改控件类型就是走这条路）。

## 9. 怎么迭代规则

```bash
# 1) 改规则
$EDITOR clitree/rules/default.rules.json
python3 -m clitree --check-rules          # 坏 JSON / 坏正则立刻报出来（非 0 退出）

# 2) 拿真实命令看效果
python3 -m clitree --parse ping
python3 -m clitree --parse --help-file /tmp/some-tool--help.txt

# 3) 跑回归（fixtures 是 29 条真机 help 文本，含 Windows 中英文两版 ping）
python3 -m pytest tests/test_parser_blocks.py tests/test_widgets.py -q
```

加新 fixture 的做法：`<命令> --help > tests/fixtures/help/<命令>.help.txt`，
文件名保持 `<工具>.help.txt`，并在测试里补一条断言（形态、条数或控件类型）。
