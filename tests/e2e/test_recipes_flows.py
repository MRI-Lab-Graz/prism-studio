"""Recipes page: score converted questionnaires and export the result."""

import csv
import json
import shutil
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from src.converters.survey import convert_survey_file_to_prism_dataset

BRS = Path(__file__).resolve().parents[2] / "official" / "library" / "survey" / "survey-brs.json"
RECIPE = Path(__file__).resolve().parents[2] / "official" / "recipe" / "survey" / "recipe-brs.json"
DATA = "participant_id,session,BRS01,BRS02,BRS03\nP001,1,3,4,2\nP001,2,4,4,3\nP002,1,1,0,2\n"
# BRS Total = BRS01 + BRS02 + BRS03:  P001 ses-1 = 9, P001 ses-2 = 11, P002 ses-1 = 3


@pytest.fixture
def scored_project(project, tmp_path):
    """The throwaway project holding real converter output for two subjects and two sessions."""
    library = tmp_path / "lib"
    library.mkdir()
    shutil.copy(BRS, library / "survey-brs.json")
    (project / "code" / "library" / "survey").mkdir(parents=True, exist_ok=True)
    shutil.copy(BRS, project / "code" / "library" / "survey" / "survey-brs.json")
    source = tmp_path / "brs.csv"
    source.write_text(DATA)
    convert_survey_file_to_prism_dataset(
        input_path=source, library_dir=library, output_root=project, name="t",
        id_column="participant_id", session_column="session", session="all",
        project_path=project, force=True, skip_participants=False,
    )
    return project


def data_files(project):
    return {
        p.relative_to(project).as_posix(): p.read_bytes()
        for p in project.rglob("sub-*/**/*")
        if p.is_file()
    }


def read_rows(path):
    with open(path, newline="") as handle:
        return list(csv.reader(handle))


