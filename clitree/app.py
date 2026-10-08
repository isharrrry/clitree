"""QApplication 装配。"""
from __future__ import annotations

import os
import sys


def run_gui(argv=None) -> int:
    from .ui import qt
    from .ui.main_window import MainWindow

    argv = list(sys.argv if argv is None else argv)
    if sys.platform.startswith("linux") and not (os.environ.get("DISPLAY")
                                                 or os.environ.get("WAYLAND_DISPLAY")):
        print("没有可用的图形环境（DISPLAY/WAYLAND_DISPLAY 都未设置）。\n"
              "本机是无头环境时，请用：clitree --parse <命令> 或 --help-file <文件>；\n"
              "想在无头机上开窗口可以用：xvfb-run -a clitree", file=sys.stderr)
        return 2
    app = qt.QApplication.instance() or qt.QApplication(argv)
    win = MainWindow()
    win.show()
    if len(argv) > 1 and not argv[1].startswith("-"):
        win.load_command(argv[1])
    return app.exec_()
