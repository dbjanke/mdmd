"""The settings dialog: editing, live preview, themes, Apply/OK/Cancel."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QDialogButtonBox
from pytestqt.qtbot import QtBot

from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.document import Heading, ListBlock
from mdmd.core.style import ELEMENTS
from mdmd.core.themes import Theme
from mdmd.ui.application import Application
from mdmd.ui.document_view import char_format_at
from mdmd.ui.footnote_popup import FootnotePopup
from mdmd.ui.property_editors import ColorEditor, FontEditor, NumberEditor
from mdmd.ui.settings_dialog import SettingsDialog, sample_document
from tests.ui.conftest import FakePrompts, needs_permissions, read_only

MakeApp = Callable[[], Application]


@pytest.fixture
def app(make_app: MakeApp) -> Application:
    return make_app()


@pytest.fixture
def dialog(qtbot: QtBot, app: Application) -> SettingsDialog:
    dialog = SettingsDialog(app)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


def select_element(dialog: SettingsDialog, key: str) -> None:
    dialog.element_list.setCurrentRow([e.key for e in ELEMENTS].index(key))


def preview_size(qtbot: QtBot, dialog: SettingsDialog, text: str) -> float:
    qtbot.wait(80)  # the preview re-renders after a short delay
    doc = dialog.preview.document()
    return char_format_at(doc, doc.find(text).selectionStart()).fontPointSize()


def combo_texts(dialog: SettingsDialog) -> list[str]:
    combo = dialog.theme_combo
    return [combo.itemText(i) for i in range(combo.count())]


class TestEditing:
    def test_editing_updates_draft_preview_and_modified_label(self, qtbot: QtBot, dialog: SettingsDialog) -> None:
        select_element(dialog, "h1")
        editor = dialog.editors["size"]
        assert isinstance(editor, NumberEditor)
        editor.spin_box.setValue(40)
        assert dialog.draft.style.number("h1", "size") == 40
        assert preview_size(qtbot, dialog, "Heading 1") == 40
        assert dialog.theme_combo.currentText() == "Default (modified)"

    def test_out_of_range_number_is_refused(self, dialog: SettingsDialog) -> None:
        select_element(dialog, "body")
        editor = dialog.editors["size"]
        assert isinstance(editor, NumberEditor)
        editor.spin_box.setValue(500)  # the spin box clamps to its maximum
        assert dialog.draft.style.number("body", "size") == 96

    def test_invalid_hex_color_is_reverted(self, dialog: SettingsDialog) -> None:
        select_element(dialog, "page")
        editor = dialog.editors["background"]
        assert isinstance(editor, ColorEditor)
        editor.hex_field.setText("#zzzzzz")
        editor.hex_field.editingFinished.emit()
        assert editor.hex_field.text() == "#ffffff"
        editor.hex_field.setText("#ABCDEF")
        editor.hex_field.editingFinished.emit()
        assert dialog.draft.style.text("page", "background") == "#abcdef"

    def test_table_font_can_follow_the_body_font(self, dialog: SettingsDialog) -> None:
        select_element(dialog, "table")
        editor = dialog.editors["fontFamily"]
        assert isinstance(editor, FontEditor)
        assert editor.inherit_box is not None and editor.inherit_box.isChecked()
        editor.inherit_box.setChecked(False)
        assert isinstance(dialog.draft.style.value("table", "fontFamily"), str)
        editor.inherit_box.setChecked(True)
        assert dialog.draft.style.value("table", "fontFamily") is None


class TestButtons:
    def test_windows_change_only_on_apply(self, dialog: SettingsDialog, app: Application) -> None:
        select_element(dialog, "h1")
        editor = dialog.editors["size"]
        assert isinstance(editor, NumberEditor)
        editor.spin_box.setValue(40)
        assert app.style == DEFAULT_STYLE
        assert dialog.apply()
        assert app.style.number("h1", "size") == 40

    def test_cancel_discards_unapplied_changes(self, dialog: SettingsDialog, app: Application) -> None:
        select_element(dialog, "h1")
        editor = dialog.editors["size"]
        assert isinstance(editor, NumberEditor)
        editor.spin_box.setValue(40)
        dialog.reject()
        assert app.style == DEFAULT_STYLE

    @needs_permissions
    def test_failed_apply_reports_and_stays_open(
        self, dialog: SettingsDialog, app: Application, config_dir: Path, prompts: FakePrompts
    ) -> None:
        with read_only(config_dir):
            assert not dialog.apply()
        assert prompts.errors[0][0] == "Cannot save settings"
        assert dialog.isVisible()
        assert app.style == DEFAULT_STYLE


class TestThemes:
    def test_default_theme_cannot_be_deleted(self, dialog: SettingsDialog) -> None:
        assert combo_texts(dialog) == ["Default"]
        assert not dialog.delete_theme_button.isEnabled()

    def test_save_as_theme_makes_it_active(
        self, dialog: SettingsDialog, app: Application, prompts: FakePrompts
    ) -> None:
        prompts.text_answers = ["  Evening "]
        dialog.save_theme_button.click()
        assert dialog.draft.active_theme == "Evening"
        assert app.themes.find("Evening") is not None
        assert combo_texts(dialog) == ["Default", "Evening"]
        assert dialog.theme_combo.currentText() == "Evening"

    @pytest.mark.parametrize("name", ["", "default", "x" * 65])
    def test_invalid_names_are_refused(
        self, dialog: SettingsDialog, app: Application, prompts: FakePrompts, name: str
    ) -> None:
        prompts.text_answers = [name]
        dialog.save_theme_button.click()
        assert prompts.errors and prompts.errors[0][0] == "Invalid theme name"
        assert app.themes.user_themes == ()

    def test_existing_name_asks_before_overwriting(
        self, dialog: SettingsDialog, app: Application, prompts: FakePrompts
    ) -> None:
        app.save_theme(Theme("Evening", DEFAULT_STYLE))
        select_element(dialog, "h1")
        editor = dialog.editors["size"]
        assert isinstance(editor, NumberEditor)
        editor.spin_box.setValue(40)
        prompts.text_answers = ["evening", "evening"]
        prompts.confirm_answers = [False, True]
        dialog.save_theme_button.click()
        theme = app.themes.find("Evening")
        assert theme is not None and theme.style == DEFAULT_STYLE
        dialog.save_theme_button.click()
        theme = app.themes.find("evening")
        assert theme is not None and theme.style.number("h1", "size") == 40
        assert len(prompts.confirmations) == 2

    def test_choosing_a_theme_loads_its_values(self, qtbot: QtBot, app: Application, make_app: MakeApp) -> None:
        app.save_theme(Theme("Big", DEFAULT_STYLE.with_value("h1", "size", 50)))
        dialog = SettingsDialog(app)
        qtbot.addWidget(dialog)
        index = dialog.theme_combo.findData("Big")
        dialog.theme_combo.activated.emit(index)
        assert dialog.draft.active_theme == "Big"
        assert dialog.draft.style.number("h1", "size") == 50
        assert preview_size(qtbot, dialog, "Heading 1") == 50
        assert app.style == DEFAULT_STYLE

    def test_delete_keeps_values_and_shows_no_theme(
        self, dialog: SettingsDialog, app: Application, prompts: FakePrompts
    ) -> None:
        prompts.text_answers = ["Evening"]
        dialog.save_theme_button.click()
        style = dialog.draft.style
        prompts.confirm_answers = [False, True]
        dialog.delete_theme_button.click()
        assert app.themes.find("Evening") is not None
        dialog.delete_theme_button.click()
        assert app.themes.find("Evening") is None
        assert dialog.draft.style == style
        assert dialog.draft.active_theme is None
        assert dialog.theme_combo.currentText() == "No theme"


class TestDialogEdges:
    def test_ok_applies_and_closes(self, dialog: SettingsDialog, app: Application) -> None:
        select_element(dialog, "h1")
        editor = dialog.editors["size"]
        assert isinstance(editor, NumberEditor)
        editor.spin_box.setValue(33)
        dialog.button_box.button(QDialogButtonBox.StandardButton.Ok).click()
        assert app.style.number("h1", "size") == 33
        assert not dialog.isVisible()

    def test_invalid_value_from_an_editor_is_reverted(self, dialog: SettingsDialog) -> None:
        select_element(dialog, "body")
        editor = dialog.editors["size"]
        assert isinstance(editor, NumberEditor)
        editor.value_edited.emit(500.0)
        assert dialog.draft.style.number("body", "size") == DEFAULT_STYLE.number("body", "size")
        assert editor.spin_box.value() == DEFAULT_STYLE.number("body", "size")

    def test_cancelled_name_prompt_saves_nothing(
        self, dialog: SettingsDialog, app: Application, prompts: FakePrompts
    ) -> None:
        prompts.text_answers = [None]
        dialog.save_theme_button.click()
        assert app.themes.user_themes == ()
        assert dialog.draft.active_theme == "Default"

    @needs_permissions
    def test_theme_that_cannot_be_written_shows_an_error(
        self, dialog: SettingsDialog, app: Application, config_dir: Path, prompts: FakePrompts
    ) -> None:
        prompts.text_answers = ["Evening"]
        with read_only(config_dir / "themes"):
            dialog.save_theme_button.click()
        assert prompts.errors[-1][0] == "Cannot save theme"
        assert app.themes.find("Evening") is None
        assert dialog.draft.active_theme == "Default"

    def test_theme_that_cannot_be_deleted_shows_an_error(
        self, dialog: SettingsDialog, app: Application, config_dir: Path, prompts: FakePrompts
    ) -> None:
        prompts.text_answers = ["Evening"]
        dialog.save_theme_button.click()
        themes = config_dir / "themes"
        themes.chmod(0o500)  # files inside cannot be removed
        prompts.confirm_answers = [True]
        try:
            dialog.delete_theme_button.click()
        finally:
            themes.chmod(0o700)
        if os.geteuid() != 0:
            assert prompts.errors[-1][0] == "Cannot delete theme"
            assert app.themes.find("Evening") is not None
            assert dialog.draft.active_theme == "Evening"

    def test_sample_contains_every_element(self) -> None:
        sample = sample_document()
        kinds = {type(block).__name__ for block in sample.blocks}
        assert {"Heading", "Paragraph", "CodeBlock", "BlockQuote", "ListBlock", "Table", "HorizontalRule"} <= kinds
        levels = {block.level for block in sample.blocks if isinstance(block, Heading)}
        assert levels == {1, 2, 3, 4, 5, 6}
        lists = [block for block in sample.blocks if isinstance(block, ListBlock)]
        assert any(b.ordered for b in lists)
        assert any(not b.ordered and b.items[0].checked is None for b in lists)
        assert any(b.items[0].checked is not None for b in lists)
        assert sample.notes
        text = str(sample.blocks)
        for kind in ("Link(", "InlineCode(", "NoteRef("):
            assert kind in text

    def test_preview_marker_opens_a_sample_popup(self, qtbot: QtBot, dialog: SettingsDialog) -> None:
        note_id = next(iter(sample_document().notes))
        dialog.preview.note_activated.emit(note_id, QRect(100, 100, 10, 10))
        popup = dialog.findChild(FootnotePopup)
        assert popup is not None
        qtbot.waitUntil(popup.isVisible)
        assert "sample footnote" in popup.view.document().toPlainText()
