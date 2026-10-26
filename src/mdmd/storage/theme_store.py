"""User themes, one JSON file each in the `themes` folder."""

import logging
from pathlib import Path
from urllib.parse import quote

from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.style import parse_style, style_to_json
from mdmd.core.themes import Theme, ThemeLibrary, ThemeNameError, validate_theme_name
from mdmd.logs import get_logger, log_event
from mdmd.storage.json_files import read_json, write_json_atomic

THEMES_DIR_NAME = "themes"
THEME_FILE_SUFFIX = ".json"

_log = get_logger("theme_store")


def theme_file_name(name: str) -> str:
    """A safe, case-insensitive file name for a theme: names differing only in case share a file."""
    return quote(name.casefold(), safe="") + THEME_FILE_SUFFIX


class ThemeStore:
    def __init__(self, config_directory: Path) -> None:
        self._directory = config_directory / THEMES_DIR_NAME

    @property
    def directory(self) -> Path:
        return self._directory

    def load_all(self) -> ThemeLibrary:
        """Never fails. Theme files that cannot be read are skipped and left untouched."""
        if not self._directory.is_dir():
            return ThemeLibrary()
        library = ThemeLibrary()
        for path in sorted(self._directory.glob(f"*{THEME_FILE_SUFFIX}")):
            theme = self._load_file(path)
            if theme is None:
                continue
            if library.find(theme.name) is not None:
                log_event(_log, "theme_duplicate_skipped", level=logging.WARNING)
                continue
            library = library.with_theme(theme)
        return library

    def _load_file(self, path: Path) -> Theme | None:
        try:
            raw = read_json(path)
            if not isinstance(raw, dict) or not isinstance(raw.get("name"), str):
                raise ValueError("theme file needs an object with a name")
            name = validate_theme_name(raw["name"])
        except (OSError, ValueError) as error:
            # ThemeNameError is a ValueError.
            log_event(_log, "theme_unreadable", level=logging.WARNING, error=type(error).__name__)
            return None
        parsed = parse_style(raw.get("settings"), DEFAULT_STYLE)
        if parsed.rejected:
            log_event(_log, "theme_values_rejected", count=len(parsed.rejected))
        return Theme(name, parsed.style)

    def save(self, theme: Theme) -> None:
        """Raises OSError if the file cannot be written, ThemeNameError for an invalid name."""
        validate_theme_name(theme.name)
        data = {"name": theme.name, "settings": style_to_json(theme.style)}
        write_json_atomic(self._directory / theme_file_name(theme.name), data)

    def delete(self, name: str) -> None:
        """Raises OSError if the file exists but cannot be removed."""
        if not name.strip():
            raise ThemeNameError("A theme name cannot be empty.")
        (self._directory / theme_file_name(name)).unlink(missing_ok=True)
