# 架构

[English](architecture.md) | **中文** | [Español](architecture.es.md)

> 属于 **CliTree** 文档的一部分 —— 返回 [README](../README.zh-CN.md)。

## 三层，一条硬规则

```
clitree/
├── core/      纯逻辑：解析、规则、控件推断、探测、懒加载、执行、落盘   ← 不 import Qt
├── ui/        Qt 界面；**只有 ui/qt.py 一个文件 import Qt**
├── rules/     default.rules.json（解析规则的唯一真相源）
tests/         169 项测试（含 offscreen GUI 冒烟）
tools/         生成依赖树 / 生成界面截图的脚本
cli/           每个工具的配置文件（缓存 ＋ 多个配置 ＋ 你的说明）
```

**硬规则**：`core` 里不出现 `PyQt5`/`PySide6`。这样做有两个实际好处：
① 解析与执行逻辑可以在无图形环境下单测（本机 CI 就是 `QT_QPA_PLATFORM=offscreen` ＋ 纯 pytest）；
② 将来要从 PyQt5 换到 PySide6（例如为了 LGPL），**只改 `ui/qt.py` 一个文件**。

## 模块职责

| 模块 | 职责 | 关键点 |
|---|---|---|
| `core/model.py` | 数据结构 `ParamSpec` / `CommandNode` / `ParseResult` | 带 `to_dict/from_dict`，配置文件里的缓存就是它 |
| `core/rules.py` | 加载 / 校验 / 深合并规则文件 | 用户覆盖写 `rules.user.json`，**不改随包规则** |
| `core/parser.py` | help 文本 → 结构化参数与子命令 | 块模型；方言识别；必填口径 |
| `core/widgets.py` | 参数 → 控件类型推断 | 每条判定都产出 `widget_reason`（界面上可见） |
| `core/discovery.py` | 探测 help 通道（含安全策略） | 危险命令直接拒绝；`-h` 需先声明；不看 rc 只看内容 |
| `core/lazy.py` | 懒加载树 | 加载只出 2 层；展开某节点才探测它 |
| `core/executor.py` | 三种执行方式 ＋ 停止 | argv 列表直传，绝不拼接 shell |
| `core/terminals.py` | 三平台「开新终端」适配 | Linux / macOS / Windows 各一套命令 |
| `core/store.py` | 配置目录、最近命令 | 按平台约定自算路径（`XDG_CONFIG_HOME` / `APPDATA` / `Library/Application Support`） |
| `core/profiles.py` | `cli/<工具名>.json` 读写 | 解析缓存 ＋ 多个配置 ＋ 参数说明 |
| `ui/qt.py` | Qt 薄适配层 | 全项目唯一 import Qt 的地方 |
| `ui/main_window.py` | 主窗装配、拖放、加载、配置行、执行 | 线程回调经队列回到主线程刷新界面 |
| `ui/tree_panel.py` | 左树 | 子命令标「未展开」，点开才触发探测 |
| `ui/param_form.py` | 右侧参数表单 | 排序、控件工厂、说明常显与双击编辑 |
| `ui/run_bar.py` / `ui/icons.py` | 三个执行按钮与状态图标 | 运行中变成「■ 停止」，各自记住上次结果 |
| `ui/log_panel.py` | 日志区 | **只有后台模式写入** |

## 一次「加载 → 执行」的完整数据流

```
用户输入 / 拖入一个 CLI
        │
        ├─ profiles.cached_node(cli)  ── 命中 ⇒ 直接渲染树与表单（**不探测**）
        │                                 状态栏写「已从缓存载入…解析于 …」
        │
        └─ 未命中 ⇒ discovery.probe(exe, rules, node_path)
                     ├─ 危险命令？ ⇒ 立即拒绝（reason 写进状态栏）
                     ├─ 交互式命令（gdb 等）⇒ 走专用通道 `-batch -ex "help all"`
                     └─ 否则按通道顺序 --help → -h → /? → -? → help → -help
                          逐条真跑，**以输出内容判定成败**（rc 完全不可信）
                          │
                          ▼
                    parser.parse_help(text, rules)  →  ParamSpec 列表 ＋ 子命令名单
                          │
                          ▼
                    widgets.infer_widget(spec)      →  控件类型 ＋ 推断依据
                          │
                          ├─ profiles.save_node(...)     把解析结果写进 cli/<工具>.json
                          └─ lazy.TreeLoader._fill(...)  只长 2 层，其余标 pending
                          │
                          ▼
                    TreePanel.show_root()  ＋  ParamForm.build()  （位置参数置顶 → 必填 → 其余）
                          │
                          用户填值 / 选配置（profiles.get_profile → form.set_value）
                          ▼
                    executor.build_argv(exe, node, values)   ← argv 列表，不经 shell
                          │
        ┌─────────────────┼──────────────────────────┐
        ▼                 ▼                          ▼
  新终端（terminals）  后台（Popen + 线程泵）      静默（Popen，不读输出）
  拿不到 rc ⇒          stdout/stderr 逐行进日志    日志区零新增行
  「已启动」           结束按 rc 判 ok / fail       结束按 rc 判 ok / fail
```

## 为什么把缓存和配置放在同一个文件

`cli/<工具名>.json` 同时装三类东西：

- `targets`：**每个被解析过的命令路径**一份解析结果（根命令是 `""`，`git clone` 是 `"clone"`）；
- `profiles`：同一个工具的**多个配置**（不同机器/场景的参数值）；
- `notes`：**你自己的参数说明**（文件级）＋ 每个配置可以再覆盖。

理由是它们天然同寿命：一个工具的参数树、你给它填的值、你对它的理解，换机器时应该一起搬走。
细节见 [配置](configuration.zh-CN.md)。

## 想看模块之间的实际依赖

`tools/deps_tree.py` 用 AST 解析 import，生成带**层级字母编号**的依赖树：

```bash
python3 tools/deps_tree.py            # 打印
python3 tools/deps_tree.py --out docs/DEPENDENCY-TREE.md
```

编号形如 `[BACD]` ＝ 一层第 2 个 → 二层第 1 个 → 三层第 3 个 → 四层第 4 个；
同一文件第二次出现只写 `↩ 见 [首次编号]`，不再重复展开。当前快照见
[DEPENDENCY-TREE.md](DEPENDENCY-TREE.md)。
