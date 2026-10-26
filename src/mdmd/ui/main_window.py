"""A top-level window: the launcher until a file is opened in it, then a document window."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMenu

from mdmd.core.style import Style
from mdmd.storage.markdown_files import FileOpenError
from mdmd.ui.document_panel import DocumentPanel
from mdmd.ui.fonts import FontResolver
from mdmd.ui.launcher_panel import LauncherPanel
from mdmd.ui.prompts import Prompts

APP_TITLE = "mdmd"
NO_RECENT_TEXT = "No Recent Files"


class WindowHost(Protocol):
    """What a window needs from the application."""

    @property
    def style(self) -> Style: ...

    @property
    def fonts(self) -> FontResolver: ...

    @property
    def window_size(self) -> tuple[int, int]: ...

    @property
    def prompts(self) -> Prompts: ...

    def recent_files(self) -> tuple[str, ...]: ...

    def open_path(self, path: Path, requester: MainWindow) -> None: ...

    def choose_and_open(self, requester: MainWindow) -> None: ...

    def show_settings(self, requester: MainWindow) -> None: ...

    def show_about(self, requester: MainWindow) -> None: ...

    def window_closed(self, window: MainWindow) -> None: ...

    def quit(self) -> None: ...


class MainWindow(QMainWindow):
    def __init__(self, host: WindowHost) -> None:
        super().__init__()
        self._host = host
        self._document: DocumentPanel | None = None
        self._launcher: LauncherPanel | None = LauncherPanel(self)
        self._launcher.open_requested.connect(lambda path: host.open_path(Path(path), self))
        self._launcher.choose_file_requested.connect(lambda: host.choose_and_open(self))
        self._launcher.set_recent_files(host.recent_files())
        self.setCentralWidget(self._launcher)
        self.setWindowTitle(APP_TITLE)
        self._document_actions: list[QAction] = []
        self._build_menus()
        self._update_actions()
        self.resize(*host.window_size)

    # -------------------------------------------------------------- state

    @property
    def is_launcher(self) -> bool:
        return self._document is None

    @property
    def document(self) -> DocumentPanel | None:
        return self._document

    @property
    def document_path(self) -> Path | None:
        return self._document.path if self._document is not None else None

    @property
    def launcher(self) -> LauncherPanel | None:
        return self._launcher

    def show_document(self, path: Path, text: str) -> None:
        """Replace the current content (launcher or document) with `path` rendered."""
        self._document = DocumentPanel(path, text, self._host.style, self._host.fonts, self)
        self._launcher = None
        self.setCentralWidget(self._document)  # deletes the previous central widget
        self.setWindowTitle(path.name)
        self._update_actions()
        self._document.view.setFocus()

    def apply_style(self, style: Style) -> None:
        if self._document is not None:
            self._document.set_style(style)

    def refresh_recent_files(self) -> None:
        if self._launcher is not None:
            self._launcher.set_recent_files(self._host.recent_files())

    def closeEvent(self, event: QCloseEvent) -> None:
        self._host.window_closed(self)
        super().closeEvent(event)

    # -------------------------------------------------------------- menus

    def _action(self, menu: QMenu, text: str, handler: Callable[[], object], *shortcuts: str) -> QAction:
        action = QAction(text, self)
        action.setShortcuts([QKeySequence(s) for s in shortcuts])
        action.triggered.connect(handler)
        menu.addAction(action)
        return action

    def _document_action(
        self, menu: QMenu, text: str, handler: Callable[[DocumentPanel], object], *shortcuts: str
    ) -> QAction:
        """An action that needs a document; it is disabled in the launcher."""

        def run() -> None:
            if self._document is not None:
                handler(self._document)

        action = self._action(menu, text, run, *shortcuts)
        self._document_actions.append(action)
        return action

    def _build_menus(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")
        self._action(file_menu, "&Open…", lambda: self._host.choose_and_open(self), "Ctrl+O")
        self._recent_menu = file_menu.addMenu("Open &Recent")
        self._recent_menu.aboutToShow.connect(self._fill_recent_menu)
        self._document_action(file_menu, "Re&load", lambda _d: self._reload(), "F5")
        file_menu.addSeparator()
        self._action(file_menu, "&Close Window", self.close, "Ctrl+W")
        self._action(file_menu, "&Quit", self._host.quit, "Ctrl+Q")

        edit_menu = bar.addMenu("&Edit")
        self._document_action(edit_menu, "&Copy", lambda d: d.view.copy(), "Ctrl+C")
        self._document_action(edit_menu, "Select &All", lambda d: d.view.selectAll(), "Ctrl+A")
        edit_menu.addSeparator()
        self._document_action(edit_menu, "&Find…", lambda d: d.finder.open(), "Ctrl+F")
        self._document_action(edit_menu, "Find &Next", lambda d: d.finder.next(), "F3")
        self._document_action(edit_menu, "Find &Previous", lambda d: d.finder.previous(), "Shift+F3")
        edit_menu.addSeparator()
        self._action(edit_menu, "&Settings…", lambda: self._host.show_settings(self), "Ctrl+,")

        view_menu = bar.addMenu("&View")
        self._document_action(view_menu, "Zoom &In", lambda d: d.zoom_in(), "Ctrl++", "Ctrl+=")
        self._document_action(view_menu, "Zoom &Out", lambda d: d.zoom_out(), "Ctrl+-")
        self._document_action(view_menu, "&Reset Zoom", lambda d: d.reset_zoom(), "Ctrl+0")

        help_menu = bar.addMenu("&Help")
        self._action(help_menu, "&About mdmd", lambda: self._host.show_about(self))

    def _update_actions(self) -> None:
        for action in self._document_actions:
            action.setEnabled(self._document is not None)

    def _fill_recent_menu(self) -> None:
        self._recent_menu.clear()
        recent = self._host.recent_files()
        if not recent:
            placeholder = self._recent_menu.addAction(NO_RECENT_TEXT)
            placeholder.setEnabled(False)
            return
        for path_text in recent:
            action = self._recent_menu.addAction(Path(path_text).name)
            action.setToolTip(path_text)
            action.setStatusTip(path_text)
            action.triggered.connect(lambda _checked=False, p=path_text: self._host.open_path(Path(p), self))

    def _reload(self) -> None:
        if self._document is None:
            return
        try:
            self._document.reload()
        except FileOpenError as error:
            self._host.prompts.error(self, "Cannot reload file", str(error))
