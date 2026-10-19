"""The shared in-app file picker: start folder, sorting, filter, selection."""

from __future__ import annotations

import os

from playwright.sync_api import expect

MODAL = "#folderBrowserModal"
NAMES = f"{MODAL} .folder-browser-file .fb-name"


def open_picker(page, method="browseFile", **options):
    """Start the picker without awaiting it (the promise resolves when the modal closes)."""
    page.evaluate(
        "([method, options]) => { window.__picked = null;"
        " window.PrismPathPicker[method](options).then(p => { window.__picked = p; }); }",
        [method, options],
    )
    expect(page.locator(MODAL)).to_be_visible()


def make_files(folder):
    for name, size, mtime in (("a.txt", 30, 300), ("b.txt", 10, 100), ("c.txt", 20, 200)):
        f = folder / name
        f.write_text("x" * size)
        os.utime(f, (mtime, mtime))


def test_starts_at_project_root_even_with_a_stale_start_path(app_page, studio_url, project, tmp_path):
    app_page.goto(f"{studio_url}/editor/")
    open_picker(app_page, startPath=str(tmp_path))
    expect(app_page.locator(f"{MODAL} .folder-browser-crumb").last).to_have_text("study")


def test_keep_start_path_reopens_at_the_callers_value(app_page, studio_url, tmp_path):
    other = tmp_path / "elsewhere"
    other.mkdir()
    app_page.goto(f"{studio_url}/editor/")
    open_picker(app_page, startPath=str(other), keepStartPath=True)
    expect(app_page.locator(f"{MODAL} .folder-browser-crumb").last).to_have_text("elsewhere")


def test_header_click_sorts_and_toggles_direction(app_page, studio_url, project):
    make_files(project)
    app_page.goto(f"{studio_url}/editor/")
    open_picker(app_page, extensions=".txt")

    expect(app_page.locator(NAMES)).to_have_text(["a.txt", "b.txt", "c.txt"])
    app_page.click(f"{MODAL} [data-sort=size]")
    expect(app_page.locator(NAMES)).to_have_text(["b.txt", "c.txt", "a.txt"])
    app_page.click(f"{MODAL} [data-sort=size]")
    expect(app_page.locator(NAMES)).to_have_text(["a.txt", "c.txt", "b.txt"])


def test_filter_hides_non_matching_entries(app_page, studio_url, project):
    make_files(project)
    app_page.goto(f"{studio_url}/editor/")
    open_picker(app_page, extensions=".txt")

    app_page.fill("#folderBrowserFilter", "b.")
    expect(app_page.locator(f"{MODAL} .fb-entry:visible .fb-name")).to_have_text(["b.txt"])


def test_double_click_picks_the_file(app_page, studio_url, project):
    make_files(project)
    app_page.goto(f"{studio_url}/editor/")
    open_picker(app_page, extensions=".txt")

    app_page.dblclick(f"{MODAL} .fb-entry[data-name='b.txt']")

    expect(app_page.locator(MODAL)).to_be_hidden()
    assert app_page.evaluate("window.__picked") == str(project.resolve() / "b.txt")
