"""`merge-versions` is a prism_tools command; the validator CLI (prism.py) only points to it."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(script, *args):
    env = {**os.environ, "PRISM_SKIP_VENV_CHECK": "1"}
    return subprocess.run(
        [sys.executable, str(ROOT / "app" / script), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
        timeout=60,
    )


def _template(path: Path, version: str, items: dict) -> Path:
    body = {
        "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv"},
        "Study": {"TaskName": "bdi", "OriginalName": "BDI", "Versions": [version]},
        "Metadata": {"SchemaVersion": "1.1.1"},
        **{k: {"Description": d, "ApplicableVersions": [version]} for k, d in items.items()},
    }
    path.write_text(json.dumps(body))
    return path


def test_prism_tools_merge_versions_dry_run(tmp_path):
    short = _template(tmp_path / "survey-bdi.json", "short", {"BDI_01": "Sadness"})
    long_ = _template(tmp_path / "bdi_long.json", "long", {"BDI_01": "Sadness", "BDI_02": "Pessimism"})

    r = _run("prism_tools.py", "merge-versions", str(short), str(long_),
             "--new-version", "long", "--existing-version", "short", "--dry-run")

    assert r.returncode == 0, r.stdout + r.stderr
    assert "Merging 'short' + 'long'" in r.stdout
    assert "No files were written" in r.stdout
    assert json.loads(short.read_text())["Study"]["Versions"] == ["short"]  # untouched


def test_prism_tools_merge_versions_writes_merged_template(tmp_path):
    short = _template(tmp_path / "survey-bdi.json", "short", {"BDI_01": "Sadness"})
    long_ = _template(tmp_path / "bdi_long.json", "long", {"BDI_01": "Sadness", "BDI_02": "Pessimism"})
    out = tmp_path / "merged.json"

    r = _run("prism_tools.py", "merge-versions", str(short), str(long_),
             "--new-version", "long", "--existing-version", "short", "--output", str(out))

    assert r.returncode == 0, r.stdout + r.stderr
    merged = json.loads(out.read_text())
    assert sorted(merged["Study"]["Versions"]) == ["long", "short"]
    assert "BDI_02" in merged


def test_missing_template_is_exit_1(tmp_path):
    r = _run("prism_tools.py", "merge-versions", str(tmp_path / "nope.json"), str(tmp_path / "x.json"))
    assert r.returncode == 1 and "Template not found" in r.stdout


def test_validator_cli_points_merge_versions_to_prism_tools():
    r = _run("prism.py", "merge-versions", "a.json", "b.json")
    assert r.returncode == 2
    assert "not part of the validator" in r.stdout
    assert "prism_tools.py merge-versions" in r.stdout
