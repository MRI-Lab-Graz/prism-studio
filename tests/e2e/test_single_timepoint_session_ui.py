"""A one-timepoint (cross-sectional) project: every session control is greyed out, the import writes ses-1."""

import json
from pathlib import Path

from playwright.sync_api import expect

from tests.e2e.test_converter_flows import open_survey_tab
from tests.e2e.test_session_map_flows import PEOPLE_LONG, make_longitudinal

LONG = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP002,post,1,0,2\n"


def survey_file(page, tmp_path, text=LONG):
    data = tmp_path / "brs.csv"
    data.write_text(text)
    page.set_input_files("#convertSurveyFile", str(data))


def test_survey_session_is_greyed_out_and_the_import_needs_no_session_choice(app_page, studio_url, tmp_path, project):
    open_survey_tab(app_page, studio_url)

    group = app_page.locator("#convertSessionGroup")
    expect(group).to_have_class(__import__("re").compile("session-derived"))
    expect(app_page.locator("#convertSessionSelect")).to_be_disabled()
    expect(app_page.locator("#convertSessionCustom")).to_be_disabled()
    expect(app_page.locator("#convertSessionBadge")).to_have_text("ONE TIMEPOINT")
    expect(app_page.locator("#convertSessionHint")).to_contain_text("ses-1")

    survey_file(app_page, tmp_path)
    expect(app_page.locator("#previewBtn")).to_be_enabled(timeout=30000)


def test_survey_session_stays_editable_in_a_longitudinal_project(app_page, studio_url, project):
    make_longitudinal(project)
    open_survey_tab(app_page, studio_url)

    expect(app_page.locator("#convertSessionSelect")).to_be_enabled()
    expect(app_page.locator("#convertSessionBadge")).to_have_text("REQUIRED")


def test_biometrics_session_is_greyed_out(app_page, studio_url):
    app_page.goto(f"{studio_url}/converter")
    app_page.click("#biometrics-tab")

    expect(app_page.locator("#biometricsSessionSelect")).to_be_disabled()
    expect(app_page.locator("#biometricsSessionCustom")).to_be_disabled()
    expect(app_page.locator("#biometricsSessionBadge")).to_have_text("ONE TIMEPOINT")


def test_environment_session_is_greyed_out(app_page, studio_url):
    app_page.goto(f"{studio_url}/converter")
    app_page.click("#environment-tab")

    expect(app_page.locator("#envSessionCol")).to_be_disabled()
    expect(app_page.locator("#envSessionOverride")).to_be_disabled()
    expect(app_page.locator("#envSessionBadge")).to_have_text("ONE TIMEPOINT")


def test_participants_cannot_split_values_by_session(app_page, studio_url, tmp_path):
    app_page.goto(f"{studio_url}/converter")
    app_page.click("#participants-tab")
    data = tmp_path / "people.csv"
    data.write_text(PEOPLE_LONG)
    app_page.set_input_files("#participantsDataFile", str(data))
    app_page.click("#participantsPreviewBtn")
    expect(app_page.locator("#participantsSessionChoiceCard")).to_be_visible(timeout=30000)

    expect(app_page.locator("#participantsSessionModeSplit")).to_be_disabled()
    expect(app_page.locator("#participantsSessionModeOne")).to_be_enabled()
