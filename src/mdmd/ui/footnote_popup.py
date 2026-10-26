"""The floating panel that shows one footnote's text beside its marker."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget

from mdmd.core.popup_placement import Rect, place_popup
from mdmd.ui.document_view import DocumentView
from mdmd.ui.renderer import RenderedDocument

POPUP_MAX_WIDTH_PX = 460
POPUP_MAX_HEIGHT_PX = 320
POPUP_SCREEN_MARGIN_PX = 8


class FootnotePopup(QFrame):
    """Closes on Esc or a click outside it (Qt popup behavior)."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.Box)
        self.setLineWidth(1)
        self._view = DocumentView(self)
        self._view.setFrameShape(QFrame.Shape.NoFrame)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)
        layout.addWidget(self._view)

    @property
    def view(self) -> DocumentView:
        return self._view

    def show_note(self, rendered: RenderedDocument, background: str, text_color: str, marker: QRect) -> None:
        screen = QGuiApplication.screenAt(marker.center()) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry().adjusted(
            POPUP_SCREEN_MARGIN_PX, POPUP_SCREEN_MARGIN_PX, -POPUP_SCREEN_MARGIN_PX, -POPUP_SCREEN_MARGIN_PX
        )
        self._view.show_rendered(rendered, background, text_color)
        chrome = 2 * (self.lineWidth() + 1)
        width = min(POPUP_MAX_WIDTH_PX, area.width())
        document = rendered.document
        document.setTextWidth(width - chrome)
        rendered.fit_images(width - chrome - 2 * document.documentMargin())
        height = min(int(document.size().height()) + chrome, POPUP_MAX_HEIGHT_PX, area.height())
        if height < document.size().height() + chrome:
            # Leave room for the scrollbar that a long footnote needs.
            document.setTextWidth(width - chrome - self._view.verticalScrollBar().sizeHint().width())
        self.resize(width, height)
        x, y = place_popup(
            Rect(marker.x(), marker.y(), marker.width(), marker.height()),
            width,
            height,
            Rect(area.x(), area.y(), area.width(), area.height()),
        )
        self.move(x, y)
        self._view.verticalScrollBar().setValue(0)
        self.show()
        self._view.setFocus()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)
