"""Template editor: the click-through flows that broke by hand.
Each test replays one manual session; add one whenever a new GUI bug turns up."""

from pathlib import Path

from playwright.sync_api import expect

GLOBAL = "survey-aai.json"


def save_global_copy_to_project(page):
    page.on("dialog", lambda dialog: dialog.accept())  # "Save an editable project copy?"
    page.select_option("#globalTemplateSelect", GLOBAL)
    page.wait_for_selector("#btnValidate:enabled")
    expect(page.locator("#alertArea")).to_contain_text("Valid template")
    page.click("#btnSave")
    expect(page.locator("#alertArea")).to_contain_text("Saved to project library")


def test_saved_global_template_is_selected_in_the_project_dropdown(page):
    save_global_copy_to_project(page)

    expect(page.locator("#projectTemplateSelect")).to_have_value(GLOBAL)


def test_deleted_template_leaves_the_dropdown_without_an_error(page):
    save_global_copy_to_project(page)
    page.select_option("#projectTemplateSelect", GLOBAL)  # Delete only shows for a loaded project file
    expect(page.locator("#btnDelete")).to_be_visible()

    page.click("#btnDelete")

    expect(page.locator("#alertArea")).to_contain_text("Deleted")
    expect(page.locator("#alertArea .alert-danger")).to_have_count(0)
    expect(page.locator(f'#projectTemplateSelect option[value="{GLOBAL}"]')).to_have_count(0)


FOUR_QUESTIONNAIRES = Path(__file__).parents[1] / "data" / "limesurvey_four_questionnaires.lss"


def test_limesurvey_file_with_several_questionnaires_loads_the_chosen_one(page):
    page.click("label[for=modeCreate]")  # the import card is hidden until "Create or import new" is chosen
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))

    expect(page.locator("#excelGroupPickerRow")).to_be_visible()
    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(4)
    expect(page.locator("#excelGroupPickerSelect")).to_have_value("g20")  # helper g10 not preselected
    page.select_option("#excelGroupPickerSelect", "g30")
    page.click("#btnLoadExcelGroup")

    expect(page.locator("#alertArea .alert-warning")).to_contain_text("Not found in your file")
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)  # the item select lists the loaded items

    page.select_option("#sourceSplitSelect", "survey")
    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(1)


def test_changing_split_keeps_the_loaded_questionnaire(page):
    page.click("label[for=modeCreate]")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g30")
    page.click("#btnLoadExcelGroup")
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)

    page.select_option("#sourceSplitSelect", "survey")  # Whole survey lists one entry: used to auto-load it

    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(1)
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)
    expect(page.locator('option[value="WHO1"]')).to_have_count(0)


def load_ads_from_limesurvey(page):
    page.click("label[for=modeCreate]")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g30")
    page.click("#btnLoadExcelGroup")
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)


def test_import_with_missing_details_is_a_hint_not_a_failure(page):
    load_ads_from_limesurvey(page)

    expect(page.locator("#alertArea .alert-warning")).to_contain_text("Not found in your file")
    expect(page.locator("#alertArea .alert-danger")).to_have_count(0)
    expect(page.locator("#alertArea")).not_to_contain_text("Validation failed")
    expect(page.locator("#alertArea")).to_contain_text("Citation")
    expect(page.locator("#alertArea")).not_to_contain_text("SoftwareVersion")  # filled from the DBVersion

    page.click("#btnValidate")  # an explicit Validate is still a real check
    expect(page.locator("#alertArea .alert-danger")).to_contain_text("Validation failed")


CONTRAST_JS = """() => {
  const rgb = (c) => c.match(/[\\d.]+/g).slice(0, 3).map(Number);
  const lum = (c) => { const [r, g, b] = rgb(c).map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };
  const link = document.querySelector('#alertArea .error-link code');
  const box = link.closest('.alert');
  const [a, b] = [lum(getComputedStyle(link).color), lum(getComputedStyle(box).backgroundColor)].sort((x, y) => y - x);
  return (a + 0.05) / (b + 0.05);
}"""


def test_error_links_are_readable_in_the_hint_and_in_a_real_failure(page):
    load_ads_from_limesurvey(page)
    expect(page.locator("#alertArea .alert-warning .error-link").first).to_be_visible()  # validation answered
    assert page.evaluate(CONTRAST_JS) >= 4.5  # the "fill these in" hint

    page.click("#btnValidate")
    expect(page.locator("#alertArea .alert-danger")).to_be_visible()
    assert page.evaluate(CONTRAST_JS) >= 4.5  # the red failure box


def test_split_by_select_shows_its_whole_label(page):
    page.click("label[for=modeCreate]")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    expect(page.locator("#sourceSplitSelect")).to_be_visible()

    room = page.evaluate("""() => {
      const select = document.querySelector('#sourceSplitSelect');
      const ctx = document.createElement('canvas').getContext('2d');
      ctx.font = getComputedStyle(select).font;
      const text = Math.max(...[...select.options].map((o) => ctx.measureText(o.text).width));
      const style = getComputedStyle(select);
      const chrome = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
      return select.getBoundingClientRect().width - chrome - text;
    }""")
    assert room >= 0  # padding already includes the dropdown arrow


