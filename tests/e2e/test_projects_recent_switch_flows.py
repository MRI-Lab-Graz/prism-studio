import json

from playwright.sync_api import expect


def _make_project(path, name):
    path.mkdir()
    (path / "project.json").write_text(json.dumps({"Basics": {"Name": name}}))
    (path / "dataset_description.json").write_text(json.dumps({"Name": name, "BIDSVersion": "1.10.0"}))


def _open_two_projects(page, studio_url, tmp_path):
    """Opens both (so both are in the recent list), `first` last; records dialogs."""
    first, second = tmp_path / "first_study", tmp_path / "second_study"
    _make_project(first, "First")
    _make_project(second, "Second")
    dialogs = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    for path in (second, first):
        page.goto(f"{studio_url}/projects")
        page.click("#card-open")
        page.fill("#existingPath", str(path))
        page.click("#loadProjectBtn")
        expect(page.locator("#projectBoxDeleteBtn")).to_be_visible()
    return first, second, dialogs


def test_recent_chip_switches_projects_without_the_busy_alert(bare_page, studio_url, tmp_path):
    """Picking the Open card re-ran the loaded project's metadata load, so the very
    next step of the same click (the busy guard) always refused the switch."""
    first, second, dialogs = _open_two_projects(bare_page, studio_url, tmp_path)
    bare_page.wait_for_timeout(1000)  # let the first project's metadata finish loading

    bare_page.locator(f'#recentProjectsList [data-path="{second}"]').first.click()

    expect(bare_page.locator("#currentProjectBanner, #projectBoxDeleteBtn").first).to_be_visible()
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert current["path"] == str(second)
    assert dialogs == []


def test_recent_chip_switches_away_from_a_project_whose_folder_is_gone(bare_page, studio_url, tmp_path):
    """Its metadata load can never succeed, so it must not be (re)started by the click."""
    import shutil

    first, second, dialogs = _open_two_projects(bare_page, studio_url, tmp_path)
    shutil.rmtree(first)
    bare_page.allowed_http = {400: "/api/projects/"}
    bare_page.goto(f"{studio_url}/projects")  # still "current", but its folder is gone
    bare_page.wait_for_timeout(1000)

    bare_page.click("#card-open")
    expect(bare_page.locator(f'#recentProjectsList [data-path="{first}"]')).to_have_count(0)
    bare_page.locator(f'#recentProjectsList [data-path="{second}"]').first.click()

    bare_page.wait_for_timeout(1500)
    assert dialogs == []
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert current["path"] == str(second)
