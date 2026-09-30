"""Projects page > DataLad Version Control card, against the real datalad / git-annex."""

import shutil
import subprocess

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.skipif(
    not (shutil.which("datalad") and shutil.which("git-annex")),
    reason="datalad and git-annex are not installed",
)


def git(project, *args):
    return subprocess.run(
        ["git", "-C", str(project), *args], capture_output=True, text=True, check=True
    ).stdout.strip()


def open_datalad_card(page, studio_url, project):
    page.goto(f"{studio_url}/projects")
    page.click("#card-open")
    page.fill("#existingPath", str(project))
    page.click("#loadProjectBtn")
    page.wait_for_selector("#dataladSectionCard", state="visible")
    page.locator('[data-bs-target="#dataladSection"]').click()
    expect(page.locator("#projectBoxDataladStateBadge")).to_be_visible()


def enable_datalad(page):
    messages = []
    page.once("dialog", lambda dialog: (messages.append(dialog.message), dialog.accept()))
    page.click("#projectBoxDataladEnableBtn")
    expect(page.locator("#projectBoxDataladStateBadge")).to_have_text("Tracked", timeout=120000)
    return messages


def test_enabling_datalad_asks_first_and_cancelling_changes_nothing(bare_page, studio_url, project):
    open_datalad_card(bare_page, studio_url, project)
    expect(bare_page.locator("#projectBoxDataladStateBadge")).to_have_text("Not tracked")
    expect(bare_page.locator("#projectBoxDataladSaveBtn")).to_be_disabled()
    bare_page.once("dialog", lambda dialog: dialog.dismiss())

    bare_page.click("#projectBoxDataladEnableBtn")

    bare_page.wait_for_timeout(1000)
    expect(bare_page.locator("#projectBoxDataladStateBadge")).to_have_text("Not tracked")
    assert not (project / ".git").exists()


def test_enabling_datalad_tracks_the_project(bare_page, studio_url, project):
    open_datalad_card(bare_page, studio_url, project)

    messages = enable_datalad(bare_page)

    assert messages and "DataLad" in messages[0]
    assert (project / ".datalad").is_dir() and (project / ".git").is_dir()
    expect(bare_page.locator("#projectBoxDataladEnableBtn")).to_be_disabled()
    expect(bare_page.locator("#projectBoxDataladSaveBtn")).to_be_enabled()


def save_snapshot(page, message=None):
    def answer(dialog):
        dialog.accept(message) if message is not None else dialog.accept()

    page.once("dialog", answer)
    page.click("#projectBoxDataladSaveBtn")


TEXT_FILES = {
    "sourcedata/answers.csv": b"a,b\n1,2\n",
    "sourcedata/table.tsv": b"participant_id\tage\nsub-01\t20\n",
    "sourcedata/notes.txt": b"free text",
    "sourcedata/meta.json": b"{}",
    "sourcedata/sheet.xlsx": b"PK\x03\x04 not a real workbook",
    "sourcedata/codebook.ods": b"PK\x03\x04 not a real sheet",
    "derivatives/helpers.R": b"x <- 1\n",
    "code/config.yaml": b"a: 1\n",
    "code/README.md": b"# hi\n",
}
BINARY_FILES = {
    "sourcedata/report.pdf": b"%PDF-1.4 " + bytes(2048),
    "sourcedata/responses.sav": b"$FL2 " + bytes(2048),
}


def is_annexed(path):
    return path.is_symlink() and ".git/annex/objects" in str(path.readlink())


def test_snapshot_commits_new_files_and_never_annexes_text_formats(bare_page, studio_url, project):
    open_datalad_card(bare_page, studio_url, project)
    enable_datalad(bare_page)
    for relative, content in {**TEXT_FILES, **BINARY_FILES}.items():
        target = project / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    commits_before = int(git(project, "rev-list", "--count", "HEAD"))

    save_snapshot(bare_page)

    expect(bare_page.locator("#projectBoxDataladFeedback")).to_contain_text("saved")
    expect(bare_page.locator("#projectBoxDataladFeedback")).to_contain_text("Checkpoint")  # the message used
    assert int(git(project, "rev-list", "--count", "HEAD")) > commits_before
    assert git(project, "status", "--porcelain") == ""  # everything was saved
    for relative in TEXT_FILES:
        assert not is_annexed(project / relative), f"text file was annexed: {relative}"
        assert (project / relative).read_bytes() == TEXT_FILES[relative]
    for relative in BINARY_FILES:
        assert is_annexed(project / relative), f"binary file was not annexed: {relative}"


def test_snapshot_with_nothing_new_says_so_instead_of_pretending(bare_page, studio_url, project):
    open_datalad_card(bare_page, studio_url, project)
    enable_datalad(bare_page)
    commits = int(git(project, "rev-list", "--count", "HEAD"))

    save_snapshot(bare_page)

    expect(bare_page.locator("#projectBoxDataladFeedback")).to_contain_text("No DataLad changes")
    assert int(git(project, "rev-list", "--count", "HEAD")) == commits


def test_snapshot_uses_the_message_the_user_typed(bare_page, studio_url, project):
    open_datalad_card(bare_page, studio_url, project)
    enable_datalad(bare_page)
    (project / "notes.txt").write_text("changed")

    save_snapshot(bare_page, message="After pilot week 1")

    expect(bare_page.locator("#projectBoxDataladFeedback")).to_contain_text("After pilot week 1")
    assert git(project, "log", "-1", "--format=%s") == "After pilot week 1"


def pending_changes(project):
    """Unsaved changes, except the live session log (tracked on purpose; the app appends to it)."""
    lines = git(project, "status", "--porcelain", "-uall").splitlines()
    return [line for line in lines if not line[3:].startswith("code/logs/")]


def assert_tracked_and_text_is_not_annexed(project, *text_files):
    """Committed from the start, nothing else pending, and text formats never annexed."""
    assert (project / ".datalad").is_dir() and (project / ".git").is_dir()
    assert pending_changes(project) == []
    committed = git(project, "ls-files").splitlines()
    for name in text_files:
        assert name in committed, f"{name} was not committed"
        assert (project / name).is_file() and not is_annexed(project / name), name


def test_creating_a_project_with_datalad_switched_on_tracks_it(bare_page, studio_url, tmp_path):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "tracked_study")
    bare_page.fill("#projectPath", str(tmp_path))
    bare_page.click('label[for="projectUseDatalad"]')
    bare_page.click("#createProjectSubmitBtnTop")
    bare_page.get_by_role("button", name="Create anyway (incomplete)").click()

    expect(bare_page.locator("#createResult")).to_contain_text("tracked_study", timeout=180000)

    assert_tracked_and_text_is_not_annexed(tmp_path / "tracked_study", "project.json")


def test_init_on_a_bids_dataset_with_datalad_switched_on_tracks_it(bare_page, studio_url, tmp_path):
    root = tmp_path / "my-bids"
    (root / "sub-01").mkdir(parents=True)
    (root / "dataset_description.json").write_text('{"Name": "x", "BIDSVersion": "1.10.0"}')
    (root / "participants.tsv").write_text("participant_id\nsub-01\n")
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-init-bids")
    bare_page.fill("#initBidsPath", str(root))
    bare_page.click('label[for="initBidsUseDatalad"]')

    bare_page.click("#initBidsSubmitBtn")

    expect(bare_page.locator("#initBidsResult")).to_contain_text("project.json", timeout=180000)
    assert_tracked_and_text_is_not_annexed(root, "project.json", "participants.tsv", "dataset_description.json")
