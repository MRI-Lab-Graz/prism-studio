"""Emoji are removed from imported texts: they broke exports and files on Windows."""

import pytest

from src.text_sanitizer import html_to_text, strip_emoji


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Wie geht es dir? 😀 gut", "Wie geht es dir? gut"),
        ("👍🏽 ok", "ok"),  # with skin tone
        ("Familie 👨‍👩‍👧 hier", "Familie hier"),  # joined by zero-width joiners
        ("❤️ mag ich", "mag ich"),  # with variation selector
        ("☺ ja", "ja"),
        ("🇦🇹 Österreich", "Österreich"),  # flag
    ],
)
def test_html_to_text_removes_emoji(text, expected):
    assert html_to_text(text) == expected


@pytest.mark.parametrize("text", ["Ärger über Ölpreise ß", "größer ≥ 5 und ≤ 7 – ok", "日本語 العربية", "© 2026 ™", "1. Frage 2)"])
def test_other_text_is_left_alone(text):
    assert strip_emoji(text) == text


def test_a_joiner_between_letters_is_kept():
    persian = "می‌خواهم"  # zero-width non-joiner/joiner are part of the spelling
    assert strip_emoji(persian) == persian
    assert strip_emoji("ab‍cd") == "ab‍cd"
