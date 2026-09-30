"""Share & Archive page: export a project the way a user does."""

import zipfile

from playwright.sync_api import expect


def start_standard_export(page, studio_url, out, validation_mode):
    page.goto(f"{studio_url}/projects/share")
    expect(page.locator("#exportProjectCard")).to_be_visible()
    if not page.locator("#exportOutputFolder").is_visible():
        page.locator('[data-bs-target="#exportSection"]').click()
    page.fill("#exportOutputFolder", str(out))
    page.select_option("#exportValidationMode", validation_mode)
    page.get_by_role("button", name="Standard Export & Save").click()
    page.wait_for_function(
        "() => document.getElementById('exportProgress').style.display === 'none'", timeout=30000
    )


def test_standard_export_is_blocked_while_validation_finds_errors(app_page, studio_url, tmp_path):
    out = tmp_path / "exports"
    out.mkdir()

    start_standard_export(app_page, studio_url, out, "both")

    expect(app_page.locator("#exportProjectCard")).to_contain_text("Export blocked: validation found")
    assert list(out.glob("*.zip")) == []


def test_standard_export_without_validation_writes_a_zip_with_the_project_files(app_page, studio_url, tmp_path):
    out = tmp_path / "exports"
    out.mkdir()

    start_standard_export(app_page, studio_url, out, "ignore")

    zips = list(out.glob("*.zip"))
    assert len(zips) == 1, app_page.inner_text("#exportProjectCard")[-400:]
    with zipfile.ZipFile(zips[0]) as z:
        assert "dataset_description.json" in " ".join(z.namelist())
