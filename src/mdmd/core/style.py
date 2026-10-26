"""Style settings: which elements exist, which properties they have, and what values are valid.

The Default theme's values live in `default_style.py`; this module holds only the
schema and the rules for reading and changing values.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum, StrEnum

type Value = str | float | bool | None
type ElementValues = Mapping[str, Value]


class Alignment(StrEnum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    JUSTIFY = "justify"


class PropertyKind(Enum):
    FONT_FAMILY = "font family"
    SIZE = "size"
    SPACE = "space"
    LINE_SPACING = "line spacing"
    COLOR = "color"
    ALIGNMENT = "alignment"
    FLAG = "flag"


@dataclass(frozen=True)
class NumberRange:
    minimum: float
    maximum: float

    def contains(self, value: float) -> bool:
        return self.minimum <= value <= self.maximum


NUMBER_RANGES = {
    PropertyKind.SIZE: NumberRange(6, 96),
    PropertyKind.SPACE: NumberRange(0, 200),
    PropertyKind.LINE_SPACING: NumberRange(0.8, 3.0),
}
MAX_FONT_FAMILY_LENGTH = 200
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@dataclass(frozen=True)
class PropertySpec:
    key: str
    label: str
    kind: PropertyKind
    optional: bool = False  # None is allowed, meaning "inherit"


@dataclass(frozen=True)
class ElementSpec:
    key: str
    label: str
    properties: tuple[PropertySpec, ...]

    def property(self, key: str) -> PropertySpec:
        for spec in self.properties:
            if spec.key == key:
                return spec
        raise KeyError(f"element {self.key!r} has no property {key!r}")


# ------------------------------------------------------------------ the schema

FONT = PropertySpec("fontFamily", "Font", PropertyKind.FONT_FAMILY)
SIZE = PropertySpec("size", "Size", PropertyKind.SIZE)
COLOR = PropertySpec("color", "Color", PropertyKind.COLOR)
LINE_SPACING = PropertySpec("lineSpacing", "Line spacing", PropertyKind.LINE_SPACING)
ALIGNMENT = PropertySpec("alignment", "Alignment", PropertyKind.ALIGNMENT)
SPACE_BEFORE = PropertySpec("spaceBefore", "Space before", PropertyKind.SPACE)
SPACE_AFTER = PropertySpec("spaceAfter", "Space after", PropertyKind.SPACE)
BACKGROUND = PropertySpec("background", "Background", PropertyKind.COLOR)

_TEXT_BLOCK = (FONT, SIZE, COLOR, LINE_SPACING, ALIGNMENT, SPACE_BEFORE, SPACE_AFTER)

ELEMENTS: tuple[ElementSpec, ...] = (
    ElementSpec("page", "Page", (BACKGROUND,)),
    ElementSpec("body", "Body text", _TEXT_BLOCK),
    *(ElementSpec(f"h{level}", f"Heading {level}", _TEXT_BLOCK) for level in range(1, 7)),
    ElementSpec("link", "Links", (COLOR, PropertySpec("underline", "Underline", PropertyKind.FLAG))),
    ElementSpec("inlineCode", "Inline code", (FONT, SIZE, COLOR, BACKGROUND)),
    ElementSpec("codeBlock", "Code block", (FONT, SIZE, COLOR, BACKGROUND, LINE_SPACING, SPACE_BEFORE, SPACE_AFTER)),
    ElementSpec("blockQuote", "Block quote", (COLOR, BACKGROUND, LINE_SPACING, ALIGNMENT, SPACE_BEFORE, SPACE_AFTER)),
    ElementSpec("list", "Lists", _TEXT_BLOCK),
    ElementSpec(
        "table",
        "Table",
        (
            PropertySpec("fontFamily", "Font", PropertyKind.FONT_FAMILY, optional=True),
            SIZE,
            COLOR,
            PropertySpec("headerBackground", "Header background", PropertyKind.COLOR),
            PropertySpec("cellBackground", "Cell background", PropertyKind.COLOR),
            PropertySpec("borderColor", "Border color", PropertyKind.COLOR),
            SPACE_BEFORE,
            SPACE_AFTER,
        ),
    ),
    ElementSpec("horizontalRule", "Horizontal rule", (COLOR, SPACE_BEFORE, SPACE_AFTER)),
    ElementSpec("footnoteMarker", "Footnote marker", (COLOR, BACKGROUND, SIZE)),
    ElementSpec("footnotePopup", "Footnote popup", (FONT, SIZE, COLOR, BACKGROUND)),
)
ELEMENTS_BY_KEY = {element.key: element for element in ELEMENTS}
HEADING_KEYS = tuple(f"h{level}" for level in range(1, 7))


# ------------------------------------------------------------------ validation


class InvalidValueError(ValueError):
    pass


def validate_value(spec: PropertySpec, value: object) -> Value:
    """Return `value` in canonical form, or raise InvalidValueError if it is not allowed."""
    if value is None:
        if spec.optional:
            return None
        raise InvalidValueError(f"{spec.label} is required")
    match spec.kind:
        case PropertyKind.FONT_FAMILY:
            if isinstance(value, str) and value.strip() and len(value) <= MAX_FONT_FAMILY_LENGTH:
                return value.strip()
        case PropertyKind.SIZE | PropertyKind.SPACE | PropertyKind.LINE_SPACING:
            number_range = NUMBER_RANGES[spec.kind]
            # bool is an int subclass; True is not a size.
            if isinstance(value, int | float) and not isinstance(value, bool) and number_range.contains(value):
                return float(value)
        case PropertyKind.COLOR:
            if isinstance(value, str) and _COLOR.match(value):
                return value.lower()
        case PropertyKind.ALIGNMENT:
            if isinstance(value, str) and value in Alignment.__members__.values():
                return value
        case PropertyKind.FLAG:
            if isinstance(value, bool):
                return value
    raise InvalidValueError(f"{spec.label}: {value!r} is not a valid {spec.kind.value}")


# ------------------------------------------------------------------ the value set


@dataclass(frozen=True)
class Style:
    """A complete set of style values: every property of every element.

    Treat as immutable; use `with_value` to change one value.
    """

    values: Mapping[str, ElementValues]

    def value(self, element: str, prop: str) -> Value:
        return self.values[element][prop]

    def text(self, element: str, prop: str) -> str:
        value = self.value(element, prop)
        if not isinstance(value, str):
            raise TypeError(f"{element}.{prop} is not text")
        return value

    def optional_text(self, element: str, prop: str) -> str | None:
        value = self.value(element, prop)
        return value if isinstance(value, str) else None

    def number(self, element: str, prop: str) -> float:
        value = self.value(element, prop)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise TypeError(f"{element}.{prop} is not a number")
        return float(value)

    def flag(self, element: str, prop: str) -> bool:
        return self.value(element, prop) is True

    def alignment(self, element: str) -> Alignment:
        return Alignment(self.text(element, "alignment"))

    def with_value(self, element: str, prop: str, value: object) -> Style:
        """A copy with one value changed. Raises InvalidValueError for a disallowed value."""
        clean = validate_value(ELEMENTS_BY_KEY[element].property(prop), value)
        changed = dict(self.values)
        changed[element] = {**self.values[element], prop: clean}
        return Style(changed)


@dataclass(frozen=True)
class ParsedStyle:
    style: Style
    rejected: tuple[str, ...]  # "element.property" names whose stored value was invalid


def parse_style(raw: object, fallback: Style) -> ParsedStyle:
    """Read stored values. Anything missing or invalid takes its value from `fallback`."""
    raw_elements = raw if isinstance(raw, dict) else {}
    rejected: list[str] = []
    values: dict[str, dict[str, Value]] = {}
    for element in ELEMENTS:
        stored = raw_elements.get(element.key)
        stored = stored if isinstance(stored, dict) else {}
        element_values: dict[str, Value] = {}
        for spec in element.properties:
            default = fallback.value(element.key, spec.key)
            if spec.key not in stored:
                element_values[spec.key] = default
                continue
            try:
                element_values[spec.key] = validate_value(spec, stored[spec.key])
            except InvalidValueError:
                rejected.append(f"{element.key}.{spec.key}")
                element_values[spec.key] = default
        values[element.key] = element_values
    return ParsedStyle(Style(values), tuple(rejected))


def style_to_json(style: Style) -> dict[str, dict[str, Value]]:
    return {element: dict(props) for element, props in style.values.items()}
