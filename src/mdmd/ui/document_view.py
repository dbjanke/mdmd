"""The read-only text view: shows a rendered document, handles marker clicks, links, and copying."""

from PySide6.QtCore import QMimeData, QPoint, QPointF, QRect, Qt, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QColor,
    QContextMenuEvent,
    QGuiApplication,
    QMouseEvent,
    QPalette,
    QResizeEvent,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
)
from PySide6.QtWidgets import QMenu, QTextBrowser, QTextEdit, QWidget

from mdmd.core.search import Match
from mdmd.ui.renderer import RenderedDocument, note_id_from_href
from mdmd.ui.text_objects import LINK_HREF_PROPERTY, NOTE_ID_PROPERTY, marker_label

OBJECT_REPLACEMENT = "￼"
IMAGE_FIT_DELAY_MS = 60
MATCH_COLOR = "#fff08a"
CURRENT_MATCH_COLOR = "#ffb347"
COPY_LINK_LABEL = "Copy Link Address"


def char_format_at(document: QTextDocument, position: int) -> QTextCharFormat:
    """The format of the character that starts at `position`."""
    cursor = QTextCursor(document)
    cursor.setPosition(min(position + 1, document.characterCount() - 1))
    return cursor.charFormat()


class DocumentView(QTextBrowser):
    note_activated = Signal(str, QRect)  # note id, marker rectangle in global coordinates

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.setUndoRedoEnabled(False)
        self.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
            | Qt.TextInteractionFlag.TextSelectableByKeyboard
            | Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self._rendered: RenderedDocument | None = None
        self._last_release = QPoint()
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.setInterval(IMAGE_FIT_DELAY_MS)
        self._fit_timer.timeout.connect(self._fit_images)
        self.anchorClicked.connect(lambda url: self._activate_anchor(url.toString()))

    # -------------------------------------------------------------- content

    def show_rendered(self, rendered: RenderedDocument, background: str, text_color: str) -> None:
        """Display `rendered`, keeping a reference so it outlives its use here."""
        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(background))
        palette.setColor(QPalette.ColorRole.Text, QColor(text_color))
        self.setPalette(palette)
        self.setDocument(rendered.document)
        self._rendered = rendered
        self._fit_images()

    def text_width(self) -> float:
        return float(self.viewport().width()) - 2 * self.document().documentMargin()

    def _fit_images(self) -> None:
        if self._rendered is not None and self._rendered.images:
            self._rendered.fit_images(self.text_width())

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_timer.start()

    # -------------------------------------------------------------- navigation

    def scroll_to_anchor(self, anchor: str) -> bool:
        if self._rendered is None or anchor not in self._rendered.anchors:
            return False
        block = self.document().findBlock(self._rendered.anchors[anchor])
        top = self.document().documentLayout().blockBoundingRect(block).top()
        self.verticalScrollBar().setValue(int(top))
        return True

    def visible_position(self) -> int:
        """The document position at the top-left of the visible area."""
        return self.cursorForPosition(QPoint(0, 0)).position()

    def _activate_anchor(self, href: str) -> None:
        note_id = note_id_from_href(href)
        if note_id is not None:
            rect = self._marker_rect(note_id, self._last_release)
            if rect is not None:
                self.note_activated.emit(note_id, rect)
        elif href.startswith("#"):
            self.scroll_to_anchor(href[1:])

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_release = event.position().toPoint()
        super().mouseReleaseEvent(event)

    def _position_under(self, viewport_point: QPoint) -> int:
        offset = QPointF(self.horizontalScrollBar().value(), self.verticalScrollBar().value())
        return self.document().documentLayout().hitTest(QPointF(viewport_point) + offset, Qt.HitTestAccuracy.ExactHit)

    def _marker_rect(self, note_id: str, viewport_point: QPoint) -> QRect | None:
        """Global rectangle of the marker for `note_id` under `viewport_point`."""
        hit = self._position_under(viewport_point)
        for position in (hit, hit - 1):
            if position >= 0 and char_format_at(self.document(), position).property(NOTE_ID_PROPERTY) == note_id:
                start = QTextCursor(self.document())
                start.setPosition(position)
                end = QTextCursor(self.document())
                end.setPosition(position + 1)
                left, right = self.cursorRect(start), self.cursorRect(end)
                local = QRect(left.left(), left.top(), max(1, right.left() - left.left()), left.height())
                return QRect(self.viewport().mapToGlobal(local.topLeft()), local.size())
        return None

    # -------------------------------------------------------------- links and copying

    def link_href_at(self, viewport_point: QPoint) -> str | None:
        position = self._position_under(viewport_point)
        if position < 0:
            return None
        href = char_format_at(self.document(), position).property(LINK_HREF_PROPERTY)
        return str(href) if href else None

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.context_menu(event.pos())
        menu.exec(event.globalPos())
        menu.deleteLater()

    def context_menu(self, viewport_point: QPoint) -> QMenu:
        """The standard Copy/Select All menu, with Copy Link Address first when over a link."""
        menu = self.createStandardContextMenu(viewport_point)
        href = self.link_href_at(viewport_point)
        if href is not None:
            copy_link = QAction(COPY_LINK_LABEL, menu)
            copy_link.triggered.connect(lambda: QGuiApplication.clipboard().setText(href))
            actions = menu.actions()
            if actions:
                menu.insertAction(actions[0], copy_link)
                menu.insertSeparator(actions[0])
            else:
                menu.addAction(copy_link)
        return menu

    def createMimeDataFromSelection(self) -> QMimeData:
        """Copy plain text only, writing footnote markers as "[n]" and dropping images."""
        mime = QMimeData()
        mime.setText(self.selected_plain_text())
        return mime

    def selected_plain_text(self) -> str:
        cursor = self.textCursor()
        text = cursor.selection().toPlainText()
        raw = self.document().toRawText()
        replacements = []
        for position in range(cursor.selectionStart(), cursor.selectionEnd()):
            if raw[position] == OBJECT_REPLACEMENT:
                label = marker_label(char_format_at(self.document(), position))
                replacements.append(f"[{label}]" if label is not None else "")
        pieces = text.split(OBJECT_REPLACEMENT)
        if len(pieces) != len(replacements) + 1:
            return text.replace(OBJECT_REPLACEMENT, "")
        out = [pieces[0]]
        for replacement, piece in zip(replacements, pieces[1:], strict=True):
            out.extend((replacement, piece))
        return "".join(out)

    # -------------------------------------------------------------- find highlighting

    def raw_text(self) -> str:
        """The document text with one character per document position, for searching."""
        return self.document().toRawText()

    def show_matches(self, matches: tuple[Match, ...], current: int | None) -> None:
        selections = []
        for index, match in enumerate(matches):
            selection = QTextEdit.ExtraSelection()
            cursor = QTextCursor(self.document())
            cursor.setPosition(match.start)
            cursor.setPosition(match.end, QTextCursor.MoveMode.KeepAnchor)
            selection.cursor = cursor
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(CURRENT_MATCH_COLOR if index == current else MATCH_COLOR))
            selection.format = fmt
            selections.append(selection)
        self.setExtraSelections(selections)
        if current is not None:
            match = matches[current]
            cursor = QTextCursor(self.document())
            cursor.setPosition(match.start)
            cursor.setPosition(match.end, QTextCursor.MoveMode.KeepAnchor)
            self.setTextCursor(cursor)
            self.ensureCursorVisible()
