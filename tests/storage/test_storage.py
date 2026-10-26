import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from mdmd.core.app_settings import AppSettings
from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.parser import DocumentParseError
from mdmd.core.themes import Theme, ThemeNameError
from mdmd.storage import markdown_files
from mdmd.storage.config_paths import config_dir
from mdmd.storage.markdown_files import (
    MAX_FILE_BYTES,
    FileOpenError,
    OpenFailure,
    load_document,
    read_markdown_file,
)
from mdmd.storage.settings_store import SettingsStore
from mdmd.storage.theme_store import ThemeStore, theme_file_name


class TestSettingsStore:
    def test_no_file_gives_defaults(self, tmp_path: Path) -> None:
        assert SettingsStore(tmp_path).load() == AppSettings()

    def test_save_then_load(self, tmp_path: Path) -> None:
        settings = AppSettings(style=DEFAULT_STYLE.with_value("h1", "size", 30), recent_files=("/x.md",))
        SettingsStore(tmp_path).update(lambda _stored: settings)
        assert SettingsStore(tmp_path).load() == settings

    def test_unparseable_file_is_kept_until_save_then_backed_up(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text("{ not json")
        store = SettingsStore(tmp_path)
        assert store.load() == AppSettings()
        assert path.read_text() == "{ not json"
        store.update(lambda stored: stored)
        assert (tmp_path / "settings.json.bak").read_text() == "{ not json"
        assert json.loads(path.read_text())["activeTheme"] == "Default"

    def test_valid_file_is_not_backed_up(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path)
        store.update(lambda stored: stored)
        store.update(lambda stored: stored)
        assert not (tmp_path / "settings.json.bak").exists()

    def test_non_object_root_is_unparseable(self, tmp_path: Path) -> None:
        (tmp_path / "settings.json").write_text("[1, 2]")
        store = SettingsStore(tmp_path)
        store.update(lambda stored: stored)
        assert (tmp_path / "settings.json.bak").exists()

    def test_save_failure_raises(self, tmp_path: Path) -> None:
        blocker = tmp_path / "file"
        blocker.write_text("")
        with pytest.raises(OSError):
            SettingsStore(blocker).update(lambda stored: stored)  # parent is a file, not a folder


class TestThemeStore:
    def test_save_load_delete(self, tmp_path: Path) -> None:
        store = ThemeStore(tmp_path)
        evening = Theme("Evening", DEFAULT_STYLE.with_value("page", "background", "#101010"))
        store.save(evening)
        assert store.load_all().find("evening") == evening
        store.delete("EVENING")
        assert store.load_all().user_themes == ()

    def test_file_names_are_safe(self) -> None:
        assert theme_file_name("../etc/passwd") == "..%2Fetc%2Fpasswd.json"
        assert theme_file_name("Evening") == theme_file_name("EVENING")

    def test_unreadable_theme_files_are_skipped_and_left_alone(self, tmp_path: Path) -> None:
        store = ThemeStore(tmp_path)
        store.save(Theme("Good", DEFAULT_STYLE))
        bad = store.directory / "bad.json"
        bad.write_text("nope")
        (store.directory / "default.json").write_text(json.dumps({"name": "Default", "settings": {}}))
        (store.directory / "nameless.json").write_text(json.dumps({"settings": {}}))
        assert [t.name for t in store.load_all().user_themes] == ["Good"]
        assert bad.read_text() == "nope"

    def test_invalid_values_in_theme_fall_back(self, tmp_path: Path) -> None:
        store = ThemeStore(tmp_path)
        store.directory.mkdir()
        raw = {"name": "Odd", "settings": {"h1": {"size": 999, "color": "#ff0000"}}}
        (store.directory / "odd.json").write_text(json.dumps(raw))
        theme = store.load_all().find("Odd")
        assert theme is not None
        assert theme.style.number("h1", "size") == DEFAULT_STYLE.number("h1", "size")
        assert theme.style.text("h1", "color") == "#ff0000"

    def test_save_rejects_default(self, tmp_path: Path) -> None:
        with pytest.raises(ThemeNameError):
            ThemeStore(tmp_path).save(Theme("Default", DEFAULT_STYLE))

    def test_delete_missing_theme_is_fine(self, tmp_path: Path) -> None:
        ThemeStore(tmp_path).delete("Ghost")


class TestMarkdownFiles:
    def test_reads_text(self, tmp_path: Path) -> None:
        path = tmp_path / "a.txt"
        path.write_text("# hi", encoding="utf-8")
        assert read_markdown_file(path) == "# hi"

    def test_invalid_utf8_is_replaced(self, tmp_path: Path) -> None:
        path = tmp_path / "a.md"
        path.write_bytes(b"caf\xe9")
        assert read_markdown_file(path) == "caf�"

    def test_failures(self, tmp_path: Path) -> None:
        with pytest.raises(FileOpenError) as missing:
            read_markdown_file(tmp_path / "missing.md")
        assert missing.value.failure is OpenFailure.NOT_FOUND
        assert "missing.md" in str(missing.value)
        with pytest.raises(FileOpenError) as folder:
            read_markdown_file(tmp_path)
        assert folder.value.failure is OpenFailure.IS_DIRECTORY

    @pytest.mark.skipif(os.geteuid() == 0, reason="root can read anything")
    def test_unreadable(self, tmp_path: Path) -> None:
        path = tmp_path / "locked.md"
        path.write_text("x")
        path.chmod(0)
        with pytest.raises(FileOpenError) as error:
            read_markdown_file(path)
        assert error.value.failure is OpenFailure.UNREADABLE

    def test_too_large(self, tmp_path: Path) -> None:
        path = tmp_path / "big.md"
        with path.open("wb") as handle:
            handle.truncate(MAX_FILE_BYTES + 1)
        with pytest.raises(FileOpenError) as error:
            read_markdown_file(path)
        assert error.value.failure is OpenFailure.TOO_LARGE


def test_config_dir_honours_absolute_xdg_only(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_dir() == tmp_path / "mdmd"
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/dir")
    assert config_dir() == Path.home() / ".config" / "mdmd"


class TestLoadDocument:
    def test_loads_and_parses(self, tmp_path: Path) -> None:
        path = tmp_path / "a.md"
        path.write_text("# Title")
        assert len(load_document(path).blocks) == 1

    def test_content_that_cannot_be_parsed_is_an_open_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "a.md"
        path.write_text("x")

        def fail(_text: str) -> object:
            raise DocumentParseError("RecursionError")

        monkeypatch.setattr(markdown_files, "parse_markdown", fail)
        with pytest.raises(FileOpenError) as error:
            load_document(path)
        assert error.value.failure is OpenFailure.UNDISPLAYABLE
        assert str(error.value) == f"{path} could not be displayed."

    def test_read_failures_pass_through(self, tmp_path: Path) -> None:
        with pytest.raises(FileOpenError) as error:
            load_document(tmp_path / "missing.md")
        assert error.value.failure is OpenFailure.NOT_FOUND


class TestSharedSettings:
    """Several mdmd processes share one settings file."""

    def test_update_applies_to_what_is_stored_now(self, tmp_path: Path) -> None:
        first, second = SettingsStore(tmp_path), SettingsStore(tmp_path)
        first.update(lambda s: replace(s, recent_files=("/a.md",)))
        second.update(lambda s: replace(s, window_size=(640, 480)))  # knew nothing of /a.md
        stored = SettingsStore(tmp_path).load()
        assert stored.recent_files == ("/a.md",)
        assert stored.window_size == (640, 480)

    def test_failed_update_leaves_the_file_alone(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path)
        store.update(lambda s: replace(s, recent_files=("/a.md",)))

        def broken(_settings: AppSettings) -> AppSettings:
            raise OSError("disk full")

        with pytest.raises(OSError):
            store.update(broken)
        assert store.load().recent_files == ("/a.md",)

    def test_concurrent_processes_lose_no_updates(self, tmp_path: Path) -> None:
        script = (
            "import sys\n"
            "from dataclasses import replace\n"
            "from pathlib import Path\n"
            "from mdmd.core.recent import add_recent\n"
            "from mdmd.storage.settings_store import SettingsStore\n"
            "store = SettingsStore(Path(sys.argv[1]))\n"
            "for n in range(5):\n"
            "    path = f'/{sys.argv[2]}-{n}.md'\n"
            "    store.update(lambda s: replace(s, recent_files=add_recent(s.recent_files, path)))\n"
        )
        workers = [subprocess.Popen([sys.executable, "-c", script, str(tmp_path), name]) for name in ("left", "right")]
        assert [worker.wait(timeout=60) for worker in workers] == [0, 0]
        recent = set(SettingsStore(tmp_path).load().recent_files)
        assert recent == {f"/{name}-{n}.md" for name in ("left", "right") for n in range(5)}

    def test_a_damaged_file_another_process_already_replaced_is_not_backed_up_again(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("{ damaged")
        first, second = SettingsStore(tmp_path), SettingsStore(tmp_path)
        first.load()
        second.load()  # both processes start while the file is damaged
        second.update(lambda s: replace(s, recent_files=("/b.md",)))  # backs up the damage, writes good settings
        first.update(lambda s: replace(s, window_size=(640, 480)))
        assert (tmp_path / "settings.json.bak").read_text() == "{ damaged"
        stored = SettingsStore(tmp_path).load()
        assert stored.recent_files == ("/b.md",)
        assert stored.window_size == (640, 480)

    def test_update_backs_up_a_damaged_file_once(self, tmp_path: Path) -> None:
        (tmp_path / "settings.json").write_text("{ damaged")
        store = SettingsStore(tmp_path)
        store.update(lambda s: replace(s, recent_files=("/a.md",)))
        store.update(lambda s: replace(s, window_size=(640, 480)))
        assert (tmp_path / "settings.json.bak").read_text() == "{ damaged"
        assert store.load().recent_files == ("/a.md",)
