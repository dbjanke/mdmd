from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from mdmd.storage.settings_store import SettingsStore
from mdmd.storage.theme_store import ThemeStore
from mdmd.ui.application import Application
from mdmd.ui.fonts import FontResolver


@dataclass
class FakePrompts:
    """Records every message and answers questions from queues set by the test."""

    errors: list[tuple[str, str]] = field(default_factory=list)
    confirmations: list[str] = field(default_factory=list)
    confirm_answers: list[bool] = field(default_factory=list)
    text_answers: list[str | None] = field(default_factory=list)
    file_answers: list[Path | None] = field(default_factory=list)
    abouts: list[str] = field(default_factory=list)

    def error(self, parent: QWidget | None, title: str, message: str) -> None:
        self.errors.append((title, message))

    def confirm(self, parent: QWidget | None, title: str, message: str) -> bool:
        self.confirmations.append(message)
        return self.confirm_answers.pop(0)

    def ask_text(self, parent: QWidget | None, title: str, label: str, initial: str) -> str | None:
        return self.text_answers.pop(0)

    def choose_markdown_file(self, parent: QWidget | None, start_dir: Path) -> Path | None:
        return self.file_answers.pop(0)

    def about(self, parent: QWidget | None, title: str, text: str) -> None:
        self.abouts.append(text)


@pytest.fixture
def prompts() -> FakePrompts:
    return FakePrompts()


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "config"
    directory.mkdir()
    return directory


@pytest.fixture
def fonts(qapp: QApplication) -> FontResolver:
    return FontResolver()


@pytest.fixture
def make_app(
    qapp: QApplication, config_dir: Path, prompts: FakePrompts, fonts: FontResolver
) -> Iterator[Callable[[], Application]]:
    created: list[Application] = []

    def factory() -> Application:
        app = Application(SettingsStore(config_dir), ThemeStore(config_dir), prompts, fonts)
        created.append(app)
        return app

    yield factory
    for app in created:
        app.quit()
    QApplication.processEvents()


@pytest.fixture
def write_md(tmp_path: Path) -> Callable[[str, str], Path]:
    def write(name: str, text: str) -> Path:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    return write


needs_permissions = pytest.mark.skipif(os.geteuid() == 0, reason="root ignores file permissions")


@contextmanager
def read_only(directory: Path) -> Iterator[None]:
    """Nothing can be created, replaced, or removed in `directory` while this is held."""
    directory.chmod(0o500)
    try:
        yield
    finally:
        directory.chmod(0o700)
