"""Themed parts live in the theme; a page must not carry its own copy (see CLAUDE.md, "One theme for every page")."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# page files that already use the theme; add a page here when it has been moved
THEMED_PAGE_FILES = [
    "app/static/js/template-editor.js",
    "app/static/css/template-editor.css",
    "app/templates/template_editor.html",
]
# markers of the old per-page look: field tiles, rings, "complete" badge, hand-built field labels
OLD_PAGE_LOOK = ["te-field", "te-item-field", "te-ring", "te-section-badge", "completionRings"]


def test_themed_pages_have_no_page_local_copies_of_themed_parts():
    for rel in THEMED_PAGE_FILES:
        text = (ROOT / rel).read_text(encoding="utf-8")
        for marker in OLD_PAGE_LOOK:
            assert marker not in text, f"{rel} still has {marker!r}: use the theme part instead"


def test_editor_builds_field_headings_only_through_the_theme():
    js = (ROOT / "app/static/js/template-editor.js").read_text(encoding="utf-8")
    assert "schema-hint" not in js
