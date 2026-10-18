"""Tool pages on an unfinished project: the blocked requests show a notice that links back to the Projects page."""

import json

import pytest
from playwright.sync_api import expect


def _make_unfinished(project):
    meta = json.loads((project / "project.json").read_text())
    meta["Basics"]["Authors"] = []  # the gate blocks until Name, Authors, Keywords and Timepoints are set
    (project / "project.json").write_text(json.dumps(meta))


@pytest.mark.parametrize("page_path", ["/converter", "/recipes", "/file-management"])
def test_a_blocked_tool_page_shows_the_notice_with_a_link_to_the_projects_page(app_page, studio_url, project, page_path):
    _make_unfinished(project)
    app_page.allowed_http[409] = "/api/"  # the blocked requests are the point of this test
    app_page.goto(f"{studio_url}{page_path}")
    link = app_page.get_by_role("link", name="Open the Projects page")
    expect(link.first).to_be_visible()
    expect(link.first).to_have_attribute("href", "/projects")
    expect(app_page.locator("#prismNotReadyNotice")).to_contain_text("Authors")  # the backend text names what is missing
    expect(link).to_have_count(1)  # one notice, not one per blocked request
