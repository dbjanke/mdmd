"""What decides how every window draws a document. Zoom is per window and not part of it."""

from dataclasses import dataclass

from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.style import Style


@dataclass(frozen=True)
class ViewPreferences:
    style: Style = DEFAULT_STYLE
    show_soft_line_breaks: bool = False  # single line endings in a paragraph show as line breaks, not spaces
