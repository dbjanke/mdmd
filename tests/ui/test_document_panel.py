"""The document view and panel: copying, markers, find, reload, zoom, and popups."""

import os
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QTextCursor
from pytestqt.qtbot import QtBot

from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.storage.markdown_files import FileOpenError
from mdmd.ui.document_panel import DocumentPanel
from mdmd.ui.document_view import COPY_LINK_LABEL, CURRENT_MATCH_COLOR, char_format_at
from mdmd.ui.file_watcher import SETTLE_DELAY_MS
from mdmd.ui.find_bar import FAILED_FIELD_STYLE
from mdmd.ui.fonts import FontResolver
from mdmd.ui.footnote_popup import POPUP_MAX_HEIGHT_PX

WriteMd = Callable[[str, str], Path]
FILE_SETTLE_WAIT_MS = SETTLE_DELAY_MS * 3

FOOTNOTES = (
    "Claim one.[^a] Claim two.[^b]\n\n"
    "[^a]: *Doll* in the [Review](https://example.com/review).\n\n"
    "[^b]: First paragraph.\n\n    Second paragraph.\n"
)


@pytest.fixture
def make_panel(qtbot: QtBot, fonts: FontResolver, write_md: WriteMd) -> Callable[[str], DocumentPanel]:
    def make(text: str) -> DocumentPanel:
        path = write_md("doc.md", text)
        panel = DocumentPanel(path, text, DEFAULT_STYLE, fonts)
        qtbot.addWidget(panel)
        panel.resize(700, 500)
        panel.show()
        qtbot.waitExposed(panel)
        return panel

    return make


def marker_positions(panel: DocumentPanel) -> list[int]:
    return [i for i, ch in enumerate(panel.view.raw_text()) if ch == "￼"]


def click_position(qtbot: QtBot, panel: DocumentPanel, position: int) -> None:
    cursor = QTextCursor(panel.view.document())
    cursor.setPosition(position)
    rect = panel.view.cursorRect(cursor)
    point = QPoint(rect.left() + 4, rect.center().y())
    qtbot.mouseClick(panel.view.viewport(), Qt.MouseButton.LeftButton, pos=point)


