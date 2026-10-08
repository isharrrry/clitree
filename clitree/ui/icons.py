"""运行状态图标：用 Qt 自带标准图标，不依赖外部资源。"""
from . import qt

_STYLE = {
    "idle": qt.QStyle.SP_MediaPlay,
    "running": qt.QStyle.SP_BrowserReload,
    "ok": qt.QStyle.SP_DialogApplyButton,
    "fail": qt.QStyle.SP_MessageBoxCritical,
    "launched": qt.QStyle.SP_TitleBarNormalButton,
    "stopped": qt.QStyle.SP_MediaStop,
    "error": qt.QStyle.SP_MessageBoxWarning,
}

TEXT = {
    "idle": "未执行",
    "running": "运行中",
    "ok": "上次成功",
    "fail": "上次失败",
    "launched": "已在终端启动（拿不到 rc）",
    "stopped": "已停止",
    "error": "启动失败",
}


def state_icon(widget, state: str):
    return widget.style().standardIcon(_STYLE.get(state, qt.QStyle.SP_MediaPlay))


def state_text(state: str) -> str:
    return TEXT.get(state, state)
