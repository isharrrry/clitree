"""GUI 冒烟（offscreen）：建窗 → 加载（2 层）→ 展开 → 控件类型 → 三模式 → 图标状态。"""
import json
import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from clitree.core.discovery import ProbeResult  # noqa: E402

ROOT_HELP = """Usage: fakecli [options] <target>

Commands:
  sub1            first subcommand
  sub2            second subcommand

Options:
  -v, --verbose    verbose output
  -n, --count <count>   how many
  -m, --mode <mode>     mode, can be one of <fast|slow|auto>
  -o, --output <FILE>   output file
"""

SUB_HELP = """Usage: fakecli sub1 [options]

Options:
  -x, --extra <VALUE>   extra value
"""


@pytest.fixture(scope="module")
def qapp():
    from clitree.ui import qt

    app = qt.QApplication.instance() or qt.QApplication([])
    yield app


class ProbeRecorder:
    def __init__(self):
        self.calls = []

    def __call__(self, exe, rules, node_path=()):
        self.calls.append((exe, tuple(node_path)))
        text = SUB_HELP if node_path else ROOT_HELP
        return ProbeResult(ok=True, raw_text=text, channel=["--help"], rc=0, grade="full",
                           dialect="usage-posix", reason="ok", man_page_seen=False)


@pytest.fixture
def win(qapp, fakecli, tmp_path):
    from clitree.ui.main_window import MainWindow

    w = MainWindow(probe_fn=ProbeRecorder(), profile_root=tmp_path)
    yield w
    w.close()


def test_load_shows_two_levels(win, fakecli):
    win.load_command(fakecli)
    labels = win.tree_labels()
    assert any("fakecli" in x for x in labels)
    assert any("sub1" in x for x in labels)
    assert win.probe_calls == 1, "加载只许探测 1 次"


def test_expanding_subcommand_probes_once(win, fakecli):
    win.load_command(fakecli)
    win.tree.expand_subcommand("sub1")
    assert win.probe_calls == 2
    win.tree.expand_subcommand("sub1")
    assert win.probe_calls == 2, "重复展开必须命中缓存"


def test_widget_types_match_param_shape(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])  # 根节点
    kinds = win.form_widget_kinds()
    assert kinds.get("--verbose") == "checkbox"
    assert kinds.get("--count") == "spin"
    assert kinds.get("--mode") == "combo"
    assert kinds.get("--output") == "path"
    combo = win.form_widget("--mode")
    assert [combo.itemText(i) for i in range(combo.count())] == ["fast", "slow", "auto"]
    assert combo.isEditable(), "下拉必须可编辑"


