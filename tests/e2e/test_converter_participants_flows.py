"""Converter > Sociodemographics: build and merge participants.tsv the way a user does."""

import csv

from playwright.sync_api import expect

PEOPLE = "participant_id,age,sex\nP001,21,f\nP002,34,m\n"


def open_participants_tab(page, studio_url):
    page.goto(f"{studio_url}/converter")
    page.click("#participants-tab")
    expect(page.locator("#participants-panel")).to_be_visible()


def select_people_file(page, tmp_path, content=PEOPLE, name="people.csv"):
    data = tmp_path / name
    data.write_text(content)
    page.set_input_files("#participantsDataFile", str(data))


def read_participants(project):
    with open(project / "participants.tsv", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def preview_and_convert(page):
    page.click("#participantsPreviewBtn")
    expect(page.locator("#participantsConvertBtn")).to_be_enabled(timeout=30000)
    page.click("#participantsConvertBtn")
    expect(page.locator("#participantsSuccess")).to_be_visible(timeout=30000)


def test_new_participants_file_is_previewed_then_written(app_page, studio_url, tmp_path, project):
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path)

    app_page.click("#participantsPreviewBtn")
    expect(app_page.locator("#participantsPreviewTable")).to_contain_text("P001", timeout=30000)
    assert not (project / "participants.tsv").exists(), "preview must not write the file"

    app_page.click("#participantsConvertBtn")
    expect(app_page.locator("#participantsSuccess")).to_be_visible(timeout=30000)

    rows = read_participants(project)
    assert [r["participant_id"] for r in rows] == ["sub-P001", "sub-P002"]
    assert rows[1]["age"] == "34"


EXISTING = "participant_id\tage\nsub-P001\t21\nsub-P002\t34\n"


def start_merge(page, studio_url, project, tmp_path, incoming):
    (project / "participants.tsv").write_text(EXISTING)
    page.on("dialog", lambda dialog: dialog.accept())
    open_participants_tab(page, studio_url)
    select_people_file(page, tmp_path, incoming)
    page.click('[data-participants-case-id="3"]')  # Merge into the existing file
    page.click("#participantsPreviewBtn")
    expect(page.locator("#participantsMergeSummary")).to_be_visible(timeout=30000)


def test_merge_with_a_conflicting_value_is_blocked_and_leaves_the_file_alone(app_page, studio_url, tmp_path, project):
    start_merge(app_page, studio_url, project, tmp_path, "participant_id,age\nP002,35\nP003,50\n")

    expect(app_page.locator("#participantsMergeConflictCount")).to_have_text("1 conflict")
    expect(app_page.locator("#participantsMergeConflictList")).to_contain_text("sub-P002")
    expect(app_page.locator("#participantsMergeConflictList")).to_contain_text("already has 34, incoming file has 35")
    expect(app_page.locator("#participantsConvertBtn")).to_be_disabled()
    assert (project / "participants.tsv").read_text() == EXISTING


def test_merge_without_conflicts_adds_new_people_and_columns_but_keeps_existing_values(app_page, studio_url, tmp_path, project):
    start_merge(
        app_page, studio_url, project, tmp_path,
        "participant_id,age,handedness\nP002,34,r\nP003,50,l\n",
    )

    expect(app_page.locator("#participantsMergeConflictCount")).to_have_text("0 conflicts")
    expect(app_page.locator("#participantsMergeNewParticipantsCount")).to_have_text("1 new participant")
    app_page.click("#participantsConvertBtn")
    expect(app_page.locator("#participantsSuccess")).to_be_visible(timeout=30000)

    rows = {r["participant_id"]: r for r in read_participants(project)}
    assert set(rows) == {"sub-P001", "sub-P002", "sub-P003"}
    assert rows["sub-P001"]["age"] == "21"  # not in the incoming file: untouched
    assert rows["sub-P001"]["handedness"] in ("", "n/a")
    assert rows["sub-P002"]["handedness"] == "r"
    assert rows["sub-P003"]["age"] == "50"


LONGITUDINAL = "participant_id,session,age\nP001,pre,21\nP001,post,22\nP002,pre,34\nP002,post,35\n"


def preview_longitudinal(page, studio_url, tmp_path, content=LONGITUDINAL):
    page.on("dialog", lambda dialog: dialog.accept())
    open_participants_tab(page, studio_url)
    select_people_file(page, tmp_path, content)
    page.click("#participantsPreviewBtn")
    expect(page.locator("#participantsSessionChoiceCard")).to_be_visible(timeout=30000)


def test_repeated_participants_block_convert_until_the_longitudinal_question_is_answered(app_page, studio_url, tmp_path, project):
    preview_longitudinal(app_page, studio_url, tmp_path)

    expect(app_page.locator("#participantsConvertBtn")).to_be_disabled()
    assert not (project / "participants.tsv").exists()


def test_longitudinal_yes_imports_the_one_chosen_session_for_everybody(app_page, studio_url, tmp_path, project):
    preview_longitudinal(app_page, studio_url, tmp_path)

    app_page.click("#participantsSessionLongitudinalYes")
    app_page.select_option("#participantsSessionColumn", "session")
    app_page.select_option("#participantsSessionValue", "pre")
    expect(app_page.locator("#participantsConvertBtn")).to_be_enabled(timeout=30000)
    app_page.click("#participantsConvertBtn")
    expect(app_page.locator("#participantsSuccess")).to_be_visible(timeout=30000)

    ages = {r["participant_id"]: r["age"] for r in read_participants(project)}
    assert ages == {"sub-P001": "21", "sub-P002": "34"}  # the "pre" rows, not "post"


def test_longitudinal_no_stops_because_participants_repeat_with_different_values(app_page, studio_url, tmp_path, project):
    preview_longitudinal(app_page, studio_url, tmp_path)

    app_page.click("#participantsSessionLongitudinalNo")
    expect(app_page.locator("#participantsConvertBtn")).to_be_enabled(timeout=30000)
    app_page.click("#participantsConvertBtn")

    expect(app_page.locator("#participantsError")).to_be_visible(timeout=30000)
    assert not (project / "participants.tsv").exists()
