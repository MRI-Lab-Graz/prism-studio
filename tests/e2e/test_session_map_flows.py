"""Longitudinal projects: the user maps every session label; nothing is filled in."""

import json

from playwright.sync_api import expect

from tests.e2e.test_converter_flows import open_survey_tab

LONG = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP001,post,4,4,3\nP002,pre,1,0,2\n"


DETECT = "/api/survey-detect-version-contexts"


def make_longitudinal(project):
    (project / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}))


def select_file(page, tmp_path):
    data = tmp_path / "brs.csv"
    data.write_text(LONG)
    page.set_input_files("#convertSurveyFile", str(data))


def test_unmapped_labels_show_empty_inputs_and_block_preview(app_page, studio_url, tmp_path, project):
    app_page.allowed_http[409] = DETECT  # unmapped labels are the point of this test
    make_longitudinal(project)
    open_survey_tab(app_page, studio_url)

    select_file(app_page, tmp_path)

    expect(app_page.locator("#sessionMapPanel")).to_be_visible(timeout=30000)
    inputs = app_page.locator("#sessionMapRows input")
    expect(inputs).to_have_count(2)
    for index in range(2):
        expect(inputs.nth(index)).to_have_value("")  # never pre-filled
    expect(app_page.locator("#previewBtn")).to_be_disabled()
    expect(app_page.locator("#sessionMapSaveBtn")).to_be_disabled()


def test_mapping_the_labels_unlocks_preview_and_convert_uses_the_names(app_page, studio_url, tmp_path, project):
    app_page.allowed_http[409] = DETECT  # unmapped labels are the point of this test
    make_longitudinal(project)
    open_survey_tab(app_page, studio_url)
    select_file(app_page, tmp_path)
    expect(app_page.locator("#sessionMapPanel")).to_be_visible(timeout=30000)

    inputs = app_page.locator("#sessionMapRows input")
    inputs.nth(0).fill("1")
    inputs.nth(1).fill("2")
    app_page.click("#sessionMapSaveBtn")

    expect(app_page.locator("#sessionMapPanel")).to_be_hidden(timeout=30000)
    saved = json.loads((project / "code" / "session_map.json").read_text())
    assert set(saved.values()) == {"1", "2"} and set(saved) == {"pre", "post"}
    app_page.select_option("#convertSessionSelect", "all")
    expect(app_page.locator("#previewBtn")).to_be_enabled()
    app_page.click("#previewBtn")
    expect(app_page.locator("#convertBtn")).to_be_enabled(timeout=30000)
    app_page.click("#convertBtn")
    app_page.wait_for_function(
        "() => !document.getElementById('surveyRunProgressContainer') "
        "|| getComputedStyle(document.getElementById('surveyRunProgressContainer')).display === 'none'",
        timeout=60000,
    )
    names = sorted(p.name for p in (project / "sub-P001").glob("ses-*"))
    assert names == ["ses-1", "ses-2"]


def test_participants_convert_names_the_unmapped_chosen_session(app_page, studio_url, tmp_path, project):
    make_longitudinal(project)
    app_page.on("dialog", lambda dialog: dialog.accept())
    app_page.goto(f"{studio_url}/converter")
    app_page.click("#participants-tab")
    data = tmp_path / "people.csv"
    data.write_text("participant_id,session,age\nP001,pre,21\nP001,post,22\nP002,pre,34\n")
    app_page.set_input_files("#participantsDataFile", str(data))
    app_page.click("#participantsPreviewBtn")
    expect(app_page.locator("#participantsSessionChoiceCard")).to_be_visible(timeout=30000)
    app_page.click("#participantsSessionLongitudinalYes")
    app_page.select_option("#participantsSessionColumn", "session")
    app_page.select_option("#participantsSessionValue", "pre")
    expect(app_page.locator("#participantsConvertBtn")).to_be_enabled(timeout=30000)

    app_page.click("#participantsConvertBtn")

    expect(app_page.locator("#participantsError")).to_contain_text("'pre'", timeout=30000)
    assert not (project / "participants.tsv").exists()


def test_a_blank_session_cell_is_explained_and_never_offered_as_something_to_map(app_page, studio_url, tmp_path, project):
    app_page.allowed_http[409] = DETECT
    make_longitudinal(project)
    open_survey_tab(app_page, studio_url)
    data = tmp_path / "brs.csv"
    data.write_text("participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP002,,1,0,2\n")

    app_page.set_input_files("#convertSurveyFile", str(data))
    # The page auto-picks the one real session ('pre'), which never imports the blank row;
    # importing "All sessions" is what brings the blank cell into play.
    app_page.select_option("#convertSessionSelect", "all")

    expect(app_page.locator("#sessionMapRows")).to_contain_text("no session value", timeout=30000)
    expect(app_page.locator("#sessionMapRows input")).to_have_count(1)  # only 'pre' can be mapped
    expect(app_page.locator("#sessionMapRows")).to_contain_text("no session value")
    app_page.locator("#sessionMapRows input").fill("1")
    app_page.click("#sessionMapSaveBtn")
    # 'pre' is saved, but the blank cell still blocks: fixing the file is the only way out
    expect(app_page.locator("#sessionMapRows input")).to_have_count(0, timeout=30000)
    expect(app_page.locator("#previewBtn")).to_be_disabled()
