"""The PyPI validator (only the files in validator_manifest.txt) must report what the full validator reports.

A manifest file that reaches a module outside the manifest used to skip its check silently
(try/except ImportError). Stage the wheel like the build does and compare both runs.
"""

import json
import re
from pathlib import Path

from wheel_helpers import run_validator, stage_wheel

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = {
    "Technical": {"StimulusType": "Questionnaire", "FileFormat": "tsv", "Language": "en"},
    "Study": {"TaskName": "ads", "OriginalName": "ads", "LicenseID": "Other", "License": ""},
    "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-10-01", "Creator": "t"},
    "ADS1": {"Description": "Q", "Levels": {"0": "never", "1": "often"}},
}


def _dataset(tmp: Path) -> Path:
    """A project with two typical mistakes: sub-02 is missing from participants.tsv, and the
    survey template was changed after its sidecar was written."""
    root = tmp / "proj"
    (root / "code" / "library" / "survey").mkdir(parents=True)
    changed = json.loads(json.dumps(TEMPLATE))
    changed["ADS1"]["Levels"] = {"0": "never", "1": "often", "2": "always"}
    (root / "code" / "library" / "survey" / "survey-ads.json").write_text(json.dumps(changed), encoding="utf-8")
    stale = json.loads(json.dumps(TEMPLATE))
    stale["ADS1"]["Levels"]["n/a"] = "Missing/Not provided"
    (root / "task-ads_survey.json").write_text(json.dumps(stale), encoding="utf-8")
    (root / "project.json").write_text(json.dumps({
        "Basics": {"Name": "N", "Authors": ["A"], "Keywords": ["k"]}, "StudyDesign": {"Timepoints": "single"},
    }), encoding="utf-8")
    (root / "dataset_description.json").write_text(json.dumps({"Name": "N", "BIDSVersion": "1.10.1"}), encoding="utf-8")
    (root / "participants.tsv").write_text("participant_id\nsub-01\n", encoding="utf-8")
    for sub in ("sub-01", "sub-02"):
        folder = root / sub / "ses-1" / "survey"
        folder.mkdir(parents=True)
        (folder / f"{sub}_ses-1_task-ads_survey.tsv").write_text("ADS1\n0\n", encoding="utf-8")
    return root


def _messages(prism: Path, dataset: Path, cwd: Path) -> list[str]:
    result = run_validator(prism, dataset, cwd, "--json")
    text = result.stdout
    start = text.index("{")
    report = json.loads(text[start:])
    found = json.dumps(report)
    return sorted(set(re.findall(r'"(?:message|msg)"\s*:\s*"([^"]+)"', found))) or [found]


def test_the_wheel_reports_the_same_findings_as_the_full_validator(tmp_path):
    wheel_prism = stage_wheel(tmp_path / "wheel")
    dataset = _dataset(tmp_path)

    full = _messages(ROOT / "app" / "prism.py", dataset, ROOT)
    wheel = _messages(wheel_prism, dataset, tmp_path)

    assert any("changed since the data was converted" in m for m in full), full  # the check does run in the repo
    assert any("participants.tsv" in m for m in full), full
    assert wheel == full
