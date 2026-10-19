"""Converter > Sociodemographics: build and merge participants.tsv the way a user does."""

import csv
import re

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


def confirm_annotation(page):
    """Annotation is a required stage: Create/Replace unlocks only after this."""
    expect(page.locator("#participantsConvertBtn")).to_be_disabled()
    page.click("#participantsAnnotationConfirmBtn", timeout=30000)
    expect(page.locator("#participantsConvertBtn")).to_be_enabled(timeout=30000)


def preview_and_convert(page):
    page.click("#participantsPreviewBtn")
    confirm_annotation(page)
    page.click("#participantsConvertBtn")
    expect(page.locator("#participantsSuccess")).to_be_visible(timeout=30000)


def test_new_participants_file_is_previewed_then_written(app_page, studio_url, tmp_path, project):
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path)

    app_page.click("#participantsPreviewBtn")
    expect(app_page.locator("#participantsPreviewTable")).to_contain_text("P001", timeout=30000)
    assert not (project / "participants.tsv").exists(), "preview must not write the file"

    confirm_annotation(app_page)
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
    confirm_annotation(app_page)
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

    app_page.click("#participantsSessionModeOne")
    app_page.select_option("#participantsSessionColumn", "session")
    app_page.select_option("#participantsSessionValue", "pre")
    confirm_annotation(app_page)
    app_page.click("#participantsConvertBtn")
    expect(app_page.locator("#participantsSuccess")).to_be_visible(timeout=30000)

    ages = {r["participant_id"]: r["age"] for r in read_participants(project)}
    assert ages == {"sub-P001": "21", "sub-P002": "34"}  # the "pre" rows, not "post"


def test_longitudinal_split_keeps_every_sessions_value_in_its_own_column(app_page, studio_url, tmp_path, project):
    preview_longitudinal(app_page, studio_url, tmp_path)

    app_page.click("#participantsSessionModeSplit")
    confirm_annotation(app_page)
    app_page.click("#participantsConvertBtn")
    expect(app_page.locator("#participantsSuccess")).to_be_visible(timeout=30000)

    rows = {r["participant_id"]: r for r in read_participants(project)}
    assert rows["sub-P001"]["age@ses-pre"] == "21" and rows["sub-P001"]["age@ses-post"] == "22"
    assert rows["sub-P002"]["age@ses-post"] == "35"


def test_identical_repeated_rows_collapse_without_asking_anything(app_page, studio_url, tmp_path, project):
    same = "participant_id,session,age\nP001,pre,21\nP001,post,21\nP002,pre,34\nP002,post,34\n"
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path, same)
    app_page.click("#participantsPreviewBtn")

    confirm_annotation(app_page)
    expect(app_page.locator("#participantsSessionChoiceCard")).to_be_hidden()
    app_page.click("#participantsConvertBtn")
    expect(app_page.locator("#participantsSuccess")).to_be_visible(timeout=30000)
    assert [r["age"] for r in read_participants(project)] == ["21", "34"]


LIMESURVEY_REPEATS = (
    "participant_id,startdate,submitdate,age\n"
    "P001,2026-01-05 10:00:00,2026-01-05 10:10:00,21\n"
    "P001,2026-03-05 10:00:00,2026-03-05 10:10:00,22\n"
    "P002,2026-01-06 10:00:00,2026-01-06 10:10:00,34\n"
    "P002,2026-03-06 10:00:00,2026-03-06 10:10:00,35\n"
)


def test_repeats_without_a_session_column_can_be_numbered_by_date(app_page, studio_url, tmp_path, project):
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path, LIMESURVEY_REPEATS)
    app_page.click("#participantsPreviewBtn")

    expect(app_page.locator("#participantsSessionByDateBtn")).to_be_visible(timeout=30000)
    app_page.click("#participantsSessionByDateBtn")
    expect(app_page.locator("#participantsSessionModeOne")).to_be_visible(timeout=30000)
    app_page.click("#participantsSessionModeOne")
    app_page.select_option("#participantsSessionValue", "2")
    confirm_annotation(app_page)
    app_page.click("#participantsConvertBtn")
    expect(app_page.locator("#participantsSuccess")).to_be_visible(timeout=30000)

    assert {r["participant_id"]: r["age"] for r in read_participants(project)} == {"sub-P001": "22", "sub-P002": "35"}


def test_a_new_preview_revokes_the_annotation_confirmation(app_page, studio_url, tmp_path, project):
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path)
    app_page.click("#participantsPreviewBtn")
    confirm_annotation(app_page)

    app_page.click("#participantsPreviewBtn")
    expect(app_page.locator("#participantsConvertBtn")).to_be_disabled()
    expect(app_page.locator("#convertBtnHint")).to_contain_text("Confirm the annotation", timeout=30000)


def test_a_failed_preview_scrolls_its_message_into_view(app_page, studio_url, tmp_path, project):
    app_page.set_viewport_size({"width": 1280, "height": 450})  # the message lives below the fold
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path, "name,age\n" + "".join(f"x{i},{i}\n" for i in range(60)))
    app_page.click("#participantsPreviewBtn")

    message = app_page.locator("#participantsError, #participantsInfo").locator("visible=true").first
    expect(message).to_be_visible(timeout=30000)
    expect(message).to_be_in_viewport()


def test_a_semicolon_file_is_detected_without_touching_the_separator(app_page, studio_url, tmp_path, project):
    """German Excel exports use ';' - the ID column must be found with "Auto-detect"."""
    open_participants_tab(app_page, studio_url)
    content = "participant_id;age;iq\n" + "".join(f"P{i};{20 + i};10{i % 10},5\n" for i in range(1, 12))
    select_people_file(app_page, tmp_path, content)
    app_page.click("#participantsPreviewBtn")
    expect(app_page.locator("#participantsPreviewTable")).to_contain_text("sub-P1", timeout=30000)


def test_an_empty_file_says_so_next_to_the_id_column(app_page, studio_url, tmp_path):
    app_page.allowed_http[400] = "/api/participants-detect-id"  # the answer is the message shown below
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path, "")
    expect(app_page.locator("#participantsIdColumnHint")).to_contain_text("empty", timeout=30000)


PROBLEMS = "participant_id,age,iq\nP1,21,100\nP-2,22,99\nP 2,23,98\n,24,97\nP5,twenty,96\nP6,200,95\nP7,30,94\n"


def test_problems_in_the_table_are_listed_and_errors_block_convert(app_page, studio_url, tmp_path):
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path, PROBLEMS)
    app_page.click("#participantsPreviewBtn")
    info = app_page.locator("#participantsInfo")
    expect(info).to_contain_text("no participant ID", timeout=30000)
    expect(info).to_contain_text("sub-P2")
    expect(info).to_contain_text("not numbers")
    expect(info).to_contain_text("outside 0-120")
    expect(info).to_have_class(re.compile("alert-danger"))
    app_page.click("#participantsAnnotationConfirmBtn", timeout=30000)
    expect(app_page.locator("#participantsConvertBtn")).to_be_disabled()


def test_the_preview_names_the_columns_that_are_not_imported_yet(app_page, studio_url, tmp_path):
    open_participants_tab(app_page, studio_url)
    select_people_file(app_page, tmp_path, "participant_id,age,sex,iq,vo2max\nP1,21,f,100,40\nP2,30,m,99,38\n")
    app_page.click("#participantsPreviewBtn")
    text = app_page.locator("#participantsPreviewAvailabilityText")
    expect(text).to_contain_text("NOT imported yet", timeout=30000)
    expect(text).to_contain_text("iq")
    expect(text).to_contain_text("vo2max")
