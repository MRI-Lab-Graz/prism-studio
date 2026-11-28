"""Recipe builder: build a scoring recipe in the page, save it, and score data with it."""

import json
import re
import shutil
import statistics

import pytest
from playwright.sync_api import expect

from tests.e2e.test_recipes_flows import (  # noqa: F401  (scored_project is a fixture)
    DEMO,
    eventually,
    open_recipes,
    read_rows,
    run_and_wait_for,
    scored_project,
)

RECIPE_FILE = "code/recipes/survey/recipe-demo.json"


def open_builder(page, studio_url, project, template="demo"):
    page.on("dialog", lambda dialog: dialog.accept())
    (project / "code" / "library" / "survey").mkdir(parents=True, exist_ok=True)
    shutil.copy(DEMO, project / "code" / "library" / "survey" / "survey-demo.json")
    page.goto(f"{studio_url}/recipe-builder")
    page.select_option("#rbSurveyPicker", template)
    expect(page.locator("#rbItemList .rb-item")).to_have_count(8, timeout=30000)


def add_scale(page, name, items=3, method=None):
    page.click("#rbAddScaleBtn")
    page.fill("#rbScaleNameInput", name)
    page.click("#rbScaleNameConfirmBtn")
    card = page.locator("#rbScaleCanvas .rb-scale-card").last
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

    expect(app_page.locator("#rbMetaName")).to_have_value("PRISM demonstration questionnaire")
    expect(app_page.locator("#rbMetaCitation")).to_have_value(re.compile("PRISM specification"))


def test_preview_shows_the_scale_the_user_built_and_the_reversed_item(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    app_page.click("#rbInversionToggle")  # folded while nothing is inverted
    app_page.locator("#rbInvertItemList label", has_text="DEMO02").locator("input").check()
    add_scale(app_page, "Total", method="sum")

    recipe = preview_recipe(app_page)

    assert recipe["Scores"] == [{"Name": "Total", "Method": "sum", "Items": ["DEMO01", "DEMO02", "DEMO03"], **recipe["Scores"][0]}]
    assert recipe["Scores"][0]["Items"] == ["DEMO01", "DEMO02", "DEMO03"] and recipe["Scores"][0]["Method"] == "sum"
    assert recipe["Transforms"]["Invert"]["Items"] == ["DEMO02"]
    assert recipe["Transforms"]["Invert"]["Scale"] == {"min": 0, "max": 4}  # read from the template
    assert not (project / RECIPE_FILE).exists()  # a preview writes nothing


def test_save_writes_the_recipe_into_the_project_and_says_where(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "Total", method="sum")

    app_page.click("#rbSaveBtn")

    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)
    saved = json.loads((project / RECIPE_FILE).read_text(encoding="utf-8"))
    assert saved["Survey"]["TaskName"] == "demo"
    assert saved["Scores"][0]["Items"] == ["DEMO01", "DEMO02", "DEMO03"]
    expect(app_page.locator("#rbStatus")).to_contain_text("recipe-demo.json")


def test_a_saved_recipe_is_loaded_back_when_the_template_is_opened_again(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "Total", method="sum")
    app_page.click("#rbSaveBtn")
    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)

    app_page.reload()
    app_page.select_option("#rbSurveyPicker", "demo")

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
        "Survey": {"TaskName": "demo", "Name": "PRISM demonstration questionnaire"},
        "Scores": [{"Name": "Total", "Method": "sum", "Items": ["DEMO01", "DEMO02", "DEMO03"]}],
        "Psychometrics": {"Reliability": {"InternalConsistency": {"CronbachAlpha": 0.84}}},
        "Usage": {"ScoringGuidelines": {"en": "Higher means more resilient."}},
    }
    recipe_path.write_text(json.dumps(hand_written))
    open_builder(app_page, studio_url, project)
    expect(app_page.locator("#rbScaleCanvas .rb-scale-card")).to_have_count(1, timeout=30000)
    app_page.fill("#rbMetaDesc", "Edited in the builder")

    app_page.click("#rbSaveBtn")

    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)
    saved = json.loads(recipe_path.read_text(encoding="utf-8"))
    assert saved["Psychometrics"] == hand_written["Psychometrics"]
    assert saved["Usage"] == hand_written["Usage"]


