"""Converter page: convert real input files the way a user does."""

import json
import shutil

import pytest
from playwright.sync_api import expect

from src.session_map import save_session_map
from tests.template_fixtures import completed_official_library

BRS_CSV = "participant_id,BRS01,BRS02,BRS03\nP001,3,4,2\nP002,1,0,2\n"


@pytest.fixture
def longitudinal(project):
    """Choosing and typing a session is what a project with several timepoints offers (a one-timepoint
    project greys the session out: see test_single_timepoint_session_ui.py). Labels map to themselves."""
    meta = json.loads((project / "project.json").read_text())
    meta["StudyDesign"] = {"Timepoints": "multiple"}
    (project / "project.json").write_text(json.dumps(meta))
    save_session_map(project, {label: label for label in ("1", "01", "2", "3", "pre", "post")})


@pytest.fixture
def project_with_brs(project):
    """The project holds a completed copy of the BRS template, as after the "complete your template" step:
    converting data needs a project template that says who answered and how it was administered."""
    shutil.copy(completed_official_library() / "survey-brs.json", project / "code" / "library" / "survey" / "survey-brs.json")


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


def convert_survey(page, tmp_path, session, content=BRS_CSV):
    """Preview, then convert; returns once the run has finished."""
    select_survey_file(page, tmp_path, content)
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
@pytest.mark.usefixtures("longitudinal")
@pytest.mark.usefixtures("project_with_brs")
def test_survey_convert_writes_prism_files_in_the_session_exactly_as_typed(app_page, studio_url, tmp_path, project, session):
    open_survey_tab(app_page, studio_url)

    convert_survey(app_page, tmp_path, session)

    written = written_files(project)
    for participant in ("sub-P001", "sub-P002"):
        assert any(f"{participant}/ses-{session}/" in p and p.endswith(".tsv") for p in written), written


@pytest.mark.usefixtures("longitudinal")
def test_survey_convert_without_a_session_asks_for_one_and_writes_nothing(app_page, studio_url, tmp_path, project):
    app_page.allowed_http[400] = "/api/survey-detect-version-contexts"  # a longitudinal project wants a session
    app_page.allowed_http[500] = "/api/survey-workflow-command"
    open_survey_tab(app_page, studio_url)
    select_survey_file(app_page, tmp_path)

    app_page.click("#previewBtn")

    expect(app_page.locator("#convertBtn")).to_be_disabled()  # no preview, so nothing to convert
    expect(app_page.locator("#convertError")).to_contain_text("session", timeout=30000)
    assert written_files(project) == []


def test_version_detection_falls_back_to_the_global_library_like_convert_does(app_page, studio_url, tmp_path):
    """The project library is empty, so only the global BRS template can match the columns."""
    open_survey_tab(app_page, studio_url)

    with app_page.expect_response("**/api/survey-detect-version-contexts") as detect:
        select_survey_file(app_page, tmp_path)

    assert detect.value.status == 200, detect.value.text()


def test_previewing_with_only_the_official_template_names_what_is_missing_and_leaves_a_copy_to_fill_in(
    app_page, studio_url, tmp_path, project
):
    app_page.allowed_http[400] = "/api/survey-workflow-command"
    open_survey_tab(app_page, studio_url)
    select_survey_file(app_page, tmp_path)

    app_page.click("#previewBtn")

    error = app_page.locator("#convertError")
    expect(error).to_contain_text("Technical/Respondent", timeout=30000)
    expect(error).to_contain_text("code/library/survey/survey-brs.json")
    assert (project / "code" / "library" / "survey" / "survey-brs.json").is_file()  # to fill in, in the Template editor
    expect(app_page.locator("#convertBtn")).to_be_disabled()
    assert written_files(project) == []


def _session_label_is_green(page):
    """The Session ID label is green once a session is chosen, red while it is still missing."""
    r, g, _ = page.evaluate(
        "() => getComputedStyle(document.querySelector('#convertSessionGroup label'))"
        ".color.match(/\\d+/g).map(Number)"
    )
    return g > r


@pytest.mark.usefixtures("longitudinal")
def test_session_id_label_turns_green_once_a_session_is_chosen(app_page, studio_url):
    open_survey_tab(app_page, studio_url)
    assert not _session_label_is_green(app_page)

    app_page.fill("#convertSessionCustom", "1")
    assert _session_label_is_green(app_page)

    app_page.fill("#convertSessionCustom", "")
    assert not _session_label_is_green(app_page)


REPEATED_CSV = (
    "participant_id,startdate,BRS01,BRS02,BRS03\n"
    "P001,2026-09-01 10:00:00,4,4,3\n"
    "P001,2026-03-01 10:00:00,3,4,2\n"
    "P002,2026-03-02 10:00:00,1,0,2\n"
)


