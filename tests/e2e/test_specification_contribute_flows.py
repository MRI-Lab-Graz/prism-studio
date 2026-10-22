"""Contribute page: an unknown metric in the open project is added locally, shared (preview only) and removed."""

import json

from playwright.sync_api import expect


def add_biosample_data(project):
    (project / "biosample-saliva_biosample.json").write_text(json.dumps({
        "Technical": {"SpecimenType": "saliva"}, "Study": {"BiosampleName": "saliva"},
        "Metadata": {"SchemaVersion": "1.1.0", "CreationDate": "2026-10-23"},
        "sample_id": {"Description": "Tube", "Units": "n/a"},
        "dhea_s": {"Description": "Salivary DHEA-S", "Units": "pg/mL", "MinValue": 0}}), encoding="utf-8")
    folder = project / "sub-01" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    (folder / "sub-01_ses-1_biosample-saliva_biosample.tsv").write_text("sample_id\tdhea_s\nS-1\t5\n", encoding="utf-8")


def test_an_unknown_metric_is_added_shared_and_removed(app_page, studio_url, project):
    add_biosample_data(project)
    app_page.goto(f"{studio_url}/specifications/contribute")

    expect(app_page.locator("#spec-unknown")).to_contain_text("dhea_s")
    app_page.get_by_role("button", name="Add to this project").click()
    expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    expect(app_page.locator("#spec-local")).to_contain_text("prism:dhea-s.saliva")
    expect(app_page.locator("#spec-unknown")).to_contain_text("Nothing")
    assert (project / "code" / "specification" / "terms" / "biosample" / "dhea-s.json").is_file()

    app_page.get_by_role("button", name="Share…").first.click()
    dialog = app_page.locator("#spec-propose-dialog")
    expect(dialog).to_be_visible()
    expect(app_page.locator("#spec-propose-json")).to_contain_text("prism:dhea-s.saliva")
    link = app_page.locator("#spec-propose-open")
    expect(link).to_be_visible()
    assert link.get_attribute("href").startswith("https://github.com/MRI-Lab-Graz/prism-specification/issues/new")
    assert link.get_attribute("rel") == "noopener noreferrer"
    app_page.locator("#spec-propose-close").click()
    expect(dialog).not_to_be_visible()

    app_page.once("dialog", lambda confirm: confirm.accept())
    app_page.get_by_role("button", name="Remove").first.click()
    expect(app_page.locator("#spec-local")).to_contain_text("None yet")
    assert not (project / "code" / "specification" / "terms" / "biosample" / "dhea-s.json").exists()


def test_a_hostile_column_name_is_shown_as_text_not_as_html(app_page, studio_url, project):
    add_biosample_data(project)
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data['<img src=x onerror="window.pwned=1">'] = {"Description": "x", "Units": "pg/mL"}
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    app_page.goto(f"{studio_url}/specifications/contribute")
    expect(app_page.locator("#spec-unknown")).to_contain_text("<img src=x")
    assert app_page.evaluate("window.pwned") is None
    assert app_page.locator("#spec-unknown img").count() == 0
