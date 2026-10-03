"""Recipe builder: build a scoring recipe in the page, save it, and score data with it."""

import json
import re
import shutil

import pytest
from playwright.sync_api import expect

from tests.e2e.test_recipes_flows import (  # noqa: F401  (scored_project is a fixture)
    BRS,
    eventually,
    open_recipes,
    read_rows,
    run_and_wait_for,
    scored_project,
)

RECIPE_FILE = "code/recipes/survey/recipe-brs.json"


def open_builder(page, studio_url, project, template="brs"):
    page.on("dialog", lambda dialog: dialog.accept())
    (project / "code" / "library" / "survey").mkdir(parents=True, exist_ok=True)
    shutil.copy(BRS, project / "code" / "library" / "survey" / "survey-brs.json")
    page.goto(f"{studio_url}/recipe-builder")
    page.select_option("#rbSurveyPicker", template)
    expect(page.locator("#rbItemList .rb-item")).to_have_count(3, timeout=30000)


def add_scale(page, name, items=3, method=None):
    page.click("#rbAddScaleBtn")
    page.fill("#rbScaleNameInput", name)
    page.click("#rbScaleNameConfirmBtn")
    card = page.locator("#rbScaleCanvas .rb-scale-card").last
    card.locator(".rb-scale-chevron").click()  # a new scale starts collapsed
    for index in range(items):
        page.locator("#rbItemList .rb-item-cb").nth(index).check()
    if items:
        card.locator(".rb-add-selected-btn").click()
    if method:
        card.locator(".rb-scale-method").select_option(method)
    return card


def preview_recipe(page):
    page.click("#rbPreviewBtn")
    expect(page.locator("#rbJsonPreview")).not_to_be_empty()
    recipe = json.loads(page.locator("#rbJsonPreview").inner_text())
    page.keyboard.press("Escape")
    return recipe


def test_template_details_are_prefilled(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)

    expect(app_page.locator("#rbMetaName")).to_have_value("Resilience (BRS)")
    expect(app_page.locator("#rbMetaCitation")).to_have_value(re.compile("Smith, B.W."))


def test_preview_shows_the_scale_the_user_built_and_the_reversed_item(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    app_page.locator("#rbInvertItemList label", has_text="BRS02").locator("input").check()
    add_scale(app_page, "Total", method="sum")

    recipe = preview_recipe(app_page)

    assert recipe["Scores"] == [{"Name": "Total", "Method": "sum", "Items": ["BRS01", "BRS02", "BRS03"], **recipe["Scores"][0]}]
    assert recipe["Scores"][0]["Items"] == ["BRS01", "BRS02", "BRS03"] and recipe["Scores"][0]["Method"] == "sum"
    assert recipe["Transforms"]["Invert"]["Items"] == ["BRS02"]
    assert recipe["Transforms"]["Invert"]["Scale"] == {"min": 0, "max": 4}  # read from the template
    assert not (project / RECIPE_FILE).exists()  # a preview writes nothing


def test_save_writes_the_recipe_into_the_project_and_says_where(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "Total", method="sum")

    app_page.click("#rbSaveBtn")

    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)
    saved = json.loads((project / RECIPE_FILE).read_text())
    assert saved["Survey"]["TaskName"] == "brs"
    assert saved["Scores"][0]["Items"] == ["BRS01", "BRS02", "BRS03"]
    expect(app_page.locator("#rbStatus")).to_contain_text("recipe-brs.json")


def test_a_saved_recipe_is_loaded_back_when_the_template_is_opened_again(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "Total", method="sum")
    app_page.click("#rbSaveBtn")
    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)

    app_page.reload()
    app_page.select_option("#rbSurveyPicker", "brs")

    card = app_page.locator("#rbScaleCanvas .rb-scale-card")
    expect(card).to_have_count(1, timeout=30000)
    expect(card.locator(".rb-scale-name-label")).to_have_text("Total")
    expect(card.locator(".rb-scale-method")).to_have_value("sum")


def test_a_scale_without_items_is_refused_and_says_why(app_page, studio_url, project):
    app_page.allowed_http[400] = "/api/recipe-builder/save"  # the refusal is the point
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "Total", items=0)

    app_page.click("#rbSaveBtn")

    expect(app_page.locator("#rbStatus")).to_contain_text("Items must be a non-empty list", timeout=30000)
    assert not (project / RECIPE_FILE).exists()


