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
    page.click("#btnCreateOpen")  # the import card is collapsed until opened
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


def test_changing_split_keeps_the_loaded_questionnaire_when_the_confirm_is_declined(page):
    page.click("#btnCreateOpen")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g30")
    page.click("#btnLoadExcelGroup")
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)  # loaded, never saved: unsaved work

    messages = []
    page.on("dialog", lambda dialog: (messages.append(dialog.message), dialog.dismiss()))
    page.select_option("#sourceSplitSelect", "survey")  # Whole survey lists one entry: used to auto-load it

    expect(page.locator("#excelGroupPickerSelect option")).to_have_count(1)
    assert any("unsaved changes" in m for m in messages)
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)
    expect(page.locator('option[value="WHO1"]')).to_have_count(0)


def load_ads_from_limesurvey(page):
    page.click("#btnCreateOpen")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g30")
    page.click("#btnLoadExcelGroup")
    expect(page.locator('option[value="ADS1_1"]')).to_have_count(1)


def test_import_with_missing_details_is_a_hint_not_a_failure(page):
    load_ads_from_limesurvey(page)

    expect(page.locator("#alertArea .alert-warning")).to_contain_text("Not found in your file")
    expect(page.locator("#alertArea .alert-danger")).to_have_count(0)
    expect(page.locator("#alertArea")).not_to_contain_text("Validation failed")
    expect(page.locator("#alertArea")).to_contain_text("SoftwareVersion")

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
    page.click("#btnCreateOpen")
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
    page.click("#btnCreateOpen")
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
    page.click("#btnCreateOpen")
    page.set_input_files("#templateImportInput", str(FOUR_QUESTIONNAIRES))
    page.select_option("#excelGroupPickerSelect", "g20")

    expect(page.locator("#libraryMatchCard")).to_be_hidden()
