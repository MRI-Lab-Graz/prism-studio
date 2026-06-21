from __future__ import annotations

from src.cross_platform import (
    describe_case_insensitive_id_collisions,
    find_case_insensitive_id_collisions,
)


def test_find_case_insensitive_id_collisions_detects_case_only_variants():
    collisions = find_case_insensitive_id_collisions(["sub-Ab", "sub-ab", "sub-100"])
    assert collisions == {"sub-ab": ["sub-Ab", "sub-ab"]}


def test_find_case_insensitive_id_collisions_ignores_distinct_ids():
    collisions = find_case_insensitive_id_collisions(["sub-100", "sub-101", "sub-Ab"])
    assert collisions == {}


def test_find_case_insensitive_id_collisions_ignores_exact_duplicates():
    """An id repeated verbatim (same case) is not a collision — just a
    duplicate, handled elsewhere."""
    collisions = find_case_insensitive_id_collisions(["sub-Ab", "sub-Ab"])
    assert collisions == {}


def test_find_case_insensitive_id_collisions_skips_empty_values():
    collisions = find_case_insensitive_id_collisions(["sub-Ab", "", None, "sub-ab"])
    assert collisions == {"sub-ab": ["sub-Ab", "sub-ab"]}


def test_describe_case_insensitive_id_collisions_returns_none_when_clean():
    assert describe_case_insensitive_id_collisions(["sub-100", "sub-101"]) is None


def test_describe_case_insensitive_id_collisions_message_names_both_variants():
    message = describe_case_insensitive_id_collisions(["sub-Ab", "sub-ab"])
    assert message is not None
    assert "sub-Ab" in message
    assert "sub-ab" in message
    assert "case-insensitive" in message