def test_saving_keeps_everything_in_the_recipe_that_the_builder_does_not_edit(app_page, studio_url, project):
    recipe_path = project / RECIPE_FILE
    recipe_path.parent.mkdir(parents=True)
    hand_written = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "brs", "Name": "Resilience (BRS)"},
        "Scores": [{"Name": "Total", "Method": "sum", "Items": ["BRS01", "BRS02", "BRS03"]}],
        "Psychometrics": {"Reliability": {"InternalConsistency": {"CronbachAlpha": 0.84}}},
        "Usage": {"ScoringGuidelines": {"en": "Higher means more resilient."}},
    }
    recipe_path.write_text(json.dumps(hand_written))
    open_builder(app_page, studio_url, project)
    expect(app_page.locator("#rbScaleCanvas .rb-scale-card")).to_have_count(1, timeout=30000)
    app_page.fill("#rbMetaDesc", "Edited in the builder")

    app_page.click("#rbSaveBtn")

    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)
    saved = json.loads(recipe_path.read_text())
    assert saved["Psychometrics"] == hand_written["Psychometrics"]
    assert saved["Usage"] == hand_written["Usage"]


def test_a_recipe_built_here_scores_the_data_with_the_reversed_item(app_page, studio_url, scored_project):
    """End to end: builder -> saved project recipe -> Recipes page -> numbers."""
    open_builder(app_page, studio_url, scored_project)
    app_page.locator("#rbInvertItemList label", has_text="BRS02").locator("input").check()
    add_scale(app_page, "Total", method="sum")
    app_page.click("#rbSaveBtn")
    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)

    open_recipes(app_page, studio_url)
    run_and_wait_for(app_page, scored_project / "derivatives/survey/long_en/e2e_brs.csv")

    # BRS02 is reversed on its 0-4 range (x -> 4 - x):
    #   P001 ses-1: 3 + (4-4) + 2 = 5     P001 ses-2: 4 + (4-4) + 3 = 7     P002 ses-1: 1 + (4-0) + 2 = 7
    assert read_rows(scored_project / "derivatives/survey/long_en/e2e_brs.csv") == [
        ["participant_id", "session", "Total"],
        ["sub-P001", "ses-1", "5"],
        ["sub-P001", "ses-2", "7"],
        ["sub-P002", "ses-1", "7"],
    ]


def test_without_a_project_the_builder_says_so(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/recipe-builder")

    expect(bare_page.locator("body")).to_contain_text("No project loaded")


def switch_on_irv(page):
    page.locator("#rbIncludeIrv").check()
    expect(page.locator("#rbRunSummary")).to_contain_text("IRV")  # the summary now explains the new column
    # The summary just grew, so the Save button moved; settle on it before clicking, as a person would.
    page.locator("#rbSaveBtn").scroll_into_view_if_needed()
    page.wait_for_timeout(400)


def test_irv_is_the_spread_of_the_raw_answers_and_ignores_reverse_coding(app_page, studio_url, scored_project):
    open_builder(app_page, studio_url, scored_project)
    app_page.locator("#rbInvertItemList label", has_text="BRS02").locator("input").check()
    add_scale(app_page, "Total", method="sum")
    switch_on_irv(app_page)
    app_page.click("#rbSaveBtn")
    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)

    open_recipes(app_page, studio_url)
    run_and_wait_for(app_page, scored_project / "derivatives/survey/long_en/e2e_brs.csv")

    rows = read_rows(scored_project / "derivatives/survey/long_en/e2e_brs.csv")
    assert rows[0] == ["participant_id", "session", "Total", "IRV"]
    # sample standard deviation (n-1) of the RAW answers: (3,4,2) -> 1, (4,4,3) -> 0.577, (1,0,2) -> 1
    assert [float(row[3]) for row in rows[1:]] == pytest.approx([1.0, 0.5773502691896257, 1.0])
    assert [row[2] for row in rows[1:]] == ["5", "7", "7"]  # the reversed Total is unaffected by IRV


def test_the_irv_choice_is_remembered_with_the_saved_recipe(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "Total", method="sum")
    switch_on_irv(app_page)
    app_page.click("#rbSaveBtn")
    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)

    app_page.reload()
    app_page.select_option("#rbSurveyPicker", "brs")

    expect(app_page.locator("#rbScaleCanvas .rb-scale-card")).to_have_count(1, timeout=30000)
    expect(app_page.locator("#rbIncludeIrv")).to_be_checked()


def test_the_summary_explains_the_irv_column_only_while_it_is_switched_on(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "Total", method="sum")
    summary = app_page.locator("#rbRunSummary")
    expect(summary).not_to_contain_text("IRV")

    app_page.locator("#rbIncludeIrv").check()

    expect(summary).to_contain_text("sample standard deviation")
    expect(summary).to_contain_text("Reverse coding is ignored")
    expect(summary).to_contain_text("3 items")

    app_page.locator("#rbIncludeIrv").uncheck()

    expect(summary).not_to_contain_text("IRV")
