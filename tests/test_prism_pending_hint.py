"""prism.py ends a run with a one-line update hint when a newer modality schema exists."""

import json
import os
import subprocess
import sys
from pathlib import Path

import src.modality_versions as mv

PRISM = Path(__file__).resolve().parents[1] / "app" / "prism.py"


def _run(tmp_path, survey_version):
    project = tmp_path / "proj"
    (project / "sub-01" / "survey").mkdir(parents=True)
    (project / "sub-01" / "survey" / "sub-01_task-x_survey.tsv").write_text("a\n1\n")
    (project / "dataset_description.json").write_text(json.dumps({"Name": "x", "BIDSVersion": "1.8.0"}))
    (project / "project.json").write_text(json.dumps({"SchemaVersions": {"survey": survey_version}}))
    return subprocess.run(
        [sys.executable, str(PRISM), str(project), "--no-bids"],
        capture_output=True, text=True, env={**os.environ, "PRISM_SKIP_VENV_CHECK": "1"},
    )


def test_hint_shown_when_pinned_older(tmp_path):
    assert "A newer survey schema is available" in _run(tmp_path, "0.0.1").stderr


def test_no_hint_when_pinned_at_current(tmp_path):
    assert "A newer survey schema" not in _run(tmp_path, mv.current_version("survey")).stderr
