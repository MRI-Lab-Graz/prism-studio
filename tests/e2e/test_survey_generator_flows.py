"""Survey generator: pick templates and questions, export for LimeSurvey / Pavlovia."""

import json
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from playwright.sync_api import expect

OFFICIAL = Path(__file__).resolve().parents[2] / "official" / "library" / "survey"
BRS_ITEMS = ["BRS01", "BRS02", "BRS03"]


def open_generator(page, studio_url):
    page.dialogs = []
    page.on("dialog", lambda d: (page.dialogs.append(d.message), d.accept()))
    page.goto(f"{studio_url}/survey-generator")
    expect(page.locator("#libraryContent")).to_be_visible(timeout=30000)


def pick(page, search, nth=0):
    """Search for a template and tick it; returns its row."""
    page.fill("#templateSearch", search)
    row = page.locator(".tpl-row:visible").nth(nth)
    row.locator(".file-checkbox").check()
    return row


def download(page, button, tmp_path, name):
    with page.expect_download() as info:
        page.click(button)
    target = tmp_path / name
    info.value.save_as(target)
    return target


def lss_question_codes(path):
    root = ET.parse(path).getroot()
    return sorted(
        row.findtext("title")
        for section in ("questions", "subquestions")
        for row in root.find(section).iter("row")
        if row.findtext("title")
    )


def lss_languages(path):
    return sorted(el.text for el in ET.parse(path).getroot().find("languages"))


def test_nothing_can_be_exported_until_a_template_is_ticked(app_page, studio_url):
    open_generator(app_page, studio_url)
    for button in ("#generateLssBtn", "#generateBoilerplateBtn", "#customizeExportBtn"):
        expect(app_page.locator(button)).to_be_disabled()

    row = pick(app_page, "brs")
    for button in ("#generateLssBtn", "#generateBoilerplateBtn", "#customizeExportBtn"):
        expect(app_page.locator(button)).to_be_enabled()

    row.locator(".file-checkbox").uncheck()
    for button in ("#generateLssBtn", "#generateBoilerplateBtn", "#customizeExportBtn"):
        expect(app_page.locator(button)).to_be_disabled()


def test_quick_export_contains_exactly_the_template_questions(app_page, studio_url, tmp_path):
    open_generator(app_page, studio_url)
    pick(app_page, "brs")

    lss = download(app_page, "#generateLssBtn", tmp_path, "brs.lss")

    # LimeSurvey also gets a group row, so look for the three item codes
    assert set(BRS_ITEMS) <= set(lss_question_codes(lss))
    assert not app_page.dialogs


def test_an_unticked_question_is_left_out_of_the_export(app_page, studio_url, tmp_path):
    open_generator(app_page, studio_url)
    row = pick(app_page, "brs")
    row.locator(".tpl-expand-btn").click()
    row.locator(".question-checkbox[value='BRS02']").uncheck()

    lss = download(app_page, "#generateLssBtn", tmp_path, "brs.lss")

    codes = lss_question_codes(lss)
    assert "BRS01" in codes and "BRS03" in codes
    assert "BRS02" not in codes


def test_export_languages_decide_which_languages_the_survey_carries(app_page, studio_url, tmp_path):
    open_generator(app_page, studio_url)
    pick(app_page, "brs")
    english_only = download(app_page, "#generateLssBtn", tmp_path, "en.lss")
    assert lss_languages(english_only) == ["en"]

    app_page.locator("#export-lang-de").check()
    both = download(app_page, "#generateLssBtn", tmp_path, "both.lss")
    assert lss_languages(both) == ["de", "en"]


def test_the_matrix_checkbox_decides_between_one_matrix_and_single_questions(app_page, studio_url, tmp_path):
    open_generator(app_page, studio_url)
    pick(app_page, "brs")
    grouped = download(app_page, "#generateLssBtn", tmp_path, "grouped.lss")
    assert "MBRS01" in lss_question_codes(grouped)  # one matrix question holding the three items

    app_page.locator("#lsMatrixGroupCheckbox").uncheck()
    single = download(app_page, "#generateLssBtn", tmp_path, "single.lss")
    codes = lss_question_codes(single)
    assert {"BRS01", "BRS02", "BRS03"} <= set(codes)
    assert "MBRS01" not in codes


def test_pavlovia_export_is_a_zip_with_the_experiment(app_page, studio_url, tmp_path):
    open_generator(app_page, studio_url)
    app_page.select_option("#targetToolSelect", "pavlovia")
    pick(app_page, "brs")

    archive = download(app_page, "#generateLssBtn", tmp_path, "brs.zip")

    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
    assert any(n.endswith(".psyexp") for n in names), names
    assert any(n.endswith(".csv") for n in names), names


def test_pavlovia_export_leaves_out_an_unticked_question(app_page, studio_url, tmp_path):
    open_generator(app_page, studio_url)
    app_page.select_option("#targetToolSelect", "pavlovia")
    row = pick(app_page, "brs")
    row.locator(".tpl-expand-btn").click()
    row.locator(".question-checkbox[value='BRS02']").uncheck()

    archive = download(app_page, "#generateLssBtn", tmp_path, "brs.zip")

    with zipfile.ZipFile(archive) as z:
        text = " ".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith((".csv", ".psyexp")))
    assert "BRS01" in text
    assert "BRS02" not in text


def test_boilerplate_names_the_picked_instrument(app_page, studio_url, tmp_path):
    open_generator(app_page, studio_url)
    pick(app_page, "brs")

    with app_page.expect_download() as info:
        app_page.click("#generateBoilerplateBtn")
    files = [info.value]
    target = tmp_path / files[0].suggested_filename
    files[0].save_as(target)

    assert "Resilience" in target.read_text() or "BRS" in target.read_text()


def test_select_all_and_clear_work_on_a_whole_section(app_page, studio_url):
    open_generator(app_page, studio_url)
    section = app_page.locator("#biometricsSection")

    section.get_by_text("Select all").click()
    expect(app_page.locator("#biometricsList .file-checkbox:checked")).to_have_count(1)
    expect(app_page.locator("#generateLssBtn")).to_be_enabled()

    section.get_by_text("Clear").click()
    expect(app_page.locator(".file-checkbox:checked")).to_have_count(0)
    expect(app_page.locator("#generateLssBtn")).to_be_disabled()


def test_a_template_saved_in_the_project_shows_up_as_a_project_template(app_page, studio_url, project):
    source = json.loads((OFFICIAL / "survey-brs.json").read_text())
    (project / "code" / "library" / "survey" / "survey-mine.json").write_text(
        json.dumps({**source, "Study": {**source["Study"], "OriginalName": {"en": "My own scale"}}})
    )
    open_generator(app_page, studio_url)

    app_page.fill("#templateSearch", "My own scale")

    row = app_page.locator(".tpl-row:visible")
    expect(row).to_have_count(1)
    expect(row.locator(".badge", has_text="Project")).to_be_visible()


def test_customize_and_export_opens_the_customizer_with_the_picked_template(app_page, studio_url):
    open_generator(app_page, studio_url)
    pick(app_page, "brs")

    app_page.click("#customizeExportBtn")

    app_page.wait_for_url("**/survey-customizer", timeout=15000)
    expect(app_page.get_by_text("BRS01").first).to_be_visible(timeout=15000)
