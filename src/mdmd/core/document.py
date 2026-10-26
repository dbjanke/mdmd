"""The rendered-document model: what a Markdown file means, independent of any toolkit."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

# ---------------------------------------------------------------- inline content


@dataclass(frozen=True)
class Text:
    text: str


@dataclass(frozen=True)
class Emphasis:
    children: tuple[Inline, ...]


@dataclass(frozen=True)
class Strong:
    children: tuple[Inline, ...]


@dataclass(frozen=True)
class Strikethrough:
    children: tuple[Inline, ...]


@dataclass(frozen=True)
class InlineCode:
    text: str


@dataclass(frozen=True)
class Link:
    href: str
    children: tuple[Inline, ...]


@dataclass(frozen=True)
class Image:
    src: str
    alt: str


@dataclass(frozen=True)
class NoteRef:
    """A footnote marker. `note_id` keys into `Document.notes`; `label` is what the marker shows."""

    note_id: str
    label: str


@dataclass(frozen=True)
class LineBreak:
    """A hard line break inside a block."""


type Inline = Text | Emphasis | Strong | Strikethrough | InlineCode | Link | Image | NoteRef | LineBreak

# ----------------------------------------------------------------- block content


class CellAlignment(Enum):
    DEFAULT = "default"
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@dataclass(frozen=True)
class Paragraph:
    inlines: tuple[Inline, ...]


@dataclass(frozen=True)
class Heading:
    level: int
    inlines: tuple[Inline, ...]
    anchor: str


@dataclass(frozen=True)
class CodeBlock:
    text: str


@dataclass(frozen=True)
class BlockQuote:
    blocks: tuple[Block, ...]


@dataclass(frozen=True)
class ListItem:
    blocks: tuple[Block, ...]
    checked: bool | None = None  # None: not a task item


@dataclass(frozen=True)
class ListBlock:
    ordered: bool
    start: int
    items: tuple[ListItem, ...]


@dataclass(frozen=True)
class TableCell:
    inlines: tuple[Inline, ...]


@dataclass(frozen=True)
class Table:
    alignments: tuple[CellAlignment, ...]
    header: tuple[TableCell, ...]
    rows: tuple[tuple[TableCell, ...], ...]


@dataclass(frozen=True)
class HorizontalRule:
    pass


type Block = Paragraph | Heading | CodeBlock | BlockQuote | ListBlock | Table | HorizontalRule


@dataclass(frozen=True)
class Document:
    blocks: tuple[Block, ...]
    notes: dict[str, tuple[Block, ...]] = field(default_factory=dict)
