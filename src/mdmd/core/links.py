"""What links and image sources point at.

mdmd never opens links. The only navigation is a `#fragment` link scrolling to a
heading in the same document.
"""

from pathlib import Path
from urllib.parse import unquote, urlsplit

_LOCAL_SCHEMES = {"", "file"}


def heading_fragment(href: str) -> str | None:
    """The anchor a same-document link points at, lowercased like heading anchors, or None."""
    if not href.startswith("#") or len(href) == 1:
        return None
    return unquote(href[1:]).lower()


def resolve_image_path(src: str, base_dir: Path) -> Path | None:
    """The local file an image source names, or None for remote and unsupported sources.

    Relative paths resolve against the displayed file's folder; remote images are never fetched.
    """
    parts = urlsplit(src)
    if parts.scheme not in _LOCAL_SCHEMES or not parts.path:
        return None
    path = Path(unquote(parts.path))
    return path if path.is_absolute() else base_dir / path
