"""主窗口：拖入/输入 CLI → 加载（2 层）→ 展开 → 填参数 → 三种方式执行。"""
from __future__ import annotations

import os
import queue
import time

from . import qt
from .log_panel import LogPanel
from .param_form import ParamForm
from .run_bar import RunBar
from .tree_panel import TreePanel
from ..core import executor, lazy, profiles as PF, rules as rules_mod, store
from ..core.model import CommandNode


class MainWindow(qt.QMainWindow):
    def __init__(self, probe_fn=None, parent=None, profile_root=None):
        super().__init__(parent)
        self.setWindowTitle("CliTree — CLI 参数树")
        self.resize(1100, 700)
        self.setAcceptDrops(True)

        self.rules = rules_mod.load_rules()
        self._probe_fn = probe_fn
        self._loader: lazy.TreeLoader | None = None
        self._current: CommandNode | None = None
        self._handle = None
        self._running: dict = {}
        self._done = False
        self._queue: queue.Queue = queue.Queue()
        self._status: list[str] = []
        self.runner = executor.Runner()
        self.profile_root = profile_root
        self.cli_name = ""
        self.loaded_from_cache = False

        # 顶部：命令输入 + 加载
        self.cmd_edit = qt.QLineEdit()
        self.cmd_edit.setPlaceholderText("输入一个 CLI（也可以把可执行文件拖进窗口）")
        load_btn = qt.QPushButton("加载")
        load_btn.clicked.connect(lambda: self.load_command(self.cmd_edit.text()))
        expand_btn = qt.QPushButton("全量展开")
        expand_btn.clicked.connect(self.expand_all)
        top = qt.QHBoxLayout()
        top.addWidget(qt.QLabel("CLI："))
        top.addWidget(self.cmd_edit, 1)
        top.addWidget(load_btn)
        top.addWidget(expand_btn)

        self.tree = TreePanel(on_expand=self._on_expand, on_select=self._on_select)
        self.form = ParamForm(on_note_changed=self._on_note_changed)
        self.log = LogPanel()
        self.run_bar = RunBar(on_run=self.run)

        left = qt.QWidget()
        left_lay = qt.QVBoxLayout(left)
        left_lay.addWidget(qt.QLabel("命令分支 / 参数（点开子命令才去探测它的 help）"))
        left_lay.addWidget(self.tree)

        # 配置行：同一个 CLI 的多个配置随便切；参数值可另存为新配置
        self.profile_combo = qt.QComboBox()
        self.profile_combo.currentTextChanged.connect(self._on_profile_selected)
        self.profile_name_edit = qt.QLineEdit()
        self.profile_name_edit.setPlaceholderText("新配置名")
        save_btn = qt.QPushButton("保存")
        save_btn.clicked.connect(self.save_current_profile)
        saveas_btn = qt.QPushButton("另存为…")
        saveas_btn.clicked.connect(self._on_save_as_clicked)
        del_btn = qt.QPushButton("删除")
        del_btn.clicked.connect(self.delete_current_profile)
        reparse_btn = qt.QPushButton("重新解析")
        reparse_btn.clicked.connect(self.reparse)
        self.profile_row = qt.QWidget()
        prow = qt.QHBoxLayout(self.profile_row)
        prow.setContentsMargins(0, 0, 0, 0)
        prow.addWidget(qt.QLabel("配置："))
        prow.addWidget(self.profile_combo, 1)
        prow.addWidget(save_btn)
        prow.addWidget(self.profile_name_edit)
        prow.addWidget(saveas_btn)
        prow.addWidget(del_btn)
        prow.addWidget(reparse_btn)

        right = qt.QWidget()
        right_lay = qt.QVBoxLayout(right)
        right_lay.addWidget(qt.QLabel("参数（控件类型按参数形态推断，右键标签可改）"))
        right_lay.addWidget(self.profile_row)
        right_lay.addWidget(self.form, 1)
        right_lay.addWidget(self.run_bar)
        right_lay.addWidget(self.log, 1)

        splitter = qt.QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([420, 680])

        central = qt.QWidget()
        lay = qt.QVBoxLayout(central)
        lay.addLayout(top)
        lay.addWidget(splitter)
        self.setCentralWidget(central)

        self._timer = qt.QTimer(self)
        self._timer.timeout.connect(self._drain)
        self._timer.start(40)

    # ---------------------------------------------------------------- 加载
    def load_command(self, cmd: str) -> None:
        cmd = (cmd or "").strip()
        if not cmd:
            return
        self.cmd_edit.setText(cmd)
        # GUI 层再拦一道：危险命令连探测都不做（注入的 probe_fn 也绕不过去）
        name = os.path.basename(cmd.split()[0])
        deny = set((self.rules.get("helpChannels") or {}).get("denyNeverProbe") or [])
        if name in deny:
            self._add_status(f"安全策略：{name} 属于危险命令，CliTree 不探测也不执行它")
            self.tree.clear()
            self.form.build([])
            return
        self.cli_name = os.path.basename(cmd.split()[0]).rsplit(".", 1)[0]
        self._loader = lazy.TreeLoader(self.rules, probe_fn=self._probe_fn)
        self._loader.executable = cmd
        self._loader.cmd_hint = cmd.split()[0]

        cached = PF.cached_node(self.cli_name, [], self.profile_root)
        if cached is not None:
            root = cached
            self.loaded_from_cache = True
            meta = PF.node_meta(self.cli_name, [], self.profile_root) or {}
            self._add_status(
                f"已从缓存载入 {self.cli_name}（{PF.profile_path(self.cli_name, self.profile_root).name}"
                f"｜解析于 {meta.get('parsedAt', '?')}｜参数 {len(root.options)}）"
                f"；点「重新解析」才会重新跑 help")
            self._loader._root = root
        else:
            root = self._loader.load_root(cmd)
            self.loaded_from_cache = False
        self._current = root
        self.tree.show_root(root)
        self.form.build(root.options, cli_name=self.cli_name)
        self._load_profiles_into_combo()
        self._apply_notes()
        if root.load_state == "failed":
            self._add_status(f"取不到 help：{root.error}")
        else:
            self._add_status(f"已加载 {root.name}：参数 {len(root.options)} · 子命令 {len(root.subcommands)}"
                             f"（方言 {root.dialect}／帮助质量 {root.grade}）")
            if not self.loaded_from_cache:
                self._write_cache(root, [])
        store.push_recent(cmd)

    def _on_expand(self, node: CommandNode) -> None:
        if self._loader is None:
            return
        self._add_status(f"展开 {node.name} …")
        self._loader.expand(node)
        if node.load_state == "loaded":
            self._write_cache(node, list(node.path[1:]))
        self.tree.refresh()
        self.tree.select_node(node.path[1:])
        if node.load_state == "failed":
            self._add_status(f"「{node.name}」取不到 help：{node.error}")

    def _write_cache(self, node: CommandNode, node_path: list) -> None:
        meta = dict(getattr(node, "probe_meta", {}) or {})
        meta["exe"] = (self._loader.executable if self._loader else "")
        try:
            PF.save_node(self.cli_name, node_path, node, meta, root=self.profile_root)
        except Exception as exc:      # 写配置失败不该打断使用
            self._add_status(f"写配置文件失败：{exc}")

    def reparse(self) -> None:
        """强制重新跑 help 并刷新缓存（缓存里的东西不会被当成"已是最新"）。"""
        if not self._loader:
            return
        root = self._loader.load_root(self._loader.executable)
        self._loader._cache.pop((self._loader.executable, ()), None)
        self._current = root
        self.loaded_from_cache = False
        self.tree.show_root(root)
        self.form.build(root.options, cli_name=self.cli_name)
        if root.load_state == "loaded":
            self._write_cache(root, [])
            self._add_status(f"已重新解析 {self.cli_name}：参数 {len(root.options)}"
                             f"（方言 {root.dialect}／帮助质量 {root.grade}）")
        else:
            self._add_status(f"重新解析失败：{root.error}")

    # ---------------------------------------------------------------- 参数说明
    def set_note(self, key: str, text: str, scope: str = "file") -> None:
        """scope="file" 对所有配置生效；scope="profile" 只对当前配置生效。"""
        profile = self.profile_combo.currentText() if scope == "profile" else None
        PF.set_note(self.cli_name, key, text, root=self.profile_root, profile=profile)
        self._apply_notes()
        where = f"配置「{profile}」" if profile else "该 CLI 的全部配置"
        self._add_status(f"已更新 {key} 的说明（{where}）")

    def _on_note_changed(self, key: str, text: str) -> None:
        self.set_note(key, text, scope="file")

    def _apply_notes(self) -> None:
        if not self.cli_name:
            return
        profile = self.profile_combo.currentText() or None
        for key in self.form.order():
            text, _source = PF.get_note(self.cli_name, key, self.profile_root, profile=profile)
            self.form.set_note(key, text, self.form._descs.get(key, ""))

    # ---------------------------------------------------------------- 配置
    def profile_names(self) -> list:
        return PF.list_profiles(self.cli_name, self.profile_root)

    def _load_profiles_into_combo(self, select: str = "") -> None:
        names = self.profile_names()
        if not names:
            PF.save_values(self.cli_name, "默认", {}, root=self.profile_root)
            names = ["默认"]
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItems(names)
        active = select or PF.active_profile(self.cli_name, self.profile_root) or names[0]
        idx = self.profile_combo.findText(active)
        self.profile_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.profile_combo.blockSignals(False)
        self._apply_profile_values(self.profile_combo.currentText())

    def _apply_profile_values(self, name: str) -> None:
        prof = PF.get_profile(self.cli_name, name, self.profile_root)
        for key in list(self.form.order()):
            self.form.set_value(key, "")
        self.form.set_extra_text("")             # 「其他输入」一并复位，随后按配置载入
        for key, val in (prof.get("values") or {}).items():
            self.form.set_value(key, val)        # "@extra" 由 ParamForm.set_value 特判

    def _on_profile_selected(self, name: str) -> None:
        if not name:
            return
        self.switch_profile(name)

    def switch_profile(self, name: str) -> None:
        current = self.profile_combo.currentText()
        if current and current != name:          # 切走前先把当前值存好，防丢
            PF.save_values(self.cli_name, current, self.form.values(), root=self.profile_root)
        PF.set_active(self.cli_name, name, root=self.profile_root)
        self.profile_combo.blockSignals(True)
        if self.profile_combo.findText(name) < 0:
            self.profile_combo.addItem(name)
        self.profile_combo.setCurrentText(name)
        self.profile_combo.blockSignals(False)
        self._apply_profile_values(name)
        self._apply_notes()
        self._add_status(f"已切到配置「{name}」")

    def save_current_profile(self) -> None:
        name = self.profile_combo.currentText() or "默认"
        PF.save_values(self.cli_name, name, self.form.values(), root=self.profile_root)
        self._add_status(f"已保存配置「{name}」")

    def save_as_profile(self, name: str, note: str = "") -> None:
        if not name:
            return
        PF.create_profile(self.cli_name, name, self.form.values(), root=self.profile_root, note=note)
        self._load_profiles_into_combo(select=name)
        self._add_status(f"已把当前参数另存为新配置「{name}」")

    def delete_current_profile(self) -> None:
        name = self.profile_combo.currentText()
        if not name:
            return
        PF.delete_profile(self.cli_name, name, root=self.profile_root)
        self._load_profiles_into_combo()
        self._add_status(f"已删除配置「{name}」")

    def _on_save_as_clicked(self) -> None:
        name = self.profile_name_edit.text().strip()
        if not name:
            name, ok = qt.QInputDialog.getText(self, "另存为新配置", "配置名：")
            if not ok or not name.strip():
                return
            name = name.strip()
        self.save_as_profile(name)
        self.profile_name_edit.clear()

    def _on_select(self, node: CommandNode) -> None:
        self._current = node
        cli = os.path.basename(self._loader.executable.split()[0]).rsplit(".", 1)[0] if self._loader else ""
        self.form.build(node.options, cli_name=cli)

    def expand_all(self) -> None:
        if self._loader is None:
            return
        n = self._loader.expand_all(self._loader._root)
        self.tree.refresh()
        self._add_status(f"全量展开完成，探测了 {n} 个节点")

    # ---------------------------------------------------------------- 执行
    @property
    def probe_calls(self) -> int:
        calls = getattr(self._probe_fn, "calls", None)
        if calls is not None:
            return len(calls)
        return self._loader.probe_count if self._loader else 0

    def _argv(self, override=None) -> list:
        if override is not None:
            return list(override)
        exe = self._loader.executable.split()[0] if self._loader else ""
        node = self._current or (self._loader._root if self._loader else None)
        if node is None:
            return []
        return executor.build_argv(exe, node, self.form.values())

    def run(self, mode: str, argv_override=None) -> None:
        if self.stop(mode):          # 第二次点击 = 停止，而不是再跑一遍
            return
        argv = self._argv(argv_override)
        if not argv:
            self._add_status("没有可执行的命令行（先加载一个 CLI）")
            return
        name = os.path.basename(argv[0])
        deny = set((self.rules.get("helpChannels") or {}).get("denyNeverProbe") or [])
        if name in deny:
            self._add_status(f"安全策略：{name} 属于危险命令，CliTree 不执行它")
            self.run_bar.set_state(mode, "fail")
            return

        self.run_bar.set_state(mode, "running")
        self._add_status(f"[{mode}] {' '.join(argv)}")
        if mode == "terminal":
            handle = self.runner.start_terminal(argv)
            self._finish(mode, handle)
        elif mode == "silent":
            qt.QApplication.setOverrideCursor(qt.Qt.WaitCursor)
            handle = self.runner.start_silent(argv, on_done=lambda r: self._queue.put((mode, r)))
            self._running[mode] = handle
        else:
            handle = self.runner.start_background(
                argv, on_line=lambda line: self._queue.put(("line", line)),
                on_done=lambda r: self._queue.put((mode, r)))
            self._running[mode] = handle

    def stop(self, mode: str) -> bool:
        """终止某个正在跑的模式；返回是否真的停了一次。"""
        handle = self._running.get(mode)
        if handle is None or not self.run_bar.is_running(mode):
            return False
        handle.stop()
        self._add_status(f"[{mode}] 已请求停止（终止进程）")
        return True

    def _finish(self, mode: str, handle) -> None:
        self._running.pop(mode, None)
        self._handle = None
        state = handle.state if getattr(handle, "state", "ok") != "running" else "ok"
        self.run_bar.set_state(mode, state)
        self._add_status(f"[{mode}] 结果：{state}")

    def _drain(self) -> None:
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                return
            if kind == "line":
                self.log.append(str(payload))
                continue
            try:
                qt.QApplication.restoreOverrideCursor()
            except Exception:
                pass
            self._finish(kind, payload)
            self._done = True

    def wait_for_run(self, timeout: float = 15.0) -> None:
        self._done = False
        deadline = time.time() + timeout
        while time.time() < deadline:
            qt.QApplication.processEvents()
            self._drain()
            if self._done:
                qt.QApplication.processEvents()
                return
            time.sleep(0.02)

    # ---------------------------------------------------------------- 拖放
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        urls = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.load_command(urls[0])

    # ---------------------------------------------------------------- 查询接口
    def log_lines(self) -> list:
        return self.log.lines()

    def status_lines(self) -> list:
        return list(self._status)

    def tree_labels(self) -> list:
        return self.tree.labels()

    def set_value(self, key: str, value) -> None:
        self.form.set_value(key, value)

    def form_widget_kinds(self) -> dict:
        return self.form.widget_kinds()

    def form_widget(self, key: str):
        return self.form.widget_for(key)

    def form_tooltips(self) -> dict:
        return self.form.tooltips()

    def form_param_order(self) -> list:
        return self.form.order()

    def form_descriptions(self) -> dict:
        return self.form.descriptions()

    def form_required_marks(self) -> dict:
        return self.form.required_marks()

    def form_labels(self) -> dict:
        return self.form.labels()

    def _add_status(self, text: str) -> None:
        self._status.append(text)
        self.statusBar().showMessage(text)
