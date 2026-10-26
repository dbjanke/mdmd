"""Questions and messages shown to the user, behind one interface so tests can answer them."""

from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox, QWidget

MARKDOWN_FILE_FILTER = "Markdown files (*.md *.markdown *.mdown);;All files (*)"


class Prompts(Protocol):
    def error(self, parent: QWidget | None, title: str, message: str) -> None: ...

    def confirm(self, parent: QWidget | None, title: str, message: str) -> bool: ...

    def ask_text(self, parent: QWidget | None, title: str, label: str, initial: str) -> str | None: ...

    def choose_markdown_file(self, parent: QWidget | None, start_dir: Path) -> Path | None: ...

    def about(self, parent: QWidget | None, title: str, text: str) -> None: ...


def plain_message_box(parent: QWidget | None, icon: QMessageBox.Icon, title: str, message: str) -> QMessageBox:
    """A message box that shows `message` literally.

    Messages carry file and theme names; QMessageBox would render text that looks like
    HTML as HTML, including clickable links.
    """
    box = QMessageBox(icon, title, message, QMessageBox.StandardButton.NoButton, parent)
    box.setTextFormat(Qt.TextFormat.PlainText)
    return box


class QtPrompts:
    def error(self, parent: QWidget | None, title: str, message: str) -> None:
        box = plain_message_box(parent, QMessageBox.Icon.Warning, title, message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    def confirm(self, parent: QWidget | None, title: str, message: str) -> bool:
        box = plain_message_box(parent, QMessageBox.Icon.Question, title, message)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def ask_text(self, parent: QWidget | None, title: str, label: str, initial: str) -> str | None:
        text, accepted = QInputDialog.getText(parent, title, label, QLineEdit.EchoMode.Normal, initial)
        return text if accepted else None

    def choose_markdown_file(self, parent: QWidget | None, start_dir: Path) -> Path | None:
        name, _filter = QFileDialog.getOpenFileName(parent, "Open File", str(start_dir), MARKDOWN_FILE_FILTER)
        return Path(name) if name else None

    def about(self, parent: QWidget | None, title: str, text: str) -> None:
        box = plain_message_box(parent, QMessageBox.Icon.Information, title, text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()
