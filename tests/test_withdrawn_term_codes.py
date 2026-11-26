"""Term codes that mean something else (or do not exist) are never shipped and are reported."""

import json
import subprocess
from pathlib import Path

from src.participants_levels import WRONG_TERM_CODES, check_participants_levels

ROOT = Path(__file__).resolve().parents[1]


def test_no_shipped_file_carries_a_wrong_code():
    pattern = "|".join(WRONG_TERM_CODES)
    found = subprocess.run(
        ["git", "grep", "-lwE", pattern, "--", "src", "app", "official", "examples"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    ).stdout.split()

    assert found == ["src/participants_levels.py"]


def test_the_education_codes_are_listed_as_genes():
    assert "Gene" in WRONG_TERM_CODES["ncit:C17782"]


def test_a_project_carrying_a_wrong_code_is_warned(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\teducation\nsub-01\t2\n")
    sidecar = {
        "education": {
            "Levels": {"2": "Apprenticeship"},
            "Annotations": {
                "Levels": {"2": {"TermURL": "ncit:C17782", "Label": "Apprenticeship"}}
            },
        }
    }
    (tmp_path / "participants.json").write_text(json.dumps(sidecar))

    issues = check_participants_levels(str(tmp_path))

    assert [i[0] for i in issues] == ["WARNING"]
    assert "education" in issues[0][1] and "ncit:C17782" in issues[0][1]
    assert "CDKN1A Gene" in issues[0][1]


def test_a_project_with_correct_codes_is_not_warned(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\tsex\nsub-01\tF\n")
    sidecar = {
        "sex": {
            "Levels": {"F": "Female"},
            "Annotations": {"Levels": {"F": {"TermURL": "snomed:248152002"}}},
        }
    }
    (tmp_path / "participants.json").write_text(json.dumps(sidecar))

    assert check_participants_levels(str(tmp_path)) == []
