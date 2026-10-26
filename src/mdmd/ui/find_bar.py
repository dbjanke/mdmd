"""The find bar: a search field, Previous/Next, Match case, a match count, and a close button."""

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget

FAILED_FIELD_STYLE = "QLineEdit { background-color: #f8d7da; color: #58151c; }"
FIELD_MIN_WIDTH_PX = 220


class FindBar(QWidget):
    search_changed = Signal()
    next_requested = Signal()
    previous_requested = Signal()
    closed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._field = QLineEdit(self)
        self._field.setPlaceholderText("Find")
        self._field.setClearButtonEnabled(True)
        self._field.setMinimumWidth(FIELD_MIN_WIDTH_PX)
        self._field.textChanged.connect(self.search_changed)
        self._field.installEventFilter(self)
        previous = QToolButton(self)
        previous.setText("Previous")
        previous.clicked.connect(self.previous_requested)
        following = QToolButton(self)
        following.setText("Next")
        following.clicked.connect(self.next_requested)
        self._match_case = QCheckBox("Match case", self)
        self._match_case.toggled.connect(self.search_changed)
        self._count = QLabel("0 of 0", self)
        close = QToolButton(self)
        close.setText("✕")
        close.setToolTip("Close find bar (Esc)")
        close.setAutoRaise(True)
        close.clicked.connect(self.close_bar)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        for widget in (self._field, previous, following, self._match_case, self._count):
            layout.addWidget(widget)
        layout.addStretch(1)
        layout.addWidget(close)
        self.hide()

    @property
    def field(self) -> QLineEdit:
        return self._field

    @property
    def match_case_box(self) -> QCheckBox:
        return self._match_case

    @property
    def count_text(self) -> str:
        return self._count.text()

    @property
    def term(self) -> str:
        return self._field.text()

    @property
    def match_case(self) -> bool:
        return self._match_case.isChecked()

    def open_bar(self) -> None:
        self.show()
        self._field.setFocus()
        self._field.selectAll()

    def close_bar(self) -> None:
        self.hide()
        self.closed.emit()

    def show_result(self, label: str, failed: bool) -> None:
        self._count.setText(label)
        self._field.setStyleSheet(FAILED_FIELD_STYLE if failed else "")

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._field and event.type() == QEvent.Type.KeyPress and isinstance(event, QKeyEvent):
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                shifted = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                (self.previous_requested if shifted else self.next_requested).emit()
                return True
            if event.key() == Qt.Key.Key_Escape:
                self.close_bar()
                return True
        return super().eventFilter(watched, event)
