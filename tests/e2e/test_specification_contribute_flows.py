"""Contribute page: an unknown metric in the open project is added locally, shared (preview only) and removed."""

import pytest
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
    choose_kind(app_page, studio_url, "biosample")

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
    choose_kind(app_page, studio_url, "biosample")
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
    choose_kind(app_page, studio_url, "biosample")
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


def choose_kind(page, studio_url, kind):
    page.goto(f"{studio_url}/specifications/contribute")
    page.locator("#spec-kind").select_option(kind)


def open_all_sections(page):
    page.locator("#spec-sections .collapse").first.wait_for(state="attached")  # the example arrives after the kind is chosen
    page.evaluate("document.querySelectorAll('#spec-sections .collapse').forEach(c => c.classList.add('show'))")


def proposal_entry(page, label):
    open_all_sections(page)
    return page.locator("#spec-sections").get_by_label(label, exact=True)


def add_missing(page, label, value):
    proposal_entry(page, label).select_option(label="Missing: add a value…")
    page.locator("#spec-sections").get_by_label(f"New value for {label}").fill(value)


def page_words(page):
    """The visible text of the page card and the open dialog, without code elements and the proposal document."""
    return page.evaluate("""() => ["#spec-contribute", "#spec-propose-dialog"].map(selector => {
        const copy = document.querySelector(selector).cloneNode(true);
        copy.querySelectorAll("code, #spec-propose-json").forEach(n => n.remove());
        copy.removeAttribute("id");
        document.body.appendChild(copy);
        const text = copy.innerText; copy.remove(); return text;
    }).join(" ")""").lower()


