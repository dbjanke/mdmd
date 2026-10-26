"""The command-line entry point and the window menus."""

import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from mdmd import __main__ as entry
from mdmd.ui import single_instance
from mdmd.ui.application import Application
from mdmd.ui.main_window import NO_RECENT_TEXT, MainWindow
from mdmd.ui.single_instance import send_to_running_instance
from tests.ui.conftest import FakePrompts

MakeApp = Callable[[], Application]
WriteMd = Callable[[str, str], Path]


def actions_by_text(window: MainWindow) -> dict[str, object]:
    found = {}
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        for action in menu.actions():  # type: ignore[union-attr]
            found[action.text().replace("&", "")] = action
    return found


class TestEntryPoint:
    def test_files_are_handed_to_a_running_instance(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        sent: list[list[str]] = []
        monkeypatch.setattr(entry, "send_to_running_instance", lambda paths: sent.append(paths) or True)
        monkeypatch.chdir(tmp_path)
        assert entry.main(["notes.md", "sub/../other.md"]) == 0
        assert sent == [[str(tmp_path / "notes.md"), str(tmp_path / "other.md")]]

    def test_help_exits_cleanly(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as exit_info:
            entry.main(["--help"])
        assert exit_info.value.code == 0
        assert "Markdown" in capsys.readouterr().out


class TestMenus:
    def test_document_items_are_disabled_in_the_launcher(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        launcher = app.open_launcher()
        actions = actions_by_text(launcher)
        for name in ("Reload", "Copy", "Select All", "Find…", "Find Next", "Zoom In", "Reset Zoom"):
            assert not actions[name].isEnabled(), name  # type: ignore[attr-defined]
        for name in ("Open…", "Settings…", "Quit", "About mdmd"):
            assert actions[name].isEnabled(), name  # type: ignore[attr-defined]
        app.open_path(write_md("a.md", "a"), launcher)
        assert actions["Reload"].isEnabled()  # type: ignore[attr-defined]

    def test_shortcuts(self, make_app: MakeApp) -> None:
        actions = actions_by_text(make_app().open_launcher())
        expected = {
            "Open…": "Ctrl+O",
            "Reload": "F5",
            "Close Window": "Ctrl+W",
            "Quit": "Ctrl+Q",
            "Copy": "Ctrl+C",
            "Select All": "Ctrl+A",
            "Find…": "Ctrl+F",
            "Find Next": "F3",
            "Find Previous": "Shift+F3",
            "Settings…": "Ctrl+,",
            "Zoom In": "Ctrl++",
            "Zoom Out": "Ctrl+-",
            "Reset Zoom": "Ctrl+0",
        }
        for name, shortcut in expected.items():
            assert actions[name].shortcut().toString() == shortcut, name  # type: ignore[attr-defined]

    def test_open_recent_lists_files_and_opens_them(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        window = app.open_launcher()
        recent_menu = window._recent_menu
        recent_menu.aboutToShow.emit()
        assert [a.text() for a in recent_menu.actions()] == [NO_RECENT_TEXT]
        path = write_md("a.md", "a")
        app.start([path])
        recent_menu.aboutToShow.emit()
        (entry_action,) = recent_menu.actions()
        assert entry_action.text() == "a.md"
        entry_action.trigger()
        assert len(app.windows) == 2  # already open: brought to front, not reopened

    def test_reload_failure_is_reported_and_content_kept(
        self, make_app: MakeApp, write_md: WriteMd, prompts: FakePrompts
    ) -> None:
        app = make_app()
        path = write_md("a.md", "Kept text")
        app.start([path])
        window = app.windows[0]
        path.unlink()
        actions_by_text(window)["Reload"].trigger()  # type: ignore[attr-defined]
        assert prompts.errors[-1][0] == "Cannot reload file"
        assert window.document is not None
        assert "Kept text" in window.document.view.document().toPlainText()

    def test_settings_shortcut_opens_the_dialog(self, make_app: MakeApp) -> None:
        app = make_app()
        window = app.open_launcher()
        actions_by_text(window)["Settings…"].trigger()  # type: ignore[attr-defined]
        assert app.settings_dialog is not None and app.settings_dialog.isVisible()


class TestFullStart:
    def test_first_instance_listens_and_opens_files(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        doc = tmp_path / "doc.md"
        doc.write_text("# Hello")
        name = f"mdmd-test-{uuid.uuid4().hex}"
        apps: list[Application] = []
        real_application = entry.Application

        def recording_application(*args: object) -> Application:
            app = real_application(*args)  # type: ignore[arg-type]
            apps.append(app)
            return app

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setattr(single_instance, "socket_path", lambda: name)
        monkeypatch.setattr(entry, "Application", recording_application)
        listening: list[bool] = []

        def run_event_loop(_self: QApplication) -> int:
            listening.append(send_to_running_instance([], name=name))
            return 0

        monkeypatch.setattr(QApplication, "exec", run_event_loop)
        assert entry.main([str(doc)]) == 0
        assert listening == [True]
        (app,) = apps
        assert [w.windowTitle() for w in app.windows] == ["doc.md"]
        app.quit()
