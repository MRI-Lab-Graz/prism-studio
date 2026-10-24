"""Every module that writes ses-<label> output names for imported data follows the project's
Timepoints rule (single -> ses-1, multiple -> the session map), or says why it does not."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = re.compile(r"resolve_import_session|session_target|project_timepoints|session_map_for_conversion")

FOLLOWS_POLICY = [
    "src/batch_convert.py",
    "src/converters/biometrics.py",
    "src/environment_conversion.py",
    "app/src/converters/survey.py",
    "app/src/web/services/project_registration.py",
]

EXEMPT = {  # writes ses- names, but not from the data being imported
    "app/src/converters/survey_core.py": "normalizers; survey.py applies the policy before them",
    "src/recipes_surveys.py": "reads sessions of an existing dataset",
    "src/methods_project.py": "reads sessions of an existing dataset",
    "src/environment_mri_scan.py": "reads sessions from existing BIDS paths",
    "src/bids_file_deleter.py": "matches existing folders",
    "src/converters/phenotype_import.py": "imports an existing dataset when a project is created (no declaration yet)",
    "src/converters/phenotype_export.py": "export",
    "src/converters/excel_to_biometrics.py": "template builder: SessionHint metadata, no data files",
    "app/src/converters/excel_to_survey.py": "template builder: SessionHint metadata, no data files",
    "app/src/web/validation.py": "statistics labels",
    "app/src/web/blueprints/conversion_biometrics_handlers.py": "passes sessions on to project_registration",
    "app/src/cli/commands/dataset.py": "smoketest dataset builder",
}

KNOWN_GAPS: dict[str, str] = {}  # importers that still use their own session handling

EXEMPT["app/src/converters/csv.py"] = (
    "legacy LimeSurvey batch (survey import-limesurvey-batch): refused in any project, so only plain folders reach it"
)

WRITES_SESSIONS = re.compile(r'f"ses-\{|"ses-" \+|f\'ses-\{')


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_policy_followers_consult_the_policy():
    for rel in FOLLOWS_POLICY:
        assert POLICY.search(_read(rel)), rel


def test_every_session_writing_module_is_classified():
    found = {
        p.relative_to(ROOT).as_posix()
        for root in ("src", "app/src")
        for p in (ROOT / root).rglob("*.py")
        if WRITES_SESSIONS.search(p.read_text(encoding="utf-8"))
    }
    classified = set(FOLLOWS_POLICY) | set(EXEMPT) | set(KNOWN_GAPS)
    assert not found - classified, f"classify these importers (follow the policy or exempt with a reason): {sorted(found - classified)}"
