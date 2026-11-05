"""The DataLad page (/projects/datalad) for the loaded project, against the real datalad / git-annex."""

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
    page.wait_for_selector("#projectBoxSaveBtn")
    page.goto(f"{studio_url}/projects/datalad")
    expect(page.locator("#dataladStepTitle")).not_to_have_text("Checking this project...")


def action(page, action_id):
    return page.locator(f'#dataladStepCard [data-action="{action_id}"]')


def enable_datalad(page):
    messages = []
    page.once("dialog", lambda dialog: (messages.append(dialog.message), dialog.accept()))
    # Wait for the request itself: a status poll flips the badge to "Tracked" while the enable
    # request is still running, and its final commit would sweep up files written in that window.
    with page.expect_response("**/api/projects/datalad/enable", timeout=120000):
        action(page, "enable").click()
    # the next step after switching on is putting the project on a server; snapshots stay local until then
    expect(page.locator("#dataladStepTitle")).to_have_text("Not on a server yet", timeout=120000)
    return messages


def test_enabling_datalad_asks_first_and_cancelling_changes_nothing(bare_page, studio_url, project):
    open_datalad_card(bare_page, studio_url, project)
    expect(action(bare_page, "enable")).to_have_text("Enable DataLad")
    expect(action(bare_page, "save")).to_have_count(0)
    bare_page.once("dialog", lambda dialog: dialog.dismiss())

    action(bare_page, "enable").click()

    bare_page.wait_for_timeout(1000)
    expect(action(bare_page, "enable")).to_be_visible()
    assert not (project / ".git").exists()


def test_enabling_datalad_tracks_the_project(bare_page, studio_url, project):
    open_datalad_card(bare_page, studio_url, project)

    messages = enable_datalad(bare_page)

    assert messages and "DataLad" in messages[0]
    assert (project / ".datalad").is_dir() and (project / ".git").is_dir()
    expect(action(bare_page, "enable")).to_have_count(0)
    expect(action(bare_page, "put-on-server")).to_be_enabled()
    expect(action(bare_page, "save")).to_be_enabled()


def save_snapshot(page, message=None):
    # The test project is not PRISM-valid: the save gate refuses first (400) and asks "Save anyway?"; say yes.
    page.allowed_http[400] = "/api/projects/datalad/save"

    def answer(dialog):
        if dialog.type == "prompt":
            dialog.accept(message) if message is not None else dialog.accept()
        else:
            dialog.accept()

    page.on("dialog", answer)
    action(page, "save").click()


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

    expect(bare_page.locator("#dataladJobResult")).to_contain_text("saved")
    expect(bare_page.locator("#dataladJobResult")).to_contain_text("Save PRISM project changes")  # the backend's default
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

    expect(bare_page.locator("#dataladJobResult")).to_contain_text("No DataLad changes")
    assert int(git(project, "rev-list", "--count", "HEAD")) == commits


def test_snapshot_uses_the_message_the_user_typed(bare_page, studio_url, project):
    open_datalad_card(bare_page, studio_url, project)
    enable_datalad(bare_page)
    (project / "notes.txt").write_text("changed")

    save_snapshot(bare_page, message="After pilot week 1")

    expect(bare_page.locator("#dataladJobResult")).to_contain_text("After pilot week 1")
    # the acknowledged invalid save is recorded in the message (it travels with the commit)
    assert git(project, "log", "-1", "--format=%s") == "After pilot week 1 [saved with 1 validation error(s)]"


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


def test_creating_a_project_with_datalad_switched_on_tracks_it(bare_page, studio_url, tmp_path, fill_required_metadata):
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-create")
    bare_page.fill("#projectName", "tracked_study")
    bare_page.fill("#projectPath", str(tmp_path))
    bare_page.click('label[for="projectUseDatalad"]')
    fill_required_metadata(bare_page)
    bare_page.click("#createProjectSubmitBtnTop")

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


def test_put_on_an_unreachable_server_explains_what_is_wrong(bare_page, studio_url, project):
    if not shutil.which("ssh"):
        pytest.skip("ssh is not installed")
    open_datalad_card(bare_page, studio_url, project)
    enable_datalad(bare_page)
    action(bare_page, "put-on-server").click()
    bare_page.fill("#dataladLocation", "nobody@no-such-host.invalid:/srv/x")

    bare_page.click("#dataladLocationStartBtn")

    # The test project has a validation error: the errors are listed first, with the acknowledgement button.
    send_anyway = bare_page.locator("#dataladSendAnywayBtn")
    expect(send_anyway).to_have_text("Send anyway, I understand this dataset has 1 errors", timeout=120000)
    send_anyway.click()

    result = bare_page.locator("#dataladJobResult .alert-danger")
    expect(result).to_be_visible(timeout=120000)
    expect(result).not_to_be_empty()
    expect(action(bare_page, "put-on-server")).to_be_enabled()  # the step is still offered, nothing is locked


def test_without_a_project_the_page_leads_with_open_from_server(bare_page, studio_url):
    bare_page.goto(f"{studio_url}/projects/datalad")

    expect(bare_page.locator("#dataladStepTitle")).to_have_text("No project open")
    expect(action(bare_page, "open-from-server")).to_have_text("Open from server...")
    action(bare_page, "open-from-server").click()
    expect(bare_page.locator("#dataladTarget")).to_be_visible()  # asks where to put the copy
    for more in ("get-latest", "get-data", "doctor"):
        expect(bare_page.locator(f'#dataladMore [data-action="{more}"]')).to_be_visible()
    expect(bare_page.locator("#navbarDataladToggle")).to_be_visible()  # the navbar item shows without a project
