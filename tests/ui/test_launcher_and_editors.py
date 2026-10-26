from pathlib import Path

from pytestqt.qtbot import QtBot

from mdmd.core.style import ELEMENTS_BY_KEY, PropertyKind
from mdmd.ui.launcher_panel import LauncherPanel
from mdmd.ui.property_editors import AlignmentEditor, FlagEditor, FontEditor, NumberEditor, make_editor


class TestLauncher:
    def test_empty_list_message(self, qtbot: QtBot) -> None:
        panel = LauncherPanel()
        qtbot.addWidget(panel)
        panel.set_recent_files(())
        assert panel.showing_empty_message

    def test_entries_show_name_folder_and_missing_mark(self, qtbot: QtBot, tmp_path: Path) -> None:
        present = tmp_path / "here.md"
        present.write_text("x")
        panel = LauncherPanel()
        qtbot.addWidget(panel)
        panel.set_recent_files((str(present), str(tmp_path / "gone.md")))
        texts = [panel.recent_list.item(i).text() for i in range(panel.recent_list.count())]
        assert texts == [f"here.md\n{tmp_path}", f"gone.md (missing)\n{tmp_path}"]
        assert not panel.showing_empty_message

    def test_activating_an_entry_requests_it(self, qtbot: QtBot, tmp_path: Path) -> None:
        panel = LauncherPanel()
        qtbot.addWidget(panel)
        panel.set_recent_files((str(tmp_path / "a.md"),))
        with qtbot.waitSignal(panel.open_requested) as signal:
            panel.recent_list.itemActivated.emit(panel.recent_list.item(0))
        assert signal.args == [str(tmp_path / "a.md")]


class TestEditors:
    def test_factory_picks_an_editor_per_kind(self, qtbot: QtBot) -> None:
        body = ELEMENTS_BY_KEY["body"]
        assert isinstance(make_editor(body.property("fontFamily"), ["A"]), FontEditor)
        assert isinstance(make_editor(body.property("size"), ["A"]), NumberEditor)
        assert isinstance(make_editor(body.property("alignment"), ["A"]), AlignmentEditor)
        assert isinstance(make_editor(ELEMENTS_BY_KEY["link"].property("underline"), ["A"]), FlagEditor)

    def test_set_value_does_not_emit(self, qtbot: QtBot) -> None:
        editor = NumberEditor(PropertyKind.SIZE)
        qtbot.addWidget(editor)
        with qtbot.assertNotEmitted(editor.value_edited):
            editor.set_value(20.0)

    def test_number_ranges_match_the_schema(self, qtbot: QtBot) -> None:
        spacing = NumberEditor(PropertyKind.LINE_SPACING)
        qtbot.addWidget(spacing)
        assert (spacing.spin_box.minimum(), spacing.spin_box.maximum()) == (0.8, 3.0)

    def test_uninstalled_font_is_shown_and_kept(self, qtbot: QtBot) -> None:
        editor = FontEditor(["Alpha", "Beta"], optional=False)
        qtbot.addWidget(editor)
        editor.set_value("Gamma")
        assert editor.combo.currentText() == "Gamma (not installed)"
        with qtbot.waitSignal(editor.value_edited) as signal:
            editor.combo.setCurrentIndex(1)
        assert signal.args == ["Beta"]

    def test_alignment_and_flag_emit_values(self, qtbot: QtBot) -> None:
        alignment = AlignmentEditor()
        qtbot.addWidget(alignment)
        with qtbot.waitSignal(alignment.value_edited) as signal:
            alignment.combo.setCurrentIndex(3)
        assert signal.args == ["justify"]
        flag = FlagEditor("")
        qtbot.addWidget(flag)
        flag.set_value(True)
        with qtbot.waitSignal(flag.value_edited) as signal:
            flag.check_box.setChecked(False)
        assert signal.args == [False]
