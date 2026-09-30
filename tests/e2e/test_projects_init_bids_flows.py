"""Projects page > Init PRISM on an existing BIDS dataset."""

import json

import pytest
from playwright.sync_api import expect

SCAN = b"not really a nifti, but it must stay byte for byte"


@pytest.fixture
def bids(tmp_path):
    root = tmp_path / "my-bids"
    (root / "sub-01" / "anat").mkdir(parents=True)
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "My BIDS", "BIDSVersion": "1.10.0"})
    )
    (root / "sub-01" / "anat" / "sub-01_T1w.nii.gz").write_bytes(SCAN)
    (root / "participants.tsv").write_text("participant_id\nsub-01\n")
    return root


def open_init_form(page, studio_url, path, name=None):
    page.goto(f"{studio_url}/projects")
    page.click("#card-init-bids")
    page.fill("#initBidsPath", str(path))
    if name:
        page.fill("#initBidsName", name)


def test_init_adds_prism_files_and_leaves_the_data_alone(bare_page, studio_url, bids):
    before = (bids / "participants.tsv").read_text()
    open_init_form(bare_page, studio_url, bids)

    bare_page.click("#initBidsSubmitBtn")

    expect(bare_page.locator("#initBidsResult")).to_contain_text("project.json", timeout=60000)
    for added in (".bidsignore", ".prismrc.json", "project.json"):
        assert (bids / added).is_file(), added
    for folder in ("sourcedata", "derivatives", "code"):
        assert (bids / folder).is_dir(), folder
    assert (bids / "sub-01" / "anat" / "sub-01_T1w.nii.gz").read_bytes() == SCAN
    assert (bids / "participants.tsv").read_text() == before
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert current["path"] == str(bids)


def test_init_stores_the_display_name_in_project_json(bare_page, studio_url, bids):
    open_init_form(bare_page, studio_url, bids, name="Sleep and memory")

    bare_page.click("#initBidsSubmitBtn")

    expect(bare_page.locator("#initBidsResult")).to_contain_text("project.json", timeout=60000)
    project = json.loads((bids / "project.json").read_text())
    assert "Sleep and memory" in json.dumps(project)


def test_init_refuses_a_folder_that_is_not_a_bids_root_and_adds_nothing(bare_page, studio_url, tmp_path):
    bare_page.allowed_http[400] = "/api/projects/init-on-bids"  # the refusal is the point
    plain = tmp_path / "not-bids"
    plain.mkdir()
    (plain / "notes.txt").write_text("hello")
    open_init_form(bare_page, studio_url, plain)

    bare_page.click("#initBidsSubmitBtn")

    expect(bare_page.locator("#initBidsResult")).to_contain_text("dataset_description", timeout=60000)
    assert sorted(p.name for p in plain.iterdir()) == ["notes.txt"]
    current = bare_page.request.get(f"{studio_url}/api/projects/current").json()
    assert not current["path"]


def test_init_twice_keeps_the_existing_project_metadata(bare_page, studio_url, bids):
    (bids / "project.json").write_text(
        json.dumps({"Basics": {"Name": "Hand written"}, "StudyDesign": {"Timepoints": "single"}})
    )
    open_init_form(bare_page, studio_url, bids)

    bare_page.click("#initBidsSubmitBtn")

    expect(bare_page.locator("#initBidsResult")).to_be_visible(timeout=60000)
    project = json.loads((bids / "project.json").read_text())
    assert project["Basics"]["Name"] == "Hand written"
    assert project["StudyDesign"]["Timepoints"] == "single"


def test_init_with_a_path_that_does_not_exist_says_so_and_creates_nothing(bare_page, studio_url, tmp_path):
    bare_page.allowed_http[400] = "/api/projects/init-on-bids"
    ghost = tmp_path / "no-such-folder"
    open_init_form(bare_page, studio_url, ghost)

    bare_page.click("#initBidsSubmitBtn")

    expect(bare_page.locator("#initBidsResult")).to_be_visible(timeout=60000)
    assert not ghost.exists()


def test_remote_source_without_a_url_is_refused_before_anything_is_sent(bare_page, studio_url, tmp_path):
    messages = []
    bare_page.on("dialog", lambda dialog: (messages.append(dialog.message), dialog.accept()))
    requests = []
    bare_page.on("request", lambda r: "/api/projects/init-on-bids" in r.url and requests.append(r.url))
    bare_page.goto(f"{studio_url}/projects")
    bare_page.click("#card-init-bids")
    bare_page.click('label[for="initBidsSourceRemote"]')
    expect(bare_page.locator("#initBidsRemoteGroup")).to_be_visible()
    expect(bare_page.locator("#initBidsLocalGroup")).to_be_hidden()
    bare_page.fill("#initBidsClonePath", str(tmp_path / "clone-here"))

    bare_page.click("#initBidsSubmitBtn")

    bare_page.wait_for_timeout(500)
    assert messages and "Git/DataLad URL" in messages[0]
    assert requests == [] and not (tmp_path / "clone-here").exists()
