import pytest

from mdmd.core.default_style import DEFAULT_STYLE
from mdmd.core.settings_draft import SettingsDraft
from mdmd.core.themes import (
    MAX_THEME_NAME_LENGTH,
    Theme,
    ThemeLibrary,
    ThemeNameError,
    is_deletable,
    theme_status,
    validate_theme_name,
)

EVENING = Theme("Evening", DEFAULT_STYLE.with_value("page", "background", "#000000"))


class TestNames:
    def test_name_is_trimmed(self) -> None:
        assert validate_theme_name("  Evening ") == "Evening"

    @pytest.mark.parametrize("name", ["", "   ", "Default", "default", " DEFAULT ", "a\tb", "x" * 65])
    def test_invalid_names(self, name: str) -> None:
        with pytest.raises(ThemeNameError):
            validate_theme_name(name)

    def test_longest_allowed_name(self) -> None:
        assert validate_theme_name("x" * MAX_THEME_NAME_LENGTH)


class TestLibrary:
    def test_default_theme_is_always_first(self) -> None:
        library = ThemeLibrary((Theme("Zed", DEFAULT_STYLE), Theme("alpha", DEFAULT_STYLE)))
        assert [t.name for t in library.themes] == ["Default", "alpha", "Zed"]

    def test_find_ignores_case(self) -> None:
        library = ThemeLibrary((EVENING,))
        assert library.find("EVENING") is EVENING
        assert library.find("Morning") is None
        assert library.find(None) is None

    def test_saving_same_name_in_other_case_replaces(self) -> None:
        library = ThemeLibrary((EVENING,)).with_theme(Theme("evening", DEFAULT_STYLE))
        assert [t.name for t in library.user_themes] == ["evening"]

    def test_default_cannot_be_overwritten_or_deleted(self) -> None:
        with pytest.raises(ThemeNameError):
            ThemeLibrary().with_theme(Theme("Default", DEFAULT_STYLE))
        with pytest.raises(ThemeNameError):
            ThemeLibrary().without("default")
        assert not is_deletable("Default")
        assert not is_deletable(None)
        assert is_deletable("Evening")

    def test_without_removes_ignoring_case(self) -> None:
        assert ThemeLibrary((EVENING,)).without("evening").user_themes == ()


class TestStatus:
    def test_matching_values_are_not_modified(self) -> None:
        status = theme_status(EVENING.style, "Evening", ThemeLibrary((EVENING,)))
        assert (status.name, status.modified, status.label) == ("Evening", False, "Evening")

    def test_changed_values_are_modified(self) -> None:
        style = EVENING.style.with_value("h1", "size", 40)
        status = theme_status(style, "evening", ThemeLibrary((EVENING,)))
        assert status.label == "Evening (modified)"

    def test_no_active_or_missing_theme_shows_no_theme(self) -> None:
        assert theme_status(DEFAULT_STYLE, None, ThemeLibrary()).label == "No theme"
        assert theme_status(DEFAULT_STYLE, "Gone", ThemeLibrary()).label == "No theme"


class TestDraft:
    def test_load_theme_replaces_values_and_active(self) -> None:
        draft = SettingsDraft(DEFAULT_STYLE, "Default").load_theme(EVENING)
        assert (draft.style, draft.active_theme) == (EVENING.style, "Evening")

    def test_delete_active_theme_keeps_values_and_clears_active(self) -> None:
        draft = SettingsDraft(EVENING.style, "Evening").theme_deleted("evening")
        assert (draft.style, draft.active_theme) == (EVENING.style, None)

    def test_delete_other_theme_keeps_active(self) -> None:
        draft = SettingsDraft(EVENING.style, "Evening").theme_deleted("Morning")
        assert draft.active_theme == "Evening"

    def test_invalid_value_leaves_draft_unchanged(self) -> None:
        draft = SettingsDraft(DEFAULT_STYLE, "Default")
        with pytest.raises(ValueError):
            draft.with_value("h1", "size", 1)
        assert draft.style == DEFAULT_STYLE
