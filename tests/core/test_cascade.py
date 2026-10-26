from mdmd.core.cascade import Container, gap_between, paragraph_text_style, table_text_style
from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.style import Alignment

STYLE = (
    DEFAULT_STYLE.with_value("body", "fontFamily", "Body Font")
    .with_value("body", "color", "#000001")
    .with_value("list", "fontFamily", "List Font")
    .with_value("list", "size", 13)
    .with_value("list", "color", "#000002")
    .with_value("blockQuote", "color", "#000003")
    .with_value("blockQuote", "alignment", "right")
    .with_value("blockQuote", "lineSpacing", 2.0)
)


def test_top_level_paragraph_uses_body() -> None:
    text = paragraph_text_style(STYLE, [])
    assert (text.font_family, text.color) == ("Body Font", "#000001")


def test_list_paragraph_uses_list_values() -> None:
    text = paragraph_text_style(STYLE, [Container.LIST])
    assert (text.font_family, text.size, text.color) == ("List Font", 13, "#000002")


def test_quote_keeps_enclosing_font_but_takes_its_own_color_spacing_alignment() -> None:
    text = paragraph_text_style(STYLE, [Container.BLOCK_QUOTE])
    assert text.font_family == "Body Font"
    assert (text.color, text.line_spacing, text.alignment) == ("#000003", 2.0, Alignment.RIGHT)


def test_innermost_container_wins() -> None:
    quote_in_list = paragraph_text_style(STYLE, [Container.LIST, Container.BLOCK_QUOTE])
    assert (quote_in_list.font_family, quote_in_list.color) == ("List Font", "#000003")
    list_in_quote = paragraph_text_style(STYLE, [Container.BLOCK_QUOTE, Container.LIST])
    assert (list_in_quote.font_family, list_in_quote.color) == ("List Font", "#000002")


def test_table_font_falls_back_to_body_when_unset() -> None:
    assert table_text_style(STYLE.with_value("table", "fontFamily", None)).font_family == "Body Font"
    assert table_text_style(STYLE.with_value("table", "fontFamily", "Table Font")).font_family == "Table Font"


def test_gap_is_additive() -> None:
    assert gap_between(10, 24) == 34
