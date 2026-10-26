"""One editing control per kind of style property."""

import re
from collections.abc import Sequence

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QWidget,
)

from mdmd.core.style import NUMBER_RANGES, Alignment, PropertyKind, PropertySpec, Value

NOT_INSTALLED_SUFFIX = " (not installed)"
SAME_AS_BODY_TEXT = "Same as body text"
SWATCH_STYLE = "QToolButton {{ background-color: {color}; border: 1px solid #888; min-width: 28px; }}"
_HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_NUMBER_FORMAT = {  # decimals, step
    PropertyKind.SIZE: (1, 0.5),
    PropertyKind.SPACE: (0, 1.0),
    PropertyKind.LINE_SPACING: (2, 0.05),
}


class PropertyEditor(QWidget):
    """Emits `value_edited` when the user changes the value; `set_value` never emits."""

    value_edited = Signal(object)

    def set_value(self, value: Value) -> None:
        raise NotImplementedError


class FontEditor(PropertyEditor):
    def __init__(self, families: Sequence[str], optional: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._families = list(families)
        self._combo = QComboBox(self)
        self._combo.setMaxVisibleItems(20)
        self._combo.currentIndexChanged.connect(self._emit_family)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo, 1)
        self._inherit: QCheckBox | None = None
        if optional:
            self._inherit = QCheckBox(SAME_AS_BODY_TEXT, self)
            self._inherit.toggled.connect(self._inherit_toggled)
            layout.addWidget(self._inherit)

    @property
    def combo(self) -> QComboBox:
        return self._combo

    @property
    def inherit_box(self) -> QCheckBox | None:
        """The "Same as body text" box, for optional fonts only."""
        return self._inherit

    def set_value(self, value: Value) -> None:
        family = value if isinstance(value, str) else None
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItems(self._families)
        if family is not None and family not in self._families:
            self._combo.addItem(family + NOT_INSTALLED_SUFFIX, family)
        if family is not None:
            index = self._combo.findData(family)
            self._combo.setCurrentIndex(index if index >= 0 else self._combo.findText(family))
        self._combo.blockSignals(False)
        if self._inherit is not None:
            self._inherit.blockSignals(True)
            self._inherit.setChecked(family is None)
            self._inherit.blockSignals(False)
            self._combo.setEnabled(family is not None)

    def _current_family(self) -> str:
        data = self._combo.currentData()
        return str(data) if data else self._combo.currentText()

    def _emit_family(self) -> None:
        self.value_edited.emit(self._current_family())

    def _inherit_toggled(self, inherit: bool) -> None:
        self._combo.setEnabled(not inherit)
        self.value_edited.emit(None if inherit else self._current_family())


class NumberEditor(PropertyEditor):
    """Out-of-range input is refused by the spin box, which keeps its previous value."""

    def __init__(self, kind: PropertyKind, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        number_range = NUMBER_RANGES[kind]
        decimals, step = _NUMBER_FORMAT[kind]
        self._spin = QDoubleSpinBox(self)
        self._spin.setRange(number_range.minimum, number_range.maximum)
        self._spin.setDecimals(decimals)
        self._spin.setSingleStep(step)
        if kind is not PropertyKind.LINE_SPACING:  # line spacing is a plain multiple of the font size
            self._spin.setSuffix(" pt")
        self._spin.valueChanged.connect(lambda v: self.value_edited.emit(float(v)))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._spin)
        layout.addStretch(1)

    @property
    def spin_box(self) -> QDoubleSpinBox:
        return self._spin

    def set_value(self, value: Value) -> None:
        self._spin.blockSignals(True)
        self._spin.setValue(float(value) if isinstance(value, int | float) else self._spin.minimum())
        self._spin.blockSignals(False)


class ColorEditor(PropertyEditor):
    """A swatch that opens a color picker, plus a hex field. An invalid hex value is reverted."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = "#000000"
        self._swatch = QToolButton(self)
        self._swatch.setToolTip("Choose color")
        self._swatch.clicked.connect(self._pick)
        self._hex = QLineEdit(self)
        self._hex.setMaxLength(7)
        self._hex.setFixedWidth(self._hex.fontMetrics().horizontalAdvance("#0000000") + 16)
        self._hex.editingFinished.connect(self._hex_edited)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._swatch)
        layout.addWidget(self._hex)
        layout.addStretch(1)

    @property
    def hex_field(self) -> QLineEdit:
        return self._hex

    def set_value(self, value: Value) -> None:
        self._value = str(value)
        self._hex.setText(self._value)
        self._swatch.setStyleSheet(SWATCH_STYLE.format(color=self._value))

    def _hex_edited(self) -> None:
        text = self._hex.text().strip()
        if not _HEX_COLOR.match(text):
            self._hex.setText(self._value)
            return
        if text.lower() != self._value:
            self._commit(text.lower())

    def _pick(self) -> None:
        color = QColorDialog.getColor(QColor(self._value), self, "Choose Color")
        if color.isValid():
            self._commit(color.name())

    def _commit(self, color: str) -> None:
        self.set_value(color)
        self.value_edited.emit(color)


class AlignmentEditor(PropertyEditor):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._combo = QComboBox(self)
        for alignment in Alignment:
            self._combo.addItem(alignment.value.capitalize(), alignment.value)
        self._combo.currentIndexChanged.connect(lambda _i: self.value_edited.emit(self._combo.currentData()))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo)
        layout.addStretch(1)

    @property
    def combo(self) -> QComboBox:
        return self._combo

    def set_value(self, value: Value) -> None:
        self._combo.blockSignals(True)
        self._combo.setCurrentIndex(max(0, self._combo.findData(value)))
        self._combo.blockSignals(False)


class FlagEditor(PropertyEditor):
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._check = QCheckBox(label, self)
        self._check.toggled.connect(lambda checked: self.value_edited.emit(bool(checked)))
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._check)

    @property
    def check_box(self) -> QCheckBox:
        return self._check

    def set_value(self, value: Value) -> None:
        self._check.blockSignals(True)
        self._check.setChecked(value is True)
        self._check.blockSignals(False)


def make_editor(spec: PropertySpec, families: Sequence[str], parent: QWidget | None = None) -> PropertyEditor:
    match spec.kind:
        case PropertyKind.FONT_FAMILY:
            return FontEditor(families, spec.optional, parent)
        case PropertyKind.SIZE | PropertyKind.SPACE | PropertyKind.LINE_SPACING:
            return NumberEditor(spec.kind, parent)
        case PropertyKind.COLOR:
            return ColorEditor(parent)
        case PropertyKind.ALIGNMENT:
            return AlignmentEditor(parent)
        case PropertyKind.FLAG:
            return FlagEditor("", parent)  # the form row already shows the label
