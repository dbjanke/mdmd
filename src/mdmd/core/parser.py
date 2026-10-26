"""Turn Markdown source into a `Document`.

markdown-it-py does the parsing (CommonMark plus GitHub-style extensions); this
module only translates its flat token stream into the document model.
"""

from __future__ import annotations

from collections.abc import Sequence

from markdown_it import MarkdownIt
from markdown_it.token import Token
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

from mdmd.core.citations import link_citations
from mdmd.core.document import (
    Block,
    BlockQuote,
    CellAlignment,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    HorizontalRule,
    Image,
    Inline,
    InlineCode,
    LineBreak,
    Link,
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
from mdmd.core.slugs import SlugAllocator

FOOTNOTE_ID_PREFIX = "fn:"
_TASK_CHECKBOX_CLASS = "task-list-item-checkbox"
_TASK_CHECKED_MARK = 'checked="checked"'
_ALIGNMENTS = {
    "text-align:left": CellAlignment.LEFT,
    "text-align:center": CellAlignment.CENTER,
    "text-align:right": CellAlignment.RIGHT,
}
_INLINE_CONTAINERS: dict[str, tuple[str, type[Emphasis] | type[Strong] | type[Strikethrough]]] = {
    "em_open": ("em_close", Emphasis),
    "strong_open": ("strong_close", Strong),
    "s_open": ("s_close", Strikethrough),
}


def _make_markdown_it() -> MarkdownIt:
    # Raw HTML is off, so tags in the source stay literal text.
    return (
        MarkdownIt("commonmark", {"html": False, "linkify": True})
        .enable(["table", "strikethrough", "linkify"])
        .use(front_matter_plugin)
        .use(footnote_plugin)
        .use(tasklists_plugin)
    )


_MARKDOWN = _make_markdown_it()


def parse_markdown(source: str) -> Document:
    tokens = _MARKDOWN.parse(source, {})
    builder = _BlockBuilder(tokens)
    blocks, notes = builder.build()
    return link_citations(Document(blocks=blocks, notes=notes))


def footnote_note_id(footnote_index: int) -> str:
    return f"{FOOTNOTE_ID_PREFIX}{footnote_index + 1}"


class _BlockBuilder:
    """Walks the block-level token stream, one container at a time."""

    def __init__(self, tokens: Sequence[Token]) -> None:
        self._tokens = tokens
        self._pos = 0
        self._slugs = SlugAllocator()

    def build(self) -> tuple[tuple[Block, ...], dict[str, tuple[Block, ...]]]:
        notes: dict[str, tuple[Block, ...]] = {}
        blocks: list[Block] = []
        while self._pos < len(self._tokens):
            token = self._tokens[self._pos]
            if token.type == "footnote_block_open":
                notes.update(self._footnote_block())
            else:
                block = self._block()
                if block is not None:
                    blocks.append(block)
        return tuple(blocks), notes

    # -- helpers

    def _next(self) -> Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def _blocks_until(self, close_type: str) -> tuple[Block, ...]:
        blocks: list[Block] = []
        while self._tokens[self._pos].type != close_type:
            block = self._block()
            if block is not None:
                blocks.append(block)
        self._next()  # the close token
        return tuple(blocks)

    # -- blocks

    def _block(self) -> Block | None:
        token = self._next()
        match token.type:
            case "paragraph_open":
                inline = self._next()
                self._next()  # paragraph_close
                return Paragraph(_inlines(inline.children or []))
            case "heading_open":
                inline = self._next()
                self._next()  # heading_close
                inlines = _inlines(inline.children or [])
                anchor = self._slugs.allocate(plain_text(inlines))
                return Heading(level=int(token.tag[1:]), inlines=inlines, anchor=anchor)
            case "fence" | "code_block":
                return CodeBlock(token.content.removesuffix("\n"))
            case "blockquote_open":
                return BlockQuote(self._blocks_until("blockquote_close"))
            case "bullet_list_open":
                return ListBlock(ordered=False, start=1, items=self._list_items("bullet_list_close"))
            case "ordered_list_open":
                start = int(str(token.attrs.get("start", 1)))
                return ListBlock(ordered=True, start=start, items=self._list_items("ordered_list_close"))
            case "table_open":
                return self._table()
            case "hr":
                return HorizontalRule()
            case _:
                # front_matter and anything without a visual form.
                return None

    def _list_items(self, close_type: str) -> tuple[ListItem, ...]:
        items: list[ListItem] = []
        while self._next().type != close_type:  # consumes list_item_open
            is_task = "task-list-item" in str(self._tokens[self._pos - 1].attrs.get("class", ""))
            checked = self._take_task_checkbox() if is_task else None
            items.append(ListItem(blocks=self._blocks_until("list_item_close"), checked=checked))
        return tuple(items)

    def _take_task_checkbox(self) -> bool | None:
        """Remove the checkbox token the tasklists plugin puts in the first inline, and report its state."""
        inline = self._tokens[self._pos + 1] if self._pos + 1 < len(self._tokens) else None
        if inline is None or inline.type != "inline" or not inline.children:
            return None
        first = inline.children[0]
        if first.type != "html_inline" or _TASK_CHECKBOX_CLASS not in first.content:
            return None
        checked = _TASK_CHECKED_MARK in first.content
        rest = inline.children[1:]
        if rest and rest[0].type == "text":
            rest[0].content = rest[0].content.removeprefix(" ")
        inline.children = rest
        return checked

    def _table(self) -> Table:
        alignments: list[CellAlignment] = []
        header: list[TableCell] = []
        rows: list[tuple[TableCell, ...]] = []
        row: list[TableCell] = []
        while (token := self._next()).type != "table_close":
            match token.type:
                case "th_open" | "td_open":
                    inline = self._next()
                    cell = TableCell(_inlines(inline.children or []))
                    if token.type == "th_open":
                        alignments.append(_ALIGNMENTS.get(str(token.attrs.get("style", "")), CellAlignment.DEFAULT))
                        header.append(cell)
                    else:
                        row.append(cell)
                case "tr_close" if row:
                    rows.append(tuple(row))
                    row = []
                case _:
                    pass
        return Table(alignments=tuple(alignments), header=tuple(header), rows=tuple(rows))

    def _footnote_block(self) -> dict[str, tuple[Block, ...]]:
        self._next()  # footnote_block_open
        notes: dict[str, tuple[Block, ...]] = {}
        while (token := self._next()).type != "footnote_block_close":
            if token.type == "footnote_open":
                notes[footnote_note_id(int(token.meta["id"]))] = self._blocks_until("footnote_close")
        return notes


# ------------------------------------------------------------------ inline content


def _inlines(tokens: Sequence[Token]) -> tuple[Inline, ...]:
    result, _ = _inline_run(tokens, 0, close_type=None)
    return result


def _inline_run(tokens: Sequence[Token], pos: int, close_type: str | None) -> tuple[tuple[Inline, ...], int]:
    """Collect inlines from `pos` up to `close_type` (or the end). Returns them and the position after."""
    result: list[Inline] = []
    while pos < len(tokens):
        token = tokens[pos]
        pos += 1
        if token.type == close_type:
            break
        match token.type:
            case "text" | "html_inline":
                result.append(Text(token.content))
            case "softbreak":
                result.append(Text(" "))
            case "hardbreak":
                result.append(LineBreak())
            case "code_inline":
                result.append(InlineCode(token.content))
            case "link_open":
                children, pos = _inline_run(tokens, pos, "link_close")
                result.append(Link(href=str(token.attrs.get("href", "")), children=children))
            case "image":
                result.append(Image(src=str(token.attrs.get("src", "")), alt=token.content))
            case "footnote_ref":
                index = int(token.meta["id"])
                result.append(NoteRef(note_id=footnote_note_id(index), label=str(index + 1)))
            case kind if kind in _INLINE_CONTAINERS:
                close, container = _INLINE_CONTAINERS[kind]
                children, pos = _inline_run(tokens, pos, close)
                result.append(container(children))
            case _:
                # footnote_anchor and other tokens with no visual form.
                pass
    return tuple(result), pos
