import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

import bids_validator

ENGINE = "/fake/bin/bids-validator-deno"
ROOT = Path(__file__).resolve().parents[1]


def use_engine(monkeypatch, report=None, stdout=None, returncode=None):
    """Pretend bids-validator-deno is installed and prints `report`; return the recorded commands."""
    calls = []
    if returncode is None:  # the engine exits 16 when its report holds an error, else 0
        issues = ((report or {}).get("issues") or {}).get("issues", [])
        returncode = 16 if any(i.get("severity") == "error" for i in issues) else 0
    monkeypatch.setattr(bids_validator, "find_bids_engine", lambda: ENGINE)
    monkeypatch.setattr(bids_validator, "bids_engine_version", lambda: "3.0.2")

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = stdout if stdout is not None else json.dumps(report or {"issues": {"issues": []}})
        return SimpleNamespace(stdout=out, stderr="", returncode=returncode)

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)
    return calls


def test_deno_parser_suppresses_recommended_key_warnings(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    deno_report = {
        "issues": {
            "issues": [
                {
                    "code": "SIDECAR_KEY_RECOMMENDED",
                    "subCode": "SequenceName",
                    "severity": "warning",
                    "issueMessage": "Recommended key is missing",
                    "location": "/sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz",
                },
                {
                    "code": "EVENTS_TSV_MISSING",
                    "severity": "warning",
                    "issueMessage": "events.tsv is missing",
                    "location": "/sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz",
                },
            ]
        }
    }

    use_engine(monkeypatch, deno_report)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    _level, message, _path = issues[0]
    assert "EVENTS_TSV_MISSING" in message
    assert "SIDECAR_KEY_RECOMMENDED" not in message


def test_deno_parser_suppresses_citation_precedence_conflict(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "CITATION.cff").write_text(
        "cff-version: 1.2.0\ntitle: Demo\nmessage: cite\nauthors:\n  - family-names: Doe\n",
        encoding="utf-8",
    )

    deno_report = {
        "issues": {
            "issues": [
                {
                    "code": "BIDS_AUTHORS_AND_CITATION_FILE_MUTUALLY_EXCLUSIVE",
                    "severity": "error",
                    "issueMessage": "Authors and citation file are mutually exclusive",
                    "location": "/CITATION.cff",
                },
                {
                    "code": "EVENTS_TSV_MISSING",
                    "severity": "warning",
                    "issueMessage": "events.tsv is missing",
                    "location": "/sub-01/ses-1/func/sub-01_ses-1_task-rest_bold.nii.gz",
                },
            ]
        }
    }

    use_engine(monkeypatch, deno_report)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    _level, message, _path = issues[0]
    assert "EVENTS_TSV_MISSING" in message
    assert "AUTHORS_AND_CITATION_FILE_MUTUALLY_EXCLUSIVE" not in message


def _make_unfetched_annex_symlink(path):
    """Create a broken symlink mimicking an un-fetched git-annex file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.symlink_to(path.parent / ".git" / "annex" / "objects" / "does-not-exist")


def test_deno_parser_downgrades_unfetched_annex_content_to_warning(
    monkeypatch, tmp_path
):
    dataset = tmp_path / "dataset"
    nifti = dataset / "sub-01" / "ses-1" / "anat" / "sub-01_ses-1_T1w.nii.gz"
    _make_unfetched_annex_symlink(nifti)

    deno_report = {
        "issues": {
            "issues": [
                {
                    "code": "NIFTI_HEADER_UNREADABLE",
                    "severity": "error",
                    "issueMessage": "Could not read NIfTI header",
                    "location": "/sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz",
                },
            ]
        }
    }

    use_engine(monkeypatch, deno_report)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    level, message, _path = issues[0]
    assert level == "WARNING"
    assert "datalad get -r ." in message


def test_deno_parser_keeps_genuinely_broken_file_as_error(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    # A real (non-symlink) file is not a git-annex placeholder, so this
    # must stay a hard error rather than being downgraded.
    nifti = dataset / "sub-01" / "ses-1" / "anat" / "sub-01_ses-1_T1w.nii.gz"
    nifti.parent.mkdir(parents=True)
    nifti.write_bytes(b"not a real nifti file")

    deno_report = {
        "issues": {
            "issues": [
                {
                    "code": "NIFTI_HEADER_UNREADABLE",
                    "severity": "error",
                    "issueMessage": "Could not read NIfTI header",
                    "location": "/sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz",
                },
            ]
        }
    }

    use_engine(monkeypatch, deno_report)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    level, message, _path = issues[0]
    assert level == "ERROR"
    assert "datalad get" not in message


def test_engine_is_found_next_to_python_before_path(monkeypatch, tmp_path):
    name = "bids-validator-deno.exe" if sys.platform == "win32" else "bids-validator-deno"
    local = tmp_path / name
    local.write_text("")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(bids_validator.shutil, "which", lambda n: "/elsewhere/" + n)
    assert bids_validator.find_bids_engine() == str(local)


def test_engine_falls_back_to_path_then_none(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(bids_validator.shutil, "which", lambda n: "/usr/bin/" + n)
    assert bids_validator.find_bids_engine() == "/usr/bin/bids-validator-deno"
    monkeypatch.setattr(bids_validator.shutil, "which", lambda n: None)
    assert bids_validator.find_bids_engine() is None


def test_command_line_is_the_engine_and_ignores_nifti_headers_by_default(monkeypatch, tmp_path):
    calls = use_engine(monkeypatch)
    bids_validator.run_bids_validator(str(tmp_path))
    bids_validator.run_bids_validator(str(tmp_path), check_nifti_headers=True)
    assert calls == [
        [ENGINE, str(tmp_path), "--format", "json", "--ignoreNiftiHeaders"],
        [ENGINE, str(tmp_path), "--format", "json"],
    ]


def test_backend_info_names_the_engine_and_its_version(monkeypatch, tmp_path):
    use_engine(monkeypatch)
    info = {}
    bids_validator.run_bids_validator(str(tmp_path), backend_info=info)
    assert info == {
        "engine": "bids-validator-deno",
        "version": "3.0.2",
        "spec": "bids-validator-deno@3.0.2",
    }


def test_a_report_with_errors_and_exit_code_16_keeps_its_issues(monkeypatch, tmp_path):
    report = {"issues": {"issues": [{"code": "JSON_KEY_REQUIRED", "severity": "error", "location": "/dataset_description.json"}]}}
    use_engine(monkeypatch, report, returncode=16)
    issues = bids_validator.run_bids_validator(str(tmp_path))
    assert [i[0] for i in issues] == ["ERROR"]
    assert not any(i[1].startswith("PRISM902") for i in issues)


def test_real_3_0_2_output_keeps_real_problems_and_silences_prism_folders(monkeypatch):
    dataset = ROOT / "examples" / "wellbeing_multi_demo"
    fixture = ROOT / "tests" / "data" / "bids_validator_3_0_2_wellbeing_report.json"
    use_engine(monkeypatch, stdout=fixture.read_text(encoding="utf-8"), returncode=16)
    messages = [i[1] for i in bids_validator.run_bids_validator(str(dataset))]
    not_included = [m for m in messages if m.startswith("[BIDS] NOT_INCLUDED")]
    assert not_included, "the real DEMO_GUIDE.md problem must stay"
    assert all("/survey/" not in m for m in not_included)
    assert any("PARTICIPANT_ID_MISMATCH" in m for m in messages)
    assert not any("JSON_KEY_RECOMMENDED" in m for m in messages)
