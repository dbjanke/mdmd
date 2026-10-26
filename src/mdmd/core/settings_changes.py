"""The ways the stored settings change, as named functions applied to whatever is stored now.

Several mdmd processes share one settings file, so a change is never "save these
settings" but "apply this change to the current settings". Each function here
returns such a change.
"""

from collections.abc import Callable
from dataclasses import replace

from mdmd.core.app_settings import AppSettings, clamp_window_size
from mdmd.core.recent import add_recent, remove_recent
from mdmd.core.style import Style
from mdmd.core.themes import same_name

type SettingsChange = Callable[[AppSettings], AppSettings]


def recent_file_opened(path: str) -> SettingsChange:
    """`path` moves to the top of the recent files."""
    return lambda settings: replace(settings, recent_files=add_recent(settings.recent_files, path))


def recent_file_forgotten(path: str) -> SettingsChange:
    return lambda settings: replace(settings, recent_files=remove_recent(settings.recent_files, path))


def window_resized(width: int, height: int) -> SettingsChange:
    """New windows open at this size (kept within sensible bounds)."""
    size = clamp_window_size(width, height)
    return lambda settings: replace(settings, window_size=size)


def appearance_applied(style: Style, active_theme: str | None) -> SettingsChange:
    """The settings dialog's Apply: new working values, tied to `active_theme` or to none."""
    return lambda settings: replace(settings, style=style, active_theme=active_theme)


def theme_deleted(name: str) -> SettingsChange:
    """If theme `name` was active, the working settings keep their values but belong to no theme."""

    def change(settings: AppSettings) -> AppSettings:
        active = settings.active_theme
        if active is not None and same_name(active, name):
            return replace(settings, active_theme=None)
        return settings

    return change
