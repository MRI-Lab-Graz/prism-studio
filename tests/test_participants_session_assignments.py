"""Participants import: the project's session decisions are applied automatically."""

import pandas as pd

from src.participants_converter import ParticipantsConverter, load_participant_source
from src.session_assignments import set_assignment

ROWS = [
    {"id": "1", "token": "a", "startdate": "2026-03-01 09:00:00", "submitdate": "", "age": 29},
    {"id": "2", "token": "a", "startdate": "2026-03-01 11:00:00", "submitdate": "x", "age": 30},
    {"id": "3", "token": "a", "startdate": "2026-09-01 10:00:00", "submitdate": "x", "age": 31},
    {"id": "4", "token": "b", "startdate": "2026-03-02 10:00:00", "submitdate": "x", "age": 40},
]
MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "token", "standard_variable": "participant_id", "type": "string"},
        "age": {"source_column": "age", "standard_variable": "age", "type": "string"},
    },
}


def _csv(tmp_path):
    path = tmp_path / "in.csv"
    pd.DataFrame(ROWS).to_csv(path, index=False)
    return path


def test_loader_leaves_out_the_incomplete_response(tmp_path):
    df, _ = load_participant_source(_csv(tmp_path), sessions_from_date="startdate", id_column="token")

    assert sorted(zip(df["id"].astype(str), df["session"])) == [("2", "1"), ("3", "2"), ("4", "1")]


def test_loader_applies_decisions(tmp_path):
    df, _ = load_participant_source(
        _csv(tmp_path), sessions_from_date="startdate", id_column="token",
        decisions={"2": {"skip": True}},
    )

    assert sorted(zip(df["id"].astype(str), df["session"])) == [("3", "1"), ("4", "1")]


def test_convert_reads_the_project_decisions_file(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    set_assignment(project, "2", skip=True)  # drop a's first completed response

    ok, df, messages = ParticipantsConverter(project).convert_participant_data(
        _csv(tmp_path), MAPPING, output_file=project / "participants.tsv",
        sessions_from_date="startdate", session_column="session", session_value="1",
        reject_conflicting_repeats=True,
    )

    assert ok, messages
    assert dict(zip(df["participant_id"], df["age"].astype(str))) == {"sub-a": "31", "sub-b": "40"}


def test_convert_ignores_decisions_saved_for_another_survey(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    set_assignment(project, "2", survey_id="999999", skip=True)  # a CSV is "default", not that survey

    ok, df, messages = ParticipantsConverter(project).convert_participant_data(
        _csv(tmp_path), MAPPING, output_file=project / "participants.tsv",
        sessions_from_date="startdate", session_column="session", session_value="1",
        reject_conflicting_repeats=True,
    )

    assert ok, messages
    assert dict(zip(df["participant_id"], df["age"].astype(str))) == {"sub-a": "30", "sub-b": "40"}


# --- GUI preview, CLI preview, corrupt decisions file ---------------------------------

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

CSV = (
    "id,token,startdate,submitdate,age\n"
    "1,a,2026-03-01 10:00:00,x,30\n"
    "2,a,2026-09-01 10:00:00,x,31\n"
    "3,b,2026-03-02 10:00:00,x,40\n"
)
REPO = Path(__file__).resolve().parent.parent


def _project_with_skip(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps({
        "Basics": {"Name": "x", "Authors": ["A"], "Keywords": ["k"]},
        "StudyDesign": {"Timepoints": "single"},
    }), encoding="utf-8")
    set_assignment(project, "2", skip=True)
    return project


def test_gui_preview_applies_the_project_decisions(tmp_path):
    from flask import Flask

    from src.web.blueprints import conversion_participants_blueprint as module

    project = _project_with_skip(tmp_path)
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(module.conversion_participants_bp)
    client = app.test_client()
    with client.session_transaction() as s:
        s["current_project_path"] = str(project)

    payload = client.post(
        "/api/participants-preview",
        data={"mode": "file", "file": (io.BytesIO(CSV.encode()), "d.csv"),
              "id_column": "token", "sessions_from_date": "startdate"},
        content_type="multipart/form-data",
    ).get_json()

    assert payload["participant_count"] == 2
    assert all("2" not in c["values"] for c in payload["session_candidates"])


def test_gui_preview_ignores_decisions_saved_for_another_survey(tmp_path):
    from flask import Flask

    from src.web.blueprints import conversion_participants_blueprint as module

    project = tmp_path / "proj"
    project.mkdir()
    (project / "project.json").write_text(json.dumps({
        "Basics": {"Name": "x", "Authors": ["A"], "Keywords": ["k"]},
        "StudyDesign": {"Timepoints": "single"},
    }), encoding="utf-8")
    set_assignment(project, "2", survey_id="999999", skip=True)
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(module.conversion_participants_bp)
    client = app.test_client()
    with client.session_transaction() as s:
        s["current_project_path"] = str(project)

    payload = client.post(
        "/api/participants-preview",
        data={"mode": "file", "file": (io.BytesIO(CSV.encode()), "d.csv"),
              "id_column": "token", "sessions_from_date": "startdate"},
        content_type="multipart/form-data",
    ).get_json()

    assert payload["participant_count"] == 2
    assert any("2" in c["values"] for c in payload["session_candidates"])


def test_cli_preview_applies_the_project_decisions(tmp_path):
    project = _project_with_skip(tmp_path)
    source = tmp_path / "in.csv"
    source.write_text(CSV, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(REPO / "app" / "prism_tools.py"), "participants", "preview",
         "--input", str(source), "--project", str(project), "--id-column", "token",
         "--sessions-from-date", "startdate", "--json"],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO), timeout=60,
    )

    payload = json.loads(result.stdout)
    assert payload["participant_count"] == 2
    assert all("2" not in c["values"] for c in payload["session_candidates"])


def test_corrupt_decisions_file_is_not_reported_as_a_repeated_row_conflict(tmp_path):
    from src.participants_backend import preview_participants_merge

    project = tmp_path / "proj"
    (project / "code").mkdir(parents=True)
    (project / "code" / "session_assignments.json").write_text(
        '{"version": 2, "surveys": {"default": {"responses": {"1": {"skip": "yes"}}}}}', encoding="utf-8"
    )
    (project / "participants.tsv").write_text("participant_id\tage\nsub-b\t40\n", encoding="utf-8")
    source = tmp_path / "in.csv"
    source.write_text(CSV, encoding="utf-8")

    with pytest.raises(ValueError, match="session_assignments.json"):
        preview_participants_merge(project, source, MAPPING, sessions_from_date="startdate")
