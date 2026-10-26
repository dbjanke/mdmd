"""Mapping stored font family names to fonts that are actually installed."""

from PySide6.QtGui import QFont, QFontDatabase

from mdmd.core.default_style import GENERIC_FAMILIES, MONO_FAMILY


class FontResolver:
    """A family that is not installed renders with the element's Default family; the stored value is kept."""

    def __init__(self) -> None:
        self._installed = frozenset(QFontDatabase.families())

    def is_available(self, family: str) -> bool:
        return family in self._installed or family in GENERIC_FAMILIES

    def font(self, family: str, fallback_family: str, point_size: float) -> QFont:
        chosen = family if self.is_available(family) else fallback_family
        font = QFont()
        font.setFamilies([chosen])
        font.setPointSizeF(point_size)
        if chosen == MONO_FAMILY:
            font.setStyleHint(QFont.StyleHint.Monospace)
        return font