def test_checkbox_shows_help_explanation(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    tips = win.form_tooltips()
    assert "verbose output" in tips.get("--verbose", ""), "勾选框旁必须有解释文字"


def test_background_run_logs_into_window(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    win.set_value("--verbose", True)
    win.run("background", argv_override=[sys.executable, fakecli, "--verbose"])
    win.wait_for_run(timeout=15)
    assert any("FAKECLI line" in line for line in win.log_lines())
    assert win.run_bar.state_of("background") == "ok"


def test_silent_run_adds_no_log(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    before = len(win.log_lines())
    win.run("silent", argv_override=[sys.executable, fakecli])
    win.wait_for_run(timeout=15)
    assert len(win.log_lines()) == before, "静默模式日志区不许新增行"
    assert win.run_bar.state_of("silent") == "ok"


def test_failed_run_marks_button_fail(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    win.run("background", argv_override=[sys.executable, fakecli, "--fail"])
    win.wait_for_run(timeout=15)
    assert win.run_bar.state_of("background") == "fail"


def test_terminal_run_marks_launched(win, fakecli, monkeypatch):
    from clitree.core import executor as E

    monkeypatch.setattr(E.Runner, "start_terminal",
                        lambda self, argv, platform=None: E.RunHandle(state="launched", argv=argv, rc=None))
    win.load_command(fakecli)
    win.tree.select_node([])
    win.run("terminal", argv_override=[sys.executable, fakecli])
    assert win.run_bar.state_of("terminal") == "launched"


def test_dangerous_command_is_refused_in_ui(win):
    win.load_command("/sbin/shutdown")
    assert any("安全策略" in line for line in win.log_lines() + win.status_lines())


def test_widget_override_persists(tmp_path, monkeypatch, qapp, fakecli):
    from clitree.core import store as S
    from clitree.ui.main_window import MainWindow

    user_rules = tmp_path / "rules.user.json"
    monkeypatch.setattr(S, "user_rules_path", lambda: user_rules)
    w = MainWindow(probe_fn=ProbeRecorder(), profile_root=tmp_path)
    try:
        w.load_command(fakecli)
        w.tree.select_node([])
        w.form.change_widget_kind("--verbose", "spin")
        assert user_rules.is_file()
        import json

        data = json.loads(user_rules.read_text())
        assert data["widgets"]["overrides"]["fakecli"]["--verbose"] == "spin"
    finally:
        w.close()


# ---- 表单可用性（2026-10 修订）：说明常显 / 必填排序 / 停止 ----

def test_positionals_first_then_required(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    order = win.form_param_order()
    assert order[0] == "@0", f"位置参数必须置顶: {order}"


def test_descriptions_are_always_visible(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    descs = win.form_descriptions()
    assert "verbose output" in descs.get("--verbose", "")
    assert "mode, can be one of" in descs.get("--mode", "")


def test_required_marks_only_where_meaningful(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    marks = win.form_required_marks()
    assert marks.get("@0") == "＊必填", marks
    assert marks.get("--verbose", "") == "", "可选项不该显示标记"


def test_long_and_short_names_both_shown(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    labels = win.form_labels()
    assert "--verbose" in labels.get("--verbose", "")
    assert "-v" in labels.get("--verbose", "")


def test_second_click_stops_the_run(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    win.run("background", argv_override=[sys.executable, fakecli, "--sleep", "30"])
    assert "停止" in win.run_bar.button_text("background")
    win.run("background", argv_override=[sys.executable, fakecli, "--sleep", "30"])  # 再点 = 停
    win.wait_for_run(timeout=15)
    assert win.run_bar.state_of("background") == "stopped"


def test_button_text_restored_after_run(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    win.run("silent", argv_override=[sys.executable, fakecli])
    win.wait_for_run(timeout=15)
    assert "停止" not in win.run_bar.button_text("silent")


# ---- CLI 配置文件（cli/<工具名>.json：多配置 ＋ 解析缓存）----

from clitree.core import profiles as PF   # noqa: E402


def make_win(tmp_path, recorder):
    from clitree.ui.main_window import MainWindow

    return MainWindow(probe_fn=recorder, profile_root=tmp_path)


def test_load_writes_cache_file(tmp_path, qapp, fakecli):
    rec = ProbeRecorder()
    w = make_win(tmp_path, rec)
    try:
        w.load_command(fakecli)
        assert PF.profile_path("fakecli", tmp_path).is_file()
        assert PF.cached_node("fakecli", [], tmp_path) is not None
    finally:
        w.close()


def test_second_load_uses_cache_and_does_not_probe(tmp_path, qapp, fakecli):
    w1 = make_win(tmp_path, ProbeRecorder())
    w1.load_command(fakecli)
    w1.close()
    rec2 = ProbeRecorder()
    w2 = make_win(tmp_path, rec2)
    try:
        w2.load_command(fakecli)
        assert rec2.calls == [], "有缓存就不该再去跑 help"
        assert w2.loaded_from_cache is True
        assert any("fakecli" in x for x in w2.tree_labels())
        assert "--verbose" in w2.form_widget_kinds()
    finally:
        w2.close()


def test_reparse_forces_probe_and_updates_cache(tmp_path, qapp, fakecli):
    w1 = make_win(tmp_path, ProbeRecorder())
    w1.load_command(fakecli)
    w1.close()
    rec2 = ProbeRecorder()
    w2 = make_win(tmp_path, rec2)
    try:
        w2.load_command(fakecli)
        assert rec2.calls == []
        w2.reparse()
        assert len(rec2.calls) == 1
        assert w2.loaded_from_cache is False
    finally:
        w2.close()


def test_save_as_creates_named_profile(tmp_path, qapp, fakecli):
    w = make_win(tmp_path, ProbeRecorder())
    try:
        w.load_command(fakecli)
        w.set_value("--verbose", True)
        w.save_as_profile("带 verbose")
        assert "带 verbose" in w.profile_names()
        assert w.profile_combo.currentText() == "带 verbose"
        assert PF.get_profile("fakecli", "带 verbose", tmp_path)["values"]["--verbose"] is True
    finally:
        w.close()


def test_switch_profile_restores_values(tmp_path, qapp, fakecli):
    w = make_win(tmp_path, ProbeRecorder())
    try:
        w.load_command(fakecli)
        w.set_value("--count", "3")
        w.save_current_profile()                 # 存进「默认」
        w.set_value("--count", "9")
        w.save_as_profile("b")                   # 另存为新配置
        w.switch_profile("默认")
        assert w.form.values().get("--count") == "3"
        w.switch_profile("b")
        assert w.form.values().get("--count") == "9"
    finally:
        w.close()


def test_profiles_persist_across_windows(tmp_path, qapp, fakecli):
    w1 = make_win(tmp_path, ProbeRecorder())
    w1.load_command(fakecli)
    w1.set_value("--count", "7")
    w1.save_as_profile("持久")
    w1.close()
    w2 = make_win(tmp_path, ProbeRecorder())
    try:
        w2.load_command(fakecli)
        assert "持久" in w2.profile_names()
        w2.switch_profile("持久")
        assert w2.form.values().get("--count") == "7"
    finally:
        w2.close()


def test_switching_profile_autosaves_previous_values(tmp_path, qapp, fakecli):
    w = make_win(tmp_path, ProbeRecorder())
    try:
        w.load_command(fakecli)
        w.set_value("--count", "11")
        w.save_current_profile()
        w.switch_profile("默认")                  # 值没改，不该丢
        assert w.form.values().get("--count") == "11"
    finally:
        w.close()


# ---- 参数说明：显示 help 原文 ＋ 双击改成自己的说明 ----

def test_help_description_is_shown_by_default(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    assert "verbose output" in win.form.note_texts()["--verbose"]


def test_double_click_edits_note_and_marks_it(win, fakecli):
    win.load_command(fakecli)
    win.tree.select_node([])
    win.form.begin_note_edit("--verbose")
    assert win.form.is_editing_note("--verbose") is True
    win.form.commit_note_edit("--verbose", "打开详细输出，排错时用")
    assert win.form.is_editing_note("--verbose") is False
    shown = win.form.note_texts()["--verbose"]
    assert "打开详细输出，排错时用" in shown
    assert "原：verbose output" in shown, "必须同时给出 help 原文，便于分辨"


def test_custom_note_persists_into_file_and_next_session(tmp_path, qapp, fakecli):
    w1 = make_win(tmp_path, ProbeRecorder())
    w1.load_command(fakecli)
    w1.tree.select_node([])
    w1.set_note("--verbose", "打开详细输出")
    w1.close()
    data = json.loads(PF.profile_path("fakecli", tmp_path).read_text())
    assert data["notes"]["--verbose"] == "打开详细输出"

    w2 = make_win(tmp_path, ProbeRecorder())        # 走缓存那条路
    try:
        w2.load_command(fakecli)
        w2.tree.select_node([])
        assert "打开详细输出" in w2.form.note_texts()["--verbose"]
    finally:
        w2.close()


def test_profile_level_note_wins_over_file_level(tmp_path, qapp, fakecli):
    w = make_win(tmp_path, ProbeRecorder())
    try:
        w.load_command(fakecli)
        w.tree.select_node([])
        w.set_note("--verbose", "文件级说明")
        w.save_as_profile("排错")
        w.set_note("--verbose", "排错时必开", scope="profile")
        w.switch_profile("默认")
        assert "文件级说明" in w.form.note_texts()["--verbose"]
        w.switch_profile("排错")
        assert "排错时必开" in w.form.note_texts()["--verbose"]
    finally:
        w.close()
