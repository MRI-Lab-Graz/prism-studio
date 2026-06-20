import json
import os
import sys
from types import SimpleNamespace


sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

import bids_validator


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

    def fake_run(cmd, check=False, stdout=None, stderr=None, text=False):
        if cmd[:2] == ["deno", "--version"]:
            return SimpleNamespace(stdout="deno 2.0.0", stderr="", returncode=0)
        if cmd[:2] == ["deno", "run"]:
            return SimpleNamespace(
                stdout=json.dumps(deno_report),
                stderr="",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    _level, message, _path = issues[0]
    assert "EVENTS_TSV_MISSING" in message
    assert "SIDECAR_KEY_RECOMMENDED" not in message


def test_legacy_parser_suppresses_recommended_key_warnings(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()

    legacy_report = {
        "issues": {
            "errors": [],
            "warnings": [
                {
                    "key": "SIDECAR_KEY_RECOMMENDED",
                    "reason": "Recommended sidecar key missing",
                    "files": [
                        {
                            "file": {
                                "relativePath": "sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz"
                            }
                        }
                    ],
                },
                {
                    "key": "PARTICIPANT_ID_MISMATCH",
                    "reason": "Participant mismatch",
                    "files": [
                        {
                            "file": {
                                "relativePath": "participants.tsv"
                            }
                        }
                    ],
                },
            ],
        }
    }

    def fake_run(cmd, check=False, stdout=None, stderr=None, text=False):
        if cmd[:2] == ["deno", "--version"]:
            raise FileNotFoundError("deno not installed")
        if cmd[:2] == ["bids-validator", "--version"]:
            return SimpleNamespace(stdout="1.14.0", stderr="", returncode=0)
        if cmd and cmd[0] == "bids-validator":
            return SimpleNamespace(
                stdout=json.dumps(legacy_report),
                stderr="",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    _level, message, _path = issues[0]
    assert "PARTICIPANT_ID_MISMATCH" in message
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

    def fake_run(cmd, check=False, stdout=None, stderr=None, text=False):
        if cmd[:2] == ["deno", "--version"]:
            return SimpleNamespace(stdout="deno 2.0.0", stderr="", returncode=0)
        if cmd[:2] == ["deno", "run"]:
            return SimpleNamespace(
                stdout=json.dumps(deno_report),
                stderr="",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    _level, message, _path = issues[0]
    assert "EVENTS_TSV_MISSING" in message
    assert "AUTHORS_AND_CITATION_FILE_MUTUALLY_EXCLUSIVE" not in message


def test_legacy_parser_suppresses_citation_precedence_conflict(monkeypatch, tmp_path):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "CITATION.cff").write_text(
        "cff-version: 1.2.0\ntitle: Demo\nmessage: cite\nauthors:\n  - family-names: Doe\n",
        encoding="utf-8",
    )

    legacy_report = {
        "issues": {
            "errors": [
                {
                    "key": "AUTHORS_AND_CITATION_FILE_MUTUALLY_EXCLUSIVE",
                    "reason": "Authors and citation file are mutually exclusive",
                    "files": [
                        {
                            "file": {
                                "relativePath": "CITATION.cff"
                            }
                        }
                    ],
                }
            ],
            "warnings": [
                {
                    "key": "PARTICIPANT_ID_MISMATCH",
                    "reason": "Participant mismatch",
                    "files": [
                        {
                            "file": {
                                "relativePath": "participants.tsv"
                            }
                        }
                    ],
                }
            ],
        }
    }

    def fake_run(cmd, check=False, stdout=None, stderr=None, text=False):
        if cmd[:2] == ["deno", "--version"]:
            raise FileNotFoundError("deno not installed")
        if cmd[:2] == ["bids-validator", "--version"]:
            return SimpleNamespace(stdout="1.14.0", stderr="", returncode=0)
        if cmd and cmd[0] == "bids-validator":
            return SimpleNamespace(
                stdout=json.dumps(legacy_report),
                stderr="",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    _level, message, _path = issues[0]
    assert "PARTICIPANT_ID_MISMATCH" in message
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

    def fake_run(cmd, check=False, stdout=None, stderr=None, text=False):
        if cmd[:2] == ["deno", "--version"]:
            return SimpleNamespace(stdout="deno 2.0.0", stderr="", returncode=0)
        if cmd[:2] == ["deno", "run"]:
            return SimpleNamespace(
                stdout=json.dumps(deno_report),
                stderr="",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)

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

    def fake_run(cmd, check=False, stdout=None, stderr=None, text=False):
        if cmd[:2] == ["deno", "--version"]:
            return SimpleNamespace(stdout="deno 2.0.0", stderr="", returncode=0)
        if cmd[:2] == ["deno", "run"]:
            return SimpleNamespace(
                stdout=json.dumps(deno_report),
                stderr="",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    level, message, _path = issues[0]
    assert level == "ERROR"
    assert "datalad get" not in message


def test_legacy_parser_downgrades_unfetched_annex_content_to_warning(
    monkeypatch, tmp_path
):
    dataset = tmp_path / "dataset"
    nifti = dataset / "sub-01" / "ses-1" / "anat" / "sub-01_ses-1_T1w.nii.gz"
    _make_unfetched_annex_symlink(nifti)

    legacy_report = {
        "issues": {
            "errors": [
                {
                    "key": "NIFTI_HEADER_UNREADABLE",
                    "reason": "Could not read NIfTI header",
                    "files": [
                        {
                            "file": {
                                "relativePath": "sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz"
                            }
                        }
                    ],
                }
            ],
            "warnings": [],
        }
    }

    def fake_run(cmd, check=False, stdout=None, stderr=None, text=False):
        if cmd[:2] == ["deno", "--version"]:
            raise FileNotFoundError("deno not installed")
        if cmd[:2] == ["bids-validator", "--version"]:
            return SimpleNamespace(stdout="1.14.0", stderr="", returncode=0)
        if cmd and cmd[0] == "bids-validator":
            return SimpleNamespace(
                stdout=json.dumps(legacy_report),
                stderr="",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 1
    level, message, _path = issues[0]
    assert level == "WARNING"
    assert "datalad get -r ." in message


def test_legacy_parser_level_does_not_leak_across_issues(monkeypatch, tmp_path):
    """An annex-unfetched downgrade on one error must not leak its WARNING
    level onto the next genuine error processed in the same batch."""
    dataset = tmp_path / "dataset"
    unfetched = dataset / "sub-01" / "ses-1" / "anat" / "sub-01_ses-1_T1w.nii.gz"
    _make_unfetched_annex_symlink(unfetched)

    legacy_report = {
        "issues": {
            "errors": [
                {
                    "key": "NIFTI_HEADER_UNREADABLE",
                    "reason": "Could not read NIfTI header",
                    "files": [
                        {
                            "file": {
                                "relativePath": "sub-01/ses-1/anat/sub-01_ses-1_T1w.nii.gz"
                            }
                        }
                    ],
                },
                {
                    "key": "PARTICIPANT_ID_MISMATCH",
                    "reason": "Participant mismatch",
                    "files": [
                        {"file": {"relativePath": "participants.tsv"}}
                    ],
                },
            ],
            "warnings": [],
        }
    }

    def fake_run(cmd, check=False, stdout=None, stderr=None, text=False):
        if cmd[:2] == ["deno", "--version"]:
            raise FileNotFoundError("deno not installed")
        if cmd[:2] == ["bids-validator", "--version"]:
            return SimpleNamespace(stdout="1.14.0", stderr="", returncode=0)
        if cmd and cmd[0] == "bids-validator":
            return SimpleNamespace(
                stdout=json.dumps(legacy_report),
                stderr="",
                returncode=0,
            )
        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(bids_validator.subprocess, "run", fake_run)

    issues = bids_validator.run_bids_validator(str(dataset), verbose=False)

    assert len(issues) == 2
    levels_by_message = {message: level for level, message, _path in issues}
    nifti_level = next(
        level for msg, level in levels_by_message.items() if "NIFTI_HEADER" in msg
    )
    participant_level = next(
        level
        for msg, level in levels_by_message.items()
        if "PARTICIPANT_ID_MISMATCH" in msg
    )
    assert nifti_level == "WARNING"
    assert participant_level == "ERROR"