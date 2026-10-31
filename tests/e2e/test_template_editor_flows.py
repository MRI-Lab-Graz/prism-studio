"""Template editor in a real browser: empty required fields are red until filled, the section badge and the
rings follow live, and the numbers are the backend's."""

import json

from tests.template_fixtures import project_template


def _open_incomplete_template(page, project, studio_url):
    template = project_template()
    template["Technical"].pop("Respondent")
    template["Study"].pop("Authors", None)
    (project / "code" / "library" / "survey" / "survey-x.json").write_text(json.dumps(template), encoding="utf-8")
    page.goto(f"{studio_url}/template-editor", wait_until="networkidle")
    page.select_option("#projectTemplateSelect", "survey-x.json")
    page.wait_for_selector("#completionRings", state="visible")


def _administration(page):
    section = page.locator("details.te-subgroup", has=page.locator(".te-subgroup-title", has_text="Administration"))
    section.locator("summary").click()
    return section


def test_an_empty_required_field_is_red_and_the_section_counts_it(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)
    administration = _administration(page)

    badge = administration.locator(".te-section-badge")
    assert badge.inner_text() == "1 required" and "bg-danger" in badge.get_attribute("class")
    field = administration.locator("#field_Technical_Respondent")
    assert "is-invalid" in field.get_attribute("class")
    assert page.locator("#ringRequired").get_attribute("aria-label") != "Required 100%"


def test_filling_the_field_turns_everything_green_without_a_reload(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)
    administration = _administration(page)

    administration.locator("#field_Technical_Respondent").select_option("self")

    page.wait_for_function("document.querySelector('#ringRequired').getAttribute('aria-label') === 'Required 100%'")
    assert administration.locator(".te-section-badge").inner_text() == "✓ complete"
    assert "is-invalid" not in administration.locator("#field_Technical_Respondent").get_attribute("class")


def test_the_fair_ring_counts_recommended_fields_and_never_blocks(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)

    page.evaluate("document.querySelectorAll('details.te-subgroup').forEach((d) => { d.open = true; })")
    fair = page.locator("#ringFair")
    before = fair.get_attribute("aria-label")
    page.locator("#field_Study_DOI").fill("10.1000/182")

    page.wait_for_function(f"document.querySelector('#ringFair').getAttribute('aria-label') !== {json.dumps(before)}")
    assert page.locator("#ringFairText").inner_text().split("/")[0].isdigit()


def test_languages_is_a_pull_down_and_the_pick_becomes_a_green_chip(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)
    section = page.locator("details.te-subgroup", has=page.locator(".te-subgroup-title", has_text="Languages"))
    section.locator("summary").click()

    field = section.locator("[data-field-path='I18n/Languages']")
    field.locator("select").wait_for()
    field.locator("select").select_option("fr")
    assert "fr" in page.locator("#langBadges").inner_text()  # the same code as the language bar: item texts get the slot too
    chips = [t.replace("\n", " ") for t in field.locator(".chip-badge").all_inner_texts()]
    assert chips == ["de (German) ×", "en (English) ×", "fr (French) ×"]
    assert field.locator("select option[value='fr']").count() == 0  # a picked language leaves the list
    assert field.locator("select option[value='de']").count() == 0  # so does one the template already has


def test_default_language_offers_the_chosen_languages_and_follows_them(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)
    section = page.locator("details.te-subgroup", has=page.locator(".te-subgroup-title", has_text="Languages"))
    section.locator("summary").click()
    languages = section.locator("[data-field-path='I18n/Languages']")
    default = section.locator("select[data-field-path='I18n/DefaultLanguage']")
    default.wait_for()
    assert default.locator("option").evaluate_all("o => o.map(x => x.value)") == ["", "de", "en"]

    languages.locator("select").select_option("fr")
    assert "fr" in default.locator("option").evaluate_all("o => o.map(x => x.value)")

    default.select_option("fr")
    page.once("dialog", lambda dialog: dialog.accept())
    languages.locator(".chip-badge", has_text="fr").click()
    assert default.input_value() == ""
    assert default.locator("option").evaluate_all("o => o.map(x => x.value)") == ["", "de", "en"]


def _languages_section(page):
    section = page.locator("details.te-subgroup", has=page.locator(".te-subgroup-title", has_text="Languages"))
    section.locator("summary").click()
    return section


def _chip_codes(section):
    return [t.split(" ")[0] for t in section.locator("[data-field-path='I18n/Languages'] .chip-badge").all_inner_texts()]


def test_the_language_bar_adds_from_a_pull_down_and_declares_the_language(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)
    page.click("#btnAddLang")
    page.locator("#langChooser").select_option("fr")
    assert "fr" in page.locator("#langBadges").inner_text()
    assert "fr" in _chip_codes(_languages_section(page))


def test_the_language_bar_removes_from_a_pull_down_and_undeclares_the_language(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)
    page.once("dialog", lambda dialog: dialog.accept())
    page.click("#btnRemoveLang")
    page.locator("#langChooser").select_option("en")
    assert "en" not in _chip_codes(_languages_section(page))


def test_removing_a_chip_asks_first_and_declining_keeps_it(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)
    section = _languages_section(page)
    page.once("dialog", lambda dialog: dialog.dismiss())
    section.locator("[data-field-path='I18n/Languages'] .chip-badge", has_text="en").click()
    assert _chip_codes(section) == ["de", "en"]


def _open_template_without_items(page, project, studio_url):
    template = project_template()
    for key in [k for k in template if k not in {"Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"}]:
        del template[key]
    template["I18n"]["Languages"] = ["en"]
    template["Technical"].pop("Language", None)
    template["I18n"].pop("DefaultLanguage", None)
    (project / "code" / "library" / "survey" / "survey-x.json").write_text(json.dumps(template), encoding="utf-8")
    page.goto(f"{studio_url}/template-editor", wait_until="networkidle")
    page.select_option("#projectTemplateSelect", "survey-x.json")
    page.wait_for_selector("#completionRings", state="visible")


def test_a_language_added_to_a_template_without_items_shows_in_the_bar(page, project, studio_url):
    _open_template_without_items(page, project, studio_url)
    page.click("#btnAddLang")
    page.locator("#langChooser").select_option("fr")
    assert page.locator("#langBadges [data-lang='fr']").count() == 1
    assert page.locator("#langBadges [data-lang='en']").count() == 1  # the declared one is listed too


def test_clicking_a_language_makes_it_the_primary_one(page, project, studio_url):
    _open_template_without_items(page, project, studio_url)
    assert "No primary language set" in page.locator("#langPrimaryBadge").inner_text()
    page.locator("#langBadges [data-lang='en'] [data-lang-primary]").click()
    assert page.locator("#langPrimaryBadge").inner_text() == "Primary: en"
    section = _languages_section(page)
    assert section.locator("select[data-field-path='I18n/DefaultLanguage']").input_value() == "en"


def test_every_language_in_the_bar_has_an_x_that_removes_it(page, project, studio_url):
    _open_template_without_items(page, project, studio_url)
    page.once("dialog", lambda dialog: dialog.accept())
    page.locator("#langBadges [data-lang='en'] [data-lang-remove]").click()
    assert page.locator("#langBadges [data-lang='en']").count() == 0
