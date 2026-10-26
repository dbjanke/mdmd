"""Building a Qt text document from a `Document` and a `Style`.

Qt combines adjacent block margins by taking the larger one, but mdmd's spacing
is additive. So every element gets its whole gap (previous element's space after
plus its own space before) as its top margin, and bottom margins stay zero.
One exception: Qt ignores the top margin of a block that directly follows a
frame (code block, block quote, table), so that gap goes on the frame's bottom
margin instead.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QTextFormat,
    QTextFrame,
    QTextFrameFormat,
    QTextImageFormat,
    QTextLength,
    QTextList,
    QTextListFormat,
    QTextTableCellFormat,
    QTextTableFormat,
)

from mdmd.core.cascade import Container, TextStyle, element_text_style, paragraph_text_style, table_text_style
from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.document import (
    Block,
    BlockQuote,
    CellAlignment,
    CodeBlock,
    Document,
    Emphasis,
    Heading,
    HorizontalRule,
    Image,
    Inline,
    InlineCode,
    LineBreak,
    Link,
    ListBlock,
    NoteRef,
    Paragraph,
    Strikethrough,
    Strong,
    Table,
    Text,
)
from mdmd.core.headings import heading_anchors
from mdmd.core.inline_text import plain_text
from mdmd.core.links import heading_fragment, resolve_image_path
from mdmd.core.style import Alignment, Style
from mdmd.core.zoom import ZOOM_DEFAULT_PERCENT
from mdmd.ui.fonts import FontResolver
from mdmd.ui.text_objects import LINK_HREF_PROPERTY, install_text_objects, note_marker_format
from mdmd.ui.untrusted_text import tooltip_text

PX_PER_PT = 96 / 72  # Qt lays out block margins and fixed line heights in 96-dpi pixels
PAGE_MARGIN_PT = 18
INDENT_WIDTH_PT = 18
CODE_PADDING_PT = 6
QUOTE_PADDING_PT = 8
TABLE_CELL_PADDING_PT = 4
TABLE_BORDER_PX = 1
RULE_THICKNESS_PT = 1
NOTE_HREF_PREFIX = "mdmd-note:"
IMAGE_URL_PREFIX = "mdmd-image:"
LINE_SEPARATOR = "\u2028"

_ALIGNMENTS = {
    Alignment.LEFT: Qt.AlignmentFlag.AlignLeft,
    Alignment.CENTER: Qt.AlignmentFlag.AlignHCenter,
    Alignment.RIGHT: Qt.AlignmentFlag.AlignRight,
    Alignment.JUSTIFY: Qt.AlignmentFlag.AlignJustify,
}
_CELL_ALIGNMENTS = {
    CellAlignment.LEFT: Qt.AlignmentFlag.AlignLeft,
    CellAlignment.CENTER: Qt.AlignmentFlag.AlignHCenter,
    CellAlignment.RIGHT: Qt.AlignmentFlag.AlignRight,
}
_BULLETS = (QTextListFormat.Style.ListDisc, QTextListFormat.Style.ListCircle, QTextListFormat.Style.ListSquare)


@dataclass(frozen=True)
class RenderOptions:
    zoom_percent: int = ZOOM_DEFAULT_PERCENT
    base_dir: Path | None = None  # folder relative image paths resolve against; None loads no images
    # Footnote popup content: nothing is clickable (markers become plain "[n]" text, no link is an
    # anchor), and each link's address is written after its text so it can be selected.
    popup: bool = False


@dataclass(frozen=True)
class PlacedImage:
    position: int
    natural_size: QSize
    indent_px: float


@dataclass
class RenderedDocument:
    document: QTextDocument
    anchors: dict[str, int] = field(default_factory=dict)  # heading anchor -> document position
    images: list[PlacedImage] = field(default_factory=list)

    def fit_images(self, text_width: float) -> None:
        """Scale images wider than the text column down to fit; never scale up."""
        for image in self.images:
            natural = image.natural_size
            width = min(float(natural.width()), max(1.0, text_width - image.indent_px))
            cursor = QTextCursor(self.document)
            cursor.setPosition(image.position)
            cursor.movePosition(QTextCursor.MoveOperation.NextCharacter, QTextCursor.MoveMode.KeepAnchor)
            fmt = cursor.charFormat().toImageFormat()
            fmt.setWidth(width)
            fmt.setHeight(natural.height() * width / natural.width())
            cursor.setCharFormat(fmt)


def render_document(
    document: Document, style: Style, fonts: FontResolver, options: RenderOptions | None = None
) -> RenderedDocument:
    return _Writer(document, style, fonts, options or RenderOptions()).render()


@dataclass(frozen=True)
class _Context:
    containers: tuple[Container, ...] = ()
    indent: int = 0  # list nesting level, for indentation

    @property
    def in_list(self) -> bool:
        return Container.LIST in self.containers


@dataclass
class _ListMembership:
    """Joins each item's first block to one Qt list, creating the list on the first item."""

    list_format: QTextListFormat
    checked: bool | None = None
    _qt_list: QTextList | None = None

    def attach(self, cursor: QTextCursor) -> None:
        if self._qt_list is None:
            self._qt_list = cursor.createList(self.list_format)
        else:
            self._qt_list.add(cursor.block())


