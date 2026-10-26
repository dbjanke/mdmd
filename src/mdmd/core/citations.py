"""Numbered citations: "[3]" in the text pointing at item 3 of a closing Sources list.

Research write-ups often cite this way instead of using Markdown footnotes. When a
document ends with a heading such as "Sources" followed by an ordered list, each
"[N]" whose N is in that list becomes a footnote marker showing item N. The list
itself stays in place.
"""

from __future__ import annotations

import re
from dataclasses import replace

from mdmd.core.document import (
    Block,
    BlockQuote,
    Document,
    Emphasis,
    Heading,
    Inline,
    ListBlock,
    ListItem,
    NoteRef,
    Paragraph,
    Strikethrough,
    Strong,
    Table,
    TableCell,
    Text,
)
from mdmd.core.inline_text import plain_text

SOURCE_LIST_HEADINGS = frozenset({"sources", "references", "citations", "notes"})
CITATION_ID_PREFIX = "cite:"
_CITATION = re.compile(r"\[(\d+)\]")


def citation_note_id(number: int) -> str:
    return f"{CITATION_ID_PREFIX}{number}"


def link_citations(document: Document) -> Document:
    sources = _closing_source_list(document.blocks)
    if sources is None:
        return document
    notes = {citation_note_id(sources.start + i): item.blocks for i, item in enumerate(sources.items)}
    linker = _Linker(valid_numbers=range(sources.start, sources.start + len(sources.items)))
    body = (*(linker.block(block) for block in document.blocks[:-1]), document.blocks[-1])
    linked_notes = {note_id: tuple(linker.block(b) for b in blocks) for note_id, blocks in document.notes.items()}
    return Document(blocks=body, notes=linked_notes | notes)


def _closing_source_list(blocks: tuple[Block, ...]) -> ListBlock | None:
    if len(blocks) < 2:
        return None
    heading, last = blocks[-2], blocks[-1]
    if not (isinstance(last, ListBlock) and last.ordered and last.items):
        return None
    if not (isinstance(heading, Heading) and plain_text(heading.inlines).strip().lower() in SOURCE_LIST_HEADINGS):
        return None
    return last


class _Linker:
    def __init__(self, valid_numbers: range) -> None:
        self._valid = valid_numbers

    def block(self, block: Block) -> Block:
        match block:
            case Paragraph(inlines):
                return Paragraph(self.inlines(inlines))
            case Heading():
                return replace(block, inlines=self.inlines(block.inlines))
            case BlockQuote(blocks):
                return BlockQuote(tuple(self.block(b) for b in blocks))
            case ListBlock():
                items = tuple(ListItem(tuple(self.block(b) for b in item.blocks), item.checked) for item in block.items)
                return replace(block, items=items)
            case Table():
                return replace(
                    block,
                    header=tuple(self._cell(c) for c in block.header),
                    rows=tuple(tuple(self._cell(c) for c in row) for row in block.rows),
                )
            case _:
                return block

    def _cell(self, cell: TableCell) -> TableCell:
        return TableCell(self.inlines(cell.inlines))

    def inlines(self, inlines: tuple[Inline, ...]) -> tuple[Inline, ...]:
        result: list[Inline] = []
        for inline in inlines:
            match inline:
                case Text(text):
                    result.extend(self._split(text))
                case Emphasis(children):
                    result.append(Emphasis(self.inlines(children)))
                case Strong(children):
                    result.append(Strong(self.inlines(children)))
                case Strikethrough(children):
                    result.append(Strikethrough(self.inlines(children)))
                case _:
                    # Code and link text are left alone: "[1]" there is not a citation.
                    result.append(inline)
        return tuple(result)

    def _split(self, text: str) -> list[Inline]:
        pieces: list[Inline] = []
        last_end = 0
        for match in _CITATION.finditer(text):
            number = int(match.group(1))
            if number not in self._valid:
                continue
            if match.start() > last_end:
                pieces.append(Text(text[last_end : match.start()]))
            pieces.append(NoteRef(note_id=citation_note_id(number), label=str(number)))
            last_end = match.end()
        if last_end < len(text):
            pieces.append(Text(text[last_end:]))
        return pieces
