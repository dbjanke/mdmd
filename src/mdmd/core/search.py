"""Find: locating matches in a document's text and stepping through them."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Match:
    start: int
    end: int


def find_matches(text: str, term: str, match_case: bool) -> tuple[Match, ...]:
    """Every non-overlapping occurrence of `term`. Positions index into `text` unchanged."""
    if not term:
        return ()
    # re.IGNORECASE keeps positions aligned with `text`; lowercasing would not
    # (some characters change length when case-folded).
    flags = 0 if match_case else re.IGNORECASE
    return tuple(Match(m.start(), m.end()) for m in re.finditer(re.escape(term), text, flags))


def first_at_or_after(matches: tuple[Match, ...], position: int) -> int | None:
    """Index of the first match starting at or after `position`, wrapping to the first match."""
    if not matches:
        return None
    for index, match in enumerate(matches):
        if match.start >= position:
            return index
    return 0


def step(index: int, count: int, forward: bool) -> int:
    """The next (or previous) match index, wrapping around."""
    if count <= 0:
        raise ValueError("cannot step through zero matches")
    return (index + (1 if forward else -1)) % count


def count_label(index: int | None, count: int) -> str:
    """'3 of 12' (1-based), or '0 of 0' when there are no matches."""
    if index is None or count == 0:
        return "0 of 0"
    return f"{index + 1} of {count}"
