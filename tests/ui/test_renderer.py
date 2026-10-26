from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QTextBlock,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextDocumentFragment,
)

from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.document import Document, Link, Paragraph, Text
from mdmd.core.parser import parse_markdown
from mdmd.core.style import Style
from mdmd.ui.document_view import char_format_at
from mdmd.ui.fonts import FontResolver
from mdmd.ui.renderer import PX_PER_PT, RenderedDocument, RenderOptions, note_id_from_href, render_document
from mdmd.ui.text_objects import (
    LINK_HREF_PROPERTY,
    MARKER_BACKGROUND_PROPERTY,
    MARKER_POINT_SIZE_PROPERTY,
    NOTE_MARKER_OBJECT_TYPE,
    marker_label,
)

# Qt text blocks and formats point into their document; keep each rendered document
# alive until the test ends, or a temporary would be freed while still in use.
_alive: list[RenderedDocument] = []


@pytest.fixture(autouse=True)
def _release_documents() -> Iterator[None]:
    yield
    _alive.clear()


def render(source: str, fonts: FontResolver, style: Style = DEFAULT_STYLE, **options: object) -> RenderedDocument:
    rendered = render_document(parse_markdown(source), style, fonts, RenderOptions(**options))  # type: ignore[arg-type]
    _alive.append(rendered)
    return rendered


def blocks(document: QTextDocument) -> list[QTextBlock]:
    result = []
    block = document.begin()
    while block.isValid():
        result.append(block)
        block = block.next()
    return result


def block_with_text(document: QTextDocument, text: str) -> QTextBlock:
    found = document.find(text)
    assert not found.isNull(), text
    return found.block()


def format_of(document: QTextDocument, text: str) -> QTextCharFormat:
    found = document.find(text)
    return char_format_at(document, found.selectionStart())


def px(points: float) -> float:
    return points * PX_PER_PT


