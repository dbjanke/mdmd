"""File names and document text must reach Qt widgets as plain text, never as markup."""

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextDocumentFragment
from PySide6.QtWidgets import QApplication, QMessageBox
from pytestqt.qtbot import QtBot

from mdmd.ui.application import Application
from mdmd.ui.launcher_panel import LauncherPanel
from mdmd.ui.prompts import QtPrompts, plain_message_box
from mdmd.ui.untrusted_text import menu_text, tooltip_text

# Linux file names cannot hold "/", so a hostile name spells it as an entity and leaves tags open.
HOSTILE_NAME = '<a href="https:&#47;&#47;evil.example">Click to unlock & <b>more.md'


def shown_text(tooltip: str) -> str:
    return QTextDocumentFragment.fromHtml(tooltip).toPlainText()


def test_tooltip_text_shows_markup_literally() -> None:
    assert shown_text(tooltip_text(HOSTILE_NAME)) == HOSTILE_NAME
    assert "<a href" not in tooltip_text(HOSTILE_NAME)


def test_tooltip_text_keeps_spaces() -> None:
    assert shown_text(tooltip_text("two  spaces")) == "two  spaces"


def test_menu_text_escapes_shortcut_markers() -> None:
    assert menu_text("Tom & Jerry.md") == "Tom && Jerry.md"
    assert menu_text("plain.md") == "plain.md"


def test_message_boxes_never_interpret_markup(qtbot: QtBot) -> None:
    box = plain_message_box(None, QMessageBox.Icon.Warning, "Cannot open file", f"/tmp/{HOSTILE_NAME} does not exist.")
    qtbot.addWidget(box)
    assert box.textFormat() == Qt.TextFormat.PlainText


def test_launcher_tooltip_is_plain(qtbot: QtBot, tmp_path: Path) -> None:
    path = str(tmp_path / HOSTILE_NAME)
    panel = LauncherPanel()
    qtbot.addWidget(panel)
    panel.set_recent_files((path,))
    assert shown_text(panel.recent_list.item(0).toolTip()) == path
    assert panel.recent_list.item(0).text().startswith(HOSTILE_NAME)


def test_open_recent_menu_shows_the_name_literally(make_app: Callable[[], Application], tmp_path: Path) -> None:
    path = tmp_path / HOSTILE_NAME
    path.write_text("x")
    app = make_app()
    app.start([path])
    window = app.windows[0]
    menu = window._recent_menu
    menu.aboutToShow.emit()
    (action,) = menu.actions()
    assert action.text() == menu_text(HOSTILE_NAME)
    assert shown_text(action.toolTip()) == str(path)


class TestQtPrompts:
    """The real message boxes, with exec() answered by the test instead of a person."""

    def answer_with(self, monkeypatch: pytest.MonkeyPatch, button: QMessageBox.StandardButton) -> list[QMessageBox]:
        shown: list[QMessageBox] = []

        def fake_exec(box: QMessageBox) -> int:
            shown.append(box)
            return int(button.value)

        monkeypatch.setattr(QMessageBox, "exec", fake_exec)
        return shown

    def test_error_and_about_show_plain_text(self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
        shown = self.answer_with(monkeypatch, QMessageBox.StandardButton.Ok)
        QtPrompts().error(None, "Cannot open file", f"{HOSTILE_NAME} does not exist.")
        QtPrompts().about(None, "About mdmd", "mdmd <b>1.0</b>")
        assert [box.textFormat() for box in shown] == [Qt.TextFormat.PlainText] * 2
        assert shown[0].text() == f"{HOSTILE_NAME} does not exist."

    @pytest.mark.parametrize(
        ("button", "expected"),
        [
            (QMessageBox.StandardButton.Yes, True),
            (QMessageBox.StandardButton.No, False),
            (QMessageBox.StandardButton.NoButton, False),  # closed with Esc or the window's close button
        ],
    )
    def test_confirm_is_true_only_for_yes(
        self,
        qapp: QApplication,
        monkeypatch: pytest.MonkeyPatch,
        button: QMessageBox.StandardButton,
        expected: bool,
    ) -> None:
        shown = self.answer_with(monkeypatch, button)
        assert QtPrompts().confirm(None, "Delete theme?", 'Delete the theme "<b>x</b>"?') is expected
        (box,) = shown
        assert box.textFormat() == Qt.TextFormat.PlainText
        assert box.defaultButton() is box.button(QMessageBox.StandardButton.No)
