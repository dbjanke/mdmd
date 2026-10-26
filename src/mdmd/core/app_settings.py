"""Everything mdmd remembers between launches except the themes, and how it is stored as JSON."""

from __future__ import annotations

from dataclasses import dataclass, field

from mdmd.core.default_style import DEFAULT_STYLE, DEFAULT_THEME_NAME
from mdmd.core.recent import parse_recent
from mdmd.core.style import Style, parse_style, style_to_json

DEFAULT_WINDOW_SIZE = (900, 700)
MIN_WINDOW_SIDE = 200
MAX_WINDOW_SIDE = 20000


@dataclass(frozen=True)
class AppSettings:
    style: Style = DEFAULT_STYLE
    active_theme: str | None = DEFAULT_THEME_NAME
    window_size: tuple[int, int] = DEFAULT_WINDOW_SIZE
    recent_files: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ParsedSettings:
    settings: AppSettings
    rejected: tuple[str, ...]  # names of stored values that were invalid and replaced


def parse_app_settings(raw: object) -> ParsedSettings:
    """Read stored settings leniently: each invalid part falls back on its own."""
    data = raw if isinstance(raw, dict) else {}
    parsed_style = parse_style(data.get("workingSettings"), DEFAULT_STYLE)
    rejected = list(parsed_style.rejected)

    active = data.get("activeTheme")
    if active is not None and not isinstance(active, str):
        rejected.append("activeTheme")
        active = None

    window_size = _parse_window_size(data.get("windowSize"))
    if window_size is None:
        if "windowSize" in data:
            rejected.append("windowSize")
        window_size = DEFAULT_WINDOW_SIZE

    settings = AppSettings(
        style=parsed_style.style,
        active_theme=active,
        window_size=window_size,
        recent_files=parse_recent(data.get("recentFiles")),
    )
    return ParsedSettings(settings, tuple(rejected))


def _parse_window_size(raw: object) -> tuple[int, int] | None:
    if not (isinstance(raw, list) and len(raw) == 2):
        return None
    width, height = raw
    for side in (width, height):
        if isinstance(side, bool) or not isinstance(side, int) or not MIN_WINDOW_SIDE <= side <= MAX_WINDOW_SIDE:
            return None
    return (width, height)


def clamp_window_size(width: int, height: int) -> tuple[int, int]:
    def clamp(side: int) -> int:
        return max(MIN_WINDOW_SIDE, min(MAX_WINDOW_SIDE, side))

    return (clamp(width), clamp(height))


def app_settings_to_json(settings: AppSettings) -> dict[str, object]:
    return {
        "workingSettings": style_to_json(settings.style),
        "activeTheme": settings.active_theme,
        "windowSize": list(settings.window_size),
        "recentFiles": list(settings.recent_files),
    }
