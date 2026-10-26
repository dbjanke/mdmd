"""Recent files, find, zoom, links, stored settings, and the instance message."""

from pathlib import Path

import pytest

from mdmd.core.app_settings import (
    DEFAULT_WINDOW_SIZE,
    AppSettings,
    app_settings_to_json,
    clamp_window_size,
    parse_app_settings,
)
from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.instance_message import InstanceMessageError, decode_open_request, encode_open_request
from mdmd.core.links import heading_fragment, resolve_image_path
from mdmd.core.recent import MAX_RECENT_FILES, add_recent, parse_recent, remove_recent
from mdmd.core.search import Match, count_label, find_matches, first_at_or_after, step
from mdmd.core.zoom import ZOOM_MAX_PERCENT, ZOOM_MIN_PERCENT, zoom_in, zoom_out


class TestRecent:
    def test_newest_first_without_duplicates(self) -> None:
        recent = add_recent(add_recent(add_recent((), "/a"), "/b"), "/a")
        assert recent == ("/a", "/b")

    def test_capped(self) -> None:
        recent: tuple[str, ...] = ()
        for n in range(MAX_RECENT_FILES + 3):
            recent = add_recent(recent, f"/f{n}")
        assert len(recent) == MAX_RECENT_FILES
        assert recent[0] == f"/f{MAX_RECENT_FILES + 2}"
        assert "/f0" not in recent

    def test_relative_path_rejected(self) -> None:
        with pytest.raises(ValueError):
            add_recent((), "notes.md")

    def test_remove(self) -> None:
        assert remove_recent(("/a", "/b"), "/a") == ("/b",)

    def test_parse_keeps_order_and_drops_bad_entries(self) -> None:
        assert parse_recent(["/a", "rel", "/b", "/a"]) == ("/a", "/b")

    @pytest.mark.parametrize("raw", [None, "x", {"a": 1}, ["/a", 3]])
    def test_unparseable_list_is_empty(self, raw: object) -> None:
        assert parse_recent(raw) == ()


class TestSearch:
    def test_case_sensitivity(self) -> None:
        assert find_matches("Doll doll DOLL", "doll", match_case=True) == (Match(5, 9),)
        assert len(find_matches("Doll doll DOLL", "doll", match_case=False)) == 3

    def test_term_is_literal_not_regex(self) -> None:
        assert find_matches("a.b axb", "a.b", match_case=True) == (Match(0, 3),)

    def test_positions_survive_case_folding_changes(self) -> None:
        # "İ" lowercases to two characters; positions must still index the original text.
        text = "İ straße STRASSE"
        (match,) = find_matches(text, "straße", match_case=False)
        assert text[match.start : match.end] == "straße"

    def test_empty_term(self) -> None:
        assert find_matches("abc", "", match_case=False) == ()

    def test_first_at_or_after_wraps(self) -> None:
        matches = (Match(0, 1), Match(10, 11))
        assert first_at_or_after(matches, 0) == 0
        assert first_at_or_after(matches, 5) == 1
        assert first_at_or_after(matches, 10) == 1
        assert first_at_or_after(matches, 11) == 0
        assert first_at_or_after((), 3) is None

    def test_step_wraps_both_ways(self) -> None:
        assert step(2, 3, forward=True) == 0
        assert step(0, 3, forward=False) == 2
        assert step(1, 3, forward=True) == 2
        with pytest.raises(ValueError):
            step(0, 0, forward=True)

    def test_count_label(self) -> None:
        assert count_label(2, 12) == "3 of 12"
        assert count_label(None, 0) == "0 of 0"


class TestZoom:
    def test_steps_and_limits(self) -> None:
        assert zoom_in(100) == 110
        assert zoom_out(100) == 90
        assert zoom_in(ZOOM_MAX_PERCENT) == ZOOM_MAX_PERCENT
        assert zoom_out(ZOOM_MIN_PERCENT) == ZOOM_MIN_PERCENT


class TestLinks:
    def test_heading_fragment(self) -> None:
        assert heading_fragment("#Key-Findings") == "key-findings"
        assert heading_fragment("#tl%3Bdr") == "tl;dr"
        assert heading_fragment("#") is None
        assert heading_fragment("https://e.com/#x") is None
        assert heading_fragment("other.md#x") is None

    def test_image_paths(self) -> None:
        base = Path("/docs")
        assert resolve_image_path("img/a%20b.png", base) == Path("/docs/img/a b.png")
        assert resolve_image_path("/abs/c.png", base) == Path("/abs/c.png")
        assert resolve_image_path("file:///abs/c.png", base) == Path("/abs/c.png")
        assert resolve_image_path("https://e.com/x.png", base) is None
        assert resolve_image_path("http://e.com/x.png", base) is None
        assert resolve_image_path("data:image/png;base64,xx", base) is None
        assert resolve_image_path("", base) is None


class TestAppSettings:
    def test_round_trip(self) -> None:
        settings = AppSettings(
            style=DEFAULT_STYLE.with_value("h1", "size", 30),
            active_theme="Evening",
            window_size=(1000, 800),
            recent_files=("/a.md",),
        )
        assert parse_app_settings(app_settings_to_json(settings)).settings == settings

    def test_degraded_example(self) -> None:
        raw = {"workingSettings": {"h1": {"size": 30}}, "activeTheme": None, "themes": {}, "recentFiles": []}
        settings = parse_app_settings(raw).settings
        assert settings.style.number("h1", "size") == 30
        assert settings.active_theme is None
        assert settings.window_size == DEFAULT_WINDOW_SIZE

    @pytest.mark.parametrize("size", [[10, 700], [900], "big", [900.5, 700], [True, 700]])
    def test_bad_window_size_falls_back(self, size: object) -> None:
        parsed = parse_app_settings({"windowSize": size})
        assert parsed.settings.window_size == DEFAULT_WINDOW_SIZE
        assert "windowSize" in parsed.rejected

    def test_bad_active_theme_becomes_none(self) -> None:
        parsed = parse_app_settings({"activeTheme": 5})
        assert parsed.settings.active_theme is None

    def test_missing_active_theme_key_means_no_theme(self) -> None:
        assert parse_app_settings({}).settings.active_theme is None

    def test_clamp_window_size(self) -> None:
        assert clamp_window_size(50, 100000) == (200, 20000)


class TestInstanceMessage:
    def test_round_trip(self) -> None:
        assert decode_open_request(encode_open_request(["/a.md", "/b c.md"])) == ["/a.md", "/b c.md"]
        assert decode_open_request(encode_open_request([])) == []

    @pytest.mark.parametrize(
        "data",
        [b"", b"\xff", b"[]", b'{"version": 2, "open": []}', b'{"version": 1, "open": ["rel.md"]}'],
    )
    def test_rejects_bad_messages(self, data: bytes) -> None:
        with pytest.raises(InstanceMessageError):
            decode_open_request(data)