def test_nothing_but_the_kind_of_data_is_shown_at_first(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/specifications/contribute")
    kind = bare_page.locator("#spec-kind")
    expect(kind).to_be_visible()
    expect(kind.locator("option:checked")).to_have_text("Choose the kind of data…")
    expect(kind.locator("option").last).to_have_text("➕ Nothing fits: a new kind of data")
    expect(bare_page.get_by_label("Not sure")).to_be_visible()
    expect(bare_page.locator("#spec-step2")).to_be_hidden()
    expect(bare_page.locator("#spec-panel-metric")).to_be_hidden()


def test_biosample_shows_the_accepted_example_beside_the_proposal(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    expect(bare_page.locator("#spec-sections")).to_contain_text("serum")
    specimen = proposal_entry(bare_page, "Specimen type")
    expect(specimen.locator("option:checked")).to_have_text("Choose…")
    expect(specimen.locator("option", has_text="saliva")).to_have_count(1)
    expect(specimen.locator("option", has_text="Missing: add a value…")).to_have_count(1)
    expect(specimen.locator("option", has_text="Unknown")).to_have_count(1)
    expect(bare_page.locator("#spec-sections").get_by_label("New value for Specimen type")).to_be_hidden()
    expect(bare_page.locator("#spec-panel-metric")).to_be_visible()  # biosample has measurements


def test_a_missing_value_is_shared_with_the_rest_as_context(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    bare_page.get_by_label("Not sure").check()
    add_missing(bare_page, "Specimen type", "sweat")
    proposal_entry(bare_page, "Collection method").select_option("swab")
    proposal_entry(bare_page, "Anticoagulant").select_option(label="Unknown")
    proposal_entry(bare_page, "Laboratory").fill("Our lab")
    bare_page.get_by_label("Unknown: Assay method").check()
    bare_page.locator("#spec-share-buttons").get_by_role("button").click()
    expect(bare_page.locator("#spec-propose-dialog")).to_be_visible()
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("sweat")
    expect(bare_page.locator("#spec-propose-json")).not_to_contain_text("swab")  # context only, not proposed
    context = bare_page.locator("#spec-propose-context")
    expect(context).to_contain_text("Technical.CollectionMethod: swab")
    expect(context).to_contain_text("Technical.Anticoagulant: Unknown")
    expect(context).to_contain_text("Technical.Laboratory: Our lab")
    expect(context).to_contain_text("Technical.AssayMethod: Unknown")
    expect(context).to_contain_text("closest: biosample")
    href = bare_page.locator("#spec-propose-open").get_attribute("href")
    assert href.startswith("https://github.com/MRI-Lab-Graz/prism-specification/issues/new")
    assert "sweat" in href and "context=" in href


def test_several_missing_lists_are_shared_one_at_a_time(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    add_missing(bare_page, "Specimen type", "sweat")
    add_missing(bare_page, "Collection method", "patch-collector")
    buttons = bare_page.locator("#spec-share-buttons").get_by_role("button")
    expect(buttons).to_have_count(2)
    buttons.nth(1).click()
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("patch-collector")
    expect(bare_page.locator("#spec-propose-json")).not_to_contain_text("sweat")
    expect(bare_page.locator("#spec-propose-context")).to_contain_text("Technical.SpecimenType: sweat (also proposed)")


def test_a_too_long_proposal_shows_the_text_to_paste(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    add_missing(bare_page, "Specimen type", "sweat")
    open_all_sections(bare_page)
    boxes = bare_page.locator("#spec-sections input[type=text]:visible:not([aria-label])")  # the free-text entries
    for index in range(boxes.count()):
        boxes.nth(index).fill("ä" * 200)
    bare_page.locator("#spec-share-buttons").get_by_role("button").click()
    expect(bare_page.locator("#spec-propose-open")).to_be_hidden()
    expect(bare_page.locator("#spec-propose-paste")).to_be_visible()
    expect(bare_page.locator("#spec-propose-context")).to_contain_text("ää")


def test_step_two_is_folded_like_the_project_page_with_plain_titles(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    toggles = bare_page.locator("#spec-sections .sm-section-toggle")
    expect(toggles).to_have_count(1)  # "About the measure" has no list to extend, so it is not shown
    expect(toggles.first).to_contain_text("How the data is collected")
    expect(toggles.first).to_contain_text("9 entries")
    summary = toggles.first.locator(".sm-section-toggle__summary")
    expect(summary).to_contain_text("Specimen type, Collection method")
    title = toggles.first.locator(".sm-section-toggle__title")
    assert abs(summary.bounding_box()["x"] - title.bounding_box()["x"]) < 2  # starts under the title, not centred
    badge = toggles.first.locator(".sm-section-toggle__badge")
    assert badge.evaluate("b => getComputedStyle(b).backgroundColor") not in ("rgba(0, 0, 0, 0)", "transparent")
    expect(bare_page.locator("#spec-sections .collapse.show")).to_have_count(0)  # every section starts closed
    toggles.first.click()
    expect(toggles.first).to_have_attribute("aria-expanded", "true")
    expect(bare_page.locator("#spec-sections .collapse.show")).to_have_count(1)
    expect(bare_page.locator("#spec-step2 button[aria-label^='About Specimen type']")).to_have_count(1)


def test_only_sections_with_something_to_propose_are_shown(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "survey")
    expect(bare_page.locator("#spec-sections .sm-section-toggle", has_text="About the measure")).to_have_count(1)
    expect(bare_page.locator("#spec-sections .sm-section-toggle", has_text="Norms")).to_have_count(0)
    expect(bare_page.locator("#spec-kind option[value='events']")).to_have_count(0)  # nothing of task events can be proposed
    expect(bare_page.locator("#spec-kind option[value='environment']")).to_have_count(1)


def test_environment_has_no_privacy_section_and_a_form_without_sample_type(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "environment")
    expect(bare_page.locator("#spec-sections .sm-section-toggle", has_text="Privacy")).to_have_count(0)
    bare_page.locator("#spec-m-pick").select_option("missing")
    expect(bare_page.locator("#spec-m-form")).to_be_visible()
    expect(bare_page.locator("#spec-m-specimen")).to_be_hidden()
    expect(bare_page.locator("#spec-m-units")).to_be_visible()


def test_example_and_proposal_stay_level_row_by_row(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    open_all_sections(bare_page)
    for label in ("Specimen type", "Laboratory", "Assay kit"):
        proposal = bare_page.locator("#spec-step2 label", has_text=label).bounding_box()
        example = bare_page.locator("#spec-step2 .spec-example-label", has_text=label).bounding_box()
        assert abs(proposal["y"] - example["y"]) < 3, label


def test_step_two_says_only_the_missing_value_is_needed(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    rule = bare_page.locator("#spec-step2-rule")
    expect(rule).to_be_visible()
    expect(rule).to_contain_text("Only fill in what is missing")
    expect(rule).to_contain_text("Missing: add a value…")


def test_the_summary_says_what_is_proposed_and_what_is_only_context(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    summary = bare_page.locator("#spec-summary")
    expect(summary).to_contain_text("Nothing to propose yet")
    add_missing(bare_page, "Specimen type", "sweat")
    expect(summary).to_contain_text("You propose: Specimen type: sweat")
    expect(summary).to_contain_text("Nothing else goes along")
    proposal_entry(bare_page, "Collection method").select_option("swab")
    proposal_entry(bare_page, "Laboratory").fill("Our lab")
    expect(summary).to_contain_text("Goes along only as context (not proposed): Collection method, Laboratory")


def test_the_measurement_pulldown_fits_inside_the_card(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "environment")
    pick = bare_page.locator("#spec-m-pick")
    expect(pick).to_be_visible()
    card = bare_page.locator("#spec-contribute").bounding_box()
    box = pick.bounding_box()
    assert box["x"] + box["width"] <= card["x"] + card["width"] + 1  # not wider than the page card


def test_measurements_are_grouped_when_their_terms_have_a_group(bare_page, studio_url):
    def add_groups(route):
        data = route.fetch().json()
        for kind in data["modalities"]:
            for metric in kind["metrics"] or []:
                metric["group"] = "Air quality" if metric["id"] in ("prism:ozone", "prism:pm10") else ("Pollen" if "pollen" in metric["id"] else None)
        route.fulfill(json=data)

    bare_page.route("**/api/spec/catalog", add_groups)
    choose_kind(bare_page, studio_url, "environment")
    groups = bare_page.locator("#spec-m-pick optgroup")
    expect(groups).to_have_count(2)
    expect(groups.first).to_have_attribute("label", "Air quality")
    expect(groups.first.locator("option")).to_have_count(2)
    expect(bare_page.locator("#spec-m-pick > option", has_text="air temperature")).to_have_count(1)  # no group: listed outside


def test_no_bids_kind_is_offered(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/specifications/contribute")
    expect(bare_page.locator("#spec-kind option", has_text="BIDS")).to_have_count(0)


NOTHING_FITS = "➕ Nothing fits: a new kind of data"


def test_nothing_fits_shows_the_new_kind_form(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "physio")
    bare_page.locator("#spec-kind").select_option(label=NOTHING_FITS)
    form = bare_page.locator("#spec-new-kind")
    expect(form).to_be_visible()
    expect(bare_page.locator("#spec-step2")).to_be_hidden()
    expect(form).to_contain_text("Until it is merged and in a PRISM release, PRISM cannot validate these files.")
    expect(form).to_contain_text("Use made-up data only")
    expect(bare_page.locator("#spec-nk-closest")).to_have_value("physio")  # the step-1 choice before "Nothing fits"


def test_a_new_kind_without_a_description_is_refused(bare_page, studio_url):
    bare_page.allowed_http[400] = "/api/spec/propose-new-kind"
    bare_page.goto(f"{studio_url}/specifications/contribute")
    bare_page.locator("#spec-kind").select_option(label=NOTHING_FITS)
    expect(bare_page.locator("#spec-nk-closest")).to_have_value("")
    bare_page.locator("#spec-nk-sample").fill("time,value\n0,1\n")
    bare_page.locator("#spec-nk-share").click()
    expect(bare_page.locator("#spec-message")).to_contain_text("the description is empty")
    expect(bare_page.locator("#spec-propose-dialog")).not_to_be_visible()


def test_a_new_kind_opens_the_prefilled_form_without_the_sample(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/specifications/contribute")
    bare_page.locator("#spec-kind").select_option(label=NOTHING_FITS)
    bare_page.locator("#spec-nk-description").fill("Skin temperature from a wrist sensor, one file per night.")
    bare_page.locator("#spec-nk-sample").fill("time,temp\n0,zzsample-123\n")
    bare_page.locator("#spec-nk-closest").select_option("physio")
    bare_page.locator("#spec-nk-share").click()
    dialog = bare_page.locator("#spec-propose-dialog")
    expect(dialog).to_be_visible()
    expect(dialog).to_contain_text('"Sample file"')
    href = bare_page.locator("#spec-propose-open").get_attribute("href")
    assert "propose-new-kind-of-data.yml" in href and "Skin" in href
    assert "zzsample" not in href
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("zzsample-123")  # the download text has it
    with bare_page.expect_download() as download:
        bare_page.locator("#spec-propose-download").click()
    assert download.value.suggested_filename.endswith(".txt")


def test_a_new_kind_sample_can_be_picked_from_a_file(bare_page, studio_url, tmp_path):
    sample = tmp_path / "sample.csv"
    sample.write_text("time,temp\n0,36.5\n", encoding="utf-8")
    bare_page.goto(f"{studio_url}/specifications/contribute")
    bare_page.locator("#spec-kind").select_option(label=NOTHING_FITS)
    bare_page.locator("#spec-nk-file").set_input_files(str(sample))
    expect(bare_page.locator("#spec-nk-sample")).to_have_value("time,temp\n0,36.5\n")


def test_a_hostile_new_kind_description_is_text(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/specifications/contribute")
    bare_page.locator("#spec-kind").select_option(label=NOTHING_FITS)
    bare_page.locator("#spec-nk-description").fill('<img src=x onerror="window.pwned=1">')
    bare_page.locator("#spec-nk-sample").fill("a,b\n1,2\n")
    bare_page.locator("#spec-nk-share").click()
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("<img src=x")
    assert bare_page.locator("#spec-contribute img, #spec-propose-dialog img").count() == 0
    assert bare_page.evaluate("window.pwned") is None


def pick_specimen(page, value):
    proposal_entry(page, "Specimen type").select_option(value)


def measurement_options(page):
    return page.locator("#spec-m-pick option").all_inner_texts()


def test_the_measurements_follow_the_chosen_specimen(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    expect(bare_page.locator("#spec-m-pick option:checked")).to_have_text("Choose…")
    expect(bare_page.locator("#spec-m-pick")).to_contain_text("C-reactive protein")
    pick_specimen(bare_page, "saliva")
    expect(bare_page.locator("#spec-m-pick")).not_to_contain_text("C-reactive protein")
    texts = " ".join(measurement_options(bare_page))
    assert "cortisol" in texts and "alpha-amylase" in texts and "prism:cortisol" in texts
    assert measurement_options(bare_page)[-1] == "Missing: add a measurement…"
    bare_page.locator("#spec-m-pick").select_option(label=next(t for t in measurement_options(bare_page) if "cortisol" in t))
    expect(bare_page.locator("#spec-m-yes")).to_be_visible()
    expect(bare_page.locator("#spec-m-form")).to_be_hidden()


def test_a_missing_measurement_starts_with_the_chosen_sample_type(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    pick_specimen(bare_page, "saliva")
    bare_page.locator("#spec-m-pick").select_option(label="Missing: add a measurement…")
    expect(bare_page.locator("#spec-m-form")).to_be_visible()
    expect(bare_page.locator("#spec-m-specimen")).to_have_value("saliva")
    expect(bare_page.locator("#spec-m-units option:checked")).to_have_text("Choose…")


def test_a_missing_measurement_starts_with_a_typed_sample_type(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    add_missing(bare_page, "Specimen type", "sweat")
    bare_page.locator("#spec-m-pick").select_option(label="Missing: add a measurement…")
    expect(bare_page.locator("#spec-m-specimen")).to_have_value("sweat")


def test_without_a_sample_type_the_measurement_form_starts_on_choose(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    bare_page.locator("#spec-m-pick").select_option(label="Missing: add a measurement…")
    expect(bare_page.locator("#spec-m-specimen option:checked")).to_have_text("Choose…")


def test_a_missing_measurement_carries_the_context(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    bare_page.get_by_label("Not sure").check()
    pick_specimen(bare_page, "saliva")
    proposal_entry(bare_page, "Laboratory").fill("Our lab")
    bare_page.locator("#spec-m-pick").select_option(label="Missing: add a measurement…")
    fill_measurement(bare_page)
    bare_page.locator("#spec-m-share").click()
    context = bare_page.locator("#spec-propose-context")
    expect(context).to_contain_text("Technical.Laboratory: Our lab")
    expect(context).to_contain_text("closest: biosample")


def test_a_kind_without_measurements_hides_the_measurement_part(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "survey")
    expect(proposal_entry(bare_page, "Respondent")).to_be_visible()
    expect(bare_page.locator("#spec-panel-metric")).to_be_hidden()


def test_use_adds_a_survey_value_shown_with_its_kind_and_removed(app_page, studio_url, project):
    choose_kind(app_page, studio_url, "survey")
    add_missing(app_page, "Respondent", "sibling")
    app_page.locator("#spec-use").click()
    expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    patch = project / "code" / "specification" / "patches" / "survey.json"
    assert json.loads(patch.read_text(encoding="utf-8"))["operations"][0]["values"] == ["sibling"]
    local = app_page.locator("#spec-values-local")
    expect(local).to_contain_text("sibling")
    expect(local).to_contain_text("Questionnaires and rating scales")
    app_page.once("dialog", lambda confirm: confirm.accept())
    local.get_by_role("button", name="Remove").first.click()
    expect(local).to_contain_text("None yet")
    assert not patch.exists() or "sibling" not in patch.read_text(encoding="utf-8")


def test_use_is_hidden_without_a_project(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    add_missing(bare_page, "Specimen type", "sweat")
    expect(bare_page.locator("#spec-use")).to_be_hidden()
    expect(bare_page.locator("body")).not_to_contain_text("Open a project first")


def test_no_page_text_uses_technical_words(app_page, studio_url, project):
    add_biosample_data(project)
    app_page.goto(f"{studio_url}/specifications/contribute")
    for kind in (None, "biosample", "survey", "new-kind"):
        if kind:
            app_page.locator("#spec-kind").select_option(kind)
            expect(app_page.locator("#spec-kind")).to_have_value(kind)
            app_page.wait_for_load_state("networkidle")
        words = page_words(app_page)
        assert not [w for w in TECHNICAL_WORDS if w in words], kind
    app_page.locator("#spec-kind").select_option("survey")
    add_missing(app_page, "Respondent", "sibling")
    app_page.locator("#spec-use").click()
    expect(app_page.locator("#spec-values-local")).to_contain_text("sibling")
    app_page.locator("#spec-share-buttons").get_by_role("button").click()
    expect(app_page.locator("#spec-propose-dialog")).to_be_visible()
    words = page_words(app_page)
    assert "share a choice with the prism community" in words  # the dialog's text is part of the check
    assert not [w for w in TECHNICAL_WORDS if w in words]


TECHNICAL_WORDS = ("modalit", "patch", "enum", "schema", "termid")


def test_yes_no_entries_are_pull_downs_without_missing(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    fasting = proposal_entry(bare_page, "Fasting required")
    expect(fasting).to_have_js_property("tagName", "SELECT")
    expect(fasting.locator("option", has_text="Unknown")).to_have_count(1)
    expect(fasting.locator("option", has_text="yes")).to_have_count(1)
    expect(fasting.locator("option", has_text="Missing")).to_have_count(0)


def test_free_text_unknown_ticks_are_named_after_their_entry(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    laboratory = proposal_entry(bare_page, "Laboratory")  # opens the folds
    bare_page.get_by_label("Unknown: Laboratory").check()
    expect(laboratory).to_be_disabled()


def test_a_slow_example_of_an_earlier_choice_does_not_replace_the_newer_one(bare_page, studio_url):
    held = []
    bare_page.route(re.compile(r".*/api/spec/example\?modality=biosample.*"), lambda route: held.append(route))
    bare_page.goto(f"{studio_url}/specifications/contribute")
    bare_page.locator("#spec-kind").select_option("biosample")
    for _ in range(100):  # until the biosample request is held
        if held:
            break
        bare_page.wait_for_timeout(50)
    bare_page.locator("#spec-kind").select_option("survey")
    expect(proposal_entry(bare_page, "Respondent")).to_be_visible()
    assert held, "the biosample example request was not held"
    held[0].continue_()
    bare_page.wait_for_timeout(500)
    expect(bare_page.locator("#spec-sections")).not_to_contain_text("serum")
    expect(proposal_entry(bare_page, "Respondent")).to_be_visible()


def test_an_addition_made_outside_the_page_is_shown_with_its_kind_and_removed(app_page, studio_url, project):
    from src.spec_overlay import add_local_values

    add_local_values(project, "Technical.Respondent", ["sibling"], modality="survey")
    patch = project / "code" / "specification" / "patches" / "survey.json"
    assert patch.is_file()
    choose_kind(app_page, studio_url, "survey")
    local = app_page.locator("#spec-values-local")
    expect(local).to_contain_text("sibling")
    expect(local).to_contain_text("Questionnaires and rating scales")  # the kind's label, not its name
    expect(app_page.get_by_role("button", name=re.compile(r"Share additions \(Questionnaires"))).to_be_visible()
    app_page.once("dialog", lambda confirm: confirm.accept())
    local.get_by_role("button", name="Remove").first.click()
    expect(local).to_contain_text("None yet")
    assert not patch.exists() or "sibling" not in patch.read_text(encoding="utf-8")


def test_a_value_found_in_the_data_is_added_to_the_project(app_page, studio_url, project):
    add_biosample_data(project)
    sidecar = project / "biosample-saliva_biosample.json"
    data = json.loads(sidecar.read_text(encoding="utf-8"))
    data["Technical"]["SpecimenType"] = "sweat"
    sidecar.write_text(json.dumps(data), encoding="utf-8")
    choose_kind(app_page, studio_url, "biosample")
    expect(app_page.locator("#spec-values-unknown")).to_contain_text("sweat")
    app_page.locator("#spec-values-unknown").get_by_role("button", name="Add to this project").click()
    expect(app_page.locator("#spec-message")).to_contain_text("Added to this project")
    expect(app_page.locator("#spec-values-unknown")).to_contain_text("Nothing")
    app_page.get_by_role("button", name="Share additions").click()
    expect(app_page.locator("#spec-propose-json")).to_contain_text("patches/biosample.json")


def test_hostile_value_is_text(app_page, studio_url):
    app_page.allowed_http[400] = "/api/spec/propose-values"
    choose_kind(app_page, studio_url, "biosample")
    opened = []
    app_page.on("dialog", lambda d: opened.append(d.message))
    add_missing(app_page, "Specimen type", '<img src=x onerror="window.pwned=1">')
    app_page.locator("#spec-share-buttons").get_by_role("button").click()
    expect(app_page.locator("#spec-message")).to_have_class(re.compile("alert-danger"))
    assert app_page.locator("#spec-contribute img").count() == 0
    assert app_page.evaluate("window.pwned") is None
    assert opened == []


def test_already_allowed_value_is_explained(bare_page, studio_url):
    bare_page.allowed_http[400] = "/api/spec/propose-values"
    choose_kind(bare_page, studio_url, "biosample")
    add_missing(bare_page, "Specimen type", "saliva")
    bare_page.locator("#spec-share-buttons").get_by_role("button").click()
    expect(bare_page.locator("#spec-message")).to_contain_text("already allowed")


def choose_measurement(page, studio_url, answer="Missing: add a measurement…"):
    choose_kind(page, studio_url, "biosample")
    if answer:
        page.locator("#spec-m-pick").select_option(label=answer)


def fill_measurement(page, name="DHEA", units="pg/mL", description="Dehydroepiandrosterone in saliva."):
    page.locator("#spec-m-name").fill(name)
    page.locator("#spec-m-description").fill(description)
    page.locator("#spec-m-units").select_option(label=units)
    page.locator("#spec-m-specimen").select_option("saliva")


def test_a_missing_measurement_without_a_project(bare_page, studio_url):
    choose_measurement(bare_page, studio_url, answer=None)
    expect(bare_page.locator("#spec-m-yes")).to_be_hidden()
    expect(bare_page.locator("#spec-m-form")).to_be_hidden()
    bare_page.locator("#spec-m-pick").select_option(label="Missing: add a measurement…")
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


def test_found_columns_show_only_for_their_own_kind(app_page, studio_url, project):
    add_biosample_data(project)
    choose_kind(app_page, studio_url, "environment")
    expect(app_page.locator("#spec-m-found")).to_be_hidden()
    expect(app_page.locator("#spec-m-use")).to_be_hidden()
    app_page.locator("#spec-kind").select_option("biosample")
    expect(app_page.locator("#spec-m-found")).to_contain_text("dhea_s")


def test_a_picked_found_column_is_forgotten_when_the_kind_changes(app_page, studio_url, project):
    add_biosample_data(project)
    choose_kind(app_page, studio_url, "biosample")
    app_page.locator("#spec-m-found").get_by_role("button", name="dhea_s").click()
    expect(app_page.locator("#spec-m-use")).to_be_visible()
    app_page.locator("#spec-kind").select_option("environment")
    expect(app_page.locator("#spec-m-use")).to_be_hidden()
    expect(app_page.locator("#spec-m-name")).not_to_have_value("dhea_s")


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
    expect(bare_page.locator("#spec-kind")).to_be_visible()


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


def test_each_share_names_its_own_download(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    add_missing(bare_page, "Specimen type", "sweat")
    bare_page.locator("#spec-share-buttons").get_by_role("button").click()
    expect(bare_page.locator("#spec-propose-download")).to_have_text("Download proposal.json")
    expect(bare_page.locator("#spec-propose-open")).to_have_text("Open the prefilled form on GitHub")
    bare_page.locator("#spec-propose-close").click()
    bare_page.locator("#spec-kind").select_option(label=NOTHING_FITS)
    bare_page.locator("#spec-nk-description").fill("Skin temperature from a wrist sensor.")
    bare_page.locator("#spec-nk-sample").fill("time,temp\n0,36.5\n")
    bare_page.locator("#spec-nk-share").click()
    expect(bare_page.locator("#spec-propose-download")).to_have_text("Download new-kind-of-data.txt")


def test_a_new_kind_too_long_for_a_link_says_what_to_paste(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/specifications/contribute")
    bare_page.locator("#spec-kind").select_option(label=NOTHING_FITS)
    bare_page.locator("#spec-nk-description").fill("A wrist sensor. " * 450)  # about 7,200 characters
    bare_page.locator("#spec-nk-sample").fill("time,temp\n0,zzsample-123\n")
    bare_page.locator("#spec-nk-share").click()
    open_link = bare_page.locator("#spec-propose-open")
    expect(open_link).to_have_text("Open the form on GitHub")
    href = open_link.get_attribute("href")
    assert href == bare_page.locator("#spec-contribute").get_attribute("data-new-kind-form-url")
    assert "zzsample" not in href
    text = bare_page.locator("#spec-propose-text")
    expect(text).to_contain_text("Paste the description, the closest kind of data and the sample from the download into their fields of the form.")
    expect(text).not_to_contain_text("prefilled")
    expect(bare_page.locator("#spec-propose-json")).to_contain_text("zzsample-123")


def test_a_measurement_without_a_unit_is_refused(bare_page, studio_url):
    bare_page.allowed_http[400] = "/api/spec/propose-metric"
    choose_measurement(bare_page, studio_url)
    bare_page.locator("#spec-m-name").fill("DHEA")
    bare_page.locator("#spec-m-description").fill("Dehydroepiandrosterone in saliva.")
    bare_page.locator("#spec-m-specimen").select_option("saliva")
    expect(bare_page.locator("#spec-m-units option:checked")).to_have_text("Choose…")
    bare_page.locator("#spec-m-share").click()
    expect(bare_page.locator("#spec-message")).to_contain_text("units")
    expect(bare_page.locator("#spec-message")).to_have_class(re.compile("alert-danger"))
    expect(bare_page.locator("#spec-propose-dialog")).not_to_be_visible()


def test_the_open_measurement_form_follows_a_new_sample_type(bare_page, studio_url):
    choose_kind(bare_page, studio_url, "biosample")
    pick_specimen(bare_page, "saliva")
    bare_page.locator("#spec-m-pick").select_option(label="Missing: add a measurement…")
    expect(bare_page.locator("#spec-m-specimen")).to_have_value("saliva")
    pick_specimen(bare_page, "serum")
    expect(bare_page.locator("#spec-m-pick")).to_have_value("missing")
    expect(bare_page.locator("#spec-m-specimen")).to_have_value("serum")
