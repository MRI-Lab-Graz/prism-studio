"""Survey customizer: arrange the picked questions into groups and export."""

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from playwright.sync_api import expect


def open_customizer(page, studio_url, *searches):
    """Pick templates on the generator (like a user) and press Customize & Export."""
    page.dialogs = []
    page.on("dialog", lambda d: (page.dialogs.append(d.message), d.accept()))
    page.goto(f"{studio_url}/survey-generator")
    expect(page.locator("#libraryContent")).to_be_visible(timeout=30000)
    for search in searches:
        page.fill("#templateSearch", search)
        page.locator(".tpl-row:visible").first.locator(".file-checkbox").check()
    page.click("#customizeExportBtn")
    page.wait_for_url("**/survey-customizer", timeout=15000)
    expect(page.locator("#customizerMain")).to_be_visible(timeout=15000)


def export(page, tmp_path, name="my_survey", survey_name="My Survey", button="#exportBtn"):
    if survey_name is not None:
        page.fill("#surveyName", survey_name)
    with page.expect_download() as info:
        page.click(button)
    target = tmp_path / name
    info.value.save_as(target)
    return target


def lss_root(path):
    return ET.parse(path).getroot()


def lss_codes(path):
    root = lss_root(path)
    return sorted(
        r.findtext("title")
        for section in ("questions", "subquestions")
        for r in root.find(section).iter("row")
        if r.findtext("title")
    )


def lss_group_names(path):
    return [r.findtext("group_name") for r in lss_root(path).find("group_l10ns").iter("row")]


def sub_row(page, code):
    return page.locator(".matrix-subquestion", has=page.locator(".question-code", has_text=re.compile(f"^{code}$")))


def test_a_survey_name_is_required_before_anything_is_exported(app_page, studio_url):
    open_customizer(app_page, studio_url, "brs")
    downloads = []
    app_page.on("download", lambda d: downloads.append(d))

    app_page.click("#exportBtn")

    app_page.wait_for_timeout(800)
    assert not downloads
    assert app_page.dialogs == ["Please enter a survey name before exporting."]
    expect(app_page.locator("#surveyName")).to_have_class(re.compile("is-invalid"))


def test_the_export_carries_the_survey_name_and_one_group_per_template(app_page, studio_url, tmp_path):
    open_customizer(app_page, studio_url, "brs", "gad7")

    lss = export(app_page, tmp_path, "s.lss", survey_name="Anxiety and resilience")

    assert "Anxiety and resilience" in lss.read_text()
    names = " ".join(lss_group_names(lss))
    assert "Resilience" in names and "Generalized Anxiety" in names
    codes = lss_codes(lss)
    assert {"BRS01", "BRS02", "BRS03"} <= set(codes)
    # LimeSurvey subquestion codes are shortened to 5 characters (GAD701 -> GAD01)
    assert len([c for c in codes if re.fullmatch(r"GAD0\d", c)]) == 7


def test_a_switched_off_question_is_not_exported(app_page, studio_url, tmp_path):
    open_customizer(app_page, studio_url, "brs")
    sub_row(app_page, "BRS02").locator(".question-enabled").click()

    lss = export(app_page, tmp_path, "s.lss")

    codes = lss_codes(lss)
    assert "BRS01" in codes and "BRS03" in codes
    assert "BRS02" not in codes


def test_matrix_required_switch_decides_if_the_matrix_is_mandatory(app_page, studio_url, tmp_path):
    open_customizer(app_page, studio_url, "brs")
    required = lambda lss: [r.findtext("mandatory") for r in lss_root(lss).find("questions").iter("row") if r.findtext("title") == "MBRS01"]
    assert required(export(app_page, tmp_path, "a.lss")) == ["Y"]

    app_page.locator(".matrix-mandatory").uncheck()

    assert required(export(app_page, tmp_path, "b.lss")) == ["N"]


def test_without_matrix_grouping_every_item_is_its_own_question(app_page, studio_url, tmp_path):
    open_customizer(app_page, studio_url, "brs")
    app_page.locator("#matrixMode").uncheck()

    lss = export(app_page, tmp_path, "s.lss")

    codes = lss_codes(lss)
    assert {"BRS01", "BRS02", "BRS03"} <= set(codes)
    assert "MBRS01" not in codes


def test_renaming_a_group_changes_the_group_in_the_export(app_page, studio_url, tmp_path):
    open_customizer(app_page, studio_url, "brs")
    app_page.locator(".group-item .rename-group-btn").first.click()
    app_page.fill("#renameGroupName", "Coping block")
    app_page.click("#confirmRenameGroup")
    expect(app_page.locator("#groupsList .group-name").first).to_have_text("Coping block")

    lss = export(app_page, tmp_path, "s.lss")

    assert lss_group_names(lss) == ["Coping block"]


def test_a_new_group_can_take_a_question_by_dragging_and_is_exported(app_page, studio_url, tmp_path):
    open_customizer(app_page, studio_url, "gad7")
    app_page.locator("#addGroupBtn").click()
    app_page.fill("#newGroupName", "Extra")
    app_page.click("#confirmAddGroup")
    expect(app_page.locator("#groupsList .group-name")).to_have_text(["Generalized Anxiety Disorder (GAD-7)", "Extra"])

    lss = export(app_page, tmp_path, "s.lss")

    # an empty group is not exported as an empty page
    assert "Extra" not in " ".join(n or "" for n in lss_group_names(lss))


def test_reset_brings_back_a_switched_off_question(app_page, studio_url):
    open_customizer(app_page, studio_url, "brs")
    sub_row(app_page, "BRS02").locator(".question-enabled").click()
    expect(app_page.locator("#questionsContainer .matrix-subquestion")).to_have_count(2)

    app_page.click("#resetBtn")

    expect(app_page.locator("#questionsContainer .matrix-subquestion")).to_have_count(3)
    expect(sub_row(app_page, "BRS02").locator(".question-enabled")).to_be_checked()


def test_pavlovia_target_exports_a_zip_with_every_group(app_page, studio_url, tmp_path):
    open_customizer(app_page, studio_url, "brs")
    app_page.select_option("#targetTool", "pavlovia")

    archive = export(app_page, tmp_path, "s.zip")

    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        text = " ".join(z.read(n).decode("utf-8", "ignore") for n in names if n.endswith((".csv", ".psyexp")))
    assert any(n.endswith(".psyexp") for n in names)
    assert "BRS01" in text


def test_the_word_export_is_a_questionnaire_document(app_page, studio_url, tmp_path):
    open_customizer(app_page, studio_url, "brs")

    docx = export(app_page, tmp_path, "s.docx", button="#exportWordBtn")

    with zipfile.ZipFile(docx) as z:
        body = z.read("word/document.xml").decode("utf-8")
    assert "tend to bounce back" in body


def test_the_preview_shows_the_questions_as_a_respondent_sees_them(app_page, studio_url):
    open_customizer(app_page, studio_url, "brs")

    app_page.click("#previewQuestionnaireBtn")

    expect(app_page.locator("#previewModalBody")).to_contain_text("I tend to bounce back quickly")


def test_save_to_project_copies_the_templates_into_the_project_library(app_page, studio_url, tmp_path, project):
    open_customizer(app_page, studio_url, "brs")
    app_page.locator("#saveToProject").check()

    export(app_page, tmp_path, "s.lss")

    assert (project / "code" / "library" / "survey" / "survey-brs.json").exists()

