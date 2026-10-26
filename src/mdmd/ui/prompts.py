"""Questions and messages shown to the user, behind one interface so tests can answer them."""

from pathlib import Path
from typing import Protocol

from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox, QWidget

MARKDOWN_FILE_FILTER = "Markdown files (*.md *.markdown *.mdown);;All files (*)"


class Prompts(Protocol):
    def error(self, parent: QWidget | None, title: str, message: str) -> None: ...

    def confirm(self, parent: QWidget | None, title: str, message: str) -> bool: ...

    def ask_text(self, parent: QWidget | None, title: str, label: str, initial: str) -> str | None: ...

    def choose_markdown_file(self, parent: QWidget | None, start_dir: Path) -> Path | None: ...

    def about(self, parent: QWidget | None, title: str, text: str) -> None: ...


class QtPrompts:
    def error(self, parent: QWidget | None, title: str, message: str) -> None:
        QMessageBox.warning(parent, title, message)

    def confirm(self, parent: QWidget | None, title: str, message: str) -> bool:
        answer = QMessageBox.question(parent, title, message)
        return answer == QMessageBox.StandardButton.Yes

    def ask_text(self, parent: QWidget | None, title: str, label: str, initial: str) -> str | None:
        text, accepted = QInputDialog.getText(parent, title, label, QLineEdit.EchoMode.Normal, initial)
        return text if accepted else None

    def choose_markdown_file(self, parent: QWidget | None, start_dir: Path) -> Path | None:
        name, _filter = QFileDialog.getOpenFileName(parent, "Open File", str(start_dir), MARKDOWN_FILE_FILTER)
        return Path(name) if name else None

    def about(self, parent: QWidget | None, title: str, text: str) -> None:
        QMessageBox.about(parent, title, text)
