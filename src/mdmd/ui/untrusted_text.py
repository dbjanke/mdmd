"""Showing untrusted text (file names, link addresses, document text) in Qt widgets as plain text.

Several Qt widgets guess whether a string is rich text: tooltips and message boxes
render it as HTML when it looks like markup, and menu items treat "&" as a
shortcut marker. Text from files or file names must never be interpreted that way.
"""

from PySide6.QtGui import Qt


def tooltip_text(text: str) -> str:
    """A tooltip that shows `text` literally. Qt renders tooltips that look like HTML as HTML."""
    return Qt.convertFromPlainText(text, Qt.WhiteSpaceMode.WhiteSpacePre)


def menu_text(text: str) -> str:
    """A menu item label that shows `text` literally. A single "&" would mark a keyboard shortcut."""
    return text.replace("&", "&&")
