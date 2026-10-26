"""Where a footnote popup goes: beside its marker, kept on screen."""

from dataclasses import dataclass

POPUP_GAP_PX = 4  # between the marker and the popup


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


def place_popup(marker: Rect, width: int, height: int, screen: Rect) -> tuple[int, int]:
    """Top-left corner for a popup of `width` x `height`.

    Below the marker when it fits, otherwise above it, otherwise against the
    screen's bottom edge. Horizontally it starts at the marker and shifts left to
    stay on screen. A popup larger than the screen is pinned to its top-left.
    """
    below = marker.bottom + POPUP_GAP_PX
    above = marker.y - POPUP_GAP_PX - height
    if below + height <= screen.bottom:
        y = below
    elif above >= screen.y:
        y = above
    else:
        y = screen.bottom - height
    x = min(marker.x, screen.right - width)
    return (max(screen.x, x), max(screen.y, y))
