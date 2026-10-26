"""Themes: named, complete copies of the style values, and the rules for naming them."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from mdmd.core.default_style import DEFAULT_STYLE, DEFAULT_THEME_NAME
from mdmd.core.style import Style

MAX_THEME_NAME_LENGTH = 64


@dataclass(frozen=True)
class Theme:
    name: str
    style: Style


DEFAULT_THEME = Theme(DEFAULT_THEME_NAME, DEFAULT_STYLE)


class ThemeNameError(ValueError):
    pass


def same_name(a: str, b: str) -> bool:
    return a.casefold() == b.casefold()


def validate_theme_name(name: str) -> str:
    """Return the cleaned name, or raise ThemeNameError with a message fit to show the user."""
    clean = name.strip()
    if not clean:
        raise ThemeNameError("A theme name cannot be empty.")
    if len(clean) > MAX_THEME_NAME_LENGTH:
        raise ThemeNameError(f"A theme name can have at most {MAX_THEME_NAME_LENGTH} characters.")
    if any(unicodedata.category(ch).startswith("C") for ch in clean):
        raise ThemeNameError("A theme name cannot contain control characters.")
    if same_name(clean, DEFAULT_THEME_NAME):
        raise ThemeNameError(f'"{DEFAULT_THEME_NAME}" is the built-in theme and cannot be replaced.')
    return clean


@dataclass(frozen=True)
class ThemeLibrary:
    """The Default theme plus the user's themes. Names are unique ignoring case."""

    user_themes: tuple[Theme, ...] = ()

    def __post_init__(self) -> None:
        ordered = tuple(sorted(self.user_themes, key=lambda t: t.name.casefold()))
        object.__setattr__(self, "user_themes", ordered)

    @property
    def themes(self) -> tuple[Theme, ...]:
        return (DEFAULT_THEME, *self.user_themes)

    def find(self, name: str | None) -> Theme | None:
        if name is None:
            return None
        return next((t for t in self.themes if same_name(t.name, name)), None)

    def with_theme(self, theme: Theme) -> ThemeLibrary:
        """Add `theme`, replacing any user theme with the same name. The Default theme is never replaced."""
        validate_theme_name(theme.name)
        others = tuple(t for t in self.user_themes if not same_name(t.name, theme.name))
        return ThemeLibrary((*others, theme))

    def without(self, name: str) -> ThemeLibrary:
        if same_name(name, DEFAULT_THEME_NAME):
            raise ThemeNameError(f'The "{DEFAULT_THEME_NAME}" theme cannot be deleted.')
        return ThemeLibrary(tuple(t for t in self.user_themes if not same_name(t.name, name)))


def is_deletable(name: str | None) -> bool:
    return name is not None and not same_name(name, DEFAULT_THEME_NAME)


@dataclass(frozen=True)
class ThemeStatus:
    """Which theme the working settings belong to, and whether they still match it."""

    name: str | None
    modified: bool

    @property
    def label(self) -> str:
        if self.name is None:
            return "No theme"
        return f"{self.name} (modified)" if self.modified else self.name


def theme_status(style: Style, active_theme: str | None, library: ThemeLibrary) -> ThemeStatus:
    theme = library.find(active_theme)
    if theme is None:
        return ThemeStatus(name=None, modified=False)
    return ThemeStatus(name=theme.name, modified=style != theme.style)