class TestText:
    def test_text_and_order(self, fonts: FontResolver) -> None:
        raw = render("# Title\n\nFirst para.\n\nSecond para.", fonts).document.toPlainText()
        assert raw.index("Title") < raw.index("First para.") < raw.index("Second para.")

    def test_code_block_keeps_lines_and_indentation(self, fonts: FontResolver) -> None:
        doc = render("```\na\n    b\n```", fonts).document
        assert "a\n    b" in doc.toPlainText()

    def test_heading_is_bold_at_its_size(self, fonts: FontResolver) -> None:
        doc = render("# Big", fonts).document
        fmt = format_of(doc, "Big")
        assert fmt.fontWeight() == QFont.Weight.Bold
        assert fmt.fontPointSize() == pytest.approx(22.0)

    def test_inline_styles(self, fonts: FontResolver) -> None:
        doc = render("*it* **bo** ~~st~~ `co`", fonts).document
        assert format_of(doc, "it").fontItalic()
        assert format_of(doc, "bo").fontWeight() == QFont.Weight.Bold
        assert format_of(doc, "st").fontStrikeOut()
        code = format_of(doc, "co")
        assert code.background().color() == QColor(DEFAULT_STYLE.text("inlineCode", "background"))

    def test_zoom_scales_text(self, fonts: FontResolver) -> None:
        doc = render("plain", fonts, zoom_percent=200).document
        assert format_of(doc, "plain").fontPointSize() == pytest.approx(22.0)

    def test_unknown_font_family_falls_back(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("body", "fontFamily", "No Such Font 12345")
        fmt = format_of(render("text", fonts, style).document, "text")
        assert fmt.fontFamilies() == ["Sans Serif"]

    def test_line_spacing_is_a_multiple_of_font_size(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("body", "lineSpacing", 2.0)
        block_format = block_with_text(render("text", fonts, style).document, "text").blockFormat()
        assert block_format.lineHeightType() == QTextBlockFormat.LineHeightTypes.FixedHeight.value
        assert block_format.lineHeight() == pytest.approx(px(11 * 2.0))


class TestSpacing:
    def test_gap_between_blocks_is_additive(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("h2", "spaceAfter", 10).with_value("body", "spaceBefore", 5)
        doc = render("## Head\n\nBody", fonts, style).document
        assert block_with_text(doc, "Body").blockFormat().topMargin() == pytest.approx(px(15))
        assert block_with_text(doc, "Head").blockFormat().bottomMargin() == 0

    def test_gap_after_a_frame_goes_on_the_frame(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("codeBlock", "spaceAfter", 20).with_value("body", "spaceBefore", 3)
        doc = render("```\ncode\n```\n\nAfter", fonts, style).document
        assert block_with_text(doc, "After").blockFormat().topMargin() == 0
        frame = QTextCursor(block_with_text(doc, "code")).currentFrame()
        assert frame.frameFormat().bottomMargin() == pytest.approx(px(23))

    def test_first_element_has_only_its_space_before(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("h1", "spaceBefore", 7)
        doc = render("# First", fonts, style).document
        assert block_with_text(doc, "First").blockFormat().topMargin() == pytest.approx(px(7))

    def test_leading_frame_leaves_no_visible_empty_block(self, fonts: FontResolver) -> None:
        doc = render("```\ncode\n```", fonts).document
        first = blocks(doc)[0]
        assert first.text() == ""
        assert first.blockFormat().lineHeight() == 0


class TestNesting:
    def test_list_paragraphs_use_list_style(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("list", "color", "#123456")
        doc = render("- item", fonts, style).document
        assert format_of(doc, "item").foreground().color() == QColor("#123456")
        assert block_with_text(doc, "item").textList() is not None

    def test_quote_paragraphs_take_quote_color(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("blockQuote", "color", "#654321")
        doc = render("> quoted", fonts, style).document
        assert format_of(doc, "quoted").foreground().color() == QColor("#654321")

    def test_ordered_list_start_and_task_markers(self, fonts: FontResolver) -> None:
        doc = render("7. seven\n8. eight\n\n- [x] done\n- [ ] open", fonts).document
        assert block_with_text(doc, "seven").textList().format().start() == 7
        assert block_with_text(doc, "done").blockFormat().marker() == QTextBlockFormat.MarkerType.Checked
        assert block_with_text(doc, "open").blockFormat().marker() == QTextBlockFormat.MarkerType.Unchecked

    def test_items_of_one_list_share_a_qt_list(self, fonts: FontResolver) -> None:
        doc = render("1. a\n2. b\n   - inner\n3. c", fonts).document
        outer = block_with_text(doc, "a").textList()
        assert block_with_text(doc, "c").textList() == outer
        assert block_with_text(doc, "inner").textList() != outer


class TestTables:
    def test_alignment_and_header(self, fonts: FontResolver) -> None:
        doc = render("| L | R |\n|:--|--:|\n| x | y |", fonts).document
        assert format_of(doc, "L").fontWeight() == QFont.Weight.Bold
        assert block_with_text(doc, "y").blockFormat().alignment() & Qt.AlignmentFlag.AlignRight
        assert QTextCursor(block_with_text(doc, "x")).currentTable() is not None

    def test_optional_table_font(self, fonts: FontResolver) -> None:
        body_family = DEFAULT_STYLE.with_value("body", "fontFamily", "Monospace")
        assert format_of(render("| h |\n|---|\n| c |", fonts, body_family).document, "c").fontFamilies() == [
            "Monospace"
        ]
        own = body_family.with_value("table", "fontFamily", "Sans Serif")
        assert format_of(render("| h |\n|---|\n| c |", fonts, own).document, "c").fontFamilies() == ["Sans Serif"]


class TestLinksAndMarkers:
    def test_external_link_is_not_an_anchor_but_keeps_its_address(self, fonts: FontResolver) -> None:
        fmt = format_of(render("[site](https://e.com)", fonts).document, "site")
        assert not fmt.isAnchor()
        assert QTextDocumentFragment.fromHtml(fmt.toolTip()).toPlainText() == "https://e.com"
        assert fmt.property(LINK_HREF_PROPERTY) == "https://e.com"

    def test_heading_link_is_an_anchor_only_when_the_heading_exists(self, fonts: FontResolver) -> None:
        doc = render("# Key Findings\n\n[go](#Key-Findings) [nowhere](#missing)", fonts).document
        assert format_of(doc, "go").anchorHref() == "#key-findings"
        assert not format_of(doc, "nowhere").isAnchor()

    def test_heading_anchor_positions(self, fonts: FontResolver) -> None:
        rendered = render("# One\n\ntext\n\n# Two", fonts)
        assert set(rendered.anchors) == {"one", "two"}
        assert rendered.document.findBlock(rendered.anchors["two"]).text() == "Two"

    def test_link_addresses_shown_only_when_asked_and_different(self, fonts: FontResolver) -> None:
        source = "[Review](https://e.com/r) and https://plain.example"
        assert "(https://e.com/r)" not in render(source, fonts).document.toPlainText()
        shown = render(source, fonts, popup=True).document.toPlainText()
        assert "Review (https://e.com/r)" in shown
        assert "(http://plain.example)" not in shown and "(https://plain.example)" not in shown

    def test_popup_content_has_nothing_clickable(self, fonts: FontResolver) -> None:
        source = "# Top\n\nSee [top](#top) and note[^n] then [1].\n\n[^n]: x\n\n## Sources\n\n1. Source"
        rendered = render(source, fonts, popup=True)
        doc = rendered.document
        assert "\ufffc" not in doc.toRawText()
        assert "note[1] then [1]." in doc.toPlainText()
        link = doc.find("top", doc.find("See"))
        assert not char_format_at(doc, link.selectionStart()).isAnchor()

    def test_footnote_markers_are_pill_objects(self, fonts: FontResolver) -> None:
        doc = render("A[^x] B[^y] C[^x]\n\n[^x]: X\n[^y]: Y", fonts).document
        raw = doc.toRawText()
        positions = [i for i, ch in enumerate(raw) if ch == "￼"]
        formats = [char_format_at(doc, p) for p in positions]
        assert [f.objectType() for f in formats] == [NOTE_MARKER_OBJECT_TYPE] * 3
        assert [marker_label(f) for f in formats] == ["1", "2", "1"]
        assert note_id_from_href(formats[0].anchorHref()) == "fn:1"

    def test_note_id_from_href(self) -> None:
        assert note_id_from_href("mdmd-note:cite:3") == "cite:3"
        assert note_id_from_href("#heading") is None


class TestImages:
    @pytest.fixture
    def picture(self, tmp_path: Path) -> Path:
        image = QImage(400, 100, QImage.Format.Format_RGB32)
        image.fill(QColor("red"))
        path = tmp_path / "pics" / "wide.png"
        path.parent.mkdir()
        assert image.save(str(path))
        return path

    def test_relative_image_loads_and_scales_down_only(self, fonts: FontResolver, picture: Path) -> None:
        rendered = render("![alt](pics/wide.png)", fonts, base_dir=picture.parent.parent)
        assert len(rendered.images) == 1
        position = rendered.images[0].position
        rendered.fit_images(200)
        fmt = char_format_at(rendered.document, position).toImageFormat()
        assert (fmt.width(), fmt.height()) == (200, 50)
        rendered.fit_images(1000)
        fmt = char_format_at(rendered.document, position).toImageFormat()
        assert (fmt.width(), fmt.height()) == (400, 100)

    @pytest.mark.parametrize("src", ["missing.png", "https://example.com/x.png", "http://example.com/x.png"])
    def test_unavailable_images_show_alt_text(self, fonts: FontResolver, tmp_path: Path, src: str) -> None:
        rendered = render(f"before ![the alt]({src}) after", fonts, base_dir=tmp_path)
        assert rendered.images == []
        assert "before the alt after" in rendered.document.toPlainText()

    def test_non_image_file_shows_alt_text(self, fonts: FontResolver, tmp_path: Path) -> None:
        (tmp_path / "fake.png").write_text("not an image")
        rendered = render("![alt text](fake.png)", fonts, base_dir=tmp_path)
        assert "alt text" in rendered.document.toPlainText()


class TestUnusualInput:
    """Shapes the parser can produce that are easy to mishandle; each must render its text."""

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("", ""),
            ("---\ntitle: hidden\n---\n", ""),
            ("- > quoted in a list", "quoted in a list"),
            ("1. ```\n   code in a list\n   ```", "code in a list"),
            ("-\n", ""),
            ("```\n```", ""),
            ("> ", ""),
            ("| only header |\n|---|", "only header"),
            ("- [x] ", ""),
            ("# ![alt in heading](missing.png)", "alt in heading"),
            ("[![alt in link](missing.png)](https://e.com)", "alt in link"),
            ("> > > deeply nested", "deeply nested"),
            ("```\n```\n\n```\n```\n\n---\n\n> q", "q"),
        ],
    )
    def test_renders(self, fonts: FontResolver, tmp_path: Path, source: str, expected: str) -> None:
        text = render(source, fonts, base_dir=tmp_path).document.toPlainText()
        assert expected in text

    def test_dashes_after_the_first_line_are_a_rule_not_front_matter(self, fonts: FontResolver) -> None:
        doc = render("Intro\n\n---\n\nmore\n\n---\n", fonts).document
        assert "Intro" in doc.toPlainText()
        assert "more" in doc.toPlainText()


class TestElementStyles:
    def test_headings_and_code_inside_lists_keep_their_own_style(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("list", "fontFamily", "Monospace").with_value("list", "size", 15)
        doc = render("- ## Listed heading\n- ```\n  listed code\n  ```", fonts, style).document
        heading = format_of(doc, "Listed heading")
        assert heading.fontPointSize() == pytest.approx(DEFAULT_STYLE.number("h2", "size"))
        assert heading.fontWeight() == QFont.Weight.Bold
        code = format_of(doc, "listed code")
        assert code.fontPointSize() == pytest.approx(DEFAULT_STYLE.number("codeBlock", "size"))

    def test_paragraph_in_quote_in_list_uses_list_font_and_quote_color(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("list", "size", 15).with_value("blockQuote", "color", "#00aa00")
        fmt = format_of(render("- > inner", fonts, style).document, "inner")
        assert fmt.fontPointSize() == 15
        assert fmt.foreground().color() == QColor("#00aa00")

    @pytest.mark.parametrize(
        ("alignment", "flag"),
        [
            ("left", Qt.AlignmentFlag.AlignLeft),
            ("center", Qt.AlignmentFlag.AlignHCenter),
            ("right", Qt.AlignmentFlag.AlignRight),
            ("justify", Qt.AlignmentFlag.AlignJustify),
        ],
    )
    def test_alignment(self, fonts: FontResolver, alignment: str, flag: Qt.AlignmentFlag) -> None:
        style = DEFAULT_STYLE.with_value("body", "alignment", alignment)
        assert block_with_text(render("text", fonts, style).document, "text").blockFormat().alignment() & flag

    def test_link_underline_off_and_color(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("link", "underline", False).with_value("link", "color", "#ff0000")
        fmt = format_of(render("[site](https://e.com)", fonts, style).document, "site")
        assert not fmt.fontUnderline()
        assert fmt.foreground().color() == QColor("#ff0000")

    def test_code_block_background_and_rule_color(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("codeBlock", "background", "#010203")
        doc = render("```\ncode\n```", fonts, style).document
        frame = QTextCursor(block_with_text(doc, "code")).currentFrame()
        assert frame.frameFormat().background().color() == QColor("#010203")

    def test_marker_uses_marker_style(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("footnoteMarker", "background", "#123123").with_value(
            "footnoteMarker", "size", 12
        )
        doc = render("A[^n]\n\n[^n]: x", fonts, style).document
        fmt = char_format_at(doc, doc.toRawText().index("￼"))
        assert fmt.property(MARKER_BACKGROUND_PROPERTY) == "#123123"
        assert fmt.property(MARKER_POINT_SIZE_PROPERTY) == 12

    def test_lines_holding_images_may_grow(self, fonts: FontResolver, tmp_path: Path) -> None:
        image = QImage(10, 300, QImage.Format.Format_RGB32)
        image.fill(QColor("blue"))
        image.save(str(tmp_path / "tall.png"))
        doc = render("before ![t](tall.png) after", fonts, base_dir=tmp_path).document
        block_format = block_with_text(doc, "before").blockFormat()
        assert block_format.lineHeightType() == QTextBlockFormat.LineHeightTypes.MinimumHeight.value

    def test_nested_list_adds_no_space_but_the_list_after_does(self, fonts: FontResolver) -> None:
        style = DEFAULT_STYLE.with_value("list", "spaceAfter", 20).with_value("body", "spaceBefore", 1)
        doc = render("- outer\n  - inner\n- next\n\nafter", fonts, style).document
        assert block_with_text(doc, "inner").blockFormat().topMargin() == 0
        assert block_with_text(doc, "next").blockFormat().topMargin() == 0
        assert block_with_text(doc, "after").blockFormat().topMargin() == pytest.approx(px(21))

    def test_footnotes_and_citations_coexist(self, fonts: FontResolver) -> None:
        rendered = render("Note[^a] and cite [1].\n\n[^a]: footnote\n\n## Sources\n\n1. source", fonts)
        doc = rendered.document
        ids = [char_format_at(doc, i).anchorHref() for i, ch in enumerate(doc.toRawText()) if ch == "￼"]
        assert ids == ["mdmd-note:fn:1", "mdmd-note:cite:1"]


class TestUntrustedTooltips:
    def test_markup_in_a_link_address_is_shown_literally(self, fonts: FontResolver) -> None:
        # The parser percent-encodes markup in addresses, so build the link directly.
        href = '"><b>bold</b><a href="https://evil.example">click'
        document = Document(blocks=(Paragraph((Link(href, (Text("site"),)),)),))
        rendered = render_document(document, DEFAULT_STYLE, fonts)
        _alive.append(rendered)
        tooltip = format_of(rendered.document, "site").toolTip()
        assert "<b>" not in tooltip
        assert QTextDocumentFragment.fromHtml(tooltip).toPlainText() == href

    def test_markup_in_image_alt_text_is_shown_literally(self, fonts: FontResolver, tmp_path: Path) -> None:
        image = QImage(4, 4, QImage.Format.Format_RGB32)
        image.save(str(tmp_path / "p.png"))
        doc = render("![<i>alt</i>](p.png)", fonts, base_dir=tmp_path).document
        tooltip = char_format_at(doc, doc.toRawText().index("￼")).toolTip()
        assert QTextDocumentFragment.fromHtml(tooltip).toPlainText() == "<i>alt</i>"
