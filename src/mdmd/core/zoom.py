"""Per-window zoom, kept as an integer percentage so repeated steps never drift."""

ZOOM_MIN_PERCENT = 50
ZOOM_MAX_PERCENT = 300
ZOOM_STEP_PERCENT = 10
ZOOM_DEFAULT_PERCENT = 100


def zoom_in(percent: int) -> int:
    return min(ZOOM_MAX_PERCENT, percent + ZOOM_STEP_PERCENT)


def zoom_out(percent: int) -> int:
    return max(ZOOM_MIN_PERCENT, percent - ZOOM_STEP_PERCENT)