class TestCopy:
    def test_markers_copy_as_bracketed_numbers(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel(FOOTNOTES)
        panel.view.selectAll()
        text = panel.view.selected_plain_text()
        assert "Claim one.[1] Claim two.[2]" in text
        assert "￼" not in text

    def test_copy_puts_plain_text_on_clipboard(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("Hello *there*")
        panel.view.selectAll()
        panel.view.copy()
        assert QGuiApplication.clipboard().text() == "Hello there"


class TestLinks:
    def test_link_address_found_under_pointer(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("Go to [the site](https://example.com) now")
        cursor = panel.view.document().find("the site")
        rect = panel.view.cursorRect(QTextCursor(panel.view.document().findBlock(cursor.selectionStart())))
        start = QTextCursor(panel.view.document())
        start.setPosition(cursor.selectionStart() + 2)
        point = panel.view.cursorRect(start).center()
        assert panel.view.link_href_at(point) == "https://example.com"
        assert panel.view.link_href_at(QPoint(rect.left() + 1, rect.center().y())) is None

    def test_heading_link_scrolls(self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]) -> None:
        filler = "\n\n".join(f"Paragraph {n}." for n in range(80))
        panel = make_panel(f"[jump](#target)\n\n{filler}\n\n## Target\n\nEnd.")
        assert panel.view.verticalScrollBar().value() == 0
        cursor = panel.view.document().find("jump")
        click_position(qtbot, panel, cursor.selectionStart() + 1)
        assert panel.view.verticalScrollBar().value() > 0


class TestFootnotePopup:
    def test_clicking_a_marker_opens_its_note_with_formatting(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]
    ) -> None:
        panel = make_panel(FOOTNOTES)
        first, _second = marker_positions(panel)
        click_position(qtbot, panel, first)
        popup = panel.popup
        assert popup is not None
        qtbot.waitUntil(popup.isVisible)
        doc = popup.view.document()
        assert "Doll in the Review (https://example.com/review)." in doc.toPlainText()
        assert char_format_at(doc, doc.find("Doll").selectionStart()).fontItalic()

    def test_second_marker_shows_both_paragraphs_and_esc_closes(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]
    ) -> None:
        panel = make_panel(FOOTNOTES)
        _first, second = marker_positions(panel)
        click_position(qtbot, panel, second)
        popup = panel.popup
        assert popup is not None
        qtbot.waitUntil(popup.isVisible)
        assert "First paragraph." in popup.view.document().toPlainText()
        assert "Second paragraph." in popup.view.document().toPlainText()
        qtbot.keyClick(popup, Qt.Key.Key_Escape)
        assert not popup.isVisible()

    def test_footnote_definitions_are_not_in_the_document(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel(FOOTNOTES)
        assert "First paragraph" not in panel.view.document().toPlainText()


class TestFind:
    TEXT = "Alpha beta.\n\nalpha gamma.\n\nALPHA delta.[^n]\n\n[^n]: alpha in a footnote."

    def test_typing_highlights_and_counts_matches_ignoring_case(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]
    ) -> None:
        panel = make_panel(self.TEXT)
        panel.finder.open()
        qtbot.keyClicks(panel.find_bar.field, "alpha")
        assert panel.finder.match_count == 3  # footnote text is not searched
        assert panel.finder.current_index == 0
        assert len(panel.view.extraSelections()) == 3
        current = panel.view.extraSelections()[0]
        assert current.format.background().color().name() == CURRENT_MATCH_COLOR

    def test_next_and_previous_wrap(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel(self.TEXT)
        bar = panel.find_bar
        panel.finder.open()
        bar.field.setText("alpha")
        panel.finder.previous()
        assert panel.finder.current_index == 2
        panel.finder.next()
        assert panel.finder.current_index == 0
        assert bar.count_text == "1 of 3"

    def test_match_case(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel(self.TEXT)
        bar = panel.find_bar
        panel.finder.open()
        bar.match_case_box.setChecked(True)
        bar.field.setText("alpha")
        assert panel.finder.match_count == 1

    def test_no_match_marks_field_failed_and_close_clears(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]
    ) -> None:
        panel = make_panel(self.TEXT)
        bar = panel.find_bar
        panel.finder.open()
        bar.field.setText("zebra")
        assert bar.count_text == "0 of 0"
        assert bar.field.styleSheet() == FAILED_FIELD_STYLE
        bar.field.setText("alpha")
        assert bar.field.styleSheet() == ""
        qtbot.keyClick(bar.field, Qt.Key.Key_Escape)
        assert not bar.isVisible()
        assert panel.view.extraSelections() == []

    def test_enter_and_shift_enter_step(self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel(self.TEXT)
        bar = panel.find_bar
        panel.finder.open()
        bar.field.setText("alpha")
        qtbot.keyClick(bar.field, Qt.Key.Key_Return)
        assert panel.finder.current_index == 1
        qtbot.keyClick(bar.field, Qt.Key.Key_Return, Qt.KeyboardModifier.ShiftModifier)
        assert panel.finder.current_index == 0

    def test_find_next_with_closed_bar_opens_it(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel(self.TEXT)
        panel.finder.next()
        assert panel.find_bar.isVisible()


class TestReloadAndZoom:
    def test_reload_shows_new_content_and_keeps_scroll(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]
    ) -> None:
        text = "\n\n".join(f"Paragraph {n}." for n in range(120))
        panel = make_panel(text)
        bar = panel.view.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        offset = bar.value()
        panel.path.write_text(text + "\n\nAppended.", encoding="utf-8")
        panel.reload()
        qtbot.wait(10)
        assert "Appended." in panel.view.document().toPlainText()
        assert bar.value() == offset

    def test_reload_of_deleted_file_raises_and_keeps_content(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("Still here.")
        panel.path.unlink()
        with pytest.raises(FileOpenError):
            panel.reload()
        assert "Still here." in panel.view.document().toPlainText()

    def test_file_change_reloads_automatically(self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("Version one.")
        replacement = panel.path.with_suffix(".tmp")
        replacement.write_text("Version two.", encoding="utf-8")
        replacement.replace(panel.path)  # the way many editors save
        qtbot.waitUntil(lambda: "Version two." in panel.view.document().toPlainText(), timeout=3000)

    def test_zoom_steps_and_limits(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("text")

        def size() -> float:
            doc = panel.view.document()
            return char_format_at(doc, doc.find("text").selectionStart()).fontPointSize()

        panel.zoom_in()
        assert panel.zoom_percent == 110
        assert size() == pytest.approx(11 * 1.1)
        for _ in range(40):
            panel.zoom_in()
        assert panel.zoom_percent == 300
        for _ in range(40):
            panel.zoom_out()
        assert panel.zoom_percent == 50
        panel.reset_zoom()
        assert size() == pytest.approx(11)

    def test_set_style_restyles(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("text")
        panel.set_style(DEFAULT_STYLE.with_value("body", "size", 20))
        doc = panel.view.document()
        assert char_format_at(doc, doc.find("text").selectionStart()).fontPointSize() == 20


class TestViewDetails:
    def test_context_menu_offers_copy_link_only_over_links(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("Plain words then [the site](https://example.com).")
        view = panel.view
        doc = view.document()
        on_link = QTextCursor(doc)
        on_link.setPosition(doc.find("the site").selectionStart() + 2)
        menu = view.context_menu(view.cursorRect(on_link).center())
        first = menu.actions()[0]
        assert first.text() == COPY_LINK_LABEL
        first.trigger()
        assert QGuiApplication.clipboard().text() == "https://example.com"
        on_text = QTextCursor(doc)
        on_text.setPosition(2)
        labels = [a.text() for a in view.context_menu(view.cursorRect(on_text).center()).actions()]
        assert COPY_LINK_LABEL not in labels

    def test_copy_leaves_out_images(
        self, make_panel: Callable[[str], DocumentPanel], write_md: WriteMd, tmp_path: Path
    ) -> None:
        image = QImage(20, 20, QImage.Format.Format_RGB32)
        image.fill(QColor("green"))
        image.save(str(tmp_path / "pic.png"))
        panel = make_panel("Before ![pic](pic.png) after[^n].\n\n[^n]: note")
        panel.view.selectAll()
        assert panel.view.selected_plain_text().strip() == "Before  after[1]."

    def test_opens_at_top_and_is_read_only(self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("\n\n".join(f"Paragraph {n}." for n in range(100)))
        assert panel.view.verticalScrollBar().value() == 0
        assert panel.view.isReadOnly()
        before = panel.view.document().toPlainText()
        panel.view.setFocus()
        qtbot.keyClicks(panel.view, "typed")
        qtbot.keyClick(panel.view, Qt.Key.Key_Backspace)
        assert panel.view.document().toPlainText() == before

    def test_wide_images_refit_when_the_window_narrows(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel], tmp_path: Path
    ) -> None:
        image = QImage(1200, 100, QImage.Format.Format_RGB32)
        image.fill(QColor("red"))
        image.save(str(tmp_path / "wide.png"))
        panel = make_panel("![wide](wide.png)")

        def image_width() -> float:
            doc = panel.view.document()
            return char_format_at(doc, doc.toRawText().index("￼")).toImageFormat().width()

        assert image_width() <= panel.view.text_width()
        panel.resize(400, 400)
        qtbot.waitUntil(lambda: image_width() <= panel.view.text_width() + 0.5, timeout=1000)
        assert image_width() < 1200

    def test_unknown_heading_anchor_does_not_scroll(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("text")
        assert not panel.view.scroll_to_anchor("nowhere")


class TestFindPositions:
    def test_search_starts_at_the_visible_position(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("\n\n".join(f"needle {n}" for n in range(150)))
        bar = panel.view.verticalScrollBar()
        bar.setValue(bar.maximum() // 2)
        panel.finder.open()
        panel.find_bar.field.setText("needle")
        index = panel.finder.current_index
        assert index is not None and 30 < index < 150

    def test_marker_labels_are_not_searchable(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("No digits here.[^n]\n\n[^n]: note 7")
        panel.finder.open()
        panel.find_bar.field.setText("1")
        assert panel.finder.match_count == 0
        panel.find_bar.field.setText("7")
        assert panel.finder.match_count == 0  # footnote text is not searched

    def test_matches_are_recomputed_after_reload(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("one cat")
        panel.finder.open()
        panel.find_bar.field.setText("cat")
        assert panel.finder.match_count == 1
        panel.path.write_text("cat cat cat", encoding="utf-8")
        panel.reload()
        assert panel.finder.match_count == 3
        assert panel.find_bar.count_text == "1 of 3"

    def test_reopening_the_bar_searches_again(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("cat cat")
        panel.finder.open()
        panel.find_bar.field.setText("cat")
        panel.find_bar.close_bar()
        assert panel.finder.match_count == 0
        panel.finder.open()
        assert panel.finder.match_count == 2

    def test_stepping_with_no_matches_does_nothing(self, make_panel: Callable[[str], DocumentPanel]) -> None:
        panel = make_panel("cat")
        panel.finder.open()
        panel.find_bar.field.setText("dog")
        panel.finder.next()
        panel.finder.previous()
        assert panel.finder.current_index is None
        assert panel.find_bar.count_text == "0 of 0"


class TestPopupAndReloadDetails:
    def test_another_marker_replaces_the_popup_content(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]
    ) -> None:
        panel = make_panel(FOOTNOTES)
        first, second = marker_positions(panel)
        click_position(qtbot, panel, first)
        popup = panel.popup
        assert popup is not None
        click_position(qtbot, panel, second)
        assert panel.popup is popup
        assert "First paragraph." in popup.view.document().toPlainText()
        assert "Doll" not in popup.view.document().toPlainText()

    def test_long_footnote_scrolls_inside_a_bounded_popup(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]
    ) -> None:
        long_note = "\n\n    ".join(f"Line {n} of a long note." for n in range(80))
        panel = make_panel(f"Claim.[^long]\n\n[^long]: {long_note}")
        click_position(qtbot, panel, marker_positions(panel)[0])
        popup = panel.popup
        assert popup is not None
        qtbot.waitUntil(popup.isVisible)
        assert popup.height() <= POPUP_MAX_HEIGHT_PX
        assert popup.view.verticalScrollBar().maximum() > 0

    @pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
    def test_failed_automatic_reload_is_quiet_and_keeps_content(
        self, qtbot: QtBot, make_panel: Callable[[str], DocumentPanel]
    ) -> None:
        panel = make_panel("Original.")
        panel.path.write_text("Changed but unreadable.", encoding="utf-8")
        panel.path.chmod(0)
        try:
            qtbot.wait(FILE_SETTLE_WAIT_MS)
            assert "Original." in panel.view.document().toPlainText()
        finally:
            panel.path.chmod(0o644)
