"""参数表单：按参数形态出控件；每条参数常显 help 说明；必填项排前面。"""
from . import qt
from ..core import store
from ..core.model import ParamSpec

MODE_LABELS = [
    ("checkbox", "勾选框"),
    ("combo", "下拉框（可编辑）"),
    ("spin", "数值框"),
    ("text", "文本框"),
    ("path", "文本框＋浏览"),
    ("tristate", "三态下拉"),
    ("multi", "多值列表"),
]

# 只有真正有意义的才显示标记：可选项不显示（实测 ping 的 32 个选项全是「未标注」，纯噪音）
REQUIRED_MARK = {"required": "＊必填", "optional": "", "unknown": "？未判定"}


class _NoteLabel(qt.QLabel):
    """参数说明行：双击即可改成自己的说明。"""

    def __init__(self, key: str, owner, text: str = ""):
        super().__init__(text)
        self._key = key
        self._owner = owner
        self.setWordWrap(True)
        self.setToolTip("双击可以改成你自己的说明（会写进 cli/<工具名>.json）")

    def mouseDoubleClickEvent(self, event) -> None:      # noqa: N802 (Qt 命名)
        self._owner.begin_note_edit(self._key)


class ParamForm(qt.QWidget):
    def __init__(self, parent=None, on_kind_changed=None, on_note_changed=None):
        super().__init__(parent)
        self._on_note_changed = on_note_changed
        self._specs: list[ParamSpec] = []
        self._widgets: dict = {}
        self._rows: dict = {}
        self._labels: dict = {}
        self._kinds: dict = {}
        self._descs: dict = {}
        self._marks: dict = {}
        self._note_labels: dict = {}
        self._note_edits: dict = {}
        self._custom_notes: dict = {}
        self._on_kind_changed = on_kind_changed
        self.cli_name = ""
        self._area = qt.QScrollArea()
        self._area.setWidgetResizable(True)
        self._host = qt.QWidget()
        self._form = qt.QFormLayout(self._host)
        self._area.setWidget(self._host)
        lay = qt.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._area)
        self._form.addRow(qt.QLabel("（选中树里的节点后，这里显示它的参数）"))

    # ---------------------------------------------------------------- 排序
    @staticmethod
    def sort_specs(specs: list) -> list:
        """位置参数置顶 → 其余必填 → 其它按 help 原顺序。"""
        def key(item):
            idx, spec = item
            if spec.position is not None:
                tier = 0
            elif spec.required == "required":
                tier = 1
            else:
                tier = 2
            return (tier, idx)

        return [s for _, s in sorted(enumerate(specs), key=key)]

    @staticmethod
    def display_name(spec: ParamSpec) -> str:
        """全称和简称一起给，并带上取值占位（如 `-c, --count <count>`）。"""
        if not spec.names:
            return spec.value_token or f"<位置参数 {spec.position}>"
        names = ", ".join(spec.names)
        if spec.takes_value and spec.value_token:
            names += f" {spec.value_token}"
        return names

    # ---------------------------------------------------------------- 构建
    def build(self, specs: list, cli_name: str = "") -> None:
        self.cli_name = cli_name
        self._specs = self.sort_specs(list(specs))
        self._widgets, self._rows, self._labels = {}, {}, {}
        self._kinds, self._descs, self._marks = {}, {}, {}
        self._note_labels, self._note_edits, self._custom_notes = {}, {}, {}
        while self._form.count():
            item = self._form.takeAt(0)
            w = item.widget()
            if w is not None:
                w.setParent(None)
        if not self._specs:
            self._form.addRow(qt.QLabel("（该节点没有可填参数）"))
            return
        for spec in self._specs:
            widget = self._make_widget(spec)
            row = self._make_row(spec, widget)
            label = self._make_label(spec)
            self._form.addRow(label, row)
            self._widgets[spec.key] = widget
            self._rows[spec.key] = row
            self._labels[spec.key] = label
            self._kinds[spec.key] = spec.widget
            self._descs[spec.key] = spec.desc or ""
            self._marks[spec.key] = REQUIRED_MARK.get(spec.required, "")

    def _make_label(self, spec: ParamSpec) -> qt.QLabel:
        text = self.display_name(spec)
        mark = REQUIRED_MARK.get(spec.required, "")
        if mark:
            text += f"  [{mark}]"
        lab = qt.QLabel(text)
        lab.setWordWrap(True)
        tip = [spec.desc or "（help 里没有这条参数的说明）"]
        if spec.default:
            tip.append(f"默认值：{spec.default}")
        if spec.example:
            tip.append(f"示例：{spec.example}")
        tip.append(f"推断依据：{spec.widget_reason}")
        lab.setToolTip("\n".join(tip))
        lab.setContextMenuPolicy(qt.Qt.CustomContextMenu)
        lab.customContextMenuRequested.connect(lambda pos, s=spec: self._show_kind_menu(s))
        return lab

    def _make_row(self, spec: ParamSpec, widget) -> qt.QWidget:
        """控件 ＋ 常显的 help 说明（灰色小字，不再只藏在 tooltip 里）。"""
        host = qt.QWidget()
        v = qt.QVBoxLayout(host)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)
        v.addWidget(widget)
        desc = spec.desc or "（help 里没有这条参数的说明）"
        extra = []
        if spec.default:
            extra.append(f"默认 {spec.default}")
        if spec.example:
            extra.append(f"示例 {spec.example}")
        if extra:
            desc += "　·　" + "　·　".join(extra)
        lab = _NoteLabel(spec.key, self, desc)
        lab.setStyleSheet("color: #666;")
        v.addWidget(lab)
        self._note_labels[spec.key] = lab
        host.setToolTip(spec.widget_reason)
        return host

    def _make_widget(self, spec: ParamSpec):
        kind = spec.widget
        if kind == "checkbox":
            w = qt.QCheckBox("开启")
            w.setToolTip(spec.desc)
            return w
        if kind == "tristate":
            w = qt.QComboBox()
            w.addItems(["默认（不传）", "启用", "禁用"])
            w.setToolTip(spec.desc)
            return w
        if kind == "combo":
            w = qt.QComboBox()
            w.setEditable(True)
            w.addItems(list(spec.choices or []))
            w.setCurrentIndex(-1)
            w.setToolTip(spec.desc)
            return w
        if kind == "spin":
            w = qt.QSpinBox()
            w.setRange(-1_000_000, 1_000_000)
            w.setSpecialValueText("（不传）")   # Qt 会忽略空字符串 ⇒ 必须给非空文本
            w.setValue(-1_000_000)
            w.setToolTip(spec.desc)
            return w
        if kind == "multi":
            w = qt.QListWidget()
            w.setToolTip(spec.desc + "\n每行一个值")
            w.setMaximumHeight(80)
            w.setEditTriggers(qt.QListWidget.DoubleClicked | qt.QListWidget.EditKeyPressed)
            w.addItem("")
            return w
        if kind == "path":
            host = qt.QWidget()
            lay = qt.QHBoxLayout(host)
            lay.setContentsMargins(0, 0, 0, 0)
            edit = qt.QLineEdit()
            edit.setToolTip(spec.desc)
            btn = qt.QToolButton()
            btn.setText("浏览…")
            btn.clicked.connect(lambda _=False, e=edit: self._browse(e))
            lay.addWidget(edit)
            lay.addWidget(btn)
            host.setProperty("clitree_edit", edit)
            return host
        w = qt.QLineEdit()
        w.setToolTip(spec.desc)
        return w

    def _browse(self, edit) -> None:
        path, _ = qt.QFileDialog.getOpenFileName(self, "选择文件")
        if not path:
            path = qt.QFileDialog.getExistingDirectory(self, "或选择目录")
        if path:
            edit.setText(path)

    # ---------------------------------------------------------------- 取值
    def _raw_value(self, key: str):
        w = self._widgets.get(key)
        if isinstance(w, qt.QCheckBox):
            return w.isChecked()
        if isinstance(w, qt.QComboBox):
            text = w.currentText().strip()
            if self._kinds.get(key) == "tristate":
                return {"默认（不传）": None, "启用": True, "禁用": False}.get(text, None)
            return text or None
        if isinstance(w, qt.QSpinBox):
            return None if w.value() == -1_000_000 else str(w.value())
        if isinstance(w, qt.QListWidget):
            vals = [w.item(i).text().strip() for i in range(w.count())]
            return [x for x in vals if x] or None
        if isinstance(w, qt.QWidget) and w.property("clitree_edit") is not None:
            text = w.property("clitree_edit").text().strip()
            return text or None
        if isinstance(w, qt.QLineEdit):
            text = w.text().strip()
            return text or None
        return None

    def values(self) -> dict:
        out = {}
        for spec in self._specs:
            val = self._raw_value(spec.key)
            if val is None or val is False or val == []:
                continue
            if spec.repeatable and isinstance(val, str):
                val = [x.strip() for x in val.split(",") if x.strip()]
            out[spec.key] = val
        return out

    # ---------------------------------------------------------------- 测试/GUI 接口
    def widget_kinds(self) -> dict:
        return dict(self._kinds)

    def widget_for(self, key: str):
        w = self._widgets.get(key)
        if isinstance(w, qt.QWidget) and w.property("clitree_edit") is not None:
            return w.property("clitree_edit")
        return w

    def tooltips(self) -> dict:
        return {k: v.toolTip() for k, v in self._labels.items()}

    # ---------------------------------------------------------------- 参数说明
    def set_note(self, key: str, text: str, origin: str = "") -> None:
        """显示规则：有自己的说明就显示它（并附 help 原文），否则显示 help 原文。"""
        lab = self._note_labels.get(key)
        if lab is None:
            return
        origin = origin or self._descs.get(key, "")
        text = (text or "").strip()
        self._custom_notes[key] = text
        if text:
            suffix = f"　（原：{origin}）" if origin and origin != text else ""
            lab.setText(f"✎ {text}{suffix}")
            lab.setStyleSheet("color: #124;")
        else:
            lab.setText(origin or "（help 里没有这条参数的说明）")
            lab.setStyleSheet("color: #666;")

    def note_texts(self) -> dict:
        return {k: v.text() for k, v in self._note_labels.items()}

    def custom_note(self, key: str) -> str:
        return self._custom_notes.get(key, "")

    def begin_note_edit(self, key: str) -> None:
        """双击说明 ⇒ 就地变成输入框。"""
        if key in self._note_edits or key not in self._note_labels:
            return
        lab = self._note_labels[key]
        edit = qt.QLineEdit(self.custom_note(key))
        edit.setPlaceholderText("写你自己的说明；清空则回到 help 原文")
        edit.returnPressed.connect(lambda k=key, e=edit: self.commit_note_edit(k, e.text()))
        edit.editingFinished.connect(lambda k=key, e=edit: self.commit_note_edit(k, e.text()))
        lab.hide()
        self._rows[key].layout().addWidget(edit)
        self._note_edits[key] = edit
        edit.setFocus()

    def is_editing_note(self, key: str) -> bool:
        return key in self._note_edits

    def commit_note_edit(self, key: str, text: str) -> None:
        edit = self._note_edits.pop(key, None)
        if edit is None:
            return
        edit.setParent(None)
        lab = self._note_labels.get(key)
        if lab is not None:
            lab.show()
        if self._on_note_changed:
            self._on_note_changed(key, (text or "").strip())
        else:
            self.set_note(key, (text or "").strip())

    def descriptions(self) -> dict:
        return dict(self._descs)

    def required_marks(self) -> dict:
        return dict(self._marks)

    def labels(self) -> dict:
        return {k: v.text() for k, v in self._labels.items()}

    def order(self) -> list:
        return [s.key for s in self._specs]

    def set_value(self, key: str, value) -> None:
        w = self._widgets.get(key)
        if value is None or value == "":          # 清空（切配置时先把所有值复位）
            if isinstance(w, qt.QCheckBox):
                w.setChecked(False)
            elif isinstance(w, qt.QComboBox):
                if w.isEditable():
                    w.setCurrentIndex(-1)
                    w.setEditText("")
                else:
                    w.setCurrentIndex(0)
            elif isinstance(w, qt.QSpinBox):
                w.setValue(-1_000_000)             # 特殊值文本 = 「（不传）」
            elif isinstance(w, qt.QListWidget):
                w.clear()
                w.addItem("")
            elif isinstance(w, qt.QWidget) and w.property("clitree_edit") is not None:
                w.property("clitree_edit").setText("")
            elif isinstance(w, qt.QLineEdit):
                w.setText("")
            return
        if isinstance(w, qt.QCheckBox):
            w.setChecked(bool(value))
        elif isinstance(w, qt.QComboBox):
            w.setCurrentText(str(value))
        elif isinstance(w, qt.QSpinBox):
            w.setValue(int(value))
        elif isinstance(w, qt.QListWidget):
            w.clear()
            for v in (value if isinstance(value, (list, tuple)) else [value]):
                w.addItem(str(v))
        elif isinstance(w, qt.QWidget) and w.property("clitree_edit") is not None:
            w.property("clitree_edit").setText(str(value))
        elif isinstance(w, qt.QLineEdit):
            w.setText(str(value))

    def _show_kind_menu(self, spec: ParamSpec) -> None:
        menu = qt.QMenu(self)
        for kind, label in MODE_LABELS:
            act = qt.QAction(label, menu)
            act.triggered.connect(lambda _=False, k=kind, s=spec: self.change_widget_kind(s.key, k))
            menu.addAction(act)
        menu.exec_(qt.QCursor.pos())

    def change_widget_kind(self, key: str, kind: str) -> None:
        """用户纠正控件类型 ⇒ 写进用户覆盖文件，下次加载同一 CLI 自动生效。"""
        spec = next((s for s in self._specs if s.key == key), None)
        if spec is None:
            return
        old_row = self._rows.get(key)
        spec.widget = kind
        spec.widget_reason = f"规则覆盖：用户在 rules.user.json 指定 {key} 为 {kind}"
        self._kinds[key] = kind
        new_widget = self._make_widget(spec)
        new_row = self._make_row(spec, new_widget)
        self._widgets[key] = new_widget
        self._rows[key] = new_row
        lab = self._labels.get(key)
        if lab is not None:
            row, _role = self._form.getWidgetPosition(lab)
            if row >= 0:
                if old_row is not None:
                    self._form.removeWidget(old_row)
                self._form.setWidget(row, qt.QFormLayout.FieldRole, new_row)
        if old_row is not None and old_row is not new_row:
            old_row.setParent(None)
        if self.cli_name:
            store.save_widget_override(self.cli_name, key, kind)
        if self._on_kind_changed:
            self._on_kind_changed(self.cli_name, key, kind)
