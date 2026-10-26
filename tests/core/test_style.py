import pytest

from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.style import (
    ELEMENTS,
    ELEMENTS_BY_KEY,
    InvalidValueError,
    parse_style,
    style_to_json,
    validate_value,
)

SIZE = ELEMENTS_BY_KEY["body"].property("size")
SPACE = ELEMENTS_BY_KEY["body"].property("spaceBefore")
SPACING = ELEMENTS_BY_KEY["body"].property("lineSpacing")
COLOR = ELEMENTS_BY_KEY["body"].property("color")
ALIGN = ELEMENTS_BY_KEY["body"].property("alignment")
FONT = ELEMENTS_BY_KEY["body"].property("fontFamily")
TABLE_FONT = ELEMENTS_BY_KEY["table"].property("fontFamily")
UNDERLINE = ELEMENTS_BY_KEY["link"].property("underline")


def test_default_style_has_every_property_and_each_is_valid() -> None:
    for element in ELEMENTS:
        assert set(DEFAULT_STYLE.values[element.key]) == {p.key for p in element.properties}
        for spec in element.properties:
            value = DEFAULT_STYLE.value(element.key, spec.key)
            assert validate_value(spec, value) == value


def test_default_heading_sizes_follow_the_scale() -> None:
    sizes = [DEFAULT_STYLE.number(f"h{n}", "size") for n in range(1, 7)]
    assert sizes == [22.0, 17.6, 14.3, 12.65, 11.0, 9.9]


@pytest.mark.parametrize(
    ("spec", "value"),
    [(SIZE, 6), (SIZE, 96), (SPACE, 0), (SPACE, 200), (SPACING, 0.8), (SPACING, 3.0)],
)
def test_range_limits_are_inclusive(spec: object, value: float) -> None:
    assert validate_value(spec, value) == value  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("spec", "value"),
    [
        (SIZE, 5.9),
        (SIZE, 96.1),
        (SPACE, -1),
        (SPACE, 201),
        (SPACING, 0.79),
        (SPACING, 3.01),
        (SIZE, True),
        (SIZE, "11"),
        (COLOR, "#12345"),
        (COLOR, "123456"),
        (COLOR, "#12345g"),
        (COLOR, "red"),
        (ALIGN, "middle"),
        (FONT, ""),
        (FONT, "   "),
        (FONT, None),
        (FONT, 12),
        (UNDERLINE, 1),
        (UNDERLINE, "true"),
    ],
)
def test_invalid_values_are_rejected(spec: object, value: object) -> None:
    with pytest.raises(InvalidValueError):
        validate_value(spec, value)  # type: ignore[arg-type]


def test_colors_are_normalised_to_lowercase() -> None:
    assert validate_value(COLOR, "#AbCdEf") == "#abcdef"


def test_table_font_is_optional_but_body_font_is_not() -> None:
    assert validate_value(TABLE_FONT, None) is None
    with pytest.raises(InvalidValueError):
        validate_value(FONT, None)


def test_with_value_changes_one_value_only() -> None:
    changed = DEFAULT_STYLE.with_value("h1", "size", 30)
    assert changed.number("h1", "size") == 30
    assert DEFAULT_STYLE.number("h1", "size") == 22.0
    assert changed.values["body"] == DEFAULT_STYLE.values["body"]
    assert changed != DEFAULT_STYLE


def test_with_value_rejects_out_of_range_and_unknown_property() -> None:
    with pytest.raises(InvalidValueError):
        DEFAULT_STYLE.with_value("h1", "size", 200)
    with pytest.raises(KeyError):
        DEFAULT_STYLE.with_value("page", "size", 10)


class TestParseStyle:
    def test_missing_everything_gives_defaults(self) -> None:
        parsed = parse_style(None, DEFAULT_STYLE)
        assert parsed.style == DEFAULT_STYLE
        assert parsed.rejected == ()

    def test_degraded_example_keeps_only_the_stored_size(self) -> None:
        parsed = parse_style({"h1": {"size": 30}}, DEFAULT_STYLE)
        assert parsed.style.number("h1", "size") == 30
        assert parsed.style.text("h1", "color") == DEFAULT_STYLE.text("h1", "color")
        assert parsed.style.values["body"] == DEFAULT_STYLE.values["body"]

    def test_invalid_value_falls_back_for_that_property_only(self) -> None:
        parsed = parse_style({"body": {"color": "nope", "size": 500, "lineSpacing": 2.0}}, DEFAULT_STYLE)
        assert parsed.style.text("body", "color") == DEFAULT_STYLE.text("body", "color")
        assert parsed.style.number("body", "size") == DEFAULT_STYLE.number("body", "size")
        assert parsed.style.number("body", "lineSpacing") == 2.0
        assert set(parsed.rejected) == {"body.color", "body.size"}

    def test_element_that_is_not_an_object_falls_back(self) -> None:
        parsed = parse_style({"body": "big"}, DEFAULT_STYLE)
        assert parsed.style.values["body"] == DEFAULT_STYLE.values["body"]

    def test_unknown_keys_are_ignored(self) -> None:
        parsed = parse_style({"sidebar": {"size": 3}, "body": {"weight": 700}}, DEFAULT_STYLE)
        assert parsed.style == DEFAULT_STYLE
        assert parsed.rejected == ()

    def test_unknown_font_family_is_kept(self) -> None:
        parsed = parse_style({"body": {"fontFamily": "Not Installed Sans"}}, DEFAULT_STYLE)
        assert parsed.style.text("body", "fontFamily") == "Not Installed Sans"

    def test_round_trip(self) -> None:
        style = DEFAULT_STYLE.with_value("table", "fontFamily", "Serif").with_value("link", "underline", False)
        assert parse_style(style_to_json(style), DEFAULT_STYLE).style == style
