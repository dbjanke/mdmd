"""Finding headings in a document, wherever they are nested."""

from collections.abc import Iterable, Iterator

from mdmd.core.document import Block, BlockQuote, Heading, ListBlock


def iter_headings(blocks: Iterable[Block]) -> Iterator[Heading]:
    for block in blocks:
        match block:
            case Heading():
                yield block
            case BlockQuote(children):
                yield from iter_headings(children)
            case ListBlock(items=items):
                for item in items:
                    yield from iter_headings(item.blocks)
            case _:
                pass


def heading_anchors(blocks: Iterable[Block]) -> frozenset[str]:
    return frozenset(heading.anchor for heading in iter_headings(blocks))
