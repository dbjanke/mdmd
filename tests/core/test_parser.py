from mdmd.core.document import (
    BlockQuote,
    CellAlignment,
    CodeBlock,
    Emphasis,
    Heading,
    HorizontalRule,
    Image,
    InlineCode,
    LineBreak,
    Link,
    ListBlock,
    NoteRef,
    Paragraph,
    Strikethrough,
    Strong,
    Table,
    Text,
)
from mdmd.core.inline_text import plain_text
from mdmd.core.parser import parse_markdown


def only_paragraph(source: str) -> Paragraph:
    blocks = parse_markdown(source).blocks
    assert len(blocks) == 1
    assert isinstance(blocks[0], Paragraph)
    return blocks[0]


class TestHeadings:
    def test_atx_and_setext_levels(self) -> None:
        blocks = parse_markdown("# One\n\nTwo\n---\n\n###### Six\n\nAlso one\n===\n").blocks
        assert [b.level for b in blocks if isinstance(b, Heading)] == [1, 2, 6, 1]

    def test_anchors_are_unique_and_github_style(self) -> None:
        blocks = parse_markdown("## Key Findings\n\n## Key Findings\n\n## TL;DR\n").blocks
        assert [b.anchor for b in blocks if isinstance(b, Heading)] == ["key-findings", "key-findings-1", "tldr"]


class TestInlines:
    def test_emphasis_strong_strike_code(self) -> None:
        paragraph = only_paragraph("*a* **b** ~~c~~ `d`")
        assert paragraph.inlines == (
            Emphasis((Text("a"),)),
            Text(" "),
            Strong((Text("b"),)),
            Text(" "),
            Strikethrough((Text("c"),)),
            Text(" "),
            InlineCode("d"),
        )

    def test_soft_break_is_a_space_and_hard_break_is_kept(self) -> None:
        assert only_paragraph("a\nb").inlines == (Text("a"), Text(" "), Text("b"))
        assert only_paragraph("a  \nb").inlines == (Text("a"), LineBreak(), Text("b"))

    def test_links_and_autolinks(self) -> None:
        paragraph = only_paragraph("[site](https://e.com) and www.example.com and <https://x.org>")
        links = [i for i in paragraph.inlines if isinstance(i, Link)]
        assert [link.href for link in links] == ["https://e.com", "http://www.example.com", "https://x.org"]

    def test_angle_bracket_link_destination(self) -> None:
        paragraph = only_paragraph("[Help](<https://en.wikipedia.org/wiki/Help_(novel)>)")
        assert paragraph.inlines == (Link("https://en.wikipedia.org/wiki/Help_(novel)", (Text("Help"),)),)

    def test_image(self) -> None:
        assert only_paragraph("![a cat](img/cat.png)").inlines == (Image(src="img/cat.png", alt="a cat"),)

    def test_raw_html_is_literal_text(self) -> None:
        assert only_paragraph("a <b>bold</b>").inlines == (Text("a <b>bold</b>"),)

    def test_html_block_is_literal_text(self) -> None:
        paragraph = only_paragraph("<div>\nhi\n</div>")
        assert "<div>" in "".join(i.text for i in paragraph.inlines if isinstance(i, Text))


class TestBlocks:
    def test_front_matter_is_hidden(self) -> None:
        blocks = parse_markdown("---\ntitle: secret\n---\nBody\n").blocks
        assert blocks == (Paragraph((Text("Body"),)),)

    def test_fenced_and_indented_code(self) -> None:
        blocks = parse_markdown("```python\nx = 1\n```\n\n    indented\n").blocks
        assert blocks == (CodeBlock("x = 1"), CodeBlock("indented"))

    def test_nested_block_quotes(self) -> None:
        (outer,) = parse_markdown("> a\n>> b\n").blocks
        assert isinstance(outer, BlockQuote)
        assert isinstance(outer.blocks[1], BlockQuote)

    def test_ordered_list_start_and_nesting(self) -> None:
        (lst,) = parse_markdown("3. three\n4. four\n   - nested\n").blocks
        assert isinstance(lst, ListBlock)
        assert lst.ordered
        assert lst.start == 3
        nested = lst.items[1].blocks[1]
        assert isinstance(nested, ListBlock)
        assert not nested.ordered

    def test_task_list_states_and_text(self) -> None:
        (lst,) = parse_markdown("- [x] done\n- [ ] todo\n- plain\n").blocks
        assert isinstance(lst, ListBlock)
        assert [item.checked for item in lst.items] == [True, False, None]
        assert lst.items[0].blocks == (Paragraph((Text("done"),)),)

    def test_table_alignment_and_cells(self) -> None:
        (table,) = parse_markdown("| a | b | c |\n|:--|:-:|--:|\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |\n").blocks
        assert isinstance(table, Table)
        assert table.alignments == (CellAlignment.LEFT, CellAlignment.CENTER, CellAlignment.RIGHT)
        assert len(table.header) == 3
        assert len(table.rows) == 2
        assert table.rows[1][2].inlines == (Text("6"),)

    def test_table_without_alignment(self) -> None:
        (table,) = parse_markdown("| a |\n|---|\n| 1 |\n").blocks
        assert isinstance(table, Table)
        assert table.alignments == (CellAlignment.DEFAULT,)

    def test_horizontal_rule(self) -> None:
        assert parse_markdown("a\n\n---\n\nb").blocks[1] == HorizontalRule()

    def test_empty_document(self) -> None:
        assert parse_markdown("").blocks == ()


class TestFootnotes:
    SOURCE = (
        "The pairing.[^1] A second note follows.[^note] Again.[^1]\n\n"
        "[^note]: First paragraph of a longer note.\n\n"
        "    Second paragraph, indented four spaces.\n\n"
        "[^1]: *A Man Named Doll*, reviewed in the [Literary Review](https://example.com/review).\n"
    )

    def test_numbered_by_first_reference_and_repeat_reference_shares_number(self) -> None:
        document = parse_markdown(self.SOURCE)
        refs = [i for i in only_blocks_inlines(document.blocks) if isinstance(i, NoteRef)]
        assert [r.label for r in refs] == ["1", "2", "1"]
        assert refs[0].note_id == refs[2].note_id
        assert refs[0].note_id != refs[1].note_id

    def test_definitions_are_not_in_the_body(self) -> None:
        document = parse_markdown(self.SOURCE)
        assert len(document.blocks) == 1

    def test_note_content_keeps_formatting_and_paragraphs(self) -> None:
        document = parse_markdown(self.SOURCE)
        first = document.notes["fn:1"]
        assert isinstance(first[0], Paragraph)
        assert isinstance(first[0].inlines[0], Emphasis)
        assert any(isinstance(i, Link) for i in first[0].inlines)
        assert len(document.notes["fn:2"]) == 2

    def test_missing_definition_is_literal_and_unused_definition_is_dropped(self) -> None:
        document = parse_markdown("A claim.[^missing]\n\n[^unused]: Nobody references this.\n")
        assert document.blocks == (Paragraph((Text("A claim.[^missing]"),)),)
        assert document.notes == {}


def only_blocks_inlines(blocks: tuple[object, ...]) -> list[object]:
    return [inline for block in blocks if isinstance(block, Paragraph) for inline in block.inlines]


def test_plain_text_covers_every_inline_kind() -> None:
    paragraph = only_paragraph("*a* **b** ~~c~~ `d` [e](x) ![f](y.png) g  \nh[^n]\n\n[^n]: note")
    assert plain_text(paragraph.inlines) == "a b c d e f g h"
