"""The application: keeps track of the windows and decides where a file opens.

Settings and themes come from `SharedSettings`, which keeps them in step with other
mdmd processes; this class only reacts to their changes.
"""

from __future__ import annotations

import logging
import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal

from mdmd.core.app_settings import AppSettings
from mdmd.core.settings_changes import appearance_applied, recent_file_forgotten, recent_file_opened, window_resized
from mdmd.core.settings_draft import SettingsDraft
from mdmd.core.style import Style
from mdmd.core.themes import Theme, ThemeLibrary
from mdmd.logs import get_logger, log_event
from mdmd.storage.markdown_files import FileOpenError, OpenFailure, load_document
from mdmd.storage.settings_store import SettingsStore
from mdmd.storage.theme_store import ThemeStore
from mdmd.ui.fonts import FontResolver
from mdmd.ui.main_window import MainWindow
from mdmd.ui.prompts import Prompts
from mdmd.ui.settings_dialog import SettingsDialog
from mdmd.ui.shared_settings import SharedSettings

_log = get_logger("app")
_FORGET_ON = (OpenFailure.NOT_FOUND, OpenFailure.IS_DIRECTORY)


def app_version() -> str:
    try:
        return version("mdmd")
    except PackageNotFoundError:
        return "unknown"


class Application(QObject):
    last_window_closed = Signal()

    def __init__(
        self, settings_store: SettingsStore, theme_store: ThemeStore, prompts: Prompts, fonts: FontResolver
    ) -> None:
        super().__init__()
        self._shared = SharedSettings(settings_store, theme_store, self)
        self._shared.settings_changed.connect(self._settings_changed)
        self._prompts = prompts
        self._fonts = fonts
        self._windows: list[MainWindow] = []
        self._settings_dialog: SettingsDialog | None = None
        log_event(_log, "started", themes=len(self.themes.user_themes), recent=len(self.recent_files()))

    # -------------------------------------------------------------- what windows and the dialog read

    @property
    def style(self) -> Style:
        return self._shared.settings.style

    @property
    def active_theme(self) -> str | None:
        return self._shared.settings.active_theme

    @property
    def themes(self) -> ThemeLibrary:
        return self._shared.themes

    @property
    def fonts(self) -> FontResolver:
        return self._fonts

    @property
    def prompts(self) -> Prompts:
        return self._prompts

    @property
    def window_size(self) -> tuple[int, int]:
        return self._shared.settings.window_size

    @property
    def windows(self) -> tuple[MainWindow, ...]:
        return tuple(self._windows)

    @property
    def settings_dialog(self) -> SettingsDialog | None:
        return self._settings_dialog

    def recent_files(self) -> tuple[str, ...]:
        return self._shared.settings.recent_files

    # -------------------------------------------------------------- opening files

    def start(self, paths: list[Path]) -> None:
        """Open each path in its own window. Failures are reported together; the launcher appears if nothing opened."""
        failures = [message for path in paths if (message := self._open(path, requester=None)) is not None]
        if failures:
            parent = self._windows[0] if self._windows else None
            title = "Cannot open file" if len(failures) == 1 else "Cannot open files"
            self._prompts.error(parent, title, "\n".join(failures))
        if not self._windows:
            self.open_launcher()

    def open_launcher(self) -> MainWindow:
        window = self._new_window()
        _bring_to_front(window)
        return window

    def open_path(self, path: Path, requester: MainWindow) -> None:
        message = self._open(path, requester)
        if message is not None:
            self._prompts.error(requester, "Cannot open file", message)

    def choose_and_open(self, requester: MainWindow) -> None:
        current = requester.document_path
        recent = self.recent_files()
        start_dir = current.parent if current else Path(recent[0]).parent if recent else Path.home()
        chosen = self._prompts.choose_markdown_file(requester, start_dir)
        if chosen is not None:
            self.open_path(chosen, requester)

    def _open(self, path: Path, requester: MainWindow | None) -> str | None:
        """Open `path`, or bring its window to the front. Returns an error message on failure."""
        absolute = Path(os.path.abspath(path))  # noqa: PTH100 - normalize '..' but keep symlinked paths as given
        existing = self._window_showing(absolute)
        if existing is not None:
            _bring_to_front(existing)
            self._shared.change_quietly(recent_file_opened(str(existing.document_path)))
            return None
        try:
            document = load_document(absolute)
        except FileOpenError as error:
            log_event(_log, "open_failed", level=logging.WARNING, reason=error.failure.name)
            if error.failure in _FORGET_ON:
                self._shared.change_quietly(recent_file_forgotten(str(absolute)))
            return str(error)
        window = requester if requester is not None and requester.is_launcher else self._new_window()
        window.show_document(absolute, document)
        _bring_to_front(window)
        self._shared.change_quietly(recent_file_opened(str(absolute)))
        return None

    def _window_showing(self, path: Path) -> MainWindow | None:
        for window in self._windows:
            shown = window.document_path
            if shown is None:
                continue
            try:
                if shown == path or shown.samefile(path):
                    return window
            except OSError:
                continue
        return None

    def _new_window(self) -> MainWindow:
        window = MainWindow(self)
        window.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._windows.append(window)
        return window

    def _settings_changed(self, previous: AppSettings, current: AppSettings) -> None:
        """Bring every window up to date with settings saved here or in another process."""
        if current.style != previous.style:
            for window in self._windows:
                window.apply_style(current.style)
        if current.recent_files != previous.recent_files:
            for window in self._windows:
                window.refresh_recent_files()

    # -------------------------------------------------------------- settings and themes

    def show_settings(self, requester: MainWindow) -> None:
        if self._settings_dialog is None:
            dialog = SettingsDialog(self)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.finished.connect(self._settings_dialog_finished)
            self._shared.themes_changed.connect(dialog.refresh_themes)
            self._settings_dialog = dialog
        _bring_to_front(self._settings_dialog)

    def _settings_dialog_finished(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.deleteLater()
        self._settings_dialog = None

    def apply_settings(self, draft: SettingsDraft) -> None:
        self._shared.change(appearance_applied(draft.style, draft.active_theme))  # raises OSError; nothing changes
        log_event(_log, "settings_applied", windows=len(self._windows))

    def save_theme(self, theme: Theme) -> None:
        self._shared.save_theme(theme)
        log_event(_log, "theme_saved", themes=len(self.themes.user_themes))

    def delete_theme(self, name: str) -> None:
        self._shared.delete_theme(name)
        log_event(_log, "theme_deleted", themes=len(self.themes.user_themes))

    # -------------------------------------------------------------- window lifecycle

    def show_about(self, requester: MainWindow) -> None:
        self._prompts.about(requester, "About mdmd", f"mdmd {app_version()}\n\nA read-only Markdown viewer.")

    def window_closed(self, window: MainWindow) -> None:
        if window not in self._windows:
            return
        self._windows.remove(window)
        self._shared.change_quietly(window_resized(window.size().width(), window.size().height()))
        if not self._windows:
            if self._settings_dialog is not None:
                self._settings_dialog.close()
            self.last_window_closed.emit()

    def quit(self) -> None:
        for window in list(self._windows):
            window.close()


def _bring_to_front(widget: MainWindow | SettingsDialog) -> None:
    widget.show()
    widget.raise_()
    widget.activateWindow()
