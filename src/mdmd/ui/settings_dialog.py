"""The settings dialog: themes, per-element properties, and a live preview.

Edits change only the dialog's draft and its preview. Apply (or OK) hands the
draft to the application, which saves it and restyles every window.
"""

from __future__ import annotations

from importlib.resources import files
from typing import Protocol

from PySide6.QtCore import QRect, QTimer
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from mdmd.core.cascade import popup_style
from mdmd.core.default_style import GENERIC_FAMILIES
from mdmd.core.document import Document
from mdmd.core.parser import parse_markdown
from mdmd.core.settings_draft import SettingsDraft
from mdmd.core.style import ELEMENTS, ElementSpec, InvalidValueError, Style
from mdmd.core.themes import Theme, ThemeLibrary, ThemeNameError, is_deletable, theme_status, validate_theme_name
from mdmd.ui.document_view import DocumentView
from mdmd.ui.fonts import FontResolver
from mdmd.ui.footnote_popup import FootnotePopup
from mdmd.ui.prompts import Prompts
from mdmd.ui.property_editors import PropertyEditor, make_editor
from mdmd.ui.renderer import RenderOptions, render_document

PREVIEW_DELAY_MS = 40
PREVIEW_MIN_WIDTH_PX = 420
DIALOG_SIZE = (1060, 680)


class SettingsHost(Protocol):
    @property
    def style(self) -> Style: ...

    @property
    def active_theme(self) -> str | None: ...

    @property
    def themes(self) -> ThemeLibrary: ...

    @property
    def fonts(self) -> FontResolver: ...

    @property
    def prompts(self) -> Prompts: ...

    def apply_settings(self, draft: SettingsDraft) -> None:
        """Raises OSError if the settings cannot be saved; nothing changes then."""
        ...

    def save_theme(self, theme: Theme) -> None:
        """Raises OSError if the theme cannot be saved."""
        ...

    def delete_theme(self, name: str) -> None:
        """Raises OSError if the theme cannot be deleted."""
        ...


def sample_document() -> Document:
    return parse_markdown(files("mdmd.ui").joinpath("resources/sample.md").read_text(encoding="utf-8"))


