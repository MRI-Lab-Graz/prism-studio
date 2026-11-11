"""The Biosample tab posts the form to `biosample import` and lists what it wrote."""

from openpyxl import Workbook
from playwright.sync_api import expect


def test_biosample_tab_imports_with_the_chosen_specimen(app_page, studio_url, project, tmp_path):
    (project / "participants.tsv").write_text("participant_id\nsub-01\n")  # a single-timepoint project
    book = tmp_path / "filled.xlsx"
    wb = Workbook()
    wb.active.title = "data"
    wb["data"].append(["participant_id", "session", "panel", "run", "sample_id", "collection_time",
                       "analyte", "value", "unit", "comment"])
    wb["data"].append(["01", "1", "hormones", None, "s1", "08:30", "cortisol", 1, "nmol/L", None])
    wb.create_sheet("panels").append(["panel", "SpecimenType"])
    wb["panels"].append(["hormones"])  # empty SpecimenType: the pull-down's choice fills it
    wb.save(book)

    app_page.goto(f"{studio_url}/converter")
    app_page.click("#biosample-tab")
    app_page.set_input_files("#biosampleFile", str(book))
    app_page.select_option("#biosampleSpecimen", "serum")
    expect(app_page.locator("#biosampleSpecimenChips .chip-badge")).to_have_text("serum ×")
    app_page.click("#biosampleImportBtn")

    expect(app_page.locator("#biosampleResult")).to_contain_text("Written")
    assert list(project.glob("sub-01/ses-1/biosample/*_biosample.tsv"))
