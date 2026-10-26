"""The content of the launcher window: recent files and an Open File button."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

NO_RECENT_FILES_TEXT = "No recent files"
MISSING_SUFFIX = " (missing)"
MISSING_COLOR = "#8a8a8a"
_PATH_ROLE = Qt.ItemDataRole.UserRole


class LauncherPanel(QWidget):
    open_requested = Signal(str)  # an absolute path from the recent list
    choose_file_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        heading = QLabel("Recent files", self)
        font = heading.font()
        font.setBold(True)
        heading.setFont(font)

        self._list = QListWidget(self)
        self._list.setAlternatingRowColors(True)
        self._list.itemActivated.connect(lambda item: self.open_requested.emit(item.data(_PATH_ROLE)))
        self._empty = QLabel(NO_RECENT_FILES_TEXT, self)
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._list)
        self._stack.addWidget(self._empty)

        self._open_button = QPushButton("Open File…", self)
        self._open_button.clicked.connect(self.choose_file_requested)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self._stack, 1)
        layout.addWidget(self._open_button, 0, Qt.AlignmentFlag.AlignLeft)

    @property
    def recent_list(self) -> QListWidget:
        return self._list

    @property
    def showing_empty_message(self) -> bool:
        return self._stack.currentWidget() is self._empty

    def set_recent_files(self, paths: tuple[str, ...]) -> None:
        self._list.clear()
        for path_text in paths:
            path = Path(path_text)
            missing = not path.exists()
            item = QListWidgetItem(f"{path.name}{MISSING_SUFFIX if missing else ''}\n{path.parent}")
            item.setData(_PATH_ROLE, path_text)
            item.setToolTip(path_text)
            if missing:
                item.setForeground(QColor(MISSING_COLOR))
                font = QFont(item.font())
                font.setItalic(True)
                item.setFont(font)
            self._list.addItem(item)
        self._stack.setCurrentWidget(self._list if paths else self._empty)
        if paths:
            self._list.setCurrentRow(0)
            self._list.setFocus()