class SettingsDialog(QDialog):
    def __init__(self, host: SettingsHost, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(*DIALOG_SIZE)
        self._host = host
        self._draft = SettingsDraft(host.style, host.active_theme)
        self._sample = sample_document()
        self._families = sorted(set(QFontDatabase.families()) | GENERIC_FAMILIES, key=str.casefold)
        self._editors: dict[str, PropertyEditor] = {}
        self._popup: FootnotePopup | None = None

        layout = QVBoxLayout(self)
        layout.addLayout(self._build_theme_row())
        layout.addLayout(self._build_editing_area(), 1)
        layout.addWidget(self._build_buttons())

        self._element_list.setCurrentRow(0)
        self._refresh_theme_controls()
        self._render_preview()

    # -------------------------------------------------------------- layout

    def _build_theme_row(self) -> QHBoxLayout:
        self._theme_combo = QComboBox(self)
        self._theme_combo.setMinimumContentsLength(18)
        self._theme_combo.activated.connect(self._theme_chosen)
        self._save_theme = QPushButton("Save as Theme…", self)
        self._save_theme.clicked.connect(self._save_as_theme)
        self._delete_theme = QPushButton("Delete Theme", self)
        self._delete_theme.clicked.connect(self._delete_active_theme)
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme:", self))
        theme_row.addWidget(self._theme_combo)
        theme_row.addWidget(self._save_theme)
        theme_row.addWidget(self._delete_theme)
        theme_row.addStretch(1)

        return theme_row

    def _build_editing_area(self) -> QHBoxLayout:
        self._element_list = QListWidget(self)
        for element in ELEMENTS:
            self._element_list.addItem(element.label)
        self._element_list.setFixedWidth(self._element_list.sizeHintForColumn(0) + 32)
        self._element_list.currentRowChanged.connect(self._element_chosen)
        self._properties = QWidget(self)
        self._properties_layout = QFormLayout(self._properties)
        self._preview = DocumentView(self)
        self._preview.setMinimumWidth(PREVIEW_MIN_WIDTH_PX)
        self._preview.note_activated.connect(self._show_preview_note)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(PREVIEW_DELAY_MS)
        self._preview_timer.timeout.connect(self._render_preview)

        properties_column = QVBoxLayout()
        properties_column.addWidget(self._properties)
        properties_column.addStretch(1)
        middle = QHBoxLayout()
        middle.addWidget(self._element_list)
        middle.addLayout(properties_column, 0)
        middle.addWidget(self._preview, 1)

        return middle

    def _build_buttons(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).clicked.connect(self._ok)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self.apply)
        buttons.rejected.connect(self.reject)
        self._button_box = buttons

        return buttons

    # -------------------------------------------------------------- state

    @property
    def draft(self) -> SettingsDraft:
        return self._draft

    @property
    def theme_combo(self) -> QComboBox:
        return self._theme_combo

    @property
    def button_box(self) -> QDialogButtonBox:
        return self._button_box

    @property
    def save_theme_button(self) -> QPushButton:
        return self._save_theme

    @property
    def delete_theme_button(self) -> QPushButton:
        return self._delete_theme

    @property
    def editors(self) -> dict[str, PropertyEditor]:
        return self._editors

    @property
    def element_list(self) -> QListWidget:
        return self._element_list

    @property
    def preview(self) -> DocumentView:
        return self._preview

    def _set_draft(self, draft: SettingsDraft) -> None:
        self._draft = draft
        self._refresh_theme_controls()
        self._load_editor_values()
        self._preview_timer.start()

    # -------------------------------------------------------------- themes

    def refresh_themes(self) -> None:
        """Show the current theme list, after a theme was saved or deleted here or in another process."""
        self._refresh_theme_controls()

    def _refresh_theme_controls(self) -> None:
        library = self._host.themes
        status = theme_status(self._draft.style, self._draft.active_theme, library)
        combo = self._theme_combo
        combo.blockSignals(True)
        combo.clear()
        if status.name is None:
            combo.addItem(status.label, None)
        for theme in library.themes:
            combo.addItem(status.label if theme.name == status.name else theme.name, theme.name)
        combo.setCurrentIndex(0 if status.name is None else combo.findData(status.name))
        combo.blockSignals(False)
        self._delete_theme.setEnabled(is_deletable(status.name))

    def _theme_chosen(self, index: int) -> None:
        theme = self._host.themes.find(self._theme_combo.itemData(index))
        if theme is not None:
            self._set_draft(self._draft.load_theme(theme))

    def _save_as_theme(self) -> None:
        prompts = self._host.prompts
        initial = self._draft.active_theme if is_deletable(self._draft.active_theme) else ""
        name = prompts.ask_text(self, "Save as Theme", "Theme name:", initial or "")
        if name is None:
            return
        try:
            clean = validate_theme_name(name)
        except ThemeNameError as error:
            prompts.error(self, "Invalid theme name", str(error))
            return
        if self._host.themes.find(clean) is not None and not prompts.confirm(
            self, "Overwrite theme?", f'A theme named "{clean}" already exists. Replace it?'
        ):
            return
        try:
            self._host.save_theme(Theme(clean, self._draft.style))
        except OSError as error:
            prompts.error(self, "Cannot save theme", f"The theme could not be saved: {error.strerror or error}")
            return
        self._set_draft(self._draft.saved_as(clean))

    def _delete_active_theme(self) -> None:
        name = self._draft.active_theme
        if not is_deletable(name) or name is None:
            return
        prompts = self._host.prompts
        if not prompts.confirm(self, "Delete theme?", f'Delete the theme "{name}"? This cannot be undone.'):
            return
        try:
            self._host.delete_theme(name)
        except OSError as error:
            prompts.error(self, "Cannot delete theme", f"The theme could not be deleted: {error.strerror or error}")
            return
        self._set_draft(self._draft.theme_deleted(name))

    # -------------------------------------------------------------- element properties

    def _element_chosen(self, row: int) -> None:
        if row < 0:
            return
        element = ELEMENTS[row]
        while self._properties_layout.rowCount():
            self._properties_layout.removeRow(0)
        self._editors = {}
        for spec in element.properties:
            editor = make_editor(spec, self._families, self._properties)
            editor.value_edited.connect(lambda value, e=element, k=spec.key: self._value_edited(e, k, value))
            self._editors[spec.key] = editor
            self._properties_layout.addRow(f"{spec.label}:", editor)
        self._load_editor_values()

    def _current_element(self) -> ElementSpec:
        return ELEMENTS[max(0, self._element_list.currentRow())]

    def _load_editor_values(self) -> None:
        element = self._current_element()
        for key, editor in self._editors.items():
            editor.set_value(self._draft.style.value(element.key, key))

    def _value_edited(self, element: ElementSpec, key: str, value: object) -> None:
        try:
            draft = self._draft.with_value(element.key, key, value)
        except InvalidValueError:
            self._editors[key].set_value(self._draft.style.value(element.key, key))
            return
        self._draft = draft
        self._refresh_theme_controls()
        self._preview_timer.start()

    # -------------------------------------------------------------- preview

    def _render_preview(self) -> None:
        style = self._draft.style
        rendered = render_document(self._sample, style, self._host.fonts)
        bar = self._preview.verticalScrollBar()
        offset = bar.value()
        self._preview.show_rendered(rendered, style.text("page", "background"), style.text("body", "color"))
        bar.setValue(min(offset, bar.maximum()))

    def _show_preview_note(self, note_id: str, marker: QRect) -> None:
        blocks = self._sample.notes.get(note_id)
        if blocks is None:
            return
        style = popup_style(self._draft.style)
        rendered = render_document(
            Document(blocks, self._sample.notes), style, self._host.fonts, RenderOptions(popup=True)
        )
        if self._popup is None:
            self._popup = FootnotePopup(self)
        self._popup.show_note(rendered, style.text("page", "background"), style.text("body", "color"), marker)

    # -------------------------------------------------------------- buttons

    def apply(self) -> bool:
        try:
            self._host.apply_settings(self._draft)
        except OSError as error:
            self._host.prompts.error(
                self, "Cannot save settings", f"The settings could not be saved: {error.strerror or error}"
            )
            return False
        return True

    def _ok(self) -> None:
        if self.apply():
            self.accept()
