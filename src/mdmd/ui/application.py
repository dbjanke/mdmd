"""The application: owns the settings, themes, and windows, and decides where a file opens."""

from __future__ import annotations

import logging
import os
from dataclasses import replace
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal

from mdmd.core.app_settings import clamp_window_size
from mdmd.core.recent import add_recent, remove_recent
from mdmd.core.settings_draft import SettingsDraft
from mdmd.core.style import Style
from mdmd.core.themes import Theme, ThemeLibrary, same_name
from mdmd.logs import get_logger, log_event
from mdmd.storage.markdown_files import FileOpenError, OpenFailure, read_markdown_file
from mdmd.storage.settings_store import SettingsStore
from mdmd.storage.theme_store import ThemeStore
from mdmd.ui.fonts import FontResolver
from mdmd.ui.main_window import MainWindow
from mdmd.ui.prompts import Prompts
from mdmd.ui.settings_dialog import SettingsDialog

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
        self._settings_store = settings_store
        self._theme_store = theme_store
        self._prompts = prompts
        self._fonts = fonts
        self._settings = settings_store.load()
        self._themes = theme_store.load_all()
        self._windows: list[MainWindow] = []
        self._settings_dialog: SettingsDialog | None = None
        log_event(_log, "started", themes=len(self._themes.user_themes), recent=len(self._settings.recent_files))

    # -------------------------------------------------------------- what windows and the dialog read

    @property
    def style(self) -> Style:
        return self._settings.style

    @property
    def active_theme(self) -> str | None:
        return self._settings.active_theme

    @property
    def themes(self) -> ThemeLibrary:
        return self._themes

    @property
    def fonts(self) -> FontResolver:
        return self._fonts

    @property
    def prompts(self) -> Prompts:
        return self._prompts

    @property
    def window_size(self) -> tuple[int, int]:
        return self._settings.window_size

    @property
    def windows(self) -> tuple[MainWindow, ...]:
        return tuple(self._windows)

    @property
    def settings_dialog(self) -> SettingsDialog | None:
        return self._settings_dialog

    def recent_files(self) -> tuple[str, ...]:
        return self._settings.recent_files

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

    def handle_open_request(self, paths: list[str]) -> None:
        """A second launch asked this instance to open `paths` (or a launcher, when empty)."""
        log_event(_log, "open_request_received", count=len(paths))
        if paths:
            self.start([Path(p) for p in paths])
        else:
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
        recent = self._settings.recent_files
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
            self._update_recent(add_recent(self._settings.recent_files, str(existing.document_path)))
            return None
        try:
            text = read_markdown_file(absolute)
        except FileOpenError as error:
            log_event(_log, "open_failed", level=logging.WARNING, reason=error.failure.name)
            if error.failure in _FORGET_ON:
                self._update_recent(remove_recent(self._settings.recent_files, str(absolute)))
            return str(error)
        window = requester if requester is not None and requester.is_launcher else self._new_window()
        window.show_document(absolute, text)
        _bring_to_front(window)
        self._update_recent(add_recent(self._settings.recent_files, str(absolute)))
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

    def _update_recent(self, recent: tuple[str, ...]) -> None:
        if recent == self._settings.recent_files:
            return
        self._settings = replace(self._settings, recent_files=recent)
        self._save_quietly()
        for window in self._windows:
            window.refresh_recent_files()

    def _save_quietly(self) -> None:
        """Save settings that are not part of an explicit Apply; failures are logged, not shown."""
        try:
            self._settings_store.save(self._settings)
        except OSError as error:
            log_event(_log, "settings_save_failed", level=logging.WARNING, error=type(error).__name__)

    # -------------------------------------------------------------- settings and themes

    def show_settings(self, requester: MainWindow) -> None:
        if self._settings_dialog is None:
            dialog = SettingsDialog(self)
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            dialog.finished.connect(self._settings_dialog_finished)
            self._settings_dialog = dialog
        _bring_to_front(self._settings_dialog)

    def _settings_dialog_finished(self) -> None:
        if self._settings_dialog is not None:
            self._settings_dialog.deleteLater()
        self._settings_dialog = None

    def apply_settings(self, draft: SettingsDraft) -> None:
        updated = replace(self._settings, style=draft.style, active_theme=draft.active_theme)
        self._settings_store.save(updated)  # raises OSError; nothing has changed yet
        self._settings = updated
        for window in self._windows:
            window.apply_style(draft.style)
        log_event(_log, "settings_applied", windows=len(self._windows))

    def save_theme(self, theme: Theme) -> None:
        self._theme_store.save(theme)
        self._themes = self._themes.with_theme(theme)
        log_event(_log, "theme_saved", themes=len(self._themes.user_themes))

    def delete_theme(self, name: str) -> None:
        self._theme_store.delete(name)
        self._themes = self._themes.without(name)
        active = self._settings.active_theme
        if active is not None and same_name(active, name):
            self._settings = replace(self._settings, active_theme=None)
            self._save_quietly()
        log_event(_log, "theme_deleted", themes=len(self._themes.user_themes))

    # -------------------------------------------------------------- window lifecycle

    def show_about(self, requester: MainWindow) -> None:
        self._prompts.about(requester, "About mdmd", f"mdmd {app_version()}\n\nA read-only Markdown viewer.")

    def window_closed(self, window: MainWindow) -> None:
        if window not in self._windows:
            return
        self._windows.remove(window)
        size = window.size()
        self._settings = replace(self._settings, window_size=clamp_window_size(size.width(), size.height()))
        self._save_quietly()
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
