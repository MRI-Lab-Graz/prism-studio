"""Validate page: run the validator on the open project and read the results."""

import json
import re
import shutil
from pathlib import Path

import pytest
from playwright.sync_api import expect

from src.converters.survey import convert_survey_file_to_prism_dataset

BRS = Path(__file__).resolve().parents[2] / "official" / "library" / "survey" / "survey-brs.json"
DATA = "participant_id,session,BRS01,BRS02,BRS03\nP001,1,3,4,2\nP002,1,1,0,2\n"


@pytest.fixture
def converted_project(tmp_path):
    """A project created the way the Projects page creates it, holding converted survey data."""
    from src.project_manager import ProjectManager

    root = tmp_path / "fresh"
    created = ProjectManager().create_project(str(root), {"name": "fresh", "sessions": 0})
    assert created["success"], created
    meta = json.loads((root / "project.json").read_text())
    meta.setdefault("StudyDesign", {})["Timepoints"] = "single"
    (root / "project.json").write_text(json.dumps(meta))
    library = tmp_path / "lib"
    library.mkdir()
    shutil.copy(BRS, library / "survey-brs.json")
    (root / "code" / "library" / "survey").mkdir(parents=True, exist_ok=True)
    shutil.copy(BRS, root / "code" / "library" / "survey" / "survey-brs.json")
    source = tmp_path / "brs.csv"
    source.write_text(DATA)
    convert_survey_file_to_prism_dataset(
        input_path=source, library_dir=library, output_root=root, name="t",
        id_column="participant_id", session_column="session", session="all",
        project_path=root, force=True, skip_participants=False,
    )
    return root


@pytest.fixture
def project(converted_project):
    """app_page opens this one instead of the bare throwaway project."""
    return converted_project


def validate_current(page, studio_url):
    page.goto(f"{studio_url}/validate")
    expect(page.locator("#uploadBtn")).to_be_enabled()
    page.click("#uploadBtn")
    page.wait_for_url("**/results/**", timeout=120000)


def verdict(page):
    return page.locator("body").inner_text()


def test_a_clean_project_is_valid_and_the_recipe_note_is_named_not_generic(app_page, studio_url):
    validate_current(app_page, studio_url)

    expect(app_page.get_by_text("Dataset is Valid!")).to_be_visible()
    # The warning about the missing recipe has its own code, not the catch-all PRISM999.
    expect(app_page.get_by_text("PRISM708")).to_be_visible()
    assert "PRISM999" not in verdict(app_page)
    app_page.get_by_text("PRISM708").click()
    expect(app_page.get_by_text("Missing survey recipes for dataset-used surveys")).to_be_visible()


def test_a_misnamed_data_file_is_an_error_that_names_the_file(app_page, studio_url, converted_project):
    survey_dir = next(converted_project.glob("sub-*/**/survey"))
    good = next(survey_dir.glob("*_survey.tsv"))
    bad = good.with_name(good.name.replace("_survey.tsv", "_survey_oops.tsv"))
    good.rename(bad)

    validate_current(app_page, studio_url)

    expect(app_page.get_by_role("heading", name=re.compile("Dataset has"))).to_be_visible()
    assert bad.name in verdict(app_page)
    app_page.get_by_role("button", name=re.compile("PRISM101")).click()
    expect(app_page.get_by_text("File Management > Filename Renamer").first).to_be_visible()
    assert "Dataset is Valid" not in verdict(app_page)


def test_fixing_the_file_and_revalidating_turns_the_verdict_green(app_page, studio_url, converted_project):
    survey_dir = next(converted_project.glob("sub-*/**/survey"))
    good = next(survey_dir.glob("*_survey.tsv"))
    bad = good.with_name(good.name.replace("_survey.tsv", "_survey_oops.tsv"))
    good.rename(bad)
    validate_current(app_page, studio_url)
    expect(app_page.get_by_role("heading", name=re.compile("Dataset has"))).to_be_visible()

    bad.rename(good)
    app_page.click("#revalidateSubmitBtn")

    expect(app_page.get_by_text("Dataset is Valid!")).to_be_visible(timeout=120000)


def test_the_report_download_matches_what_the_page_says(app_page, studio_url):
    validate_current(app_page, studio_url)
    result_id = app_page.url.rsplit("/", 1)[1]

    report = app_page.request.get(f"{studio_url}/download_report/{result_id}").json()

    assert report["results"]["valid"] is True
    assert report["results"]["summary"]["total_errors"] == 0
    assert set(report["results"]["warning_groups"]) == {"PRISM708"}


def test_without_a_project_nothing_can_be_validated_until_a_folder_is_chosen(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/validate")

    expect(bare_page.locator("#uploadBtn")).to_be_disabled()
    expect(bare_page.locator("#targetOtherFolder")).to_be_checked()


def test_prism_only_mode_skips_the_bids_validator(app_page, studio_url):
    app_page.goto(f"{studio_url}/validate")
    expect(app_page.locator("#mode_prism")).to_be_disabled()  # advanced options start locked
    app_page.locator("details summary", has_text="Advanced Options").click()
    app_page.locator("#advancedOptionsToggle").check()
    app_page.locator("#mode_prism").check()
    app_page.click("#uploadBtn")
    app_page.wait_for_url("**/results/**", timeout=120000)

    expect(app_page.get_by_text("Dataset is Valid!")).to_be_visible()
    assert "BIDS validator:" not in verdict(app_page)
    expect(app_page.locator("#revalidateMode")).to_have_value("prism-only")


def test_bids_only_mode_runs_without_the_prism_checks(app_page, studio_url):
    app_page.goto(f"{studio_url}/validate")
    app_page.locator("details summary", has_text="Advanced Options").click()
    app_page.locator("#advancedOptionsToggle").check()
    app_page.locator("#mode_bids").check()
    app_page.click("#uploadBtn")
    app_page.wait_for_url("**/results/**", timeout=120000)

    expect(app_page.locator("#revalidateMode")).to_have_value("bids-only")
    assert "PRISM708" not in verdict(app_page)  # a PRISM check, so it must not have run


def test_an_empty_project_says_there_is_no_data_instead_of_passing(bare_page, studio_url, tmp_path):
    from src.project_manager import ProjectManager

    empty = tmp_path / "empty"
    assert ProjectManager().create_project(str(empty), {"name": "empty", "sessions": 0})["success"]
    bare_page.request.post(f"{studio_url}/api/projects/current", data={"path": str(empty), "name": "empty"})

    validate_current(bare_page, studio_url)

    assert "Dataset is Valid" not in verdict(bare_page)
    expect(bare_page.get_by_role("button", name=re.compile("PRISM002"))).to_be_visible()
