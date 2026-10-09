# 执行模式

[English](execution-modes.md) | **中文** | [Español](execution-modes.es.md)

> 属于 **CliTree** 文档的一部分 —— 返回 [README](../README.zh-CN.md)。

## 三种模式

| 模式 | 实现 | 日志区 | 返回码 | 能否停止 |
|---|---|---|---|---|
| **新终端执行** | `terminals.build_terminal_argv()` 选平台终端（Linux：`gnome-terminal`/`xfce4-terminal`/`konsole`/`xterm`/`x-terminal-emulator`；macOS：`osascript` 驱动 Terminal.app；Windows：`wt.exe` 或 `cmd /c start`） | 不回流（终端自己显示） | **拿不到** | **不能**（外部窗口） |
| **后台执行** | `subprocess.Popen` ＋ 线程按行读取 stdout+stderr | 逐行实时写入 | 有 | 能 |
| **静默执行** | `Popen` 但把 stdout/stderr 丢给 `/dev/null` | **一行都不写** | 有 | 能 |

设计取向：**拿不到返回码就不判成败**。新终端模式只把按钮标成「已在终端启动」，
不会假装成功（也不会假装失败）。

## 停止

运行期间，该模式的按钮文字变成 **`■ 停止`**；再点一次即终止：

```
RunHandle.stop()  →  terminate()  →  等最多 3 秒  →  仍在 ⇒ kill()
```

- 结果状态记为 **`stopped`**（中性，不算失败），按钮图标换成停止方块；
- 后台模式停止后日志区保留已产生的输出；
- 静默模式停止同样不写日志；
- 对已经结束的运行调用 `stop()` 是**空操作**（不会改状态、不会抛异常）。

## 结果图标状态机

每个按钮**独立**记住自己上次的结果：

| 状态 | 何时 | 图标 |
|---|---|---|
| `idle` | 从未执行 | ▶ |
| `running` | 正在跑（按钮文字变「■ 停止」） | ↻ |
| `ok` | 返回码 0 | ✓ |
| `fail` | 返回码非 0 | ✗ |
| `launched` | 新终端已启动（无返回码） | 方框 |
| `stopped` | 用户点了停止 | ■ |
| `error` | 启动失败（例如找不到终端模拟器） | ⚠ |

## argv 直传：绝不经 shell

参数一律以**列表**交给子进程：

```python
argv = build_argv(exe, node, values)
# 例：{"--verbose": True, "--count": "3", "--output": "a b; rm -rf /", "@0": "host",
#      "@extra": "--tail 1"}
#   ⇒ ["ping", "--verbose", "--count", "3", "--output", "a b; rm -rf /", "host",
#      "--tail", "1"]
```

`a b; rm -rf /` 这样的值**仍然是单个 argv 元素**，不会被解释成命令分隔符（有测试锁死这一条）。
表单最末尾的「其他输入」（`@extra`）是唯一的例外：按空白拆开后**追加到 argv 最后**，用于临时补充
help 里没写到的参数。

只有「开新终端」这条路上需要拼一行命令，那时才做转义：
POSIX 用 `shlex.join`，Windows 用 `"…"` 包裹并转义内部引号。

`build_argv` 的取值规则：

| 表单状态 | 结果 |
|---|---|
| 勾选框未勾 / 下拉为空 / 数值框是「（不传）」 | **不传这个参数** |
| 勾选框已勾 | 传长名（没有长名就传短名） |
| 有取值 | 传 `名字 值` 两个元素 |
| 可重复（多值列表） | 每个值各传一次 `名字 值` |
| 位置参数 | 按顺序追加在最后（不带名字） |
| 「其他输入」（`@extra`） | 按空白拆开，追加到 argv 最后（临时补充参数用） |

## 危险命令：两道拦截

1. **探测前**：`discovery.probe()` 见到 `shutdown`/`dd`/`mkfs*` 等 24 条之一，直接返回拒绝，**一个进程都不起**；
2. **执行前**：`MainWindow.run()` 再查一次同样的名单（这样即使探针来自缓存或注入的假探针也绕不过），
   并把理由写进状态栏。

界面实测：加载 `/sbin/shutdown` ⇒ 树与表单为空、状态栏写
「安全策略：shutdown 属于危险命令，CliTree 不探测也不执行它」（截图 `08-dangerous-refused.png`）。

## 复算

```bash
python3 -m pytest tests/test_executor.py -q      # 三模式 ＋ 停止 ＋ argv 安全
python3 - <<'PY'
import sys; sys.path.insert(0, ".")
from clitree.core import executor, terminals
print(terminals.build_terminal_argv(["echo", "hi there"], platform="linux"))
print(executor.build_argv("ping", __import__("clitree.core.model", fromlist=["CommandNode"]).CommandNode(
    name="ping", path=["ping"], options=[]), {}))
PY
```
