"""Connects the find bar to a document view: searching, stepping, and highlighting."""

from PySide6.QtCore import QObject

from mdmd.core.search import Match, count_label, find_matches, first_at_or_after, step
from mdmd.ui.document_view import DocumentView
from mdmd.ui.find_bar import FindBar


class FindController(QObject):
    def __init__(self, view: DocumentView, bar: FindBar) -> None:
        super().__init__(bar)
        self._view = view
        self._bar = bar
        self._matches: tuple[Match, ...] = ()
        self._index: int | None = None
        bar.search_changed.connect(self.search_from_view)
        bar.next_requested.connect(self.next)
        bar.previous_requested.connect(self.previous)
        bar.closed.connect(self.clear)

    @property
    def match_count(self) -> int:
        return len(self._matches)

    @property
    def current_index(self) -> int | None:
        return self._index

    def open(self) -> None:
        self._bar.open_bar()
        if self._bar.term:
            self.search_from_view()

    def search_from_view(self) -> None:
        """Search again, starting from the top of the visible area."""
        self._matches = find_matches(self._view.raw_text(), self._bar.term, self._bar.match_case)
        self._index = first_at_or_after(self._matches, self._view.visible_position())
        self._show()

    def next(self) -> None:
        self._step(forward=True)

    def previous(self) -> None:
        self._step(forward=False)

    def _step(self, forward: bool) -> None:
        if not self._bar.isVisible() or not self._bar.term:
            self.open()
            return
        if self._index is None or not self._matches:
            return
        self._index = step(self._index, len(self._matches), forward)
        self._show()

    def refresh(self) -> None:
        """Re-run the search after the document was re-rendered (positions may have moved)."""
        if self._bar.isVisible() and self._bar.term:
            self.search_from_view()

    def clear(self) -> None:
        self._matches = ()
        self._index = None
        self._view.show_matches((), None)

    def _show(self) -> None:
        self._view.show_matches(self._matches, self._index)
        failed = bool(self._bar.term) and not self._matches
        self._bar.show_result(count_label(self._index, len(self._matches)), failed)
