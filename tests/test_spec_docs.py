"""The Specifications page renders the shipped docs/specs/*.md offline."""

import pytest

from src.web.spec_docs import SPEC_PAGES, render_spec_page


def test_every_listed_page_renders_html():
    for slug in SPEC_PAGES:
        html = render_spec_page(slug)
        assert "<h1" in html or "<h2" in html, slug


def test_schema_field_table_is_rendered_as_table():
    assert "<table" in render_spec_page("survey")


def test_unknown_page_raises_keyerror_not_path_traversal():
    for bad in ("../README", "nope", "..%2f..%2fCLAUDE"):
        with pytest.raises(KeyError):
            render_spec_page(bad)


def test_links_between_docs_point_at_in_app_pages():
    html = render_spec_page("eyetracking")
    assert "ERROR_CODES.md" not in html
    assert "/specifications/errors" in html


def test_links_to_repo_files_outside_docs_are_not_clickable():
    # ../../app/schemas/... only resolves on GitHub, a dead link in the app
    assert "../../app" not in render_spec_page("entities")


def test_tables_get_bootstrap_styling():
    assert '<table class="table table-sm">' in render_spec_page("survey")


def test_whats_next_navigation_section_is_dropped():
    # it links to guides that are not part of the in-app pages
    assert "What's next" not in render_spec_page("overview")


def test_pages_are_grouped_for_the_sidebar():
    from src.web.spec_docs import SPEC_GROUPS

    grouped = [slug for _, slugs in SPEC_GROUPS for slug in slugs]
    assert sorted(grouped) == sorted(SPEC_PAGES)


def test_tutorial_text_is_dropped_but_reference_stays():
    survey = render_spec_page("survey")
    assert "Starting a new survey" not in survey  # [!TIP] pointer to the workbook
    assert "How To Use The Excel Workbook" not in survey  # step-by-step procedure
    assert "Multi-version Template Fields" in survey
    assert "Starting a new biometric" not in render_spec_page("biometrics")


def test_overview_has_no_studio_guide_or_doi_placeholder():
    html = render_spec_page("overview")
    for text in ("Studio Guide", "placeholder", "step-by-step"):
        assert text not in html
