"""How style values combine: nested content inheriting from its container, and the gap between elements.

Paragraphs inside a list or block quote take that container's font, size, color,
line spacing and alignment; the innermost container wins. A block quote has no
font or size of its own, so those come from whatever encloses it. Headings and
code blocks always keep their own style.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from enum import Enum

from mdmd.core.style import Alignment, Style


class Container(Enum):
    LIST = "list"
    BLOCK_QUOTE = "blockQuote"


@dataclass(frozen=True)
class TextStyle:
    font_family: str
    size: float
    color: str
    line_spacing: float
    alignment: Alignment


def element_text_style(style: Style, element: str) -> TextStyle:
    """The text style of an element that has all five text properties (body, headings, lists)."""
    return TextStyle(
        font_family=style.text(element, "fontFamily"),
        size=style.number(element, "size"),
        color=style.text(element, "color"),
        line_spacing=style.number(element, "lineSpacing"),
        alignment=style.alignment(element),
    )


def paragraph_text_style(style: Style, containers: Sequence[Container]) -> TextStyle:
    """Text style for a paragraph nested in `containers`, outermost first."""
    result = element_text_style(style, "body")
    for container in containers:
        if container is Container.LIST:
            result = element_text_style(style, "list")
        else:
            result = replace(
                result,
                color=style.text("blockQuote", "color"),
                line_spacing=style.number("blockQuote", "lineSpacing"),
                alignment=style.alignment("blockQuote"),
            )
    return result


def table_text_style(style: Style) -> TextStyle:
    """Table cells use the table's font when set, otherwise the body font."""
    body = element_text_style(style, "body")
    return replace(
        body,
        font_family=style.optional_text("table", "fontFamily") or body.font_family,
        size=style.number("table", "size"),
        color=style.text("table", "color"),
    )


def popup_style(style: Style) -> Style:
    """The style footnote popups render with: the popup's font, size, and colors replace the body's and the list's.

    Everything else (emphasis, code, links) keeps its normal style.
    """
    popup = style.values["footnotePopup"]
    text_values = {"fontFamily": popup["fontFamily"], "size": popup["size"], "color": popup["color"]}
    values = dict(style.values)
    values["body"] = {**style.values["body"], **text_values, "spaceBefore": 0.0}
    values["list"] = {**style.values["list"], **text_values, "spaceBefore": 0.0}
    values["page"] = {"background": popup["background"]}
    return Style(values)


def gap_between(space_after: float, space_before: float) -> float:
    """Spacing between adjacent elements is additive."""
    return space_after + space_before
