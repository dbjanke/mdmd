import json
import os
from pathlib import Path

import pytest

from mdmd.core.app_settings import AppSettings
from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.themes import Theme, ThemeNameError
from mdmd.storage.config_paths import config_dir
from mdmd.storage.markdown_files import MAX_FILE_BYTES, FileOpenError, OpenFailure, read_markdown_file
from mdmd.storage.settings_store import SettingsStore
from mdmd.storage.theme_store import ThemeStore, theme_file_name


class TestSettingsStore:
    def test_no_file_gives_defaults(self, tmp_path: Path) -> None:
        assert SettingsStore(tmp_path).load() == AppSettings()

    def test_save_then_load(self, tmp_path: Path) -> None:
        settings = AppSettings(style=DEFAULT_STYLE.with_value("h1", "size", 30), recent_files=("/x.md",))
        SettingsStore(tmp_path).save(settings)
        assert SettingsStore(tmp_path).load() == settings

    def test_unparseable_file_is_kept_until_save_then_backed_up(self, tmp_path: Path) -> None:
        path = tmp_path / "settings.json"
        path.write_text("{ not json")
        store = SettingsStore(tmp_path)
        assert store.load() == AppSettings()
        assert path.read_text() == "{ not json"
        store.save(AppSettings())
        assert (tmp_path / "settings.json.bak").read_text() == "{ not json"
        assert json.loads(path.read_text())["activeTheme"] == "Default"

    def test_valid_file_is_not_backed_up(self, tmp_path: Path) -> None:
        store = SettingsStore(tmp_path)
        store.save(AppSettings())
        store.load()
        store.save(AppSettings())
        assert not (tmp_path / "settings.json.bak").exists()

    def test_non_object_root_is_unparseable(self, tmp_path: Path) -> None:
        (tmp_path / "settings.json").write_text("[1, 2]")
        store = SettingsStore(tmp_path)
        store.load()
        store.save(AppSettings())
        assert (tmp_path / "settings.json.bak").exists()

    def test_save_failure_raises(self, tmp_path: Path) -> None:
        blocker = tmp_path / "file"
        blocker.write_text("")
        with pytest.raises(OSError):
            SettingsStore(blocker).save(AppSettings())  # parent is a file, not a folder


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
