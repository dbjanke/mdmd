"""GitHub-style heading anchors, so `[see](#key-findings)` can find its heading."""

import re

_DISALLOWED = re.compile(r"[^\w\- ]", re.UNICODE)


def slugify(heading_text: str) -> str:
    """Lowercase, drop punctuation, and turn spaces into hyphens."""
    return _DISALLOWED.sub("", heading_text.strip().lower()).replace(" ", "-")


class SlugAllocator:
    """Hands out unique anchors in document order: `intro`, `intro-1`, `intro-2`, ..."""

    def __init__(self) -> None:
        self._used: set[str] = set()

    def allocate(self, heading_text: str) -> str:
        base = slugify(heading_text)
        candidate = base
        suffix = 0
        while candidate in self._used:
            suffix += 1
            candidate = f"{base}-{suffix}"
        self._used.add(candidate)
        return candidate
