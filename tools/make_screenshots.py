#!/usr/bin/env python3
"""生成界面效果截图（可重复运行）。

用法：
    xvfb-run -a python3 tools/make_screenshots.py [输出目录]
    QT_QPA_PLATFORM=offscreen python3 tools/make_screenshots.py
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from clitree.ui import qt                       # noqa: E402
from clitree.ui.main_window import MainWindow   # noqa: E402

OUT = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "screenshots")
OUT.mkdir(parents=True, exist_ok=True)
FAKECLI = str(ROOT / "tests" / "fixtures" / "fakecli.py")

app = qt.QApplication([])
win = MainWindow()
win.resize(1280, 840)
win.show()
for _ in range(3):
    app.processEvents()


def shot(name: str, status: str = "") -> None:
    if status:
        win.statusBar().showMessage(status)
    for _ in range(4):
        app.processEvents()
    path = OUT / name
    win.grab().save(str(path))
    print(f"SHOT {path}  {path.stat().st_size} B")


def settle(ms: int = 150) -> None:
    qt.QTimer.singleShot(0, lambda: None)
    for _ in range(3):
        app.processEvents()


# 1. 加载 ping：勾选框 / 数值框 / 下拉框 / 路径框 同屏
win.load_command("ping")
win.tree.select_node([])
settle()
kinds = win.form_widget_kinds()


def scroll_to(key: str) -> None:
    """把某个参数滚到可视区，方便截图展示控件形态。"""
    w = win.form._widgets.get(key)
    if w is not None:
        win.form._area.ensureWidgetVisible(w, 0, 60)
        settle()


scroll_to("-c")
shot("01-load-ping-widgets.png",
     f"ping：{len(kinds)} 个参数；-D={kinds.get('-D')} -c={kinds.get('-c')} "
     f"-M={kinds.get('-M')}（下拉 do/dont/want） -I={kinds.get('-I')}")

# 1b. 下拉框 + 路径框同屏（滚动到 -M / -I 一带）
scroll_to("-M")
shot("01b-combo-and-path.png",
     f"-M={kinds.get('-M')}，候选 do|dont|want；-I={kinds.get('-I')}，文本框＋浏览按钮")

# 2. 填好值 + 后台执行：日志进本窗、按钮变「上次成功」
win.set_value("-c", "2")
win.set_value("@0", "127.0.0.1")
win.run("background", argv_override=["ping", "-c", "2", "127.0.0.1"])
win.wait_for_run(timeout=20)
shot("02-run-background-log-ok.png",
     f"后台执行：日志 {len(win.log_lines())} 行，按钮状态 = {win.run_bar.state_of('background')}")

# 3. 静默执行：日志一行都不加，只有按钮状态变化
before = len(win.log_lines())
win.run("silent", argv_override=["ping", "-c", "1", "127.0.0.1"])
win.wait_for_run(timeout=20)
shot("03-run-silent-zero-log.png",
     f"静默执行：日志 +{len(win.log_lines()) - before} 行（应为 0），"
     f"按钮状态 = {win.run_bar.state_of('silent')}")

# 4. 失败一次：按钮图标变「上次失败」
win.run("background", argv_override=[sys.executable, FAKECLI, "--fail"])
win.wait_for_run(timeout=20)
shot("04-run-fail-icon.png",
     f"后台执行失败：按钮状态 = {win.run_bar.state_of('background')}（上一个按钮仍是 "
     f"{win.run_bar.state_of('silent')}）")

# 5. git：初始 2 层（子命令全部「未展开」，一个都没探测）
win.load_command("git")
settle()
shot("05-git-two-levels-collapsed.png",
     "git：点加载只出 2 层 —— 一级子命令显示「未展开」，没有逐个去跑 help")

# 6. 点开一个子命令：才去探测它的 help
win.tree.expand_subcommand("clone")
settle()
shot("06-git-clone-expanded.png",
     "点开 clone 之后才探测 git clone 的 help（同样命中 rc=129 但内容有效）")

# 7. tar：一次加载拿到上百个参数
win.load_command("tar")
win.tree.select_node([])
settle()
shot("07-tar-many-params.png",
     f"tar：一次性解析出 {len(win.form_widget_kinds())} 个参数（含多别名如 -A/--catenate/--concatenate）")

# 8. 危险命令：安全策略拦住（连探测都不做）
win.load_command("/sbin/shutdown")
settle()
shot("08-dangerous-refused.png", win.status_lines()[-1] if win.status_lines() else "")



# 9-10. 执行中 → 再点一次停止（按钮文字与状态）
win.load_command("ping")
win.tree.select_node([])
win.set_value("-c", "30")
win.set_value("@0", "127.0.0.1")
win.run("background", argv_override=["ping", "-c", "30", "127.0.0.1"])
for _ in range(6):
    app.processEvents()
shot("09-running-stop-button.png",
     f"执行中：按钮文字 = {win.run_bar.button_text('background')}")

win.run("background", argv_override=["ping", "-c", "30", "127.0.0.1"])   # 第二次点击 = 停止
win.wait_for_run(timeout=15)
shot("10-stopped-state.png",
     f"再次点击后：按钮状态 = {win.run_bar.state_of('background')}，"
     f"文字 = {win.run_bar.button_text('background')}")


# 11-12. 配置：一个 cli/<工具名>.json 里放多个配置，随时切
win.load_command("ping")
win.tree.select_node([])
win.set_value("-c", "2")
win.set_value("@0", "127.0.0.1")
win.save_as_profile("回环两次")
win.set_value("-c", "5")
win.set_value("@0", "8.8.8.8")
win.save_as_profile("外网五次")
shot("11-cli-profiles.png",
     f"配置都在同一个文件里（cli/ping.json）：{win.profile_names()}")

win.switch_profile("回环两次")
shot("12-profile-switched.png",
     f"切到「回环两次」后的参数值：{win.form.values()}")


# 13. 参数说明：双击改成你自己的说明（带 ✎ 标记，括号里保留 help 原文）
win.load_command("ping")
win.tree.select_node([])
win.set_note("-c", "我常用 2；外网改 1，别超过 5")
win.set_note("@0", "内网回环用 127.0.0.1，外网用 8.8.8.8")
shot("13-custom-note.png",
     "参数说明已改成自己的（✎ 标记；括号里是 help 原文）")

print("DONE", len(list(OUT.glob("*.png"))), "张")
