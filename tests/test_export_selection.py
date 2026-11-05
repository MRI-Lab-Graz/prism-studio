"""What the export (and Get data) select: one function, and it selects what the export always selected."""

import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "app"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

needs_datalad = pytest.mark.skipif(
    not shutil.which("datalad") or not shutil.which("git-annex"), reason="needs DataLad and git-annex"
)

BIN = b"\x00\x01binary\x00\n"


def _run(*cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, check=True, capture_output=True, text=True).stdout


def _put(root, rel, data=None):
    if data is None:
        data = BIN + rel.encode()  # annex keys are content hashes: every file needs its own content
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        path.write_bytes(data)
    else:
        path.write_text(data, encoding="utf-8")


def build_fixture(root: Path) -> None:
    """Three subjects, two sessions, anat/func/physio, acq and task labels, and every top-level folder."""
    _put(root, "participants.tsv", "participant_id\nsub-01\nsub-02\nsub-03\n")
    _put(root, "dataset_description.json", '{"Name": "x"}\n')
    _put(root, "task-rest_survey.json", '{"a": 1}\n')
    _put(root, "task-stai_survey.json", '{"a": 1}\n')
    for sub in ("sub-01", "sub-02", "sub-03"):
        for ses in ("ses-1", "ses-2"):
            base = f"{sub}/{ses}"
            _put(root, f"{base}/anat/{sub}_{ses}_acq-hi_T1w.nii.gz")
            _put(root, f"{base}/anat/{sub}_{ses}_acq-lo_T1w.nii.gz")
            _put(root, f"{base}/anat/{sub}_{ses}_acq-hi_T1w.json", '{"a": 1}\n')
            _put(root, f"{base}/func/{sub}_{ses}_task-rest_bold.nii.gz")
            _put(root, f"{base}/func/{sub}_{ses}_task-nback_bold.nii.gz")
            _put(root, f"{base}/physio/{sub}_{ses}_task-rest_physio.tsv.gz")
            _put(root, f"{base}/survey/{sub}_{ses}_task-stai_survey.tsv", "a\tb\n1\t2\n")
    _put(root, "derivatives/fmriprep/sub-01/out.nii.gz")
    _put(root, "code/analysis.py", "print(1)\n")
    _put(root, "analysis/model.bin")
    _put(root, "sourcedata/raw/scan.dcm")


def save_dataset(root: Path) -> None:
    _run("datalad", "create", "-c", "text2git", str(root), cwd=root.parent)
    build_fixture(root)
    _run("datalad", "save", "-m", "fixture", cwd=root)


FILTERS = dict(
    exclude_subjects={"sub-02"},
    exclude_sessions={"ses-2"},
    exclude_modalities={"physio"},
    exclude_acq={"anat": {"lo"}},
    exclude_tasks={"func": {"nback"}},
    include_derivatives=True,
    include_code=False,
    include_analysis=True,
    include_sourcedata=False,
)

# What the export fetched for FILTERS before the selection was extracted (recorded from the unchanged export).
SELECTED_BEFORE = [
    "analysis/model.bin",
    "dataset_description.json",
    "derivatives/fmriprep/sub-01/out.nii.gz",
    "participants.tsv",
    "sub-01/ses-1/anat/sub-01_ses-1_acq-hi_T1w.json",
    "sub-01/ses-1/anat/sub-01_ses-1_acq-hi_T1w.nii.gz",
    "sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz",
    "sub-01/ses-1/survey/sub-01_ses-1_task-stai_survey.tsv",
    "sub-03/ses-1/anat/sub-03_ses-1_acq-hi_T1w.json",
    "sub-03/ses-1/anat/sub-03_ses-1_acq-hi_T1w.nii.gz",
    "sub-03/ses-1/func/sub-03_ses-1_task-rest_bold.nii.gz",
    "sub-03/ses-1/survey/sub-03_ses-1_task-stai_survey.tsv",
    "task-rest_survey.json",
    "task-stai_survey.json",
]


@pytest.fixture
def identity(tmp_path, monkeypatch):
    cfg = tmp_path / "gitconfig"
    cfg.write_text("[user]\n\tname = Ada\n\temail = ada@example.org\n")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(cfg))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("HOME", str(tmp_path))


@needs_datalad
def test_the_export_selects_exactly_what_it_selected_before(tmp_path, identity):
    from src.project_manager import ProjectManager

    project = tmp_path / "study"
    save_dataset(project)
    recorded: list[list[str]] = []
    real_run = subprocess.run

    def spy(command, *args, **kwargs):
        if isinstance(command, list) and command[1:2] == ["get"] and "-n" not in command and "-r" not in command:
            recorded.append(list(command))
        return real_run(command, *args, **kwargs)

    with patch("src.project_manager.subprocess.run", spy):
        result = ProjectManager().export_project_to_plain_folder(
            project, output_root=tmp_path / "out", materialize_annex_content=True, **FILTERS
        )
    assert result.get("success") is True, result
    fetched = sorted({part for command in recorded for part in command[2:] if part not in ("--on-failure", "ignore")})
    assert fetched == SELECTED_BEFORE
