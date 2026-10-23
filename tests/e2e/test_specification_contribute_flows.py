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

    expect(app_page.locator("#spec-m-found")).to_contain_text("dhea_s")
    app_page.locator("#spec-m-found").get_by_role("button", name="dhea_s").click()
    app_page.locator("#spec-m-use").click()
    expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    expect(app_page.locator("#spec-local")).to_contain_text("prism:dhea-s.saliva")
    expect(app_page.locator("#spec-m-found")).to_contain_text("Nothing")
    assert (project / "code" / "specification" / "terms" / "biosample" / "dhea-s.json").is_file()

    app_page.get_by_role("button", name="Share…").first.click()
    dialog = app_page.locator("#spec-propose-dialog")
    expect(dialog).to_be_visible()
    expect(app_page.locator("#spec-propose-json")).to_contain_text("prism:dhea-s.saliva")
    expect(app_page.locator("#spec-propose-dialog")).to_contain_text("column name stays an alias")
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
    expect(app_page.locator("#spec-m-found")).to_contain_text("<img src=x")
    assert app_page.evaluate("window.pwned") is None
    assert app_page.locator("#spec-m-found img").count() == 0


def test_share_all_puts_every_local_measurement_in_one_proposal(app_page, studio_url, project):
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
        app_page.locator("#spec-m-found").get_by_role("button").first.click()
        app_page.locator("#spec-m-use").click()
        expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    app_page.get_by_role("button", name="Share all local measurements").click()
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
    expect(bare_page.get_by_role("button", name="Remove sweat")).to_be_visible()
    expect(bare_page.locator("#spec-v-use")).to_be_hidden()
    expect(bare_page.locator("body")).not_to_contain_text("Open a project first")
    bare_page.locator("#spec-v-share").click()
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("sweat")
    expect(bare_page.locator("#spec-propose-title")).to_have_text("Share a choice with the PRISM community")
    dialog_text = bare_page.locator("#spec-propose-dialog").inner_text().lower()
    assert "column name" not in dialog_text and "alias" not in dialog_text
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
    opened = []
    app_page.on("dialog", lambda d: opened.append(d.message))
    add_choice(app_page, '<img src=x onerror="window.pwned=1">')
    expect(app_page.locator("#spec-v-mine")).to_contain_text("<img src=x")
    app_page.locator("#spec-v-share").click()
    expect(app_page.locator("#spec-message")).to_have_class(re.compile("alert-danger"))
    assert app_page.locator("#spec-contribute img").count() == 0
    assert app_page.evaluate("window.pwned") is None
    assert opened == []


def test_already_allowed_value_is_explained(bare_page, studio_url):
    choose_values(bare_page, studio_url)
    add_choice(bare_page, "saliva")
    expect(bare_page.locator("#spec-message")).to_contain_text("already allowed")
    expect(bare_page.locator("#spec-v-mine")).not_to_contain_text("saliva")


def choose_measurement(page, studio_url, answer="No, it is still missing"):
    page.goto(f"{studio_url}/specifications/contribute")
    page.locator("#spec-what").select_option("metric")
    page.locator("#spec-m-modality").select_option("biosample")
    if answer:
        page.locator("#spec-m-listed").select_option(label=answer)


def fill_measurement(page, name="DHEA", units="pg/mL", description="Dehydroepiandrosterone in saliva."):
    page.locator("#spec-m-name").fill(name)
    page.locator("#spec-m-description").fill(description)
    page.locator("#spec-m-units").select_option(label=units)
    page.locator("#spec-m-specimen").select_option("saliva")


def test_a_missing_measurement_without_a_project(bare_page, studio_url):
    choose_measurement(bare_page, studio_url, answer=None)
    expect(bare_page.locator("#spec-m-known")).to_contain_text("cortisol")
    expect(bare_page.locator("#spec-m-yes")).to_be_hidden()
    expect(bare_page.locator("#spec-m-form")).to_be_hidden()
    bare_page.locator("#spec-m-listed").select_option(label="Yes, it is there")
    expect(bare_page.locator("#spec-m-yes")).to_be_visible()
    expect(bare_page.locator("#spec-m-form")).to_be_hidden()
    bare_page.locator("#spec-m-listed").select_option(label="No, it is still missing")
    expect(bare_page.locator("#spec-m-yes")).to_be_hidden()
    expect(bare_page.locator("#spec-m-form")).to_be_visible()
    expect(bare_page.locator("#spec-m-use")).to_be_hidden()
    expect(bare_page.locator("#spec-m-found")).to_be_hidden()
    expect(bare_page.locator("body")).not_to_contain_text("Open a project first")
    fill_measurement(bare_page)
    bare_page.locator("#spec-m-aliases").fill("dhea_s, DHEAS")
    bare_page.locator("#spec-m-share").click()
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("prism:dhea.saliva")
    expect(bare_page.locator("#spec-propose-title")).to_have_text("Share a measurement with the PRISM community")
    href = bare_page.locator("#spec-propose-open").get_attribute("href")
    assert href.startswith("https://github.com/MRI-Lab-Graz/prism-specification/issues/new")


