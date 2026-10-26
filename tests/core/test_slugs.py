import time

from mdmd.core.slugs import SlugAllocator, slugify


def allocate_all(*headings: str) -> list[str]:
    allocator = SlugAllocator()
    return [allocator.allocate(h) for h in headings]


def test_slugify_matches_github() -> None:
    assert slugify("Key Findings") == "key-findings"
    assert slugify("  TL;DR  ") == "tldr"
    assert slugify("Ames's *A Man*") == "amess-a-man"
    assert slugify("") == ""


def test_duplicates_get_increasing_suffixes() -> None:
    assert allocate_all("Intro", "Intro", "intro", "Other", "Intro") == [
        "intro",
        "intro-1",
        "intro-2",
        "other",
        "intro-3",
    ]


def test_a_heading_that_looks_like_a_suffix_is_never_reused() -> None:
    assert allocate_all("a", "a-1", "a") == ["a", "a-1", "a-2"]
    assert allocate_all("a", "a", "a-1") == ["a", "a-1", "a-1-1"]


def test_empty_headings_are_unique_too() -> None:
    assert allocate_all("", "", "") == ["", "-1", "-2"]


def test_many_duplicates_take_linear_time() -> None:
    allocator = SlugAllocator()
    started = time.perf_counter()
    for _ in range(100_000):
        allocator.allocate("same")
    assert time.perf_counter() - started < 5
    assert allocator.allocate("same") == "same-100000"