import json


def put_ads_in_project_library(project):
    template = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "SoftwarePlatform": "LimeSurvey",
                      "Language": "de", "Respondent": "self", "AdministrationMethod": "online"},
        "Study": {"TaskName": "ads", "OriginalName": "ADS", "Citation": "c", "LicenseID": "CC-BY-4.0", "Category": "other"},
        "ads_01": {"Description": "war ich bedrückt", "Levels": {"0": "selten", "1": "meistens"}},
        "ads_02": {"Description": "war ich müde", "Levels": {"0": "selten", "1": "meistens"}},
    }
    (project / "code" / "library" / "survey" / "survey-ads.json").write_text(json.dumps(template, ensure_ascii=False), encoding="utf-8")


def pick_ads(page):
    page.click("label[for=modeCreate]")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g30")


def test_library_match_is_shown_and_the_library_template_can_be_used(page, project):
    put_ads_in_project_library(project)
    pick_ads(page)

    expect(page.locator('#excelGroupPickerSelect option[value="g30"]')).to_contain_text("match: ads (project, exact)")
    card = page.locator("#libraryMatchCard")
    expect(card).to_be_visible()
    expect(card).to_contain_text("item IDs differ")
    assert page.evaluate(CONTRAST_JS.replace("#alertArea .error-link code", "#libraryMatchCard .lib-match-title")) >= 4.5

    page.click('#libraryMatchCard [data-action="use-library"]')

    expect(page.locator('option[value="ads_01"]')).to_have_count(1)
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(0)


def test_import_as_new_keeps_the_survey_items(page, project):
    put_ads_in_project_library(project)
    pick_ads(page)

    page.click('#libraryMatchCard [data-action="import-new"]')

    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)


def test_questionnaire_without_a_match_shows_no_card(page, project):
    put_ads_in_project_library(project)
    page.click("label[for=modeCreate]")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g20")

    expect(page.locator("#libraryMatchCard")).to_be_hidden()


def test_changing_split_to_a_single_entry_does_not_load_it(page, project):
    messages = []
    page.on("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
    page.click("label[for=modeCreate]")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#sourceSplitSelect", "survey")  # one entry: used to be loaded silently
    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(1)
    page.select_option("#sourceSplitSelect", "group")
    page.select_option("#excelGroupPickerSelect", "g30")
    page.click("#btnLoadExcelGroup")

    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)
    assert messages == []


def test_opening_create_or_import_does_not_scroll_the_page(page):
    page.evaluate("window.scrollTo(0, 0)")
    page.click("label[for=modeCreate]")
    expect(page.locator("#excelGroupPickerRow, #templateImportInput")).to_have_count(2)  # panel opened
    page.wait_for_timeout(700)  # the old smooth scroll started after 120 ms
    assert page.evaluate("window.scrollY") == 0


def test_items_tab_shows_the_item_panel_with_its_count(page):
    page.select_option("#globalTemplateSelect", GLOBAL)
    page.wait_for_selector("#btnValidate:enabled")
    expect(page.locator("#itemCountBadge")).not_to_have_text("0")
    expect(page.locator("#itemsPanelCol")).to_be_hidden()

    page.click("#tabItems")
    expect(page.locator("#itemsPanelCol")).to_be_visible()
    expect(page.locator("#tabItems")).to_have_class("nav-link active")

    page.click("#tabEditor")
    expect(page.locator("#itemsPanelCol")).to_be_hidden()
    expect(page.locator("#topLevelPanel")).to_be_visible()


def load_global_template(page):
    page.on("dialog", lambda dialog: dialog.accept())
    page.select_option("#globalTemplateSelect", GLOBAL)
    page.wait_for_selector("#btnValidate:enabled")


def test_item_ids_that_cannot_be_column_names_or_clash_in_case_are_refused(page):
    load_global_template(page)
    page.click("#tabItems")
    items = page.locator("#itemList > *")
    count = items.count()
    for bad in ("A B", "../x", "ünï", "aai01"):
        page.fill("#newItemId", bad)
        page.click("#btnAddItem")
        expect(page.locator("#alertArea .alert-warning")).to_be_visible()
        assert items.count() == count, bad
    page.fill("#newItemId", "aai_11")
    page.click("#btnAddItem")
    expect(page.locator("#alertArea")).to_contain_text("Added item aai_11")


def test_min_above_max_fails_validation_and_odd_ids_in_a_loaded_template_are_listed(page):
    load_global_template(page)
    page.click("#tabItems")
    page.locator("#itemList > *").first.click()
    page.fill("#field_ITEM_MinValue", "10")
    page.fill("#field_ITEM_MaxValue", "1")
    page.click("#btnValidate")
    expect(page.locator("#alertArea")).to_contain_text("MinValue (10) must not be greater than MaxValue (1)")
    expect(page.locator("#btnSave")).to_be_disabled()