def test_only_kinds_with_a_measurement_list_are_selectable(bare_page, studio_url):
    choose_measurement(bare_page, studio_url, answer=None)
    options = bare_page.locator("#spec-m-modality option")
    for index in range(options.count()):
        option = options.nth(index)
        if option.get_attribute("value") and not option.is_disabled():
            assert option.get_attribute("value") == "biosample"
    expect(bare_page.locator("#spec-m-known")).not_to_have_text("")


def test_official_name_is_refused(bare_page, studio_url):
    bare_page.allowed_http[400] = "/api/spec/propose-metric"
    choose_measurement(bare_page, studio_url)
    fill_measurement(bare_page, name="cortisol")
    bare_page.locator("#spec-m-share").click()
    expect(bare_page.locator("#spec-message")).to_contain_text("prism:cortisol")
    expect(bare_page.locator("#spec-message")).to_have_class(re.compile("alert-danger"))
    expect(bare_page.locator("#spec-propose-dialog")).not_to_be_visible()


def test_unit_other_is_free_text(bare_page, studio_url):
    choose_measurement(bare_page, studio_url)
    expect(bare_page.locator("#spec-m-units-other")).to_be_hidden()
    bare_page.locator("#spec-m-units").select_option(label="Other…")
    expect(bare_page.locator("#spec-m-units-other")).to_be_visible()
    fill_measurement(bare_page, units="Other…")
    bare_page.locator("#spec-m-units-other").fill("ng/dL")
    bare_page.locator("#spec-m-share").click()
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("ng/dL")


def test_a_missing_measurement_with_a_project(app_page, studio_url, project):
    add_biosample_data(project)
    choose_measurement(app_page, studio_url)
    expect(app_page.locator("#spec-m-found")).to_contain_text("dhea_s")
    expect(app_page.locator("#spec-m-use")).to_be_hidden()
    app_page.locator("#spec-m-found").get_by_role("button", name="dhea_s").click()
    expect(app_page.locator("#spec-m-name")).to_have_value("dhea_s")
    expect(app_page.locator("#spec-m-units")).to_have_value("pg/mL")
    expect(app_page.locator("#spec-m-specimen")).to_have_value("saliva")
    app_page.locator("#spec-m-use").click()
    expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    assert (project / "code" / "specification" / "terms" / "biosample" / "dhea-s.json").is_file()


def test_hostile_name_and_description_are_text(bare_page, studio_url):
    choose_measurement(bare_page, studio_url)
    fill_measurement(bare_page, name="<b>x</b>", description="<b>y</b> is bold")
    bare_page.locator("#spec-m-share").click()
    expect(bare_page.locator("#spec-propose-dialog")).to_contain_text("<b>x</b>")
    assert bare_page.locator("#spec-contribute b, #spec-propose-dialog b").count() == 0


def test_the_navbar_entry_leads_to_the_propose_page(bare_page, studio_url):
    bare_page.goto(studio_url)
    bare_page.locator("nav").get_by_role("link", name="Propose changes").click()
    expect(bare_page.locator("#spec-what")).to_be_visible()


def add_two_columns(project):
    """dhea_s has a unit, zzz_x has none."""
    add_biosample_data(project)
    path = project / "biosample-saliva_biosample.json"
    sidecar = json.loads(path.read_text(encoding="utf-8"))
    sidecar["zzz_x"] = {"Description": "Something without a unit"}
    path.write_text(json.dumps(sidecar), encoding="utf-8")
    tsv = project / "sub-01" / "ses-1" / "biosample" / "sub-01_ses-1_biosample-saliva_biosample.tsv"
    tsv.write_text("sample_id\tdhea_s\tzzz_x\nS-1\t5\t1\n", encoding="utf-8")


def test_picking_a_column_without_a_unit_clears_the_unit_of_the_one_before(app_page, studio_url, project):
    add_two_columns(project)
    choose_measurement(app_page, studio_url)
    found = app_page.locator("#spec-m-found")
    found.get_by_role("button", name="dhea_s").click()
    expect(app_page.locator("#spec-m-units")).to_have_value("pg/mL")
    found.get_by_role("button", name="zzz_x").click()
    expect(app_page.locator("#spec-m-units")).not_to_have_value("pg/mL")
    expect(app_page.locator("#spec-m-units-other")).to_have_value("")


def test_use_in_my_open_project_is_hidden_after_adding(app_page, studio_url, project):
    add_biosample_data(project)
    choose_measurement(app_page, studio_url)
    app_page.locator("#spec-m-found").get_by_role("button", name="dhea_s").click()
    expect(app_page.locator("#spec-m-use")).to_be_visible()
    app_page.locator("#spec-m-use").click()
    expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    expect(app_page.locator("#spec-m-use")).to_be_hidden()


def test_editing_the_name_after_picking_a_column_hides_use_in_my_open_project(app_page, studio_url, project):
    add_biosample_data(project)
    choose_measurement(app_page, studio_url)
    app_page.locator("#spec-m-found").get_by_role("button", name="dhea_s").click()
    expect(app_page.locator("#spec-m-use")).to_be_visible()
    app_page.locator("#spec-m-name").fill("Something else")
    expect(app_page.locator("#spec-m-use")).to_be_hidden()