def test_a_recipe_built_here_scores_the_data_with_the_reversed_item(app_page, studio_url, scored_project):
    """End to end: builder -> saved project recipe -> Recipes page -> numbers."""
    open_builder(app_page, studio_url, scored_project)
    app_page.click("#rbInversionToggle")  # folded while nothing is inverted
    app_page.locator("#rbInvertItemList label", has_text="DEMO02").locator("input").check()
    add_scale(app_page, "Total", method="sum")
    app_page.click("#rbSaveBtn")
    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)

    open_recipes(app_page, studio_url)
    run_and_wait_for(app_page, scored_project / "derivatives/survey/long_en/e2e_demo.csv")

    # DEMO02 is reversed on its 0-4 range (x -> 4 - x):
    #   P001 ses-1: 3 + (4-4) + 2 = 5     P001 ses-2: 4 + (4-4) + 3 = 7     P002 ses-1: 1 + (4-0) + 2 = 7
    assert read_rows(scored_project / "derivatives/survey/long_en/e2e_demo.csv") == [
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
    app_page.click("#rbInversionToggle")  # folded while nothing is inverted
    app_page.locator("#rbInvertItemList label", has_text="DEMO02").locator("input").check()
    add_scale(app_page, "Total", method="sum")
    switch_on_irv(app_page)
    app_page.click("#rbSaveBtn")
    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)

    open_recipes(app_page, studio_url)
    run_and_wait_for(app_page, scored_project / "derivatives/survey/long_en/e2e_demo.csv")

    rows = read_rows(scored_project / "derivatives/survey/long_en/e2e_demo.csv")
    assert rows[0] == ["participant_id", "session", "Total", "IRV"]
    # sample standard deviation (n-1) of the RAW answers of all 8 items (DATA, reverse coding ignored)
    raw = [[3, 4, 2, 0, 0, 4, 0, 0], [4, 4, 3, 0, 0, 4, 0, 0], [1, 0, 2, 0, 0, 4, 0, 0]]
    assert [float(row[3]) for row in rows[1:]] == pytest.approx([statistics.stdev(r) for r in raw])
    assert [row[2] for row in rows[1:]] == ["5", "7", "7"]  # the reversed Total is unaffected by IRV


def test_the_irv_choice_is_remembered_with_the_saved_recipe(app_page, studio_url, project):
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "Total", method="sum")
    switch_on_irv(app_page)
    app_page.click("#rbSaveBtn")
    expect(app_page.locator("#rbStatus")).to_contain_text("Recipe saved", timeout=30000)

    app_page.reload()
    app_page.select_option("#rbSurveyPicker", "demo")

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


def test_a_scale_named_like_an_item_or_the_id_column_is_refused_on_save(app_page, studio_url, project):
    app_page.allowed_http[400] = "/api/recipe-builder/save"
    open_builder(app_page, studio_url, project)
    add_scale(app_page, "participant_id", items=3)

    app_page.click("#rbSaveBtn")

    expect(app_page.locator("#rbStatus")).to_contain_text("collides with an ID column or an item", timeout=30000)
    assert not (project / RECIPE_FILE).exists()


def test_a_name_confirmed_while_the_dialog_still_fades_in_closes_it(app_page, studio_url, project):
    """Bootstrap ignores hide() during the fade, so the dialog stayed open over the page."""
    open_builder(app_page, studio_url, project)
    app_page.evaluate("""() => {
        document.getElementById('rbAddScaleBtn').click();
        document.getElementById('rbScaleNameInput').value = 'Total';
        document.getElementById('rbScaleNameConfirmBtn').click();
    }""")

    expect(app_page.locator("#rbScaleCanvas .rb-scale-card")).to_have_count(1)
    app_page.wait_for_timeout(1000)  # the dialog is not displayed yet at once: let the fade finish
    expect(app_page.locator("#rbScaleNameModal")).to_be_hidden()
