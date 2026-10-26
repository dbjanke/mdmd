"""What the settings dialog is editing: style values plus the active theme, before Apply."""

from __future__ import annotations

from dataclasses import dataclass

from mdmd.core.style import Style
from mdmd.core.themes import Theme, same_name


@dataclass(frozen=True)
class SettingsDraft:
    style: Style
    active_theme: str | None

    def with_value(self, element: str, prop: str, value: object) -> SettingsDraft:
        """Raises InvalidValueError if the value is out of range; the draft is then unchanged."""
        return SettingsDraft(self.style.with_value(element, prop, value), self.active_theme)

    def load_theme(self, theme: Theme) -> SettingsDraft:
        return SettingsDraft(theme.style, theme.name)

    def saved_as(self, name: str) -> SettingsDraft:
        return SettingsDraft(self.style, name)

    def theme_deleted(self, name: str) -> SettingsDraft:
        """The values stay; the working settings are no longer tied to the deleted theme."""
        if self.active_theme is not None and same_name(self.active_theme, name):
            return SettingsDraft(self.style, None)
        return self
