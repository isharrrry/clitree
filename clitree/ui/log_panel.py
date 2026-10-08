"""日志区：只有「后台执行」模式会往里写。"""
from . import qt


class LogPanel(qt.QWidget):
    def __init__(self, parent=None, max_lines: int = 5000):
        super().__init__(parent)
        self._lines: list[str] = []
        self.max_lines = max_lines
        self.view = qt.QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(max_lines)
        lay = qt.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(qt.QLabel("日志（仅「后台执行」写入；静默模式不产生日志）"))
        lay.addWidget(self.view)

    def append(self, line: str) -> None:
        self._lines.append(line)
        if len(self._lines) > self.max_lines:
            self._lines = self._lines[-self.max_lines:]
        self.view.appendPlainText(line)

    def lines(self) -> list[str]:
        return list(self._lines)

    def clear(self) -> None:
        self._lines = []
        self.view.clear()
