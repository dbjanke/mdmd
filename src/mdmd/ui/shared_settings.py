"""Settings and themes shared by every running mdmd process.

Each launch is its own process; all of them use one settings file and one themes
folder. Changes are saved as a locked read-merge-write, and both locations are
watched, so whatever one process saves reaches the others.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

from mdmd.core.app_settings import AppSettings
from mdmd.core.settings_changes import SettingsChange, theme_deleted
from mdmd.core.themes import Theme, ThemeLibrary
from mdmd.logs import get_logger, log_event
from mdmd.storage.settings_store import SettingsStore
from mdmd.storage.theme_store import ThemeStore
from mdmd.ui.file_watcher import FileWatcher

_log = get_logger("shared_settings")


class SharedSettings(QObject):
    settings_changed = Signal(object, object)  # previous AppSettings, current AppSettings
    themes_changed = Signal()

    def __init__(self, settings_store: SettingsStore, theme_store: ThemeStore, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings_store = settings_store
        self._theme_store = theme_store
        self._settings = settings_store.load()
        self._themes = theme_store.load_all()
        self._ensure_folders()
        self._settings_watcher = FileWatcher(settings_store.path, self)
        self._settings_watcher.changed.connect(lambda: self._adopt(self._settings_store.load()))
        self._themes_watcher = FileWatcher(theme_store.directory, self)
        self._themes_watcher.changed.connect(self._reload_themes)

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def themes(self) -> ThemeLibrary:
        return self._themes

    # -------------------------------------------------------------- settings

    def change(self, change: SettingsChange) -> None:
        """Save `change`. Raises OSError if it cannot be saved; nothing changes then."""
        self._adopt(self._settings_store.update(change))

    def change_quietly(self, change: SettingsChange) -> None:
        """Save a change the user did not ask for explicitly (a recent file, a window size).

        If saving fails, the failure is logged and the change is kept for this session only.
        """
        try:
            updated = self._settings_store.update(change)
        except OSError as error:
            log_event(_log, "settings_save_failed", level=logging.WARNING, error=type(error).__name__)
            updated = change(self._settings)
        self._adopt(updated)

    def _adopt(self, settings: AppSettings) -> None:
        previous = self._settings
        self._settings = settings
        if settings != previous:
            self.settings_changed.emit(previous, settings)

    # -------------------------------------------------------------- themes

    def save_theme(self, theme: Theme) -> None:
        """Raises OSError if the theme cannot be saved."""
        self._theme_store.save(theme)
        self._themes = self._themes.with_theme(theme)
        self.themes_changed.emit()

    def delete_theme(self, name: str) -> None:
        """Raises OSError if the theme cannot be deleted."""
        self._theme_store.delete(name)
        self._themes = self._themes.without(name)
        self.themes_changed.emit()
        self.change_quietly(theme_deleted(name))

    def _reload_themes(self) -> None:
        self._themes = self._theme_store.load_all()
        self.themes_changed.emit()

    def _ensure_folders(self) -> None:
        """A watch needs an existing folder to attach to."""
        for folder in (self._settings_store.path.parent, self._theme_store.directory):
            try:
                folder.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                log_event(_log, "config_dir_unavailable", level=logging.WARNING, error=type(error).__name__)
