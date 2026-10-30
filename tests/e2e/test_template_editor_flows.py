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
    assert administration.locator(".te-required-hint[data-hint-path='Technical/Respondent']").is_visible()
    assert page.locator("#ringRequired").get_attribute("aria-label") != "Required 100%"


def test_filling_the_field_turns_everything_green_without_a_reload(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)
    administration = _administration(page)

    administration.locator("#field_Technical_Respondent").select_option("self")

    page.wait_for_function("document.querySelector('#ringRequired').getAttribute('aria-label') === 'Required 100%'")
    assert administration.locator(".te-section-badge").inner_text() == "✓ complete"
    assert "is-invalid" not in administration.locator("#field_Technical_Respondent").get_attribute("class")
    assert not administration.locator(".te-required-hint[data-hint-path='Technical/Respondent']").is_visible()


def test_the_fair_ring_counts_recommended_fields_and_never_blocks(page, project, studio_url):
    _open_incomplete_template(page, project, studio_url)

    page.evaluate("document.querySelectorAll('details.te-subgroup').forEach((d) => { d.open = true; })")
    fair = page.locator("#ringFair")
    before = fair.get_attribute("aria-label")
    page.locator("#field_Study_DOI").fill("10.1000/182")

    page.wait_for_function(f"document.querySelector('#ringFair').getAttribute('aria-label') !== {json.dumps(before)}")
    assert page.locator("#ringFairText").inner_text().split("/")[0].isdigit()
