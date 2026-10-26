"""The content of a document window: one rendered file with its find bar, popup, zoom, and reload."""

import logging
from enum import Enum
from pathlib import Path

from PySide6.QtCore import QRect, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

from mdmd.core.cascade import popup_style
from mdmd.core.document import Document
from mdmd.core.parser import parse_markdown
from mdmd.core.style import Style
from mdmd.core.zoom import ZOOM_DEFAULT_PERCENT, zoom_in, zoom_out
from mdmd.logs import get_logger, log_event
from mdmd.storage.markdown_files import FileOpenError, read_markdown_file
from mdmd.ui.document_view import DocumentView
from mdmd.ui.file_watcher import FileWatcher
from mdmd.ui.find_bar import FindBar
from mdmd.ui.find_controller import FindController
from mdmd.ui.fonts import FontResolver
from mdmd.ui.footnote_popup import FootnotePopup
from mdmd.ui.renderer import RenderOptions, render_document

_log = get_logger("document")


class ScrollKeep(Enum):
    """What to preserve when the document is rendered again."""

    TOP = "top"  # start at the top
    OFFSET = "offset"  # same distance from the top (reload: content mostly unchanged)
    FRACTION = "fraction"  # same relative position (style or zoom changed every height)


class DocumentPanel(QWidget):
    def __init__(self, path: Path, text: str, style: Style, fonts: FontResolver, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._path = path
        self._style = style
        self._fonts = fonts
        self._zoom = ZOOM_DEFAULT_PERCENT
        self._document = parse_markdown(text)
        self._view = DocumentView(self)
        self._view.note_activated.connect(self._show_note)
        self._find_bar = FindBar(self)
        self._find = FindController(self._view, self._find_bar)
        self._popup: FootnotePopup | None = None
        self._watcher = FileWatcher(path, self)
        self._watcher.changed.connect(self._reload_after_change)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._view, 1)
        layout.addWidget(self._find_bar)
        self._render()
        log_event(_log, "document_shown", blocks=len(self._document.blocks), notes=len(self._document.notes))

    @property
    def path(self) -> Path:
        return self._path

    @property
    def view(self) -> DocumentView:
        return self._view

    @property
    def find_bar(self) -> FindBar:
        return self._find_bar

    @property
    def finder(self) -> FindController:
        return self._find

    @property
    def zoom_percent(self) -> int:
        return self._zoom

    # -------------------------------------------------------------- content

    def reload(self) -> None:
        """Re-read the file, keeping the scroll position. Raises FileOpenError and keeps the content on failure."""
        text = read_markdown_file(self._path)
        self._document = parse_markdown(text)
        self._watcher.accept_current()
        self._render(ScrollKeep.OFFSET)
        log_event(_log, "document_reloaded", blocks=len(self._document.blocks))

    def _reload_after_change(self) -> None:
        try:
            self.reload()
        except FileOpenError as error:
            # Automatic reloads stay quiet; an explicit Reload reports the problem.
            log_event(_log, "auto_reload_failed", level=logging.WARNING, reason=error.failure.name)

    def set_style(self, style: Style) -> None:
        self._style = style
        self._render(ScrollKeep.FRACTION)

    def zoom_in(self) -> None:
        self._set_zoom(zoom_in(self._zoom))

    def zoom_out(self) -> None:
        self._set_zoom(zoom_out(self._zoom))

    def reset_zoom(self) -> None:
        self._set_zoom(ZOOM_DEFAULT_PERCENT)

    def _set_zoom(self, percent: int) -> None:
        if percent != self._zoom:
            self._zoom = percent
            self._render(ScrollKeep.FRACTION)

    def _options(self, popup: bool = False) -> RenderOptions:
        return RenderOptions(zoom_percent=self._zoom, base_dir=self._path.parent, popup=popup)

    def _render(self, keep: ScrollKeep = ScrollKeep.TOP) -> None:
        bar = self._view.verticalScrollBar()
        offset = bar.value()
        fraction = offset / bar.maximum() if bar.maximum() > 0 else 0.0
        rendered = render_document(self._document, self._style, self._fonts, self._options())
        self._view.show_rendered(rendered, self._style.text("page", "background"), self._style.text("body", "color"))

        def restore() -> None:
            if keep is ScrollKeep.OFFSET:
                bar.setValue(min(offset, bar.maximum()))
            elif keep is ScrollKeep.FRACTION:
                bar.setValue(round(fraction * bar.maximum()))
            else:
                bar.setValue(0)

        restore()
        # The layout may finish after this call returns; restore again once it has.
        QTimer.singleShot(0, self, restore)  # tied to self: cancelled if the panel is deleted first
        self._find.refresh()

    # -------------------------------------------------------------- footnotes

    def _show_note(self, note_id: str, marker: QRect) -> None:
        blocks = self._document.notes.get(note_id)
        if blocks is None:
            return
        style = popup_style(self._style)
        note = Document(blocks=blocks, notes=self._document.notes)
        rendered = render_document(note, style, self._fonts, self._options(popup=True))
        if self._popup is None:
            self._popup = FootnotePopup(self)
        self._popup.show_note(rendered, style.text("page", "background"), style.text("body", "color"), marker)

    @property
    def popup(self) -> FootnotePopup | None:
        return self._popup
