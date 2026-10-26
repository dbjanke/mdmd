"""The settings file: working settings, active theme, window size, and recent files."""

from pathlib import Path

from mdmd.core.app_settings import AppSettings, app_settings_to_json, parse_app_settings
from mdmd.logs import get_logger, log_event
from mdmd.storage.json_files import read_json, write_json_atomic

SETTINGS_FILE_NAME = "settings.json"
BACKUP_SUFFIX = ".bak"

_log = get_logger("settings_store")


class SettingsStore:
    def __init__(self, directory: Path) -> None:
        self._path = directory / SETTINGS_FILE_NAME
        self._unreadable_file_pending_backup = False

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppSettings:
        """Never fails. A file that cannot be parsed gives Default settings and is kept until the next save."""
        if not self._path.exists():
            return AppSettings()
        try:
            raw = read_json(self._path)
            if not isinstance(raw, dict):
                raise ValueError("settings root is not an object")
        except (OSError, ValueError) as error:
            log_event(_log, "settings_unreadable", error=type(error).__name__)
            self._unreadable_file_pending_backup = True
            return AppSettings()
        parsed = parse_app_settings(raw)
        if parsed.rejected:
            log_event(_log, "settings_values_rejected", count=len(parsed.rejected), names=",".join(parsed.rejected))
        return parsed.settings

    def save(self, settings: AppSettings) -> None:
        """Raises OSError if the file cannot be written."""
        if self._unreadable_file_pending_backup:
            self._path.replace(self._path.with_name(self._path.name + BACKUP_SUFFIX))
            self._unreadable_file_pending_backup = False
            log_event(_log, "settings_backed_up")
        write_json_atomic(self._path, app_settings_to_json(settings))
