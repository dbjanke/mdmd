"""Footnote markers drawn as pills inside the text.

A marker is one object character whose format carries its label and colors; this
handler measures and paints it.
"""

from PySide6.QtCore import QRect, QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPyTextObject,
    QTextCharFormat,
    QTextDocument,
    QTextFormat,
)

NOTE_MARKER_OBJECT_TYPE = QTextFormat.ObjectTypes.UserObject + 1
MARKER_LABEL_PROPERTY = QTextFormat.Property.UserProperty + 1
MARKER_FOREGROUND_PROPERTY = QTextFormat.Property.UserProperty + 2
MARKER_BACKGROUND_PROPERTY = QTextFormat.Property.UserProperty + 3
MARKER_POINT_SIZE_PROPERTY = QTextFormat.Property.UserProperty + 4
NOTE_ID_PROPERTY = QTextFormat.Property.UserProperty + 5
LINK_HREF_PROPERTY = QTextFormat.Property.UserProperty + 6

PILL_HORIZONTAL_PADDING = 0.5  # in label heights
PILL_VERTICAL_PADDING = 0.15
PILL_SIDE_GAP = 0.15  # space on each side of the pill, in label heights


def note_marker_format(
    *, note_id: str, label: str, foreground: str, background: str, point_size: float, anchor_href: str
) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setObjectType(NOTE_MARKER_OBJECT_TYPE)
    fmt.setProperty(MARKER_LABEL_PROPERTY, label)
    fmt.setProperty(MARKER_FOREGROUND_PROPERTY, foreground)
    fmt.setProperty(MARKER_BACKGROUND_PROPERTY, background)
    fmt.setProperty(MARKER_POINT_SIZE_PROPERTY, point_size)
    fmt.setProperty(NOTE_ID_PROPERTY, note_id)
    fmt.setAnchor(True)
    fmt.setAnchorHref(anchor_href)
    fmt.setVerticalAlignment(QTextCharFormat.VerticalAlignment.AlignMiddle)
    return fmt


def _label_font(fmt: QTextFormat) -> QFont:
    font = QFont()
    font.setPointSizeF(float(fmt.property(MARKER_POINT_SIZE_PROPERTY)))
    font.setBold(True)
    return font


class NoteMarkerHandler(QPyTextObject):
    def _metrics(self, fmt: QTextFormat) -> tuple[QFontMetricsF, float, float]:
        metrics = QFontMetricsF(_label_font(fmt))
        height = metrics.height() * (1 + 2 * PILL_VERTICAL_PADDING)
        width = (
            metrics.horizontalAdvance(str(fmt.property(MARKER_LABEL_PROPERTY)))
            + metrics.height() * 2 * PILL_HORIZONTAL_PADDING
        )
        return metrics, max(width, height), height

    def intrinsicSize(self, doc: QTextDocument, pos: int, fmt: QTextFormat) -> QSizeF:
        metrics, width, height = self._metrics(fmt)
        return QSizeF(width + 2 * PILL_SIDE_GAP * metrics.height(), height)

    def drawObject(
        self, painter: QPainter, rect: QRectF | QRect, doc: QTextDocument, pos: int, fmt: QTextFormat
    ) -> None:
        metrics, width, height = self._metrics(fmt)
        pill = QRectF(rect.left() + PILL_SIDE_GAP * metrics.height(), rect.top(), width, height)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(str(fmt.property(MARKER_BACKGROUND_PROPERTY))))
        painter.drawRoundedRect(pill, height / 2, height / 2)
        painter.setPen(QColor(str(fmt.property(MARKER_FOREGROUND_PROPERTY))))
        painter.setFont(_label_font(fmt))
        painter.drawText(pill, Qt.AlignmentFlag.AlignCenter, str(fmt.property(MARKER_LABEL_PROPERTY)))
        painter.restore()


def install_text_objects(document: QTextDocument) -> None:
    """Register the marker painter. The handler is parented to the document so it lives as long as it."""
    document.documentLayout().registerHandler(NOTE_MARKER_OBJECT_TYPE, NoteMarkerHandler(document))


def marker_label(fmt: QTextFormat) -> str | None:
    """The label of a footnote marker's format, or None if the format is not a marker."""
    if fmt.objectType() != NOTE_MARKER_OBJECT_TYPE:
        return None
    return str(fmt.property(MARKER_LABEL_PROPERTY))
