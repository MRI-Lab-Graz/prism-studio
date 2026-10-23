"""Contribute page: an unknown metric in the open project is added locally, shared (preview only) and removed."""

import json
import re

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
    app_page.locator("#spec-what").select_option("metric")

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
    app_page.locator("#spec-what").select_option("metric")
    expect(app_page.locator("#spec-unknown")).to_contain_text("<img src=x")
    assert app_page.evaluate("window.pwned") is None
    assert app_page.locator("#spec-unknown img").count() == 0


def test_share_all_puts_every_local_metric_in_one_proposal(app_page, studio_url, project):
    add_biosample_data(project)
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["ferr_ugl"] = {"Description": "Ferritin", "Units": "ug/L", "MinValue": 0}
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    (project / "sub-01" / "ses-1" / "biosample" / "sub-01_ses-1_biosample-saliva_biosample.tsv").write_text(
        "sample_id\tdhea_s\tferr_ugl\nS-1\t5\t7\n", encoding="utf-8")
    app_page.goto(f"{studio_url}/specifications/contribute")
    app_page.locator("#spec-what").select_option("metric")
    for _ in range(2):
        app_page.get_by_role("button", name="Add to this project").first.click()
        expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    app_page.get_by_role("button", name="Share all local metrics").click()
    shown = app_page.locator("#spec-propose-json")
    expect(shown).to_contain_text("prism-proposal/2")
    for stem in ("dhea-s.json", "dhea-s.saliva.json", "ferr-ugl.json", "ferr-ugl.saliva.json"):  # no name typed: the column name
        expect(shown).to_contain_text(f"terms/biosample/{stem}")
    expect(app_page.locator("#spec-propose-open")).to_be_visible()


def choose_values(page, studio_url):
    page.goto(f"{studio_url}/specifications/contribute")
    page.locator("#spec-what").select_option("values")
    page.locator("#spec-v-modality").select_option("biosample")
    page.locator("#spec-v-list").select_option(label="Specimen type")


def add_choice(page, text):
    page.locator("#spec-v-input").fill(text)
    page.locator("#spec-v-add").click()


def test_nothing_but_the_choice_is_shown_at_first(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/specifications/contribute")
    expect(bare_page.locator("#spec-what")).to_be_visible()
    expect(bare_page.locator("#spec-panel-values")).to_be_hidden()
    expect(bare_page.locator("#spec-panel-metric")).to_be_hidden()
    expect(bare_page.locator("#spec-what option[value=new-modality]")).to_be_disabled()
    expect(bare_page.locator("#spec-what option[value=new-modality]")).to_have_text("A whole new kind of data (coming soon)")


def test_a_missing_choice_without_a_project(bare_page, studio_url):
    choose_values(bare_page, studio_url)
    expect(bare_page.locator("#spec-v-allowed")).to_contain_text("saliva")
    add_choice(bare_page, "sweat")
    expect(bare_page.locator("#spec-v-mine")).to_contain_text("sweat")
    expect(bare_page.locator("#spec-v-use")).to_be_hidden()
    expect(bare_page.locator("body")).not_to_contain_text("Open a project first")
    bare_page.locator("#spec-v-share").click()
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("sweat")
    href = bare_page.locator("#spec-propose-open").get_attribute("href")
    assert href.startswith("https://github.com/MRI-Lab-Graz/prism-specification/issues/new")
    bare_page.locator("#spec-propose-close").click()
    bare_page.locator("#spec-v-mine").get_by_role("button", name="Remove").click()
    expect(bare_page.locator("#spec-v-mine")).not_to_contain_text("sweat")


def test_a_missing_choice_with_a_project(app_page, studio_url, project):
    choose_values(app_page, studio_url)
    add_choice(app_page, "sweat")
    app_page.locator("#spec-v-use").click()
    expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    patch = project / "code" / "specification" / "patches" / "biosample.json"
    assert json.loads(patch.read_text(encoding="utf-8"))["operations"][0]["values"] == ["sweat"]
    expect(app_page.locator("#spec-values-local")).to_contain_text("sweat")
    app_page.once("dialog", lambda confirm: confirm.accept())
    app_page.locator("#spec-values-local").get_by_role("button", name="Remove").first.click()
    expect(app_page.locator("#spec-values-local")).to_contain_text("None yet")
    assert not patch.exists()


def test_a_value_found_in_the_data_is_added_to_the_project(app_page, studio_url, project):
    add_biosample_data(project)
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["Technical"]["SpecimenType"] = "sweat"
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    app_page.goto(f"{studio_url}/specifications/contribute")
    app_page.locator("#spec-what").select_option("values")
    expect(app_page.locator("#spec-values-unknown")).to_contain_text("sweat")
    app_page.locator("#spec-values-unknown").get_by_role("button", name="Add to this project").click()
    expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    expect(app_page.locator("#spec-values-unknown")).to_contain_text("Nothing")
    app_page.get_by_role("button", name="Share additions").click()
    expect(app_page.locator("#spec-propose-json")).to_contain_text("patches/biosample.json")


def test_hostile_value_is_text(app_page, studio_url):
    app_page.allowed_http[400] = "/api/spec/propose-values"
    choose_values(app_page, studio_url)
    app_page.on("dialog", lambda d: (_ for _ in ()).throw(AssertionError("dialog opened")))
    add_choice(app_page, '<img src=x onerror="window.pwned=1">')
    expect(app_page.locator("#spec-v-mine")).to_contain_text("<img src=x")
    app_page.locator("#spec-v-share").click()
    expect(app_page.locator("#spec-message")).to_have_class(re.compile("alert-danger"))
    assert app_page.locator("#spec-contribute img").count() == 0
    assert app_page.evaluate("window.pwned") is None


def test_already_allowed_value_is_explained(bare_page, studio_url):
    choose_values(bare_page, studio_url)
    add_choice(bare_page, "saliva")
    expect(bare_page.locator("#spec-message")).to_contain_text("already allowed")
    expect(bare_page.locator("#spec-v-mine")).not_to_contain_text("saliva")
