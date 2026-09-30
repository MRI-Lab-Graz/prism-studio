"""Converter page: convert real input files the way a user does."""

import pytest
from playwright.sync_api import expect

BRS_CSV = "participant_id,BRS01,BRS02,BRS03\nP001,3,4,2\nP002,1,0,2\n"


def open_survey_tab(page, studio_url):
    page.goto(f"{studio_url}/converter")
    page.click("#survey-tab")
    expect(page.locator("#survey-panel")).to_be_visible()


def select_survey_file(page, tmp_path, content=BRS_CSV):
    data = tmp_path / "brs.csv"
    data.write_text(content)
    page.set_input_files("#convertSurveyFile", str(data))
    expect(page.locator("#convertIdColumn")).to_have_value("participant_id")


def test_survey_file_selection_unlocks_preview_but_not_convert(app_page, studio_url, tmp_path):
    open_survey_tab(app_page, studio_url)

    select_survey_file(app_page, tmp_path)

    expect(app_page.locator("#previewBtn")).to_be_enabled()
    expect(app_page.locator("#convertBtn")).to_be_disabled()  # preview comes first


def convert_survey(page, tmp_path, session):
    """Preview, then convert; returns once the run has finished."""
    select_survey_file(page, tmp_path)
    if session:
        page.fill("#convertSessionCustom", session)
    page.click("#previewBtn")
    expect(page.locator("#convertBtn")).to_be_enabled(timeout=30000)
    page.click("#convertBtn")
    page.wait_for_function(
        "() => !document.getElementById('surveyRunProgressContainer') "
        "|| getComputedStyle(document.getElementById('surveyRunProgressContainer')).display === 'none'",
        timeout=60000,
    )


def written_files(project):
    return sorted(p.relative_to(project).as_posix() for p in project.glob("sub-*/**/*") if p.is_file())


@pytest.mark.parametrize("session", ["1", "01", "pre"])
def test_survey_convert_writes_prism_files_in_the_session_exactly_as_typed(app_page, studio_url, tmp_path, project, session):
    open_survey_tab(app_page, studio_url)

    convert_survey(app_page, tmp_path, session)

    written = written_files(project)
    for participant in ("sub-P001", "sub-P002"):
        assert any(f"{participant}/ses-{session}/" in p and p.endswith(".tsv") for p in written), written


def test_survey_convert_without_a_session_asks_for_one_and_writes_nothing(app_page, studio_url, tmp_path, project):
    open_survey_tab(app_page, studio_url)

    convert_survey(app_page, tmp_path, session="")

    expect(app_page.locator("#convertError")).to_contain_text("session ID")
    assert written_files(project) == []


def test_version_detection_falls_back_to_the_global_library_like_convert_does(app_page, studio_url, tmp_path):
    """The project library is empty, so only the global BRS template can match the columns."""
    open_survey_tab(app_page, studio_url)

    with app_page.expect_response("**/api/survey-detect-version-contexts") as detect:
        select_survey_file(app_page, tmp_path)

    assert detect.value.status == 200, detect.value.text()
