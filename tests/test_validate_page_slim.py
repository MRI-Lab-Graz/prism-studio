from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "app" / "templates" / "index.html"


def _advanced_section():
    html = INDEX.read_text(encoding="utf-8")
    return html.split("<details", 1)[1].split("</details>", 1)[0]


def test_alternative_folder_and_nifti_toggle_live_in_advanced_options():
    advanced = _advanced_section()
    for element_id in ("targetOtherFolder", "folderBtn", "check_nifti_headers"):
        assert f'id="{element_id}"' in advanced


def test_with_a_project_the_page_leads_with_a_one_line_target():
    html = INDEX.read_text(encoding="utf-8")
    assert 'id="currentProjectSummary"' in html.split("<details", 1)[0]


def test_summary_box_shows_the_logo_and_the_schemas_in_use():
    summary = INDEX.read_text(encoding="utf-8").split('id="currentProjectSummary"', 1)[1].split("Advanced Options", 1)[0]
    assert "prism_logo" in summary
    assert "project_schemas" in summary


def test_no_repeated_title_step_heading_or_dead_alert():
    html = INDEX.read_text(encoding="utf-8")
    assert html.count("'Dataset Validation'") == 1  # the page header only, no second card title
    assert "1. Select Dataset" not in html
    assert "PRISM Validator ensures" not in html
    assert 'id="browserWarning"' not in html
    assert "Note: Dataset validation is performed locally" not in html  # said in the header subtitle instead


def test_current_project_target_line_is_not_repeated_under_the_button():
    js = (INDEX.parents[1] / "static" / "js" / "index.js").read_text(encoding="utf-8")
    assert "Target: current project (default)" not in js
