"""The Specifications page renders the shipped docs/specs/*.md offline."""

import pytest

from src.web.spec_docs import SPEC_PAGES, render_spec_page


def test_every_listed_page_renders_html():
    for slug in SPEC_PAGES:
        html = render_spec_page(slug)
        assert "<h3" in html, slug  # the document title sits below the page header (h2)


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


def test_links_to_the_docs_site_are_mapped_or_dropped_not_left_as_external_links():
    # the specification repository cannot use relative links into Studio's docs, so its pages carry
    # absolute Read the Docs / GitHub URLs; offline, they must behave like the old relative links
    for slug in ("survey", "eyetracking", "biometrics", "physio"):
        html = render_spec_page(slug)
        assert "readthedocs.io" not in html and "MRI-Lab-Graz/prism-studio" not in html, slug


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


def test_the_overview_has_no_dead_offline_link_to_the_specification_repository():
    assert "github.com/MRI-Lab-Graz/prism-specification" not in render_spec_page("overview")


def test_document_headings_sit_below_the_page_header():
    """The page header is an h2, so the document's own headings start at h3 (no skipped or inverted levels)."""
    import re

    for slug in ("overview", "survey", "biosample", "entities"):
        levels = [int(n) for n in re.findall(r"<h([1-6])[ >]", render_spec_page(slug))]
        assert levels and levels[0] == 3 and min(levels) >= 3, (slug, levels)
        assert all(b - a <= 1 for a, b in zip(levels, levels[1:])), (slug, levels)
