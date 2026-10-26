"""The recent files list: absolute paths, most recent first, no duplicates."""

from pathlib import Path

MAX_RECENT_FILES = 10


def add_recent(recent: tuple[str, ...], path: str) -> tuple[str, ...]:
    """Put `path` at the top, dropping any older entry for it and anything past the limit."""
    if not Path(path).is_absolute():
        raise ValueError("recent files must be absolute paths")
    others = tuple(p for p in recent if p != path)
    return (path, *others)[:MAX_RECENT_FILES]


def remove_recent(recent: tuple[str, ...], path: str) -> tuple[str, ...]:
    return tuple(p for p in recent if p != path)


def parse_recent(raw: object) -> tuple[str, ...]:
    """Read a stored list. A list that is not a list of strings is treated as empty."""
    if not isinstance(raw, list) or not all(isinstance(p, str) for p in raw):
        return ()
    result: tuple[str, ...] = ()
    for path in reversed(raw):
        if Path(path).is_absolute():
            result = add_recent(result, path)
    return result
