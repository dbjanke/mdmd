"""Plain-text views of inline content."""

from collections.abc import Iterable

from mdmd.core.document import (
    Emphasis,
    Image,
    Inline,
    InlineCode,
    LineBreak,
    Link,
    NoteRef,
    Strikethrough,
    Strong,
    Text,
)


def plain_text(inlines: Iterable[Inline]) -> str:
    """The visible text of `inlines`, without markers or formatting."""
    parts: list[str] = []
    for inline in inlines:
        match inline:
            case Text(text) | InlineCode(text):
                parts.append(text)
            case Emphasis(children) | Strong(children) | Strikethrough(children) | Link(_, children):
                parts.append(plain_text(children))
            case Image(_, alt):
                parts.append(alt)
            case LineBreak():
                parts.append(" ")
            case NoteRef():
                pass
    return "".join(parts)
