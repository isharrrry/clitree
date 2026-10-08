"""运行栏：三个按钮，各自独立记忆「上次执行结果」；运行中该按钮变成「■ 停止」。"""
from . import icons, qt

MODES = (("terminal", "新终端执行"), ("background", "后台执行（日志在本窗口）"),
         ("silent", "静默执行（只有鼠标 busy）"))


class RunBar(qt.QWidget):
    def __init__(self, parent=None, on_run=None):
        super().__init__(parent)
        self._states = {m: "idle" for m, _ in MODES}
        self._labels = {m: label for m, label in MODES}
        self._buttons = {}
        lay = qt.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        for mode, label in MODES:
            btn = qt.QPushButton(label)
            btn.clicked.connect(lambda _=False, m=mode: (on_run and on_run(m)))
            lay.addWidget(btn)
            self._buttons[mode] = btn
        lay.addStretch(1)
        self._hint = qt.QLabel("")
        lay.addWidget(self._hint)
        for mode, _ in MODES:
            self.set_state(mode, "idle")

    def set_state(self, mode: str, state: str) -> None:
        self._states[mode] = state
        btn = self._buttons.get(mode)
        if btn is None:
            return
        if state == "running":
            btn.setText("■ 停止")
            btn.setToolTip(f"再点一次即终止「{self._labels[mode]}」")
        else:
            btn.setText(self._labels[mode])
            btn.setToolTip(icons.state_text(state))
        btn.setIcon(icons.state_icon(btn, state))

    def state_of(self, mode: str) -> str:
        return self._states.get(mode, "idle")

    def button_text(self, mode: str) -> str:
        btn = self._buttons.get(mode)
        return btn.text() if btn is not None else ""

    def is_running(self, mode: str) -> bool:
        return self._states.get(mode) == "running"

    def set_hint(self, text: str) -> None:
        self._hint.setText(text)

    def buttons(self) -> dict:
        return dict(self._buttons)
