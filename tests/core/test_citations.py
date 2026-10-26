from mdmd.core.document import Emphasis, Link, NoteRef, Paragraph, Text
from mdmd.core.parser import parse_markdown

SOURCES = "\n\n## Sources\n\n1. [First](https://a.example)\n2. [Second](https://b.example)\n"


def body_inlines(source: str) -> tuple[object, ...]:
    first = parse_markdown(source).blocks[0]
    assert isinstance(first, Paragraph)
    return first.inlines


def test_escaped_and_plain_brackets_become_markers() -> None:
    inlines = body_inlines("Claim.\\[1\\]\\[2\\] More [1]." + SOURCES)
    assert inlines == (
        Text("Claim."),
        NoteRef("cite:1", "1"),
        NoteRef("cite:2", "2"),
        Text(" More "),
        NoteRef("cite:1", "1"),
        Text("."),
    )


def test_note_holds_the_source_item() -> None:
    document = parse_markdown("Claim [2]." + SOURCES)
    (paragraph,) = document.notes["cite:2"]
    assert isinstance(paragraph, Paragraph)
    assert paragraph.inlines == (Link("https://b.example", (Text("Second"),)),)


def test_sources_list_stays_visible() -> None:
    document = parse_markdown("Claim [1]." + SOURCES)
    assert len(document.blocks) == 3


def test_numbers_outside_the_list_stay_literal() -> None:
    assert body_inlines("See [3] and [0]." + SOURCES) == (Text("See [3] and [0]."),)


def test_citations_inside_emphasis_are_linked_but_not_inside_code_or_links() -> None:
    inlines = body_inlines("*x [1]* `y [1]` [z [1]](https://e.com)" + SOURCES)
    assert inlines[0] == Emphasis((Text("x "), NoteRef("cite:1", "1")))
    assert "[1]" in str(inlines[2])
    assert isinstance(inlines[4], Link)
    assert inlines[4].children == (Text("z [1]"),)


def test_no_source_heading_means_no_citations() -> None:
    assert body_inlines("Claim [1].\n\n## Further reading\n\n1. A\n") == (Text("Claim [1]."),)


def test_source_list_must_be_last() -> None:
    source = "Claim [1].\n\n## References\n\n1. A\n\nTrailing paragraph.\n"
    assert body_inlines(source) == (Text("Claim [1]."),)


def test_unordered_source_list_does_not_count() -> None:
    assert body_inlines("Claim [1].\n\n## Notes\n\n- A\n") == (Text("Claim [1]."),)


def test_heading_match_ignores_case_and_honours_list_start() -> None:
    inlines = body_inlines("Claim [5].\n\n# REFERENCES\n\n5. Five\n")
    assert inlines[1] == NoteRef("cite:5", "5")


def test_citations_in_nested_blocks_are_linked() -> None:
    source = "# Head [1]\n\n> quoted [1]\n\n- item [2]\n\n| h [1] |\n|---|\n| c [2] |" + SOURCES
    rendered = str(parse_markdown(source).blocks)
    assert rendered.count("NoteRef(") == 5


def test_citations_inside_footnotes_are_linked() -> None:
    document = parse_markdown("Claim.[^n]\n\n[^n]: See [2]." + SOURCES)
    assert "NoteRef(note_id='cite:2'" in str(document.notes["fn:1"])
