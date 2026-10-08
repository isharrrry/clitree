"""左树：根 CLI → 子命令（初始 2 层）；点开子命令才触发探测。"""
from . import qt


class TreePanel(qt.QTreeWidget):
    def __init__(self, parent=None, on_expand=None, on_select=None):
        super().__init__(parent)
        self.setHeaderLabels(["命令 / 参数树", "说明"])
        self.setColumnWidth(0, 300)
        self._on_expand = on_expand
        self._on_select = on_select
        self.itemExpanded.connect(self._expanded)
        self.itemSelectionChanged.connect(self._selected)
        self._nodes = {}

    # ---------------------------------------------------------------- 渲染
    def show_root(self, root) -> None:
        self.clear()
        self._nodes = {}
        item = self._make_item(root, is_root=True)
        self.addTopLevelItem(item)
        item.setExpanded(True)
        self.setCurrentItem(item)

    def _make_item(self, node, is_root: bool = False):
        if is_root:
            counts = f"分支 {len(node.subcommands)} · 参数 {len(node.options)}"
            label = f"{node.name}   [{counts}]"
        else:
            label = node.name
            if node.load_state == "pending":
                label += "  (未展开)"
            elif node.load_state == "failed":
                label += "  (取不到 help)"
        item = qt.QTreeWidgetItem([label, node.desc or ""])
        self._nodes[id(item)] = node
        for child in node.subcommands:
            item.addChild(self._make_item(child))
        return item

    def refresh(self) -> None:
        root = self.root_node()
        if root is not None:
            self.show_root(root)

    def root_node(self):
        if self.topLevelItemCount() == 0:
            return None
        return self._nodes.get(id(self.topLevelItem(0)))

    def _node_of(self, item):
        return self._nodes.get(id(item))

    # ---------------------------------------------------------------- 交互
    def _expanded(self, item) -> None:
        node = self._node_of(item)
        if node is None or node.load_state != "pending" or node.depth <= 1:
            return
        if self._on_expand:
            self._on_expand(node)

    def _selected(self) -> None:
        item = self.currentItem()
        node = self._node_of(item) if item is not None else None
        if node is not None and self._on_select:
            self._on_select(node)

    def select_node(self, path: list) -> None:
        if not path:
            if self.topLevelItemCount():
                self.setCurrentItem(self.topLevelItem(0))
            return
        item = self.topLevelItem(0)
        for name in path:
            nxt = None
            for i in range(item.childCount()):
                cand = item.child(i)
                node = self._node_of(cand)
                if node is not None and node.name == name:
                    nxt = cand
                    break
            if nxt is None:
                return
            item = nxt
        self.setCurrentItem(item)

    def expand_subcommand(self, name: str) -> None:
        """展开一个子命令：交给主窗去探测（主窗会重建树，这里不要再碰 item）。"""
        root = self.topLevelItem(0)
        if root is None:
            return
        for i in range(root.childCount()):
            node = self._node_of(root.child(i))
            if node is not None and node.name == name:
                if self._on_expand:
                    self._on_expand(node)
                return

    def labels(self) -> list:
        out = []

        def walk(item):
            out.append(item.text(0))
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.topLevelItemCount()):
            walk(self.topLevelItem(i))
        return out
