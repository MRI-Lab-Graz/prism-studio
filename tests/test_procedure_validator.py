import json
from pathlib import Path

from app.src.procedure_validator import validate_procedure


def _write_project_json(project_root: Path, payload: dict) -> None:
    (project_root / "project.json").write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def test_validate_procedure_skips_warnings_when_sessions_metadata_missing(
    tmp_path: Path,
) -> None:
    _write_project_json(tmp_path, {"Basics": {"Name": "Demo"}})

    survey_dir = tmp_path / "sub-01" / "ses-01" / "survey"
    survey_dir.mkdir(parents=True)
    (survey_dir / "sub-01_ses-01_task-ads_beh.tsv").write_text(
        "participant_id\tvalue\nsub-01\t1\n",
        encoding="utf-8",
    )

    issues = validate_procedure(tmp_path, tmp_path)

    assert issues == []