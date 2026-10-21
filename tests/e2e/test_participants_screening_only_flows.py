"""Converter > Sociodemographics > Merge: tick who was only screened."""

from playwright.sync_api import expect

from tests.e2e.test_converter_participants_flows import confirm_annotation, read_participants, start_merge

INCOMING = "participant_id,age\nP002,34\nP003,50\nP004,60\n"


def _merge(page, studio_url, project, tmp_path):
    (project / "sub-P002").mkdir()  # enrolled; P003 and P004 have no sub-folder
    start_merge(page, studio_url, project, tmp_path, INCOMING)


def _convert(page):
    confirm_annotation(page)
    page.click("#participantsConvertBtn")
    expect(page.locator("#participantsSuccess")).to_be_visible(timeout=30000)


def test_participants_without_a_folder_are_ticked_and_marked_screening_only(app_page, studio_url, tmp_path, project):
    _merge(app_page, studio_url, project, tmp_path)
    ticked = lambda pid: app_page.locator(f'[data-screening-id="{pid}"]')  # noqa: E731
    expect(ticked("sub-P003")).to_be_checked()
    expect(ticked("sub-P002")).not_to_be_checked()

    ticked("sub-P004").uncheck()  # screened and enrolled later: not screening-only
    _convert(app_page)

    groups = {r["participant_id"]: r["group"] for r in read_participants(project)}
    assert groups["sub-P003"] == "screening-only"
    assert groups["sub-P004"] == "n/a"
    assert groups["sub-P002"] == "n/a"
    assert set(groups) == {"sub-P001", "sub-P002", "sub-P003", "sub-P004"}  # nobody removed


def test_the_choice_is_not_offered_when_everyone_has_a_folder(app_page, studio_url, tmp_path, project):
    for pid in ("sub-P002", "sub-P003", "sub-P004"):
        (project / pid).mkdir()
    start_merge(app_page, studio_url, project, tmp_path, INCOMING)
    expect(app_page.locator("#participantsMergeScreeningSection")).to_be_hidden()
    _convert(app_page)
    assert "group" not in read_participants(project)[0]
