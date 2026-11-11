"""The command-line entry point and the window menus."""

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from mdmd import __main__ as entry
from mdmd.ui.application import Application
from mdmd.ui.main_window import NO_RECENT_TEXT, MainWindow
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
        document_items = (
            "Reload",
            "Copy File Path",
            "Copy",
            "Select All",
            "Find…",
            "Find Next",
            "Zoom In",
            "Reset Zoom",
        )
        for name in document_items:
            assert not actions[name].isEnabled(), name  # type: ignore[attr-defined]
        for name in ("Open…", "Settings…", "Quit", "About mdmd"):
            assert actions[name].isEnabled(), name  # type: ignore[attr-defined]
        app.open_path(write_md("a.md", "a"), launcher)
        for name in document_items:
            assert actions[name].isEnabled(), name  # type: ignore[attr-defined]

    def test_show_soft_line_breaks_is_an_unchecked_toggle_also_in_the_launcher(self, make_app: MakeApp) -> None:
        launcher = make_app().open_launcher()
        action = launcher.soft_line_breaks_action
        assert action is actions_by_text(launcher)["Show Soft Line Breaks"]
        assert action.isCheckable()
        assert not action.isChecked()
        assert action.isEnabled()
        assert action.shortcuts() == []

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


def copy_file_path(window: MainWindow) -> str:
    """Trigger File > Copy File Path and return what landed on the clipboard."""
    clipboard = QGuiApplication.clipboard()
    clipboard.setText("stale")  # the clipboard outlives each test
    actions_by_text(window)["Copy File Path"].trigger()  # type: ignore[attr-defined]
    return clipboard.text()


class TestCopyFilePath:
    def test_sits_after_reload_with_no_shortcut(self, make_app: MakeApp) -> None:
        window = make_app().open_launcher()
        file_menu = window.menuBar().actions()[0].menu()
        names = [a.text().replace("&", "") for a in file_menu.actions() if not a.isSeparator()]  # type: ignore[union-attr]
        assert names == ["Open…", "Open Recent", "Reload", "Copy File Path", "Close Window", "Quit"]
        assert actions_by_text(window)["Copy File Path"].shortcuts() == []  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "typed",
        ["a b.md", "./a b.md", "sub/../a b.md", "sub//../a b.md"],
        ids=["relative", "dot", "dotdot", "double-slash"],
    )
    def test_copies_the_absolute_path_recent_files_records(
        self, make_app: MakeApp, write_md: WriteMd, monkeypatch: pytest.MonkeyPatch, typed: str
    ) -> None:
        path = write_md("a b.md", "a")
        (path.parent / "sub").mkdir()
        monkeypatch.chdir(path.parent)
        app = make_app()
        app.start([Path(typed)])
        assert copy_file_path(app.windows[0]) == app.recent_files()[0] == str(path)

    def test_keeps_a_symlink_as_given(self, make_app: MakeApp, write_md: WriteMd) -> None:
        target = write_md("real.md", "x")
        link = target.with_name("alias.md")
        link.symlink_to(target)
        app = make_app()
        app.start([link])
        assert copy_file_path(app.windows[0]) == str(link)

    @pytest.mark.parametrize(
        "name",
        ["a&b.md", "<b>bold</b>.md", "ü 名 🙂.md", "line\nbreak.md", "  spaced  .md"],
        ids=["ampersand", "html", "unicode", "newline", "spaces"],
    )
    def test_copies_unusual_names_literally(self, make_app: MakeApp, write_md: WriteMd, name: str) -> None:
        path = write_md(name, "x")
        app = make_app()
        app.start([path])
        assert copy_file_path(app.windows[0]) == str(path)

    def test_each_window_copies_its_own_path(self, make_app: MakeApp, write_md: WriteMd) -> None:
        first, second = write_md("first.md", "1"), write_md("second.md", "2")
        app = make_app()
        app.start([first, second])
        assert [copy_file_path(window) for window in app.windows] == [str(first), str(second)]

    def test_works_in_a_launcher_that_opened_a_file(self, make_app: MakeApp, write_md: WriteMd) -> None:
        path = write_md("a.md", "a")
        app = make_app()
        launcher = app.open_launcher()
        app.open_path(path, launcher)
        assert copy_file_path(launcher) == str(path)

    @pytest.mark.parametrize("gone", ["deleted", "moved"])
    def test_copies_the_opened_path_after_the_file_is_gone(
        self, make_app: MakeApp, write_md: WriteMd, gone: str
    ) -> None:
        path = write_md("a.md", "a")
        app = make_app()
        app.start([path])
        if gone == "deleted":
            path.unlink()
        else:
            path.rename(path.with_name("b.md"))
        assert copy_file_path(app.windows[0]) == str(path)


class TestFullStart:
    def test_each_launch_opens_its_files_in_its_own_application(
        self, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        (tmp_path / "notes.md").write_text("# Notes")
        (tmp_path / "other.md").write_text("# Other")
        apps: list[Application] = []
        real_application = entry.Application

        def recording_application(*args: object) -> Application:
            app = real_application(*args)  # type: ignore[arg-type]
            apps.append(app)
            return app

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
        monkeypatch.setattr(entry, "Application", recording_application)
        monkeypatch.setattr(QApplication, "exec", lambda _self: 0)
        monkeypatch.chdir(tmp_path)
        assert entry.main(["notes.md", "sub/../other.md"]) == 0
        (app,) = apps
        assert [w.document_path for w in app.windows] == [tmp_path / "notes.md", tmp_path / "other.md"]
        app.quit()
