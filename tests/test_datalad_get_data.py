"""Get data: fetch the annexed content of your own copy from the server, with the export's filters."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app", ROOT / "tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from test_export_selection import identity, save_dataset  # noqa: E402,F401

pytestmark = pytest.mark.skipif(
    not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex"
)


def _run(*cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def cli(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / "prism_tools.py"), "datalad", *args], capture_output=True, text=True, cwd=ROOT
    )


def present_files(copy: Path) -> list[str]:
    return sorted(
        str(p.relative_to(copy)) for p in copy.rglob("*")
        if p.exists() and p.is_file() and ".git" not in p.relative_to(copy).parts
    )


def studio_job(project: Path, body: dict) -> dict:
    """Start Studio's get-data job and return the finished job's status."""
    import time

    from flask import Flask

    from src.web.blueprints.projects_datalad_server_blueprint import projects_datalad_server_bp

    app = Flask(__name__, root_path=str(ROOT / "app"))
    app.register_blueprint(projects_datalad_server_bp)
    client = app.test_client()
    started = client.post("/api/projects/datalad/get-data", json={"project_path": str(project), **body})
    assert started.status_code == 200, started.get_json()
    job = started.get_json()["job_id"]
    for _ in range(300):
        status = client.get(f"/api/projects/datalad-server/sync/{job}/status").get_json()
        if status["status"] in ("complete", "error"):
            return status
        time.sleep(0.2)
    raise AssertionError(status)


def has_content(path: Path) -> bool:
    return path.exists()  # an annexed file without its content is a dangling link


@pytest.fixture
def copies(tmp_path, identity):
    """`server` (a saved dataset with annexed files) and `mine`, a clone with no data yet."""
    server, mine = tmp_path / "server", tmp_path / "mine"
    save_dataset(server)
    _run("datalad", "clone", str(server), str(mine), cwd=tmp_path)
    return server, mine


def test_a_get_that_asks_for_no_data_fetches_no_data(copies):
    """`--on-failure` is a global DataLad option; after `get` it was rejected and the fallback fetched the data."""
    from src.datalad_execution import run_datalad_get_paths

    _, mine = copies
    target = "sub-01/ses-1/anat/sub-01_ses-1_acq-hi_T1w.nii.gz"
    result = run_datalad_get_paths(mine, paths=[target], no_data=True)
    assert result["success"] is True, result
    assert "&&" not in result["command"], result["command"]
    assert not has_content(mine / target)


def test_get_data_fetches_only_the_chosen_subjects(copies):
    from src.datalad_get_data import get_data

    _, mine = copies
    result = get_data(mine, exclude_subjects={"sub-02"})
    assert result["success"] is True, result
    assert has_content(mine / "sub-01/ses-1/anat/sub-01_ses-1_acq-hi_T1w.nii.gz")
    assert has_content(mine / "sub-03/ses-2/func/sub-03_ses-2_task-rest_bold.nii.gz")
    assert not has_content(mine / "sub-02/ses-1/anat/sub-02_ses-1_acq-hi_T1w.nii.gz")
    assert not has_content(mine / "sub-02/ses-2/func/sub-02_ses-2_task-rest_bold.nii.gz")


def test_get_data_follows_the_export_filters(copies):
    from src.datalad_get_data import get_data

    _, mine = copies
    result = get_data(
        mine, exclude_sessions={"ses-2"}, exclude_modalities={"physio"}, exclude_acq={"anat": {"lo"}},
        exclude_tasks={"func": {"nback"}}, include_code=False, include_sourcedata=False,
    )
    assert result["success"] is True, result
    assert has_content(mine / "sub-01/ses-1/anat/sub-01_ses-1_acq-hi_T1w.nii.gz")
    assert has_content(mine / "derivatives/fmriprep/sub-01/out.nii.gz")
    for rel in (
        "sub-01/ses-2/anat/sub-01_ses-2_acq-hi_T1w.nii.gz",
        "sub-01/ses-1/physio/sub-01_ses-1_task-rest_physio.tsv.gz",
        "sub-01/ses-1/anat/sub-01_ses-1_acq-lo_T1w.nii.gz",
        "sub-01/ses-1/func/sub-01_ses-1_task-nback_bold.nii.gz",
        "sourcedata/raw/scan.dcm",
    ):
        assert not has_content(mine / rel), rel


def test_get_data_fetches_the_exports_defaults_when_no_filter_is_given(copies):
    """Everything but sourcedata and analysis, which the export leaves out unless asked (CLI and Studio agree)."""
    from src.datalad_get_data import get_data

    _, mine = copies
    result = get_data(mine)
    assert result["success"] is True, result
    for rel in (
        "sub-02/ses-2/physio/sub-02_ses-2_task-rest_physio.tsv.gz",
        "derivatives/fmriprep/sub-01/out.nii.gz",
    ):
        assert has_content(mine / rel), rel
    assert not has_content(mine / "analysis/model.bin")
    assert not has_content(mine / "sourcedata/raw/scan.dcm")


def test_the_function_and_the_command_without_flags_fetch_the_same_files(tmp_path, identity):
    from src.datalad_get_data import get_data

    server = tmp_path / "server"
    save_dataset(server)
    direct, cli_copy = tmp_path / "direct", tmp_path / "cli"
    for copy in (direct, cli_copy):
        _run("datalad", "clone", str(server), str(copy), cwd=tmp_path)
    assert get_data(direct)["success"] is True
    assert cli("get-data", "--project", str(cli_copy)).returncode == 0
    assert present_files(direct) == present_files(cli_copy)


def test_include_analysis_fetches_the_analysis_folder(copies):
    from src.datalad_get_data import get_data

    _, mine = copies
    assert get_data(mine, include_analysis=True)["success"] is True
    assert has_content(mine / "analysis/model.bin")
    assert not has_content(mine / "sourcedata/raw/scan.dcm")


def test_the_flags_include_analysis_and_sourcedata_fetch_those_folders(copies):
    _, mine = copies
    assert cli("get-data", "--project", str(mine), "--include-analysis", "--include-sourcedata").returncode == 0
    assert has_content(mine / "analysis/model.bin") and has_content(mine / "sourcedata/raw/scan.dcm")


def test_a_file_name_that_looks_like_an_option_is_fetched_safely(tmp_path, identity):
    from src.datalad_get_data import get_data

    server, mine = tmp_path / "server", tmp_path / "mine"
    save_dataset(server)
    (server / "-weird.bin").write_bytes(b"\x00hostile\n")
    (server / "--help").write_bytes(b"\x00hostile2\n")
    _run("datalad", "save", "-m", "hostile names", cwd=server)
    _run("datalad", "clone", str(server), str(mine), cwd=tmp_path)
    result = get_data(mine)
    assert result["success"] is True, result
    assert has_content(mine / "-weird.bin") and has_content(mine / "--help")


def test_without_a_server_it_says_so_and_succeeds(tmp_path, identity):
    from src.datalad_get_data import get_data

    alone = tmp_path / "alone"
    save_dataset(alone)
    result = get_data(alone)
    assert result["success"] is True and result["skipped"] is True and result["message"]


def test_an_unreachable_server_is_an_error_with_a_plain_sentence(copies):
    from src.datalad_get_data import get_data

    server, mine = copies
    for path in server.rglob("*"):
        if not path.is_symlink():
            path.chmod(0o700)  # the annex keeps its objects read-only
    shutil.rmtree(server)
    result = get_data(mine)
    assert result["success"] is False
    assert "server" in result["message"].lower() and "traceback" not in result["message"].lower()


def test_files_no_server_has_are_listed_as_the_error(copies):
    from src.datalad_get_data import get_data

    server, mine = copies
    _run("git", "-C", str(server), "annex", "drop", "--force", "analysis/model.bin", cwd=server.parent)
    result = get_data(mine, include_analysis=True)
    assert result["success"] is False
    assert "analysis/model.bin" in result["message"]


def test_a_label_that_looks_like_an_option_is_just_a_label(copies):
    from src.datalad_get_data import get_data

    _, mine = copies
    result = get_data(mine, exclude_subjects={"--help", "-r"}, exclude_acq={"anat": {"--x"}})
    assert result["success"] is True, result
    assert has_content(mine / "sub-01/ses-1/anat/sub-01_ses-1_acq-hi_T1w.nii.gz")


def test_the_command_runs_through_the_real_entrypoint_and_filters_like_the_export(copies):
    _, mine = copies
    done = subprocess.run(
        [sys.executable, str(ROOT / "prism_tools.py"), "datalad", "get-data", "--project", str(mine),
         "--exclude-subject", "sub-02", "--exclude-modality", "physio", "--no-code", "--json"],
        capture_output=True, text=True, cwd=ROOT,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert json.loads(done.stdout)["success"] is True
    assert has_content(mine / "sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz")
    assert not has_content(mine / "sub-02/ses-1/func/sub-02_ses-1_task-rest_bold.nii.gz")
    assert not has_content(mine / "sub-01/ses-1/physio/sub-01_ses-1_task-rest_physio.tsv.gz")


def test_studio_and_the_command_fetch_the_same_files(tmp_path, identity):
    import time

    from flask import Flask

    server = tmp_path / "server"
    save_dataset(server)
    cli_copy, studio_copy = tmp_path / "cli", tmp_path / "studio"
    for copy in (cli_copy, studio_copy):
        _run("datalad", "clone", str(server), str(copy), cwd=tmp_path)
    subprocess.run(
        [sys.executable, str(ROOT / "prism_tools.py"), "datalad", "get-data", "--project", str(cli_copy),
         "--exclude-subject", "sub-02", "--exclude-session", "ses-2", "--exclude-task", "func=nback"],
        check=True, capture_output=True, text=True, cwd=ROOT,
    )

    from src.web.blueprints.projects_datalad_server_blueprint import projects_datalad_server_bp

    app = Flask(__name__, root_path=str(ROOT / "app"))
    app.register_blueprint(projects_datalad_server_bp)
    client = app.test_client()
    started = client.post("/api/projects/datalad/get-data", json={
        "project_path": str(studio_copy), "exclude_subjects": ["sub-02"], "exclude_sessions": ["ses-2"],
        "exclude_tasks": {"func": ["nback"]},
    })
    assert started.status_code == 200, started.get_json()
    job = started.get_json()["job_id"]
    for _ in range(300):
        status = client.get(f"/api/projects/datalad-server/sync/{job}/status").get_json()
        if status["status"] in ("complete", "error"):
            break
        time.sleep(0.2)
    assert status["status"] == "complete", status

    def fetched(copy: Path) -> list[str]:
        return sorted(
            str(p.relative_to(copy)) for p in copy.rglob("*") if p.is_file() and ".git" not in p.relative_to(copy).parts
        )

    assert fetched(cli_copy) == fetched(studio_copy)
    assert has_content(studio_copy / "sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz")


def _cli_json(project, *flags):
    done = cli("get-data", "--project", str(project), *flags, "--json")
    return done, json.loads(done.stdout)


def test_no_server_through_the_command_and_studio_say_the_same(tmp_path, identity):
    alone = tmp_path / "alone"
    save_dataset(alone)
    done, payload = _cli_json(alone)
    assert done.returncode == 0 and payload["skipped"] is True and payload["success"] is True
    job = studio_job(alone, {})
    assert job["status"] == "complete" and job["result"] == payload and job["message"] == payload["message"]


def test_files_no_server_has_through_the_command_and_studio_say_the_same(copies):
    server, mine = copies
    _run("git", "-C", str(server), "annex", "drop", "--force", "analysis/model.bin", cwd=server.parent)
    done, payload = _cli_json(mine)
    assert done.returncode == 0  # analysis is not part of the default scope
    done, payload = _cli_json(mine, "--include-analysis")
    assert done.returncode == 1 and payload["success"] is False and "analysis/model.bin" in payload["message"]
    plain = cli("get-data", "--project", str(mine), "--include-analysis")
    assert plain.returncode == 1 and "analysis/model.bin" in plain.stdout + plain.stderr
    job = studio_job(mine, {"include_analysis": True})
    assert job["status"] == "error" and job["result"] == payload and "analysis/model.bin" in job["error"]


def test_an_unreachable_server_through_the_command_and_studio_say_the_same(copies):
    server, mine = copies
    for path in server.rglob("*"):
        if not path.is_symlink():
            path.chmod(0o700)
    shutil.rmtree(server)
    done, payload = _cli_json(mine)
    assert done.returncode == 1 and payload["success"] is False
    assert payload["message"] == "The server could not be reached. Check your network connection and try again."
    job = studio_job(mine, {})
    assert job["status"] == "error" and job["result"] == payload