@pytest.mark.usefixtures("longitudinal")
@pytest.mark.usefixtures("project_with_brs")
def test_repeated_ids_become_dated_sessions_when_the_page_asks_for_it(app_page, studio_url, tmp_path, project):
    open_survey_tab(app_page, studio_url)
    app_page.select_option("#convertDuplicateHandling", "sessions")

    convert_survey(app_page, tmp_path, session=None, content=REPEATED_CSV)

    assert sorted(p.name for p in (project / "sub-P001").glob("ses-*")) == ["ses-1", "ses-2"]


def test_questionnaire_without_template_is_offered_for_saving_and_does_not_block(app_page, studio_url, tmp_path, project):
    import shutil

    from tests.test_survey_cli_lsa import _library
    from tests.test_survey_lsa_unmatched_groups import _lsa_with_two_questionnaires

    shutil.copy(_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(_lsa_with_two_questionnaires(tmp_path)))
    app_page.select_option("#convertIdColumn", "token")
    app_page.select_option("#convertDuplicateHandling", "error")  # a .lsa defaults to sessions-from-dates

    app_page.click("#previewBtn")

    expect(app_page.get_by_role("button", name="Save Template").first).to_be_visible(timeout=30000)
    expect(app_page.locator("#convertBtn")).to_be_enabled()  # the matched questionnaire still converts


@pytest.mark.usefixtures("longitudinal")
def test_dates_mode_disables_the_session_id_box_and_explains_why(app_page, studio_url):
    open_survey_tab(app_page, studio_url)
    app_page.fill("#convertSessionCustom", "pre")
    app_page.select_option("#convertDuplicateHandling", "sessions")

    expect(app_page.locator("#convertSessionSelect")).to_be_disabled()
    expect(app_page.locator("#convertSessionCustom")).to_be_disabled()
    expect(app_page.locator("#convertSessionHint")).to_contain_text("completed responses only")
    expect(app_page.locator("#convertSessionBadge")).to_have_text("FROM DATES")

    app_page.select_option("#convertDuplicateHandling", "error")
    expect(app_page.locator("#convertSessionCustom")).to_be_enabled()
    expect(app_page.locator("#convertSessionBadge")).to_have_text("REQUIRED")
    expect(app_page.locator("#convertSessionCustom")).to_have_value("")


@pytest.mark.usefixtures("longitudinal")
def test_dates_mode_converts_without_a_typed_session_id(app_page, studio_url, tmp_path, project):
    from tests.lsa_fixtures import make_library, make_lsa
    import shutil

    shutil.copy(make_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(make_lsa(tmp_path)))
    app_page.select_option("#convertIdColumn", "token")
    app_page.select_option("#convertDuplicateHandling", "sessions")

    app_page.click("#previewBtn")
    expect(app_page.locator("#convertBtn")).to_be_enabled(timeout=30000)
    expect(app_page.locator("#conversionSummaryBody")).to_contain_text("incomplete response(s) left out")
    app_page.click("#convertBtn")
    app_page.wait_for_function(
        "() => !document.getElementById('surveyRunProgressContainer') "
        "|| getComputedStyle(document.getElementById('surveyRunProgressContainer')).display === 'none'",
        timeout=60000,
    )

    assert sorted(p.name for p in (project / "sub-a").glob("ses-*")) == ["ses-1", "ses-2"]


def test_dates_mode_refreshes_the_session_map_panel_with_the_real_labels(app_page, studio_url, tmp_path, project):
    import json

    from tests.lsa_fixtures import make_library, make_lsa
    import shutil

    app_page.allowed_http[409] = "/api/survey-detect-version-contexts"  # unmapped labels are the point
    app_page.allowed_http[400] = "/api/survey-detect-version-contexts"  # error mode has no session yet
    meta = json.loads((project / "project.json").read_text())  # keep the complete project, change the timepoints
    meta["StudyDesign"] = {"Timepoints": "multiple"}
    (project / "project.json").write_text(json.dumps(meta))
    shutil.copy(make_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(make_lsa(tmp_path)))
    # Let the debounced sync for the ID column settle first, so only the dropdown change can refresh the panel.
    with app_page.expect_response(lambda r: "/api/survey-detect-version-contexts" in r.url, timeout=30000):
        app_page.select_option("#convertIdColumn", "token")
    app_page.wait_for_timeout(500)

    app_page.select_option("#convertDuplicateHandling", "sessions")

    # a has two completed responses, c one: the generated labels are 1 and 2 (not a typed one).
    expect(app_page.locator("#sessionMapRows .input-group-text")).to_have_text(["1", "2"], timeout=30000)
    expect(app_page.locator("#sessionMapRows input")).to_have_count(2)


