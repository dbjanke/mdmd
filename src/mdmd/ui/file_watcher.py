"""Noticing when the displayed file changes on disk.

Editors often save by writing a new file and renaming it over the old one, which
drops a plain file watch. So the folder is watched too, and every signal is
debounced and checked against the file's size and modification time.
"""

from pathlib import Path

from PySide6.QtCore import QFileSystemWatcher, QObject, QTimer, Signal

SETTLE_DELAY_MS = 250

type Snapshot = tuple[int, int] | None  # (mtime_ns, size), None when the file is missing


def snapshot(path: Path) -> Snapshot:
    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_mtime_ns, stat.st_size)


class FileWatcher(QObject):
    changed = Signal()  # the file exists and differs from the last accepted version

    def __init__(self, path: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._path = path
        self._last = snapshot(path)
        self._watcher = QFileSystemWatcher(self)
        self._watcher.fileChanged.connect(self._schedule)
        self._watcher.directoryChanged.connect(self._schedule)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(SETTLE_DELAY_MS)
        self._timer.timeout.connect(self._check)
        self._rewatch()

    def accept_current(self) -> None:
        """Record the file as it is now, after it has been (re)loaded."""
        self._last = snapshot(self._path)

    def _rewatch(self) -> None:
        watched = set(self._watcher.files()) | set(self._watcher.directories())
        for target in (self._path, self._path.parent):
            if str(target) not in watched and target.exists():
                self._watcher.addPath(str(target))

    def _schedule(self, _changed_path: str) -> None:
        self._timer.start()

    def _check(self) -> None:
        self._rewatch()
        current = snapshot(self._path)
        if current is not None and current != self._last:
            self.changed.emit()
