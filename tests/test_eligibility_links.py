import json
from pathlib import Path

from src.eligibility import load_criteria
from tests.test_participants_cli import _run_prism_tools

AGE = {"id": "age", "label": "Age", "term": "nb:Age", "type": "numeric",
       "mode": "include", "min": 18, "max": 35, "unit": "years"}


def _project_json(root: Path, criteria):
    ready = {  # the CLI refuses projects without these four
        "Basics": {"Name": "t", "Authors": ["Doe, Jane"], "Keywords": ["a", "b", "c"]},
        "StudyDesign": {"Timepoints": "single"},
    }
    (root / "project.json").write_text(json.dumps({**ready, "Eligibility": {"Criteria": criteria}}))


def test_load_criteria(tmp_path):
    assert load_criteria(str(tmp_path)) == []
    _project_json(tmp_path, [AGE])
    assert load_criteria(str(tmp_path)) == [AGE]


def test_convert_writes_link_through_neurobagel_schema(tmp_path):
    src = tmp_path / "in.tsv"
    src.write_text("participant_id\tage\nP1\t20\nP2\t17\n", encoding="utf-8")
    proj = tmp_path / "proj"
    proj.mkdir()
    result = _run_prism_tools(
        "participants", "convert", "--input", str(src), "--project", str(proj),
        "--neurobagel-schema", json.dumps({"age": {"EligibilityCriterion": "age"}}),
        "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    sidecar = json.loads((proj / "participants.json").read_text(encoding="utf-8"))
    assert sidecar["age"]["EligibilityCriterion"] == "age"


def test_merge_apply_keeps_existing_link(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\tage\nsub-001\t21\n", encoding="utf-8")
    (tmp_path / "participants.json").write_text(json.dumps({
        "participant_id": {"Description": "id"},
        "age": {"Description": "Age", "EligibilityCriterion": "age"},
    }), encoding="utf-8")
    src = tmp_path / "src.csv"
    src.write_text("participant_id,age,group\nsub-001,21,c\nsub-002,22,p\n", encoding="utf-8")
    result = _run_prism_tools(
        "participants", "merge", "--input", str(src), "--project", str(tmp_path),
        "--apply", "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    sidecar = json.loads((tmp_path / "participants.json").read_text(encoding="utf-8"))
    assert sidecar["age"]["EligibilityCriterion"] == "age"


def test_cli_preview_returns_project_criteria(tmp_path):
    _project_json(tmp_path, [AGE])
    src = tmp_path / "in.tsv"
    src.write_text("participant_id\tage\nP1\t20\n", encoding="utf-8")
    result = _run_prism_tools(
        "participants", "preview", "--input", str(src), "--project", str(tmp_path), "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["eligibility_criteria"] == [AGE]


def test_flask_preview_returns_project_criteria(tmp_path):
    from tests.test_participants_session_map_preview import make_client, preview

    client = make_client(tmp_path, {"Eligibility": {"Criteria": [AGE]}})
    assert preview(client).get_json()["eligibility_criteria"] == [AGE]
    (tmp_path / "other").mkdir()
    bare = make_client(tmp_path / "other", {})
    assert preview(bare).get_json()["eligibility_criteria"] == []


# ---- final review: a link must be changeable and clearable on Merge ----

def test_schema_merge_changes_and_clears_a_link_but_keeps_other_keys():
    from src.participants_backend import merge_neurobagel_schema_for_columns as merge

    base = {"age": {"Description": "Age", "EligibilityCriterion": "age"}}
    merged, _ = merge(base, {"age": {"EligibilityCriterion": "iq", "Description": "ignored"}}, ["age"])
    assert merged["age"] == {"Description": "Age", "EligibilityCriterion": "iq"}
    merged, _ = merge(merged, {"age": {"EligibilityCriterion": ""}}, ["age"])
    assert merged["age"] == {"Description": "Age"}
    merged, _ = merge({"age": {}}, {"age": {"EligibilityCriterion": ""}}, ["age"])
    assert "EligibilityCriterion" not in merged["age"]


def test_merge_apply_cli_clears_an_existing_link(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\tage\nsub-001\t21\n", encoding="utf-8")
    (tmp_path / "participants.json").write_text(json.dumps({
        "participant_id": {"Description": "id"},
        "age": {"Description": "Age", "EligibilityCriterion": "age"},
    }), encoding="utf-8")
    src = tmp_path / "src.csv"
    src.write_text("participant_id,age,group\nsub-001,21,c\n", encoding="utf-8")
    result = _run_prism_tools(
        "participants", "merge", "--input", str(src), "--project", str(tmp_path), "--apply",
        "--neurobagel-schema", json.dumps({"age": {"EligibilityCriterion": ""}}), "--json",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    sidecar = json.loads((tmp_path / "participants.json").read_text(encoding="utf-8"))
    assert "EligibilityCriterion" not in sidecar["age"]


def test_flask_merge_preview_returns_project_criteria(tmp_path):
    """Merge/modify is the mode used once a project has participants files; the
    annotation card needs the criteria there too or it shows no link select."""
    import io

    from flask import Flask

    from src.web.blueprints import conversion_participants_blueprint as module

    _project_json(tmp_path, [AGE])
    (tmp_path / "participants.tsv").write_text("participant_id\tage\nsub-001\t21\n", encoding="utf-8")
    (tmp_path / "participants.json").write_text(json.dumps({"age": {"Description": "Age"}}), encoding="utf-8")
    app = Flask(__name__)
    app.secret_key = "test"  # pragma: allowlist secret
    app.register_blueprint(module.conversion_participants_bp)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session["current_project_path"] = str(tmp_path)
    response = client.post(
        "/api/participants-merge",
        data={"mode": "file", "file": (io.BytesIO(b"participant_id,age\nsub-002,22\n"), "d.csv")},
        content_type="multipart/form-data",
    )
    assert response.get_json()["eligibility_criteria"] == [AGE]


def test_flask_modify_existing_preview_returns_project_criteria(tmp_path):
    """Modify (mode=existing) previews the saved participants.tsv, no upload."""
    from tests.test_participants_session_map_preview import make_client

    client = make_client(tmp_path, {"Eligibility": {"Criteria": [AGE]}})
    (client.project / "participants.tsv").write_text("participant_id\tage\nsub-001\t21\n", encoding="utf-8")
    response = client.post("/api/participants-preview", data={"mode": "existing"})
    assert response.get_json()["eligibility_criteria"] == [AGE]