@pytest.mark.usefixtures("longitudinal")
def test_review_table_shows_the_responses_and_a_skip_changes_the_preview(app_page, studio_url, tmp_path, project):
    from tests.lsa_fixtures import make_library, make_lsa
    import shutil

    shutil.copy(make_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(make_lsa(tmp_path)))
    app_page.select_option("#convertIdColumn", "token")
    app_page.select_option("#convertDuplicateHandling", "sessions")

    app_page.click("#sessionAssignmentsBtn")

    rows = app_page.locator("#sessionAssignmentsBody tbody tr")
    expect(rows).to_have_count(6, timeout=15000)
    expect(app_page.locator("#sessionAssignmentsBody")).to_contain_text("left out")
    row2 = app_page.locator("#sessionAssignmentsBody tr[data-response-id='2']")
    expect(row2.locator(".session-cell")).to_have_text("1")

    row2.locator("input[type=checkbox][data-role=skip]").check()   # skip a's first completed response
    expect(app_page.locator("#sessionAssignmentsBody tr[data-response-id='3'] .session-cell")).to_have_text("1")
    import json
    saved = json.loads((project / "code" / "session_assignments.json").read_text())
    assert saved == {"version": 2, "surveys": {"999999": {"responses": {"2": {"skip": True}}}}}


@pytest.mark.usefixtures("longitudinal")
def test_review_table_pre_skips_incomplete_rows_and_unticking_includes_them(app_page, studio_url, tmp_path, project):
    from tests.lsa_fixtures import make_library, make_lsa
    import json
    import shutil

    shutil.copy(make_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(make_lsa(tmp_path)))
    app_page.select_option("#convertIdColumn", "token")
    app_page.select_option("#convertDuplicateHandling", "sessions")
    app_page.click("#sessionAssignmentsBtn")

    body = app_page.locator("#sessionAssignmentsBody")
    row1 = body.locator("tr[data-response-id='1']")
    skip1 = row1.locator("input[data-role=skip]")
    expect(skip1).to_be_checked(timeout=15000)
    expect(body.locator("tr[data-response-id='2'] input[data-role=skip]")).not_to_be_checked()

    skip1.uncheck()

    expect(row1.locator(".session-cell")).to_have_text("1", timeout=15000)
    expect(row1.locator("input[data-role=skip]")).not_to_be_checked()
    saved = json.loads((project / "code" / "session_assignments.json").read_text())
    assert saved == {"version": 2, "surveys": {"999999": {"responses": {"1": {"include": True}}}}}


@pytest.mark.usefixtures("longitudinal")
def test_review_session_assignment_button_folds_the_table_back_in(app_page, studio_url, tmp_path, project):
    from tests.lsa_fixtures import make_library, make_lsa
    import shutil

    shutil.copy(make_library(tmp_path) / "survey-wellbeing.json", project / "code" / "library" / "survey")
    open_survey_tab(app_page, studio_url)
    app_page.set_input_files("#convertSurveyFile", str(make_lsa(tmp_path)))
    app_page.select_option("#convertIdColumn", "token")
    app_page.select_option("#convertDuplicateHandling", "sessions")
    rows = app_page.locator("#sessionAssignmentsBody tbody tr")

    app_page.click("#sessionAssignmentsBtn")
    expect(rows).to_have_count(6, timeout=15000)

    app_page.click("#sessionAssignmentsBtn")  # second click folds it back in
    expect(app_page.locator("#sessionAssignmentsBody")).to_be_empty()

    app_page.click("#sessionAssignmentsBtn")  # and a third shows it again
    expect(rows).to_have_count(6, timeout=15000)


@pytest.mark.usefixtures("project_with_brs")
def test_preview_lists_every_answer_outside_the_scale_with_the_participant(app_page, studio_url, tmp_path):
    open_survey_tab(app_page, studio_url)
    select_survey_file(app_page, tmp_path, "participant_id,BRS01,BRS02,BRS03\nP001,9,4,2\nP002,-1,0,2\nP003,often,1,1\n")
    app_page.click("#previewBtn")
    log = app_page.locator("#conversionLog")
    expect(log).to_contain_text("outside the scale 0-4", timeout=30000)
    expect(log).to_contain_text("P001: 9")
    expect(log).to_contain_text("P002: -1")
    expect(log).to_contain_text("P003: often")


def test_a_semicolon_survey_file_is_read_with_auto_detect(app_page, studio_url, tmp_path):
    open_survey_tab(app_page, studio_url)
    data = tmp_path / "semi.csv"
    data.write_text("participant_id;BRS01;BRS02;BRS03\nP001;3;4;2\nP002;1;0;2\n")
    app_page.set_input_files("#convertSurveyFile", str(data))
    expect(app_page.locator("#convertIdColumn")).to_have_value("participant_id", timeout=30000)


@pytest.mark.usefixtures("project_with_brs")
def test_preview_warns_about_skipped_rows_and_cleaned_labels(app_page, studio_url, tmp_path):
    open_survey_tab(app_page, studio_url)
    select_survey_file(app_page, tmp_path, "participant_id,BRS01,BRS02,BRS03\nP9,2,2,2\n,3,4,2\nP 1,1,0,2\n")
    app_page.click("#previewBtn")  # a one-timepoint project asks for no session
    log = app_page.locator("#conversionLog")
    expect(log).to_contain_text("no participant ID", timeout=30000)
    expect(log).to_contain_text("'P 1' → sub-P1")