class _Writer:
    def __init__(self, document: Document, style: Style, fonts: FontResolver, options: RenderOptions) -> None:
        self._source = document
        self._style = style
        self._fonts = fonts
        self._options = options
        self._anchors_in_document = heading_anchors(document.blocks)
        self._result = RenderedDocument(QTextDocument())
        self._doc = self._result.document
        self._doc.setUndoRedoEnabled(False)
        self._doc.setDocumentMargin(self._px(PAGE_MARGIN_PT))
        self._doc.setIndentWidth(self._px(INDENT_WIDTH_PT))
        body = element_text_style(style, "body")
        self._doc.setDefaultFont(self._font(body.font_family, "body", body.size))
        install_text_objects(self._doc)
        self._cursor = QTextCursor(self._doc)
        self._fresh = True  # the cursor's block is empty and unclaimed (document start, or just after a frame)
        self._at_start = True  # first element of the document or of a frame: no previous space after
        self._pending_after = 0.0
        self._frame_just_left: QTextFrame | None = None
        self._image_count = 0

    # ------------------------------------------------------------ units and formats

    def _pt(self, points: float) -> float:
        """A point size scaled by zoom."""
        return points * self._options.zoom_percent / 100

    def _px(self, points: float) -> float:
        return self._pt(points) * PX_PER_PT

    def _font(self, family: str, element: str, size: float) -> QFont:
        fallback = DEFAULT_STYLE.optional_text(element, "fontFamily") or DEFAULT_STYLE.text("body", "fontFamily")
        return self._fonts.font(family, fallback, self._pt(size))

    def _char_format(self, text: TextStyle, element: str) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFont(self._font(text.font_family, element, text.size))
        fmt.setForeground(QBrush(QColor(text.color)))
        return fmt

    def _block_format(self, text: TextStyle, space_before: float, allow_taller_lines: bool) -> QTextBlockFormat:
        fmt = QTextBlockFormat()
        fmt.setAlignment(_ALIGNMENTS[text.alignment])
        # Line spacing is a multiple of the font size. Lines holding images may grow to fit them.
        height_type = (
            QTextBlockFormat.LineHeightTypes.MinimumHeight
            if allow_taller_lines
            else (QTextBlockFormat.LineHeightTypes.FixedHeight)
        )
        fmt.setLineHeight(self._px(text.size * text.line_spacing), height_type.value)
        fmt.setTopMargin(self._top_margin(space_before))
        fmt.setBottomMargin(0)
        return fmt

    def _gap_px(self, space_before: float) -> float:
        gap = space_before if self._at_start else self._pending_after + space_before
        return self._px(gap)

    def _top_margin(self, space_before: float) -> float:
        """Top margin for a block, moving the gap onto the frame just before it if there is one."""
        gap = self._gap_px(space_before)
        frame = self._frame_just_left
        if frame is None:
            return gap
        self._frame_just_left = None
        frame_format = frame.frameFormat()
        frame_format.setBottomMargin(gap)
        frame.setFrameFormat(frame_format)
        return 0.0

    def _frame_top_margin(self, space_before: float) -> float:
        self._frame_just_left = None
        return self._gap_px(space_before)

    def _finish_element(self, space_after: float) -> None:
        self._pending_after = space_after
        self._at_start = False

    # ------------------------------------------------------------ block plumbing

    def _start_block(self, block_format: QTextBlockFormat, char_format: QTextCharFormat) -> None:
        if self._fresh:
            current_list = self._cursor.currentList()
            if current_list is not None:
                current_list.remove(self._cursor.block())
            self._cursor.setBlockFormat(block_format)
            self._cursor.setBlockCharFormat(char_format)
            self._fresh = False
        else:
            self._cursor.insertBlock(block_format, char_format)
        self._cursor.setCharFormat(char_format)

    def _collapse_fresh_block(self) -> None:
        """Make an unclaimed empty block take no space, before a frame is placed after it."""
        if not self._fresh:
            return
        current_list = self._cursor.currentList()
        if current_list is not None:
            current_list.remove(self._cursor.block())
        fmt = QTextBlockFormat()
        fmt.setLineHeight(0, QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        self._cursor.setBlockFormat(fmt)
        tiny = QTextCharFormat()
        tiny.setFontPointSize(1)
        self._cursor.setBlockCharFormat(tiny)

    def _enter_frame(self, frame_format: QTextFrameFormat) -> QTextFrame:
        self._collapse_fresh_block()
        frame = self._cursor.insertFrame(frame_format)
        self._fresh = True
        self._at_start = True
        return frame

    def _leave(self, frame: QTextFrame) -> None:
        self._cursor.setPosition(frame.lastPosition())
        self._cursor.movePosition(QTextCursor.MoveOperation.NextBlock)
        self._fresh = True
        self._at_start = False
        self._frame_just_left = frame

    def _frame_format(self, background: str, padding_pt: float, space_before: float, ctx: _Context) -> QTextFrameFormat:
        fmt = QTextFrameFormat()
        fmt.setBackground(QBrush(QColor(background)))
        fmt.setPadding(self._px(padding_pt))
        fmt.setTopMargin(self._frame_top_margin(space_before))
        fmt.setBottomMargin(0)
        fmt.setLeftMargin(ctx.indent * self._doc.indentWidth())
        return fmt

    # ------------------------------------------------------------ blocks

    def render(self) -> RenderedDocument:
        self._blocks(self._source.blocks, _Context())
        self._collapse_fresh_block()
        return self._result

    def _blocks(self, blocks: tuple[Block, ...], ctx: _Context) -> None:
        for block in blocks:
            self._block(block, ctx)

    def _block(self, block: Block, ctx: _Context) -> None:
        match block:
            case Paragraph(inlines):
                self._paragraph(inlines, ctx)
            case Heading():
                self._heading(block, ctx)
            case CodeBlock(text):
                self._code_block(text, ctx)
            case BlockQuote(children):
                self._block_quote(children, ctx)
            case ListBlock():
                self._list(block, ctx)
            case Table():
                self._table(block, ctx)
            case HorizontalRule():
                self._rule(ctx)

    def _paragraph(
        self,
        inlines: tuple[Inline, ...],
        ctx: _Context,
        spacing: tuple[float, float] | None = None,
        membership: _ListMembership | None = None,
    ) -> None:
        text = paragraph_text_style(self._style, ctx.containers)
        element = "list" if ctx.in_list else "body"
        if spacing is None:
            spacing = (
                (0.0, 0.0)
                if ctx.in_list
                else (
                    self._style.number("body", "spaceBefore"),
                    self._style.number("body", "spaceAfter"),
                )
            )
        block_format = self._block_format(text, spacing[0], allow_taller_lines=_has_image(inlines))
        if membership is None:
            block_format.setIndent(ctx.indent)
        elif membership.checked is not None:
            marker = (
                QTextBlockFormat.MarkerType.Checked if membership.checked else QTextBlockFormat.MarkerType.Unchecked
            )
            block_format.setMarker(marker)
        char_format = self._char_format(text, element)
        self._start_block(block_format, char_format)
        if membership is not None:
            membership.attach(self._cursor)
        self._inlines(inlines, char_format, ctx)
        self._finish_element(spacing[1])

    def _heading(self, heading: Heading, ctx: _Context) -> None:
        element = f"h{heading.level}"
        text = element_text_style(self._style, element)
        block_format = self._block_format(text, self._style.number(element, "spaceBefore"), _has_image(heading.inlines))
        block_format.setIndent(ctx.indent)
        block_format.setHeadingLevel(heading.level)
        char_format = self._char_format(text, element)
        char_format.setFontWeight(QFont.Weight.Bold)
        self._start_block(block_format, char_format)
        self._result.anchors.setdefault(heading.anchor, self._cursor.block().position())
        self._inlines(heading.inlines, char_format, ctx)
        self._finish_element(self._style.number(element, "spaceAfter"))

    def _code_block(self, code: str, ctx: _Context) -> None:
        s = self._style
        frame = self._enter_frame(
            self._frame_format(
                s.text("codeBlock", "background"), CODE_PADDING_PT, s.number("codeBlock", "spaceBefore"), ctx
            )
        )
        text = TextStyle(
            font_family=s.text("codeBlock", "fontFamily"),
            size=s.number("codeBlock", "size"),
            color=s.text("codeBlock", "color"),
            line_spacing=s.number("codeBlock", "lineSpacing"),
            alignment=Alignment.LEFT,
        )
        char_format = self._char_format(text, "codeBlock")
        self._start_block(self._block_format(text, 0, allow_taller_lines=False), char_format)
        self._cursor.insertText(code.replace("\n", LINE_SEPARATOR), char_format)
        self._leave(frame)
        self._finish_element(s.number("codeBlock", "spaceAfter"))

    def _block_quote(self, children: tuple[Block, ...], ctx: _Context) -> None:
        s = self._style
        frame = self._enter_frame(
            self._frame_format(
                s.text("blockQuote", "background"), QUOTE_PADDING_PT, s.number("blockQuote", "spaceBefore"), ctx
            )
        )
        self._blocks(children, _Context(containers=(*ctx.containers, Container.BLOCK_QUOTE)))
        self._leave(frame)
        self._finish_element(s.number("blockQuote", "spaceAfter"))

    def _list(self, block: ListBlock, ctx: _Context) -> None:
        nested = ctx.in_list
        before = 0.0 if nested else self._style.number("list", "spaceBefore")
        after = 0.0 if nested else self._style.number("list", "spaceAfter")
        list_format = QTextListFormat()
        if block.ordered:
            list_format.setStyle(QTextListFormat.Style.ListDecimal)
            list_format.setStart(block.start)
        else:
            list_format.setStyle(_BULLETS[ctx.indent % len(_BULLETS)])
        list_format.setIndent(ctx.indent + 1)
        inner = _Context(containers=(*ctx.containers, Container.LIST), indent=ctx.indent + 1)
        membership = _ListMembership(list_format)
        for index, item in enumerate(block.items):
            children = item.blocks
            first: Paragraph = children[0] if children and isinstance(children[0], Paragraph) else Paragraph(())
            rest = children[1:] if children and children[0] is first else children
            membership.checked = item.checked
            spacing = (before if index == 0 else 0.0, 0.0)
            self._paragraph(first.inlines, inner, spacing=spacing, membership=membership)
            self._blocks(rest, inner)
        self._finish_element(after)

    def _table(self, table: Table, ctx: _Context) -> None:
        s = self._style
        columns = max([len(table.header), *(len(row) for row in table.rows)])
        if columns == 0:
            return
        table_format = QTextTableFormat()
        table_format.setBorder(TABLE_BORDER_PX)
        table_format.setBorderBrush(QBrush(QColor(s.text("table", "borderColor"))))
        table_format.setBorderStyle(QTextFrameFormat.BorderStyle.BorderStyle_Solid)
        table_format.setBorderCollapse(True)
        table_format.setCellSpacing(0)
        table_format.setCellPadding(self._px(TABLE_CELL_PADDING_PT))
        table_format.setTopMargin(self._frame_top_margin(s.number("table", "spaceBefore")))
        table_format.setBottomMargin(0)
        table_format.setLeftMargin(ctx.indent * self._doc.indentWidth())
        table_format.setAlignment(Qt.AlignmentFlag.AlignLeft)
        table_format.setHeaderRowCount(1)
        self._collapse_fresh_block()
        qt_table = self._cursor.insertTable(1 + len(table.rows), columns, table_format)

        text = table_text_style(s)
        rows = (table.header, *table.rows)
        for row_index, row in enumerate(rows):
            is_header = row_index == 0
            background = s.text("table", "headerBackground" if is_header else "cellBackground")
            for column in range(columns):
                cell = qt_table.cellAt(row_index, column)
                cell_format = QTextTableCellFormat()
                cell_format.setBackground(QBrush(QColor(background)))
                cell.setFormat(cell_format)
                alignment = table.alignments[column] if column < len(table.alignments) else CellAlignment.DEFAULT
                block_format = self._block_format(text, 0, allow_taller_lines=True)
                block_format.setAlignment(_CELL_ALIGNMENTS.get(alignment, Qt.AlignmentFlag.AlignLeft))
                char_format = self._char_format(text, "table")
                if is_header:
                    char_format.setFontWeight(QFont.Weight.Bold)
                self._cursor = cell.firstCursorPosition()
                self._cursor.setBlockFormat(block_format)
                self._cursor.setBlockCharFormat(char_format)
                if column < len(row):
                    self._inlines(row[column].inlines, char_format, ctx)
        self._cursor = QTextCursor(self._doc)
        self._leave(qt_table)
        self._finish_element(s.number("table", "spaceAfter"))

    def _rule(self, ctx: _Context) -> None:
        s = self._style
        if self._frame_just_left is not None:
            # Qt draws a ruler that directly follows a table starting at the table's right edge,
            # so keep an empty, zero-height block between them.
            self._collapse_fresh_block()
            self._fresh = False
            self._frame_just_left = None
        block_format = QTextBlockFormat()
        block_format.setProperty(
            QTextFormat.Property.BlockTrailingHorizontalRulerWidth,
            QTextLength(QTextLength.Type.PercentageLength, 100),
        )
        # Qt paints the ruler in the block's background color.
        block_format.setBackground(QBrush(QColor(s.text("horizontalRule", "color"))))
        block_format.setTopMargin(self._top_margin(s.number("horizontalRule", "spaceBefore")))
        block_format.setLineHeight(self._px(RULE_THICKNESS_PT), QTextBlockFormat.LineHeightTypes.FixedHeight.value)
        block_format.setIndent(ctx.indent)
        char_format = QTextCharFormat()
        char_format.setFontPointSize(1)
        self._start_block(block_format, char_format)
        self._finish_element(s.number("horizontalRule", "spaceAfter"))

    # ------------------------------------------------------------ inline content

    def _inlines(self, inlines: tuple[Inline, ...], fmt: QTextCharFormat, ctx: _Context) -> None:
        for inline in inlines:
            match inline:
                case Text(text):
                    self._cursor.insertText(text, fmt)
                case LineBreak():
                    self._cursor.insertText(LINE_SEPARATOR, fmt)
                case Emphasis(children):
                    italic = QTextCharFormat(fmt)
                    italic.setFontItalic(True)
                    self._inlines(children, italic, ctx)
                case Strong(children):
                    bold = QTextCharFormat(fmt)
                    bold.setFontWeight(QFont.Weight.Bold)
                    self._inlines(children, bold, ctx)
                case Strikethrough(children):
                    struck = QTextCharFormat(fmt)
                    struck.setFontStrikeOut(True)
                    self._inlines(children, struck, ctx)
                case InlineCode(text):
                    self._cursor.insertText(text, self._inline_code_format(fmt))
                case Link():
                    self._link(inline, fmt, ctx)
                case Image():
                    self._image(inline, fmt, ctx)
                case NoteRef(note_id, label):
                    self._note_marker(note_id, label, fmt)

    def _inline_code_format(self, fmt: QTextCharFormat) -> QTextCharFormat:
        s = self._style
        code = QTextCharFormat(fmt)
        font = self._font(s.text("inlineCode", "fontFamily"), "inlineCode", s.number("inlineCode", "size"))
        font.setBold(fmt.fontWeight() >= QFont.Weight.Bold)
        font.setItalic(fmt.fontItalic())
        code.setFont(font)
        code.setForeground(QBrush(QColor(s.text("inlineCode", "color"))))
        code.setBackground(QBrush(QColor(s.text("inlineCode", "background"))))
        return code

    def _link(self, link: Link, fmt: QTextCharFormat, ctx: _Context) -> None:
        s = self._style
        link_format = QTextCharFormat(fmt)
        link_format.setForeground(QBrush(QColor(s.text("link", "color"))))
        link_format.setFontUnderline(s.flag("link", "underline"))
        link_format.setToolTip(tooltip_text(link.href))
        link_format.setProperty(LINK_HREF_PROPERTY, link.href)
        fragment = heading_fragment(link.href)
        if fragment is not None and fragment in self._anchors_in_document and not self._options.popup:
            # Same-document heading links are the only links that do anything, so only they are anchors.
            link_format.setAnchor(True)
            link_format.setAnchorHref(f"#{fragment}")
        self._inlines(link.children, link_format, ctx)
        if self._options.popup and _address_differs(link):
            self._cursor.insertText(f" ({link.href})", fmt)

    def _image(self, image: Image, fmt: QTextCharFormat, ctx: _Context) -> None:
        base_dir = self._options.base_dir
        path = resolve_image_path(image.src, base_dir) if base_dir is not None else None
        loaded = QImage(str(path)) if path is not None and path.is_file() else QImage()
        if loaded.isNull():
            self._cursor.insertText(image.alt, fmt)
            return
        self._image_count += 1
        name = f"{IMAGE_URL_PREFIX}{self._image_count}"
        self._doc.addResource(QTextDocument.ResourceType.ImageResource.value, QUrl(name), loaded)
        image_format = QTextImageFormat()
        image_format.setName(name)
        image_format.setWidth(loaded.width())
        image_format.setHeight(loaded.height())
        image_format.setToolTip(tooltip_text(image.alt))
        position = self._cursor.position()
        self._cursor.insertImage(image_format)
        self._result.images.append(PlacedImage(position, loaded.size(), ctx.indent * self._doc.indentWidth()))

    def _note_marker(self, note_id: str, label: str, fmt: QTextCharFormat) -> None:
        if self._options.popup or note_id not in self._source.notes:
            self._cursor.insertText(f"[{label}]", fmt)
            return
        s = self._style
        marker = note_marker_format(
            note_id=note_id,
            label=label,
            foreground=s.text("footnoteMarker", "color"),
            background=s.text("footnoteMarker", "background"),
            point_size=self._pt(s.number("footnoteMarker", "size")),
            anchor_href=f"{NOTE_HREF_PREFIX}{note_id}",
        )
        self._cursor.insertText("￼", marker)


def _has_image(inlines: tuple[Inline, ...]) -> bool:
    for inline in inlines:
        match inline:
            case Image():
                return True
            case Emphasis(children) | Strong(children) | Strikethrough(children) | Link(_, children):
                if _has_image(children):
                    return True
            case _:
                pass
    return False


def _address_differs(link: Link) -> bool:
    text = plain_text(link.children).strip()
    return text not in {link.href, link.href.removeprefix("mailto:")} and not link.href.startswith("#")


def note_id_from_href(href: str) -> str | None:
    return href.removeprefix(NOTE_HREF_PREFIX) if href.startswith(NOTE_HREF_PREFIX) else None