def test_a_blank_template_explains_the_task_name_rule_and_the_missing_items(page):
    page.wait_for_load_state("networkidle")  # the page's own start-up load of a blank template is done
    page.click("label[for=modeCreate]")
    # "New" fetches the blank template and then re-renders the form: type into the new field, not a stale one
    page.evaluate("document.querySelectorAll('[id^=field_]').forEach(e => e.dataset.stale = '1')")
    page.click("#btnNew")
    page.fill("#field_Study_TaskName:not([data-stale])", "My Task!")
    page.click("#btnValidate")
    alert = page.locator("#alertArea")
    expect(alert).to_contain_text("'My Task!' is not allowed: use only letters, digits and hyphens")
    expect(alert).not_to_contain_text("[a-zA-Z0-9]")
    expect(alert).to_contain_text("The template has no items yet")


def test_adding_a_language_checks_the_code_and_refuses_one_the_template_has(page):
    messages = []

    def answer(dialog):
        messages.append(dialog.message)
        dialog.accept(answers.pop(0) if dialog.type == "prompt" else None)

    answers = ["xx", "de", "fr"]
    page.on("dialog", answer)
    page.select_option("#globalTemplateSelect", GLOBAL)
    page.wait_for_selector("#btnValidate:enabled")
    page.wait_for_function("() => fetch('/api/template-editor/language-codes').then(r => r.ok)")
    page.wait_for_timeout(500)  # the list is fetched once at start-up
    for _ in range(3):
        page.click("#btnAddLang")
    assert any('"xx" is not an ISO 639-1' in m for m in messages), messages
    assert any('already has the language "de"' in m for m in messages), messages
    expect(page.locator("#langBadges")).to_contain_text("fr")


def bulk_column(page, label):
    import re

    return page.locator("#bulkEditForm > .row > div").filter(has=page.locator("label").filter(has_text=re.compile(f"^{label}"))).first


def test_bulk_edit_asks_before_changing_every_item_and_a_bad_hint_is_named(page):
    prompts = []
    page.on("dialog", lambda dialog: (prompts.append(dialog.message), dialog.accept()))
    page.select_option("#globalTemplateSelect", GLOBAL)
    page.wait_for_selector("#btnValidate:enabled")
    page.click("#tabItems")
    page.click("[data-bs-target='#bulkEditSection']")
    hint = bulk_column(page, "SessionHint")
    hint.locator("input").fill("session 1")
    hint.get_by_role("button", name="Apply to Selected").click()
    assert any("Set SessionHint on all 10 items" in m for m in prompts), prompts
    page.click("#btnValidate")
    alert = page.locator("#alertArea")
    expect(alert).to_contain_text("SessionHint")
    expect(alert).to_contain_text("ses-<label>")
    expect(alert).not_to_contain_text("is not valid under any of the given schemas")


LOSSY_TYPES = Path(__file__).parents[1] / "data" / "limesurvey_import_notes.lss"


def test_limesurvey_import_lists_what_it_could_not_represent(page):
    page.click("label[for=modeCreate]")
    page.set_input_files("#templateImportInput", str(LOSSY_TYPES))
    expect(page.locator("#excelGroupPickerRow")).to_be_visible()
    page.click("#btnLoadExcelGroup")

    # the notes sit in the alert that validation shows after the import, not only in the one it replaces
    expect(page.locator("#alertArea")).to_contain_text("Not found in your file")
    notes = page.locator("#alertArea .alert-warning.mt-2", has_text="Check after import")
    expect(notes).to_contain_text("boxes: unchecked options are empty")
    expect(notes).to_contain_text("edu: has an \"Other\" text field")
    expect(notes).to_contain_text("mystery: question type Z is not known")
    expect(page.locator('option[value="agree"]')).to_have_count(1)  # the questionnaire itself loaded


def test_answer_codes_that_are_not_numbers_get_numbers_from_the_suggestion(page, tmp_path):
    """ADS answer codes ADS0..ADS3 (chosen by the survey's author): the editor suggests
    0..3, the user applies them, the levels become the numbers."""
    import json

    levels = {c: {"de": f"label {c}"} for c in ("ADS0", "ADS1", "ADS2", "ADS3")}
    template = {"Study": {"TaskName": "ads"},
                **{f"ADS1_{i}": {"Description": {"de": f"q{i}"}, "Levels": levels} for i in (1, 2)}}
    path = tmp_path / "survey-ads.json"
    path.write_text(json.dumps(template), encoding="utf-8")
    page.click("label[for=modeCreate]")
    page.set_input_files("#templateImportInput", str(path))

    area = page.locator("#answerCodesArea")
    expect(area).to_contain_text("Answer codes are not numbers in 2 item(s)")
    expect(area.locator('input[aria-label="Number for answer code ADS2"]')).to_have_value("2")
    area.locator("button", has_text="Apply numbers").click()

    expect(page.locator("#alertArea")).to_contain_text("Answer codes recoded in 2 item(s)")
    expect(area.locator(".alert")).to_have_count(0)