def eventually(condition, page, timeout=60.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        page.wait_for_timeout(250)  # through the page, so Playwright keeps serving its events
    return False


def open_recipes(page, studio_url, *, fmt="csv", anonymize=False, layout=None, include_raw=None):
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(f"{studio_url}/recipes")
    expect(page.locator("#derivRunBtn")).to_be_enabled(timeout=30000)
    page.select_option("#derivFormat", fmt)
    page.locator("#derivAnonymize").set_checked(anonymize)
    if layout:
        page.select_option("#derivLayout", layout)
    if include_raw is not None:
        page.locator("#derivIncludeRaw").set_checked(include_raw)


def run_and_wait_for(page, output_file):
    page.click("#derivRunBtn")
    assert eventually(output_file.exists, page), "the export was never written"
    page.wait_for_timeout(500)  # let companion files land


def test_scores_every_session_one_row_per_session_and_leaves_the_data_alone(app_page, studio_url, scored_project):
    before = data_files(scored_project)
    open_recipes(app_page, studio_url)

    run_and_wait_for(app_page, scored_project / "derivatives/survey/long_en/e2e_brs.csv")

    assert read_rows(scored_project / "derivatives/survey/long_en/e2e_brs.csv") == [
        ["participant_id", "session", "Total"],
        ["sub-P001", "ses-1", "9"],
        ["sub-P001", "ses-2", "11"],
        ["sub-P002", "ses-1", "3"],
    ]
    folder = scored_project / "derivatives/survey/long_en"
    assert (folder / "e2e_brs_codebook.json").is_file() and (folder / "e2e_brs_codebook.tsv").is_file()
    assert data_files(scored_project) == before  # "your data is not changed"


def test_wide_layout_gives_one_row_per_participant(app_page, studio_url, scored_project):
    open_recipes(app_page, studio_url, layout="wide")

    run_and_wait_for(app_page, scored_project / "derivatives/survey/wide_en/e2e_brs.csv")

    assert read_rows(scored_project / "derivatives/survey/wide_en/e2e_brs.csv") == [
        ["participant_id", "Total_ses-1", "Total_ses-2"],
        ["sub-P001", "9", "11"],
        ["sub-P002", "3", ""],
    ]


def test_raw_item_columns_are_added_only_when_asked_for(app_page, studio_url, scored_project):
    open_recipes(app_page, studio_url, include_raw=True)

    run_and_wait_for(app_page, scored_project / "derivatives/survey/long_en/e2e_brs.csv")

    rows = read_rows(scored_project / "derivatives/survey/long_en/e2e_brs.csv")
    header = rows[0]
    assert {"BRS01", "BRS02", "BRS03", "Total"} <= set(header), header
    first = dict(zip(header, rows[1]))
    assert (first["BRS01"], first["BRS02"], first["BRS03"], first["Total"]) == ("3", "4", "2", "9")


def test_one_session_only_scores_just_that_session(app_page, studio_url, scored_project):
    open_recipes(app_page, studio_url)
    app_page.locator("#derivSessionsAll").uncheck()
    app_page.select_option("#derivSessions", "ses-1")

    app_page.click("#derivRunBtn")

    assert eventually(lambda: any(scored_project.glob("derivatives/**/*brs.csv")), app_page)
    app_page.wait_for_timeout(500)
    [out] = list(scored_project.glob("derivatives/**/*brs.csv"))
    assert read_rows(out) == [
        ["participant_id", "session", "Total"],
        ["sub-P001", "ses-1", "9"],
        ["sub-P002", "ses-1", "3"],
    ]


def test_anonymizing_replaces_the_ids_consistently_and_keeps_the_scores(app_page, studio_url, scored_project):
    open_recipes(app_page, studio_url, anonymize=True)
    out = scored_project / "derivatives/survey/long_en_anon"

    run_and_wait_for(app_page, out / "e2e_brs.csv")

    rows = read_rows(out / "e2e_brs.csv")[1:]
    ids = [row[0] for row in rows]
    assert not any("P00" in identifier for identifier in ids), ids  # no original ID survives
    assert ids[0] == ids[1] != ids[2]  # same person -> same new ID, different person -> different
    assert [row[2] for row in rows] == ["9", "11", "3"]  # scores untouched
    mapping = json.loads((out / "participants_mapping.json").read_text())["mapping"]
    assert set(mapping) == {"sub-P001", "sub-P002"}
    assert mapping["sub-P001"] == ids[0] and mapping["sub-P002"] == ids[2]


def test_xlsx_export_opens_and_holds_the_scores(app_page, studio_url, scored_project):
    openpyxl = pytest.importorskip("openpyxl")
    open_recipes(app_page, studio_url, fmt="xlsx")
    out = scored_project / "derivatives/survey/long_en/e2e_brs.xlsx"

    run_and_wait_for(app_page, out)

    sheet = openpyxl.load_workbook(out).active
    rows = [[cell for cell in row] for row in sheet.iter_rows(values_only=True)]
    assert rows[0] == ("participant_id", "session", "Total") or list(rows[0]) == ["participant_id", "session", "Total"]
    assert [row[2] for row in rows[1:]] == [9, 11, 3] or [str(row[2]) for row in rows[1:]] == ["9", "11", "3"]


def test_sav_export_keeps_the_value_labels(app_page, studio_url, scored_project):
    pyreadstat = pytest.importorskip("pyreadstat")
    open_recipes(app_page, studio_url, fmt="sav")
    out = scored_project / "derivatives/survey/long_en/e2e_brs.sav"

    run_and_wait_for(app_page, out)

    frame, meta = pyreadstat.read_sav(str(out))
    assert list(frame.columns)[:3] == ["participant_id", "session", "Total"]
    assert list(frame["Total"]) == [9, 11, 3]


def test_a_custom_recipe_folder_overrides_the_official_recipe(app_page, studio_url, scored_project, tmp_path):
    custom = tmp_path / "my-recipes"
    custom.mkdir()
    recipe = json.loads(RECIPE.read_text())
    recipe["Scores"][0]["Method"] = "mean"
    recipe["Scores"][0]["Range"] = {"min": 0, "max": 4}
    (custom / "recipe-brs.json").write_text(json.dumps(recipe))
    open_recipes(app_page, studio_url)
    app_page.fill("#derivRecipeDir", str(custom))

    run_and_wait_for(app_page, scored_project / "derivatives/survey/long_en/e2e_brs.csv")

    totals = [float(row[2]) for row in read_rows(scored_project / "derivatives/survey/long_en/e2e_brs.csv")[1:]]
    assert totals == pytest.approx([3.0, 11 / 3, 1.0])  # the mean, not the sum


def test_a_recipe_filter_that_matches_nothing_writes_nothing(app_page, studio_url, scored_project):
    app_page.allowed_http[400] = "/api/recipes-surveys"
    app_page.allowed_http[404] = "/api/recipes-surveys"
    open_recipes(app_page, studio_url)
    app_page.fill("#derivSurvey", "no-such-survey")

    app_page.click("#derivRunBtn")

    app_page.wait_for_timeout(4000)
    assert not list(scored_project.glob("derivatives/**/*.csv"))
    expect(app_page.locator("#derivRunBtn")).to_be_enabled()


def test_without_a_project_the_page_says_so(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/recipes")

    expect(bare_page.locator("body")).to_contain_text("No project loaded")
