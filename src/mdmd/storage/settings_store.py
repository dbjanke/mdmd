"""The settings file: working settings, active theme, window size, and recent files.

Several mdmd processes share this file. Every change goes through `update`, which
re-reads the file under an exclusive lock and applies only that change, so one
process never overwrites what another just saved.
"""

import fcntl
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from mdmd.core.app_settings import AppSettings, app_settings_to_json, parse_app_settings
from mdmd.logs import get_logger, log_event
from mdmd.storage.json_files import read_json, write_json_atomic

SETTINGS_FILE_NAME = "settings.json"
LOCK_FILE_NAME = "settings.lock"
BACKUP_SUFFIX = ".bak"

_log = get_logger("settings_store")


class SettingsStore:
    def __init__(self, directory: Path) -> None:
        self._path = directory / SETTINGS_FILE_NAME
        self._lock_path = directory / LOCK_FILE_NAME
        self._unreadable_file_pending_backup = False

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> AppSettings:
        """Never fails. A file that cannot be parsed gives Default settings and is kept until the next save.

        Each load decides afresh whether the next save backs the file up: another process
        may have replaced a damaged file since, and a good file must never become the backup.
        """
        self._unreadable_file_pending_backup = False
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

    def update(self, change: Callable[[AppSettings], AppSettings]) -> AppSettings:
        """Apply `change` to the settings as currently stored, save, and return the result.

        Raises OSError if the file cannot be written; the stored settings are then unchanged.
        """
        with self._locked():
            updated = change(self.load())
            self._write(updated)
            return updated

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Hold an exclusive lock shared by every mdmd process using this settings folder."""
        self._lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock_path.open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _write(self, settings: AppSettings) -> None:
        """Replace the stored settings; only `update` calls this, while holding the lock."""
        if self._unreadable_file_pending_backup:
            self._path.replace(self._path.with_name(self._path.name + BACKUP_SUFFIX))
            self._unreadable_file_pending_backup = False
            log_event(_log, "settings_backed_up")
        write_json_atomic(self._path, app_settings_to_json(settings))
