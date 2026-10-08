# 参与开发

[English](contributing.md) | **中文** | [Español](contributing.es.md)

> 属于 **CliTree** 文档的一部分 —— 返回 [README](../README.zh-CN.md)。

## 环境

| 项 | 值（本机实测） |
|---|---|
| 解释器 | 系统 `python3`（3.10.12 实测；`requires-python >= 3.9`） |
| GUI | PyQt5 5.15.6 / Qt 5.15.3（系统包） |
| 测试 | pytest 9.1.1 |

```bash
python3 -c "import PyQt5" || python3 -m pip install --user PyQt5
python3 -m pytest -q                 # 158 项
```

**不要建 venv**（本机实测：`python3 -m ensurepip` 不存在 ⇒ venv 里没有 pip，
而且 venv 的 `sys.path` 看不到 `/usr/lib/python3/dist-packages`，连系统 PyQt5 也 import 不到）。
需要额外依赖时用 `python3 -m pip install --user <包>`。

无图形环境（没有 `DISPLAY` / `WAYLAND_DISPLAY`）：

- 跑测试：`QT_QPA_PLATFORM=offscreen python3 -m pytest -q`（`tests/conftest.py` 已默认设好）；
- 开窗口看界面：`xvfb-run -a python3 -m clitree`；
- 出截图：`xvfb-run -a python3 tools/make_screenshots.py`（写 `screenshots/`）。

## 测试地图

| 文件 | 覆盖 |
|---|---|
| `tests/test_rules.py` | 规则加载、深合并用户覆盖、坏 JSON/坏正则能报出来 |
| `tests/test_parser_blocks.py` | 块模型、四种方言、必填口径、27 条 fixture 逐条解析 |
| `tests/test_parser_subcommands.py` | 子命令段（含 `lsblk` 列名假阳、`git help -a` 真值） |
| `tests/test_widgets.py` | 控件推断顺序、每条例外（`--[no-]`、可重复、`curl -b` 不得判成枚举） |
| `tests/test_discovery.py` | 通道顺序、rc 不可信、危险命令被拒、man 页回退、交互式通道 |
| `tests/test_lazy.py` | 加载只 1 次探测、展开再 1 次、重复 0 次、深度上限、失败可重试 |
| `tests/test_executor.py` | argv 安全、三模式、停止、终端适配 |
| `tests/test_profiles.py` | `cli/<工具>.json` 的缓存、多配置、说明两层、回退、坏文件 |
| `tests/test_gui_smoke.py` | offscreen 建窗、加载/展开、控件类型、说明双击、配置切换、停止 |

`tests/fixtures/help/*.txt` 是 **27 条真机 help 原文**（含中文、man 页、argparse、
两行块、GNU 长选项等形态）；`tests/fixtures/fakecli.py` 是可控假 CLI（能指定返回码、往 stderr 写、
长睡眠），执行器与 GUI 测试都用它，**绝不用真命令做破坏性验证**。

## 改解析规则

见 [解析规则 § 怎么迭代规则](parsing-rules.zh-CN.md)。三条纪律：

1. 用 `--parse --help-file` 拿真实文本验证，别凭印象改正则；
2. 改完必须 `python3 -m clitree --check-rules`（非 0 即坏）；
3. 加上/更新对应测试；`fixtures` 里的期望值要**现场重算**，不许把旧读数直接抄成「通过」。

## 加一条 fixture

```bash
<pick-a-real-cli> --help > tests/fixtures/help/<name>.help.txt
# 含空格/子命令的写清通道，例如 git clone -h
```

并在测试里补断言（条数、形态或控件类型）。样本要**真机抓的原文**，不要手写、不要润色。

## 改界面

- Qt 只允许出现在 `clitree/ui/` 里，而且 **`ui/qt.py` 是唯一 import Qt 的文件**（换绑定时只改它）；
- `core/` 里禁止 import Qt（那样就没法无头单测了）；
- 新增界面行为请补一条 `test_gui_smoke.py` 的断言 —— 那里已经有一套可复用的
  `MainWindow(probe_fn=..., profile_root=tmp_path)` 夹具，不会污染真实的 `cli/`。

## 文档约定

- 每篇文档三语：`X.md`（英文）、`X.zh-CN.md`（中文）、`X.es.md`（西语），
  头部保留语言切换行 `[English](X.md) | [中文](X.zh-CN.md) | [Español](X.es.md)`；
- **改了行为就同趟改三语**（改不动就至少留 TODO，别让三语互相矛盾）；
- 文档里的数字要么能给复算命令，要么明确写「未验证」。

## 提交约定

- 提交信息用带前缀的一行标题（`feat:` / `fix:` / `docs:` / `test:` / `refactor:` / `chore:`），正文写「为什么」；
- **不要提交** `__pycache__/`、`.pytest_cache/`、`*-session.jsonl`（已在 `.gitignore`）；
- `cli/` **是**入库的（配置跟仓走）；如果里面的值不适合公开，先改 `.gitignore` 再提交；
- 大改动请附读数（跑过的测试、截图、`--parse` 输出），而不是「应该没问题」。

## 尚未验证的清单（NOINFO）

写在这里是为了不让别人误以为它们已经成立：

- **Windows / macOS**：`/?`、`-?` 通道、`cmd start` / `osascript` 开终端、PyInstaller 打包 —— 只有代码就位，**未实测**；
- **新终端模式是否真的弹出窗口**：本机无图形环境，只能读到按钮 `launched`；
- **打包**：没有做过 PyInstaller 打包验证；
- **中文以外的 locale 长期稳定性**：只测过当前机器的 locale 与 `LC_ALL=C` 的切换效果。

如果补上了其中任何一项，**请把这里的对应条目删掉并附上读数** —— 文档里留着一句假话，
比留一句「未验证」危害大得多。
