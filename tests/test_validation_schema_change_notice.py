"""Guards for surfacing validator (PRISM schema + BIDS validator) versions.

runner.validate_dataset attaches validator_info to its stats object;
format_validation_results forwards it into the results payload; and
_build_validation_results_payload persists it into project.json via
ProjectManager.record_validation_run, so a later validation of the same
project can tell the user its schema moved under them. These tests exercise
that whole chain through the actual blueprint function, not a re-description
of it.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from src.web.blueprints.validation import _build_validation_results_payload  # noqa: E402


def _stats(validator_info):
    return SimpleNamespace(validator_info=validator_info)


def test_payload_carries_validator_info_and_writes_project_json(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({"name": "demo"}), encoding="utf-8")

    results = _build_validation_results_payload(
        issues=[],
        dataset_stats=_stats(
            {"prism_schema_tag": "stable", "prism_schema_versions": {"survey": "1.1.1"}}
        ),
        dataset_path=str(tmp_path),
        schema_version="stable",
        job_id="job-1",
        library_path=None,
        run_bids=False,
        run_prism=True,
        show_bids_warnings=False,
        project_path=str(tmp_path),
    )

    assert results["validator_info"]["prism_schema_versions"] == {"survey": "1.1.1"}
    assert "schema_change_notice" not in results

    payload = json.loads((tmp_path / "project.json").read_text(encoding="utf-8"))
    assert payload["LastValidation"]["prism_schema_versions"] == {"survey": "1.1.1"}


def test_payload_flags_schema_change_notice_on_a_later_run(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps({"name": "demo"}), encoding="utf-8")

    _build_validation_results_payload(
        issues=[],
        dataset_stats=_stats(
            {"prism_schema_tag": "stable", "prism_schema_versions": {"survey": "1.1.1"}}
        ),
        dataset_path=str(tmp_path),
        schema_version="stable",
        job_id="job-1",
        library_path=None,
        run_bids=False,
        run_prism=True,
        show_bids_warnings=False,
        project_path=str(tmp_path),
    )

    second = _build_validation_results_payload(
        issues=[],
        dataset_stats=_stats(
            {"prism_schema_tag": "stable", "prism_schema_versions": {"survey": "1.2.0"}}
        ),
        dataset_path=str(tmp_path),
        schema_version="stable",
        job_id="job-2",
        library_path=None,
        run_bids=False,
        run_prism=True,
        show_bids_warnings=False,
        project_path=str(tmp_path),
    )

    assert second["schema_change_notice"]["changed"] is True
    assert second["schema_change_notice"]["previous"]["prism_schema_versions"] == {
        "survey": "1.1.1"
    }


def test_payload_skips_project_json_write_for_a_plain_bids_folder(tmp_path):
    """No project.json at the target means this isn't a PRISM project to track."""
    results = _build_validation_results_payload(
        issues=[],
        dataset_stats=_stats(
            {"prism_schema_tag": "stable", "prism_schema_versions": {"survey": "1.1.1"}}
        ),
        dataset_path=str(tmp_path),
        schema_version="stable",
        job_id="job-1",
        library_path=None,
        run_bids=False,
        run_prism=True,
        show_bids_warnings=False,
        project_path=str(tmp_path),
    )

    assert "schema_change_notice" not in results
    assert not (tmp_path / "project.json").exists()
