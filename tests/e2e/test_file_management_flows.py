"""File management page: tools that rename or delete files in the current project."""

import json
import re
import time

import pytest
from playwright.sync_api import expect


def build_two_subjects(project, ids=("1291003", "1291004")):
    (project / "participants.tsv").write_text(
        "participant_id\tage\n" + "".join(f"sub-{sid}\t{20 + i}\n" for i, sid in enumerate(ids))
    )
    for i, sid in enumerate(ids):
        folder = project / f"sub-{sid}" / "ses-1" / "survey"
        folder.mkdir(parents=True)
        (folder / f"sub-{sid}_ses-1_task-wb_survey.tsv").write_text(f"WB01\n{i}\n")
        (folder / f"sub-{sid}_ses-1_task-wb_survey.json").write_text(json.dumps({"Study": {"TaskName": "wb"}}))


def project_files(project):
    """Every project file (relative paths), ignoring git internals, session logs and the undo log."""
    return sorted(
        p.relative_to(project).as_posix()
        for p in project.rglob("*")
        if p.is_file() and ".git" not in p.parts and "logs" not in p.parts and ".prism" not in p.parts
    )


def eventually(condition, timeout=30.0):
    """Poll the disk: the page disables its button at click time, long before the work is done."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.2)
    return False


def snapshot(project):
    return {name: (project / name).read_bytes() for name in project_files(project)}


def open_ids_tab(page, studio_url):
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(f"{studio_url}/file-management")
    page.click("#fm-rename-ids-tab")
    expect(page.locator("#repoSubjectRewriteExample option").first).to_be_attached()


def preview_subject_rewrite(page, example="sub-1291003", keep="003"):
    page.select_option("#repoSubjectRewriteExample", example)
    page.fill("#repoSubjectRewriteKeep", keep)
    page.click("#repoSubjectRewritePreviewBtn")


def test_subject_rewrite_needs_a_preview_then_renames_folders_files_and_participants(app_page, studio_url, project):
    build_two_subjects(project)
    open_ids_tab(app_page, studio_url)
    expect(app_page.locator("#repoSubjectRewriteBtn")).to_be_disabled()  # nothing previewed yet

    preview_subject_rewrite(app_page)
    expect(app_page.locator("#repoSubjectRewriteBtn")).to_be_enabled(timeout=30000)
    assert (project / "sub-1291003").exists()  # a preview never touches the project

    app_page.click("#repoSubjectRewriteBtn")

    expect(app_page.locator("#fmUndoBarBtn")).to_be_visible(timeout=30000)
    assert project_files(project) == [
        "dataset_description.json",
        "participants.tsv",
        "project.json",
        "sub-003/ses-1/survey/sub-003_ses-1_task-wb_survey.json",
        "sub-003/ses-1/survey/sub-003_ses-1_task-wb_survey.tsv",
        "sub-004/ses-1/survey/sub-004_ses-1_task-wb_survey.json",
        "sub-004/ses-1/survey/sub-004_ses-1_task-wb_survey.tsv",
    ]
    assert (project / "participants.tsv").read_text() == "participant_id\tage\nsub-003\t20\nsub-004\t21\n"
    assert (project / "sub-004/ses-1/survey/sub-004_ses-1_task-wb_survey.tsv").read_text() == "WB01\n1\n"  # data intact


def test_undo_restores_the_project_exactly(app_page, studio_url, project):
    build_two_subjects(project)
    before = snapshot(project)
    open_ids_tab(app_page, studio_url)
    preview_subject_rewrite(app_page)
    expect(app_page.locator("#repoSubjectRewriteBtn")).to_be_enabled(timeout=30000)
    app_page.click("#repoSubjectRewriteBtn")
    expect(app_page.locator("#fmUndoBarBtn")).to_be_visible(timeout=30000)
    assert snapshot(project) != before

    app_page.click("#fmUndoBarBtn")

    expect(app_page.locator("#fmUndoBarBtn")).to_be_hidden(timeout=30000)
    assert snapshot(project) == before


def test_changing_the_rule_after_a_preview_locks_apply_again(app_page, studio_url, project):
    """Apply must never run a mapping the user did not preview."""
    build_two_subjects(project)
    open_ids_tab(app_page, studio_url)
    preview_subject_rewrite(app_page, keep="003")
    expect(app_page.locator("#repoSubjectRewriteBtn")).to_be_enabled(timeout=30000)

    app_page.fill("#repoSubjectRewriteKeep", "03")  # a different rule than the one previewed

    expect(app_page.locator("#repoSubjectRewriteBtn")).to_be_disabled()


def test_a_rewrite_that_would_merge_two_subjects_is_blocked(app_page, studio_url, project):
    build_two_subjects(project, ids=("1291003", "2291003"))  # both end in 003
    before = snapshot(project)
    open_ids_tab(app_page, studio_url)

    preview_subject_rewrite(app_page, example="sub-1291003", keep="003")

    expect(app_page.locator("#repoSubjectRewriteBtn")).to_be_disabled(timeout=30000)
    expect(app_page.locator("#fm-rename-ids-panel")).to_contain_text("sub-003")
    assert snapshot(project) == before


def add_second_task(project, ids=("1291003", "1291004")):
    for sid in ids:
        folder = project / f"sub-{sid}" / "ses-1" / "survey"
        (folder / f"sub-{sid}_ses-1_task-other_survey.tsv").write_text("X\n1\n")


def open_delete_tab(page, studio_url, answer="accept"):
    page.on("dialog", lambda dialog: dialog.accept() if answer == "accept" else dialog.dismiss())
    page.goto(f"{studio_url}/file-management")
    page.click("#fm-delete-tab")
    expect(page.locator("#fileDeleteSubj_sub-1291003")).to_be_attached(timeout=30000)


def tick_subject(page, subject):
    page.locator(f"#fileDeleteSubj_{subject}").check()


def test_delete_removes_only_the_selected_subjects_files_and_their_empty_folders(app_page, studio_url, project):
    build_two_subjects(project)
    open_delete_tab(app_page, studio_url)
    tick_subject(app_page, "sub-1291003")
    app_page.click("#fileDeletePreviewBtn")
    expect(app_page.locator("#fileDeleteApplyBtn")).to_be_enabled(timeout=30000)
    expect(app_page.locator("#fm-delete-panel")).to_contain_text("sub-1291003_ses-1_task-wb_survey.tsv")
    assert (project / "sub-1291003").exists()  # preview deletes nothing

    app_page.click("#fileDeleteApplyBtn")

    assert eventually(lambda: not (project / "sub-1291003").exists()), project_files(project)  # files and emptied folders
    assert (project / "sub-1291004/ses-1/survey/sub-1291004_ses-1_task-wb_survey.tsv").read_text() == "WB01\n1\n"
    assert "sub-1291003" in (project / "participants.tsv").read_text()  # documented: not updated


def test_an_entity_filter_deletes_only_the_matching_task(app_page, studio_url, project):
    build_two_subjects(project)
    add_second_task(project)
    open_delete_tab(app_page, studio_url)
    app_page.click("#fileDeleteAddFilterBtn")
    app_page.select_option(".file-delete-key-select", "task")
    app_page.select_option(".file-delete-value-select", "other")
    app_page.click("#fileDeletePreviewBtn")
    expect(app_page.locator("#fileDeleteApplyBtn")).to_be_enabled(timeout=30000)

    app_page.click("#fileDeleteApplyBtn")

    assert eventually(lambda: not [n for n in project_files(project) if "task-other" in n])
    names = project_files(project)
    assert len([n for n in names if "task-wb" in n]) == 4  # both subjects' wb .tsv and .json untouched


def test_cancelling_the_confirmation_deletes_nothing(app_page, studio_url, project):
    build_two_subjects(project)
    before = snapshot(project)
    open_delete_tab(app_page, studio_url, answer="dismiss")
    tick_subject(app_page, "sub-1291003")
    app_page.click("#fileDeletePreviewBtn")
    expect(app_page.locator("#fileDeleteApplyBtn")).to_be_enabled(timeout=30000)

    app_page.click("#fileDeleteApplyBtn")

    app_page.wait_for_timeout(1000)
    assert snapshot(project) == before


def test_changing_the_criteria_after_a_preview_locks_apply_again(app_page, studio_url, project):
    """The confirmation asks about 'the previewed files': they must be the ones that get deleted."""
    build_two_subjects(project)
    open_delete_tab(app_page, studio_url)
    tick_subject(app_page, "sub-1291003")
    app_page.click("#fileDeletePreviewBtn")
    expect(app_page.locator("#fileDeleteApplyBtn")).to_be_enabled(timeout=30000)

    tick_subject(app_page, "sub-1291004")  # the selection now differs from the preview

    expect(app_page.locator("#fileDeleteApplyBtn")).to_be_disabled()


def incoming_edf_files(tmp_path, names=("004-t2.edf", "005-t2.edf")):
    folder = tmp_path / "incoming"
    folder.mkdir()
    for name in names:
        (folder / name).write_bytes(b"EDF " + name.encode())
    return folder


def open_renamer(page, studio_url):
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(f"{studio_url}/file-management")


def define_renamer_rule(page, folder, session="t2"):
    """Fill the rule for the example file the PAGE picked (folder order varies), like a user would."""
    page.set_input_files("#renamerFiles", str(folder))
    expect(page.locator("#renamerOriginalExample")).to_contain_text(".edf")
    example = page.locator("#renamerOriginalExample").inner_text()
    subject = re.search(r"(\d{3})-", example).group(1)
    page.fill("#renamerTask", "rest")
    page.select_option("#renamerModality", "physio")
    page.fill("#renamerSubjectValue", subject)
    page.fill("#renamerSessionValue", session)
    # the output template is generated a moment after the last field changes
    expect(page.locator("#renamerNewExample")).to_have_value("sub-{subject}_ses-{session}_task-rest_physio.edf")


def test_renamer_preview_changes_nothing_and_copy_writes_the_renamed_files(app_page, studio_url, project, tmp_path):
    folder = incoming_edf_files(tmp_path)
    open_renamer(app_page, studio_url)
    define_renamer_rule(app_page, folder)

    app_page.click("#renamerDryRunBtn")

    expect(app_page.locator("#fm-renamer-panel")).to_contain_text("sub-004_ses-t2_task-rest_physio.edf")
    assert not [f for f in project_files(project) if f.startswith("sub-")]  # a preview writes nothing

    app_page.click("#renamerCopyBtn")

    target = project / "sub-004/ses-t2/physio/sub-004_ses-t2_task-rest_physio.edf"
    assert eventually(target.exists), project_files(project)
    assert target.read_bytes() == b"EDF 004-t2.edf"  # content is unchanged
    assert (project / "sub-005/ses-t2/physio/sub-005_ses-t2_task-rest_physio.edf").exists()
    assert sorted(p.name for p in folder.iterdir()) == ["004-t2.edf", "005-t2.edf"]  # originals stay


def test_renamer_keeps_a_numeric_session_exactly_as_typed(app_page, studio_url, project, tmp_path):
    """Session labels are free-form strings: '2' must never become 'ses-02'."""
    folder = incoming_edf_files(tmp_path)
    open_renamer(app_page, studio_url)
    define_renamer_rule(app_page, folder, session="2")

    app_page.click("#renamerCopyBtn")

    assert eventually(lambda: (project / "sub-004/ses-2/physio/sub-004_ses-2_task-rest_physio.edf").exists()), project_files(project)
    assert not (project / "sub-004/ses-02").exists()


def test_renamer_download_offers_a_zip_of_the_renamed_files(app_page, studio_url, tmp_path):
    folder = incoming_edf_files(tmp_path)
    open_renamer(app_page, studio_url)
    define_renamer_rule(app_page, folder)

    with app_page.expect_download() as download:
        app_page.click("#renamerDownloadBtn")

    assert download.value.suggested_filename.endswith(".zip")


def flat_survey_folder(tmp_path):
    folder = tmp_path / "flat"
    folder.mkdir()
    (folder / "sub-01_ses-1_task-wb_survey.tsv").write_text("WB01\n1\n")
    (folder / "sub-01_ses-1_task-wb_survey.json").write_text('{"Study": {"TaskName": "wb"}}')
    (folder / "sub-02_ses-t2_task-wb_survey.tsv").write_text("WB01\n2\n")
    return folder


def open_organizer_with_folder(page, studio_url, folder):
    page.on("dialog", lambda dialog: dialog.accept())
    page.goto(f"{studio_url}/file-management")
    page.click("#fm-organizer-tab")
    page.set_input_files("#organizeFolder", str(folder))  # a folder pick: browsers send relative paths
    page.select_option("#organizeModality", "survey")


def test_organizer_folder_upload_previews_then_copies_into_the_prism_layout(app_page, studio_url, project, tmp_path):
    folder = flat_survey_folder(tmp_path)
    open_organizer_with_folder(app_page, studio_url, folder)

    app_page.click("#organizeDryRunBtn")

    expect(app_page.locator("#organizeLog")).to_contain_text("Would create: sub-01_ses-1_task-wb_survey.tsv", timeout=30000)
    assert not [f for f in project_files(project) if f.startswith("sub-")]  # a dry run writes nothing
    assert not (project / "participants.tsv").exists()

    app_page.click("#organizeCopyBtn")

    first = project / "sub-01/ses-1/survey/sub-01_ses-1_task-wb_survey.tsv"
    assert eventually(first.exists), project_files(project)
    assert first.read_text() == "WB01\n1\n"  # content unchanged
    assert (project / "sub-01/ses-1/survey/sub-01_ses-1_task-wb_survey.json").exists()
    assert (project / "sub-02/ses-t2/survey/sub-02_ses-t2_task-wb_survey.tsv").read_text() == "WB01\n2\n"  # ses-t2 as is
    assert eventually(lambda: (project / "participants.tsv").exists())
    listed = (project / "participants.tsv").read_text().splitlines()[1:]
    assert sorted(line.split("\t")[0] for line in listed) == ["sub-01", "sub-02"]  # new subjects are registered


WIDE = "participant_id,T1_ADS01,T1_ADS02,T2_ADS01,T2_ADS02\nP1,1,2,3,4\nP2,5,6,7,8\n"


def open_wide_to_long(page, studio_url, tmp_path, content=WIDE):
    page.on("dialog", lambda dialog: dialog.accept())
    wide = tmp_path / "wide.csv"
    wide.write_text(content)
    page.goto(f"{studio_url}/file-management")
    page.click("#fm-wide-to-long-tab")
    page.set_input_files("#wideLongFile", str(wide))
    expect(page.locator("#wideLongIdColumn option[value=participant_id]")).to_be_attached(timeout=30000)


def test_wide_to_long_previews_then_saves_the_long_table_into_sourcedata(app_page, studio_url, project, tmp_path):
    open_wide_to_long(app_page, studio_url, tmp_path)

    app_page.click("#wideLongDataPreviewBtn")

    expect(app_page.locator("#wideLongTableBody")).to_contain_text("T2", timeout=30000)
    assert not (project / "sourcedata").exists()  # the preview writes nothing

    app_page.click("#wideLongConvertBtn")

    out = project / "sourcedata/wide_to_long/wide_long.csv"
    assert eventually(out.exists), [p for p in project.rglob("*") if "wide" in p.name]
    assert out.read_text().splitlines() == [
        "participant_id,ADS01,ADS02,session",
        "P1,1,2,T1",
        "P2,5,6,T1",
        "P1,3,4,T2",
        "P2,7,8,T2",
    ]


def test_wide_to_long_keeps_typed_session_labels_exactly(app_page, studio_url, project, tmp_path):
    """'1' and '01' are different labels: the page must write what was typed."""
    open_wide_to_long(app_page, studio_url, tmp_path)
    app_page.fill("#wideLongIndicators", "T1_:1,T2_:01")

    app_page.click("#wideLongConvertBtn")

    out = project / "sourcedata/wide_to_long/wide_long.csv"
    assert eventually(out.exists)
    sessions = [line.split(",")[-1] for line in out.read_text().splitlines()[1:]]
    assert sessions == ["1", "1", "01", "01"]


def test_wide_to_long_refuses_duplicate_ids_and_writes_nothing(app_page, studio_url, project, tmp_path):
    app_page.allowed_http[400] = "/api/"  # the refusal is the point of this test
    open_wide_to_long(
        app_page, studio_url, tmp_path,
        content="participant_id,T1_ADS01,T2_ADS01\nP1,1,2\nP1,3,4\nP2,5,6\n",
    )
    app_page.select_option("#wideLongIdColumn", "participant_id")

    app_page.click("#wideLongConvertBtn")

    expect(app_page.locator("#fm-wide-to-long-panel")).to_contain_text("non-unique values", timeout=30000)
    expect(app_page.locator("#fm-wide-to-long-panel")).to_contain_text("P1")
    assert not (project / "sourcedata").exists()


def build_runs_project(project):
    build_two_subjects(project, ids=("01",))
    folder = project / "sub-01" / "ses-1" / "survey"
    for run in ("01", "03"):
        (folder / f"sub-01_ses-1_task-wb_run-{run}_survey.tsv").write_text(f"WB01\n{run}\n")


def apply_after_preview(page, preview_btn, apply_btn):
    page.click(preview_btn)
    expect(page.locator(apply_btn)).to_be_enabled(timeout=30000)
    page.click(apply_btn)


def test_session_rewrite_adds_exactly_the_text_asked_for(app_page, studio_url, project):
    build_runs_project(project)
    open_ids_tab(app_page, studio_url)
    app_page.select_option("#repoSessionRewriteExample", "ses-1")
    app_page.fill("#repoSessionRewriteAddText", "T")

    apply_after_preview(app_page, "#repoSessionRewritePreviewBtn", "#repoSessionRewriteBtn")

    assert eventually(lambda: (project / "sub-01/ses-T1").exists()), project_files(project)
    assert not (project / "sub-01/ses-1").exists()
    survey = sorted(p.name for p in (project / "sub-01/ses-T1/survey").iterdir())
    assert all(name.startswith("sub-01_ses-T1_") for name in survey), survey


def test_run_renumbering_closes_the_gap_and_only_the_gap(app_page, studio_url, project):
    build_runs_project(project)
    open_ids_tab(app_page, studio_url)

    apply_after_preview(app_page, "#runRenumberPreviewBtn", "#runRenumberApplyBtn")

    survey = project / "sub-01/ses-1/survey"
    assert eventually(lambda: (survey / "sub-01_ses-1_task-wb_run-02_survey.tsv").exists()), project_files(project)
    assert not (survey / "sub-01_ses-1_task-wb_run-03_survey.tsv").exists()
    assert (survey / "sub-01_ses-1_task-wb_run-02_survey.tsv").read_text() == "WB01\n03\n"  # run 03's data
    assert (survey / "sub-01_ses-1_task-wb_run-01_survey.tsv").read_text() == "WB01\n01\n"


def test_filename_part_rename_changes_the_task_in_every_matching_file(app_page, studio_url, project):
    build_runs_project(project)
    open_ids_tab(app_page, studio_url)
    app_page.select_option("#repoEntityRewriteModality", "survey")
    app_page.select_option("#repoEntityRewritePart", "_task")
    app_page.fill("#repoEntityRewriteValue", "wellbeing")

    apply_after_preview(app_page, "#repoEntityRewritePreviewBtn", "#repoEntityRewriteBtn")

    survey = project / "sub-01/ses-1/survey"
    assert eventually(lambda: any("task-wellbeing" in n for n in project_files(project))), project_files(project)
    names = sorted(p.name for p in survey.iterdir())
    assert not [n for n in names if "task-wb_" in n or "task-wb." in n], names


def test_delete_scans_tsv_removes_only_scans_files(app_page, studio_url, project):
    build_two_subjects(project)
    for sid in ("1291003", "1291004"):
        (project / f"sub-{sid}/ses-1/sub-{sid}_ses-1_scans.tsv").write_text("filename\tacq_time\n")
    open_delete_tab(app_page, studio_url)

    app_page.click("#fileDeleteScansTsvBtn")

    assert eventually(lambda: not [f for f in project_files(project) if f.endswith("_scans.tsv")]), project_files(project)
    assert len([f for f in project_files(project) if f.endswith("_survey.tsv")]) == 2  # data files untouched
