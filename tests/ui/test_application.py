"""Startup, opening files, recent files, window size, and applying settings."""

import json
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.parser import DocumentParseError
from mdmd.core.recent import MAX_RECENT_FILES
from mdmd.core.settings_draft import SettingsDraft
from mdmd.core.themes import Theme
from mdmd.storage import markdown_files
from mdmd.ui.application import Application
from tests.ui.conftest import FakePrompts, needs_permissions, read_only

MakeApp = Callable[[], Application]
WriteMd = Callable[[str, str], Path]


def stored(config_dir: Path) -> dict[str, object]:
    data = json.loads((config_dir / "settings.json").read_text())
    assert isinstance(data, dict)
    return data


class TestStartup:
    def test_no_arguments_shows_launcher(self, make_app: MakeApp) -> None:
        app = make_app()
        app.start([])
        (window,) = app.windows
        assert window.is_launcher
        assert window.launcher is not None and window.launcher.showing_empty_message

    def test_paths_open_one_window_each_without_launcher(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        app.start([write_md("a.md", "# A"), write_md("b.md", "# B")])
        assert [w.windowTitle() for w in app.windows] == ["a.md", "b.md"]
        assert not any(w.is_launcher for w in app.windows)

    def test_failures_are_reported_together_and_readable_files_open(
        self, make_app: MakeApp, write_md: WriteMd, tmp_path: Path, prompts: FakePrompts
    ) -> None:
        app = make_app()
        app.start([tmp_path / "missing.md", write_md("ok.md", "fine"), tmp_path])
        assert [w.windowTitle() for w in app.windows] == ["ok.md"]
        ((title, message),) = prompts.errors
        assert title == "Cannot open files"
        assert "missing.md does not exist" in message
        assert f"{tmp_path} is a folder" in message

    def test_launcher_appears_when_nothing_opened(
        self, make_app: MakeApp, tmp_path: Path, prompts: FakePrompts
    ) -> None:
        app = make_app()
        app.start([tmp_path / "missing.md"])
        assert len(prompts.errors) == 1
        (window,) = app.windows
        assert window.is_launcher

    def test_any_extension_opens_as_markdown(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        app.start([write_md("notes.txt", "# Heading")])
        document = app.windows[0].document
        assert document is not None
        assert "Heading" in document.view.document().toPlainText()


class TestOpening:
    def test_launcher_becomes_the_document_window(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        launcher = app.open_launcher()
        app.open_path(write_md("doc.md", "text"), launcher)
        assert app.windows == (launcher,)
        assert not launcher.is_launcher
        assert launcher.windowTitle() == "doc.md"

    def test_open_from_document_window_makes_a_new_window(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        app.start([write_md("one.md", "1")])
        app.open_path(write_md("two.md", "2"), app.windows[0])
        assert [w.windowTitle() for w in app.windows] == ["one.md", "two.md"]

    def test_already_open_file_is_not_opened_twice(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        path = write_md("one.md", "1")
        app.start([path])
        app.open_path(path.parent / "." / "one.md", app.windows[0])
        app.open_path(path, app.windows[0])
        assert len(app.windows) == 1

    def test_choose_and_open_uses_the_file_chooser(
        self, make_app: MakeApp, write_md: WriteMd, prompts: FakePrompts
    ) -> None:
        app = make_app()
        launcher = app.open_launcher()
        prompts.file_answers = [None, write_md("picked.md", "x")]
        app.choose_and_open(launcher)
        assert launcher.is_launcher
        app.choose_and_open(launcher)
        assert launcher.windowTitle() == "picked.md"

    def test_about(self, make_app: MakeApp, prompts: FakePrompts) -> None:
        app = make_app()
        app.show_about(app.open_launcher())
        assert prompts.abouts and "mdmd" in prompts.abouts[0]


class TestRecentFiles:
    def test_successful_opens_are_remembered_newest_first(
        self, make_app: MakeApp, write_md: WriteMd, config_dir: Path
    ) -> None:
        app = make_app()
        a, b = write_md("a.md", "a"), write_md("b.md", "b")
        app.start([a, b])
        assert app.recent_files() == (str(b), str(a))
        assert stored(config_dir)["recentFiles"] == [str(b), str(a)]

    def test_reopening_an_open_file_moves_it_to_the_top(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        a, b = write_md("a.md", "a"), write_md("b.md", "b")
        app.start([a, b])
        app.open_path(a, app.windows[1])
        assert len(app.windows) == 2
        assert app.recent_files() == (str(a), str(b))

    def test_failed_open_is_not_remembered(self, make_app: MakeApp, tmp_path: Path) -> None:
        app = make_app()
        app.start([tmp_path / "missing.md"])
        assert app.recent_files() == ()

    def test_list_is_capped(self, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        app.start([write_md(f"f{n}.md", "x") for n in range(MAX_RECENT_FILES + 2)])
        assert len(app.recent_files()) == MAX_RECENT_FILES

    def test_missing_recent_file_shows_error_and_is_removed(
        self, make_app: MakeApp, write_md: WriteMd, prompts: FakePrompts
    ) -> None:
        app = make_app()
        path = write_md("gone.md", "x")
        app.start([path])
        app.windows[0].close()
        path.unlink()
        launcher = app.open_launcher()
        assert launcher.launcher is not None
        assert "(missing)" in launcher.launcher.recent_list.item(0).text()
        app.open_path(path, launcher)
        assert prompts.errors and "does not exist" in prompts.errors[-1][1]
        assert app.recent_files() == ()
        assert launcher.launcher.showing_empty_message

    def test_recent_files_survive_restart(self, make_app: MakeApp, write_md: WriteMd) -> None:
        path = write_md("keep.md", "x")
        make_app().start([path])
        assert make_app().recent_files() == (str(path),)


class TestWindowSize:
    def test_size_is_saved_on_close_and_used_for_new_windows(
        self, qtbot: QtBot, make_app: MakeApp, config_dir: Path
    ) -> None:
        app = make_app()
        window = app.open_launcher()
        window.resize(640, 480)
        window.close()
        assert stored(config_dir)["windowSize"] == [640, 480]
        assert make_app().open_launcher().size().toTuple() == (640, 480)

    def test_closing_the_last_window_is_announced(self, qtbot: QtBot, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        app.start([write_md("a.md", "a"), write_md("b.md", "b")])
        with qtbot.assertNotEmitted(app.last_window_closed):
            app.windows[0].close()
        with qtbot.waitSignal(app.last_window_closed, timeout=1000):
            app.windows[0].close()

    def test_quit_closes_every_window(self, qtbot: QtBot, make_app: MakeApp, write_md: WriteMd) -> None:
        app = make_app()
        app.start([write_md("a.md", "a"), write_md("b.md", "b")])
        with qtbot.waitSignal(app.last_window_closed, timeout=1000):
            app.quit()
        assert app.windows == ()


class TestSettings:
    def test_apply_restyles_every_window_and_persists(
        self, make_app: MakeApp, write_md: WriteMd, config_dir: Path
    ) -> None:
        app = make_app()
        app.start([write_md("a.md", "text"), write_md("b.md", "text")])
        style = DEFAULT_STYLE.with_value("body", "size", 20)
        app.apply_settings(SettingsDraft(style, None))
        for window in app.windows:
            assert window.document is not None
            doc = window.document.view.document()
            cursor = doc.find("text")
            cursor.setPosition(cursor.selectionStart() + 1)
            assert cursor.charFormat().fontPointSize() == 20
        assert stored(config_dir)["workingSettings"]["body"]["size"] == 20  # type: ignore[index]
        assert stored(config_dir)["activeTheme"] is None

    @needs_permissions
    def test_failed_save_changes_nothing(self, make_app: MakeApp, config_dir: Path) -> None:
        app = make_app()
        with read_only(config_dir), pytest.raises(OSError):
            app.apply_settings(SettingsDraft(DEFAULT_STYLE.with_value("body", "size", 20), None))
        assert app.style == DEFAULT_STYLE

    def test_themes_save_and_delete(self, make_app: MakeApp, config_dir: Path) -> None:
        app = make_app()
        evening = Theme("Evening", DEFAULT_STYLE.with_value("page", "background", "#101010"))
        app.save_theme(evening)
        app.apply_settings(SettingsDraft(evening.style, "Evening"))
        assert make_app().themes.find("evening") == evening
        app.delete_theme("EVENING")
        assert app.themes.find("Evening") is None
        assert app.active_theme is None
        assert stored(config_dir)["activeTheme"] is None

    def test_unparseable_settings_start_with_defaults(self, make_app: MakeApp, config_dir: Path) -> None:
        (config_dir / "settings.json").write_text("garbage")
        app = make_app()
        assert app.style == DEFAULT_STYLE
        assert (config_dir / "settings.json").read_text() == "garbage"

    def test_settings_dialog_is_a_single_instance(self, make_app: MakeApp) -> None:
        app = make_app()
        window = app.open_launcher()
        app.show_settings(window)
        first = app.settings_dialog
        app.show_settings(window)
        assert app.settings_dialog is first
        assert first is not None
        first.reject()
        assert app.settings_dialog is None


class TestEdgeCases:
    def test_settings_dialog_closes_with_the_last_window(
        self, qtbot: QtBot, make_app: MakeApp, write_md: WriteMd
    ) -> None:
        app = make_app()
        app.start([write_md("a.md", "a")])
        app.show_settings(app.windows[0])
        dialog = app.settings_dialog
        assert dialog is not None
        with qtbot.waitSignal(app.last_window_closed, timeout=1000):
            app.windows[0].close()
        assert app.settings_dialog is None

    def test_damaged_settings_leave_themes_intact(self, make_app: MakeApp, config_dir: Path) -> None:
        make_app().save_theme(Theme("Evening", DEFAULT_STYLE.with_value("page", "background", "#101010")))
        (config_dir / "settings.json").write_text("{ broken")
        app = make_app()
        assert app.style == DEFAULT_STYLE
        assert app.themes.find("Evening") is not None

    def test_active_theme_that_no_longer_exists_counts_as_none(self, make_app: MakeApp, config_dir: Path) -> None:
        (config_dir / "settings.json").write_text(json.dumps({"activeTheme": "Gone"}))
        app = make_app()
        app.show_settings(app.open_launcher())
        assert app.settings_dialog is not None
        assert app.settings_dialog.theme_combo.currentText() == "No theme"

    def test_recent_entry_that_became_a_folder_is_removed(
        self, make_app: MakeApp, tmp_path: Path, prompts: FakePrompts
    ) -> None:
        path = tmp_path / "was-a-file.md"
        path.write_text("x")
        app = make_app()
        app.start([path])
        app.windows[0].close()
        path.unlink()
        path.mkdir()
        app.open_path(path, app.open_launcher())
        assert "is a folder" in prompts.errors[-1][1]
        assert app.recent_files() == ()

    @pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
    def test_unreadable_recent_entry_is_kept(self, make_app: MakeApp, tmp_path: Path, prompts: FakePrompts) -> None:
        path = tmp_path / "locked.md"
        path.write_text("x")
        app = make_app()
        app.start([path])
        app.windows[0].close()
        path.chmod(0)
        try:
            app.open_path(path, app.open_launcher())
        finally:
            path.chmod(0o644)
        assert "cannot be read" in prompts.errors[-1][1]
        assert app.recent_files() == (str(path),)

    def test_symlink_to_an_open_file_reuses_its_window(self, make_app: MakeApp, write_md: WriteMd) -> None:
        target = write_md("real.md", "x")
        link = target.with_name("alias.md")
        link.symlink_to(target)
        app = make_app()
        app.start([target])
        app.open_path(link, app.windows[0])
        assert len(app.windows) == 1

    @needs_permissions
    def test_recent_file_save_failure_is_not_shown(
        self, make_app: MakeApp, write_md: WriteMd, config_dir: Path, prompts: FakePrompts
    ) -> None:
        app = make_app()
        with read_only(config_dir):
            app.start([write_md("a.md", "a")])
        assert prompts.errors == []
        assert app.recent_files()  # still remembered for this session


class TestHostileFiles:
    """The inputs from the security scan: each must open (or be refused) without taking the app down."""

    @pytest.mark.parametrize(
        ("name", "text", "expected"),
        [
            ("emphasis.md", "*" * 3000 + "deep" + "*" * 3000, "deep"),
            ("digits.md", "Claim [" + "1" * 5000 + "].\n\n## Sources\n\n1. one", "Claim ["),
            ("headings.md", "#\n" * 2_000 + "end", "end"),  # allocation speed itself is tested in test_slugs
        ],
        ids=["deep-emphasis", "huge-citation-number", "many-identical-headings"],
    )
    def test_crafted_documents_open(
        self, make_app: MakeApp, write_md: WriteMd, prompts: FakePrompts, name: str, text: str, expected: str
    ) -> None:
        app = make_app()
        app.start([write_md(name, text)])
        assert prompts.errors == []
        document = app.windows[0].document
        assert document is not None
        assert expected in document.view.document().toPlainText()

    def test_unparseable_content_is_reported_and_no_window_is_left_half_built(
        self, make_app: MakeApp, write_md: WriteMd, prompts: FakePrompts, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fail(_text: str) -> object:
            raise DocumentParseError("RecursionError")

        monkeypatch.setattr(markdown_files, "parse_markdown", fail)
        app = make_app()
        launcher = app.open_launcher()
        path = write_md("bad.md", "x")
        app.open_path(path, launcher)
        assert prompts.errors == [("Cannot open file", f"{path} could not be displayed.")]
        assert launcher.is_launcher
        assert app.recent_files() == ()


class TestSeveralProcesses:
    """Each launch is its own application; two Application objects on one settings folder stand in for two."""

    def test_apply_in_one_restyles_the_others_windows(self, qtbot: QtBot, make_app: MakeApp, write_md: WriteMd) -> None:
        first, second = make_app(), make_app()
        second.start([write_md("b.md", "text")])
        first.apply_settings(SettingsDraft(DEFAULT_STYLE.with_value("body", "size", 20), None))
        document = second.windows[0].document
        assert document is not None

        def body_size() -> float:
            doc = document.view.document()
            cursor = doc.find("text")
            cursor.setPosition(cursor.selectionStart() + 1)
            return cursor.charFormat().fontPointSize()

        qtbot.waitUntil(lambda: body_size() == 20, timeout=3000)
        assert second.style.number("body", "size") == 20

    def test_recent_files_are_shared_and_never_clobbered(
        self, qtbot: QtBot, make_app: MakeApp, write_md: WriteMd, config_dir: Path
    ) -> None:
        first, second = make_app(), make_app()
        launcher = second.open_launcher()
        path = write_md("a.md", "a")
        first.start([path])
        assert launcher.launcher is not None
        qtbot.waitUntil(lambda: launcher.launcher.recent_list.count() == 1, timeout=3000)
        launcher.close()  # saves the window size from a process that opened nothing
        assert stored(config_dir)["recentFiles"] == [str(path)]

    def test_a_theme_saved_in_one_is_offered_in_the_other(self, qtbot: QtBot, make_app: MakeApp) -> None:
        first, second = make_app(), make_app()
        first.save_theme(Theme("Evening", DEFAULT_STYLE))
        qtbot.waitUntil(lambda: second.themes.find("Evening") is not None, timeout=3000)
        first.delete_theme("Evening")
        qtbot.waitUntil(lambda: second.themes.find("Evening") is None, timeout=3000)

    def test_the_same_file_can_be_open_in_two_processes(self, make_app: MakeApp, write_md: WriteMd) -> None:
        path = write_md("a.md", "a")
        first, second = make_app(), make_app()
        first.start([path])
        second.start([path])
        assert len(first.windows) == len(second.windows) == 1

    def test_an_open_settings_dialog_lists_themes_saved_elsewhere(self, qtbot: QtBot, make_app: MakeApp) -> None:
        first, second = make_app(), make_app()
        second.show_settings(second.open_launcher())
        dialog = second.settings_dialog
        assert dialog is not None
        first.save_theme(Theme("Evening", DEFAULT_STYLE))
        qtbot.waitUntil(lambda: dialog.theme_combo.findData("Evening") >= 0, timeout=3000)

    def test_dialog_shows_no_theme_when_another_process_deletes_the_active_one(
        self, qtbot: QtBot, make_app: MakeApp
    ) -> None:
        first, second = make_app(), make_app()
        first.save_theme(Theme("Evening", DEFAULT_STYLE))
        qtbot.waitUntil(lambda: second.themes.find("Evening") is not None, timeout=3000)
        second.apply_settings(SettingsDraft(DEFAULT_STYLE, "Evening"))
        second.show_settings(second.open_launcher())
        dialog = second.settings_dialog
        assert dialog is not None
        assert dialog.theme_combo.currentText() == "Evening"
        first.delete_theme("Evening")
        qtbot.waitUntil(lambda: dialog.theme_combo.currentText() == "No theme", timeout=3000)
        assert dialog.theme_combo.findData("Evening") < 0


class TestOpeningEdges:
    def test_a_window_whose_file_was_deleted_does_not_block_opening_others(
        self, make_app: MakeApp, write_md: WriteMd
    ) -> None:
        gone, other = write_md("gone.md", "a"), write_md("other.md", "b")
        app = make_app()
        app.start([gone])
        gone.unlink()  # the open window now points at a missing file
        app.open_path(other, app.windows[0])
        assert [w.windowTitle() for w in app.windows] == ["gone.md", "other.md"]


class TestSettingsDamagedWhileRunning:
    """Unreadable settings mean Default settings, at start-up and while running alike."""

    def test_windows_fall_back_to_default_and_the_next_save_backs_the_file_up(
        self, qtbot: QtBot, make_app: MakeApp, write_md: WriteMd, config_dir: Path
    ) -> None:
        app = make_app()
        app.apply_settings(SettingsDraft(DEFAULT_STYLE.with_value("body", "size", 20), None))
        app.start([write_md("a.md", "text")])
        document = app.windows[0].document
        assert document is not None

        def body_size() -> float:
            doc = document.view.document()
            cursor = doc.find("text")
            cursor.setPosition(cursor.selectionStart() + 1)
            return cursor.charFormat().fontPointSize()

        assert body_size() == 20
        settings_file = config_dir / "settings.json"
        replacement = settings_file.with_suffix(".tmp")
        replacement.write_text("{ a typo")
        replacement.replace(settings_file)  # how an editor saves
        qtbot.waitUntil(lambda: body_size() == DEFAULT_STYLE.number("body", "size"), timeout=3000)
        assert app.style == DEFAULT_STYLE
        assert settings_file.read_text() == "{ a typo"  # nothing is written until the next save

        app.open_path(write_md("b.md", "b"), app.windows[0])
        assert (config_dir / "settings.json.bak").read_text() == "{ a typo"
        saved = stored(config_dir)
        assert saved["workingSettings"]["body"]["size"] == DEFAULT_STYLE.number("body", "size")  # type: ignore[index]
        assert saved["recentFiles"][0].endswith("b.md")  # type: ignore[index]
