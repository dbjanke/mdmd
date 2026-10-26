import logging

import pytest

from mdmd.core.headings import heading_anchors
from mdmd.core.parser import parse_markdown
from mdmd.core.popup_placement import POPUP_GAP_PX, Rect, place_popup
from mdmd.logs import KeyValueFormatter, get_logger, log_event

SCREEN = Rect(0, 0, 1000, 800)


class TestPlacement:
    def test_below_the_marker_when_it_fits(self) -> None:
        assert place_popup(Rect(100, 100, 20, 16), 300, 200, SCREEN) == (100, 116 + POPUP_GAP_PX)

    def test_above_when_there_is_no_room_below(self) -> None:
        assert place_popup(Rect(100, 700, 20, 16), 300, 200, SCREEN) == (100, 700 - POPUP_GAP_PX - 200)

    def test_shifted_left_to_stay_on_screen(self) -> None:
        x, _ = place_popup(Rect(900, 100, 20, 16), 300, 200, SCREEN)
        assert x == 700

    def test_pinned_when_neither_fits(self) -> None:
        assert place_popup(Rect(10, 300, 20, 16), 300, 600, SCREEN) == (10, 200)

    def test_never_off_the_top_left(self) -> None:
        assert place_popup(Rect(10, 10, 5, 5), 2000, 2000, SCREEN) == (0, 0)

    def test_screen_offset_is_respected(self) -> None:
        second = Rect(1000, 0, 800, 600)
        assert place_popup(Rect(1750, 50, 10, 10), 300, 100, second)[0] == 1500


def test_heading_anchors_include_nested_headings() -> None:
    document = parse_markdown("# Top\n\n> ## Quoted\n\n- ### Listed\n")
    assert heading_anchors(document.blocks) == {"top", "quoted", "listed"}


class TestLogFormat:
    def format(self, **fields: object) -> str:
        record = logging.LogRecord("mdmd.test", logging.INFO, __file__, 1, "something_happened", None, None)
        record.mdmd_fields = fields
        return KeyValueFormatter().format(record)

    def test_key_value_line(self) -> None:
        line = self.format(count=3, reason="NOT_FOUND")
        assert "level=info logger=mdmd.test event=something_happened count=3 reason=NOT_FOUND" in line

    def test_values_with_spaces_or_quotes_are_quoted(self) -> None:
        assert 'detail="two words"' in self.format(detail="two words")
        assert r'detail="say \"hi\""' in self.format(detail='say "hi"')
        assert 'empty=""' in self.format(empty="")

    def test_log_event_attaches_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        logger = get_logger("unit")
        logger.propagate = True
        with caplog.at_level(logging.INFO, logger="mdmd.unit"):
            log_event(logger, "tested", count=2)
        assert caplog.records[0].mdmd_fields == {"count": 2}
