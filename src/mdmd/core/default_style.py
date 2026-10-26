"""The Default theme: a plain light theme, and the fallback for any missing or invalid value."""

from mdmd.core.style import Style

DEFAULT_THEME_NAME = "Default"

SANS_FAMILY = "Sans Serif"  # fontconfig alias for the system sans-serif font
MONO_FAMILY = "Monospace"  # fontconfig alias for the system monospace font
GENERIC_FAMILIES = frozenset({SANS_FAMILY, MONO_FAMILY})

BODY_SIZE = 11.0
HEADING_SCALE = (2.0, 1.6, 1.3, 1.15, 1.0, 0.9)
HEADING_SPACE = ((24, 12), (20, 10), (16, 8), (14, 6), (12, 6), (12, 6))

TEXT_COLOR = "#333333"
HEADING_COLOR = "#222222"
ACCENT_COLOR = "#1a5fb4"


def _heading(level: int) -> dict[str, str | float]:
    before, after = HEADING_SPACE[level - 1]
    return {
        "fontFamily": SANS_FAMILY,
        "size": round(BODY_SIZE * HEADING_SCALE[level - 1], 2),
        "color": HEADING_COLOR,
        "lineSpacing": 1.2,
        "alignment": "left",
        "spaceBefore": float(before),
        "spaceAfter": float(after),
    }


DEFAULT_STYLE = Style(
    {
        "page": {"background": "#ffffff"},
        "body": {
            "fontFamily": SANS_FAMILY,
            "size": BODY_SIZE,
            "color": TEXT_COLOR,
            "lineSpacing": 1.4,
            "alignment": "left",
            "spaceBefore": 0.0,
            "spaceAfter": 10.0,
        },
        **{f"h{level}": _heading(level) for level in range(1, 7)},
        "link": {"color": ACCENT_COLOR, "underline": True},
        "inlineCode": {"fontFamily": MONO_FAMILY, "size": 10.0, "color": TEXT_COLOR, "background": "#f0f0f0"},
        "codeBlock": {
            "fontFamily": MONO_FAMILY,
            "size": 10.0,
            "color": TEXT_COLOR,
            "background": "#f5f5f5",
            "lineSpacing": 1.3,
            "spaceBefore": 4.0,
            "spaceAfter": 12.0,
        },
        "blockQuote": {
            "color": "#555555",
            "background": "#f7f7f7",
            "lineSpacing": 1.4,
            "alignment": "left",
            "spaceBefore": 4.0,
            "spaceAfter": 12.0,
        },
        "list": {
            "fontFamily": SANS_FAMILY,
            "size": BODY_SIZE,
            "color": TEXT_COLOR,
            "lineSpacing": 1.4,
            "alignment": "left",
            "spaceBefore": 0.0,
            "spaceAfter": 10.0,
        },
        "table": {
            "fontFamily": None,
            "size": 10.0,
            "color": TEXT_COLOR,
            "headerBackground": "#eeeeee",
            "cellBackground": "#ffffff",
            "borderColor": "#cccccc",
            "spaceBefore": 4.0,
            "spaceAfter": 12.0,
        },
        "horizontalRule": {"color": "#cccccc", "spaceBefore": 12.0, "spaceAfter": 12.0},
        "footnoteMarker": {"color": "#ffffff", "background": ACCENT_COLOR, "size": 8.0},
        "footnotePopup": {"fontFamily": SANS_FAMILY, "size": 10.0, "color": TEXT_COLOR, "background": "#fffbea"},
    }
)
