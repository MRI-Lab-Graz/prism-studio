"""participants.tsv columns are shared terms (specification v1.5.28, `tables` in entities.schema.json).

Nothing is participants-specific in the code: a table is read like a term modality, plus `termsFrom` and `unitsOptional`.
Design: docs/handouts/2026-11-25-sociodemographics-terms-design.md
"""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "src"))

from src.mappings_coverage import coverage  # noqa: E402
from src.specification import current_specification, load_specification, use_specification  # noqa: E402
from src.term_registry import resolve_column, term_columns  # noqa: E402

TEMPLATE = json.loads((REPO / "official" / "participants.json").read_text(encoding="utf-8"))
NO_TERM = {"participant_id", "medication_details", "psychiatric_diagnosis_details", "neurological_diagnosis_details"}


def _tools(*args):
    r = subprocess.run(
        [sys.executable, str(REPO / "prism_tools.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads(r.stdout)


def test_every_template_column_names_its_term_and_resolves_to_it():
    registry = current_specification().registry_for("participants")
    columns = dict(term_columns(TEMPLATE, "participants"))
    assert set(columns) >= {"age", "sex", "bmi", "medication_details"}
    assert not set(columns) & {"participant_id", "@context", "Technical", "Study", "I18n", "Metadata"}
    for name, definition in columns.items():
        if name in NO_TERM:
            assert "Term" not in definition
            continue
        found = resolve_column(registry, name, definition, None)
        assert found.kind == "term" and found.term["TermID"] == definition["Term"], (name, found.message)


def test_terms_from_adds_body_measures_without_counting_them_twice():
    spec = current_specification()
    assert "height" in spec.registry_for("participants")
    assert "height" not in spec.terms["participants"]
    assert coverage({"participants": spec.terms["participants"]}, spec.mappings_for)["participants"]["total"] == 26


def test_cli_list_and_coverage_include_participants():
    ids = [t["TermID"] for t in _tools("terms", "list", "--modality", "participants", "--json")["terms"]]
    assert "prism:age" in ids
    assert "participants" in _tools("terms", "coverage", "--json")["modalities"]


def test_cli_suggest_finds_a_term_of_terms_from():
    data = _tools("terms", "suggest", "height", "--modality", "participants", "--json")
    assert data["kind"] == "term" or data["similar"] == ["prism:height"], data


def _issues(root, columns):
    from schema_manager import load_all_schemas
    from validator import DatasetValidator

    (root / "participants.json").write_text(json.dumps(columns), encoding="utf-8")
    with use_specification(load_specification(project_root=root)):
        return DatasetValidator(load_all_schemas(str(REPO / "app" / "schemas"))).validate_table_sidecars(str(root))


def test_validator_gives_notices_never_errors(tmp_path):
    issues = _issues(tmp_path, {
        "participant_id": {"Description": "ID"},
        "height": {"Term": "prism:height", "Units": "cm"},
        "arrival_note": {"Description": "free text"},
        "other": {"Term": "prism:not-a-term"},
    })
    assert {level for level, _ in issues} == {"INFO"}, issues
    text = "\n".join(m for _, m in issues)
    assert "arrival_note" in text and "other" in text and "height" not in text and "participant_id" not in text


def test_validate_dataset_reports_participant_notices(tmp_path):
    from runner import validate_dataset

    (tmp_path / "dataset_description.json").write_text('{"Name": "x", "BIDSVersion": "1.8.0"}', encoding="utf-8")
    (tmp_path / "participants.json").write_text(json.dumps({"arrival_note": {"Description": "x"}}), encoding="utf-8")
    issues, _stats = validate_dataset(str(tmp_path), run_bids=False, run_prism=True)
    assert any("arrival_note" in str(issue[1]) for issue in issues), issues


def test_broken_participants_json_does_not_crash(tmp_path):
    (tmp_path / "participants.json").write_text("[not json", encoding="utf-8")
    from validator import DatasetValidator

    assert DatasetValidator({}).validate_table_sidecars(str(tmp_path)) == []


def test_a_project_can_add_and_link_its_own_participant_term(tmp_path):
    sidecar = tmp_path / "participants.json"
    sidecar.write_text(json.dumps({"shoe_size": {"Description": "shoe size", "Units": "EU"}}), encoding="utf-8")
    _tools("spec", "local", "add-term", "--project", str(tmp_path), "--sidecar", str(sidecar),
           "--column", "shoe_size", "--modality", "participants", "--json")
    spec = load_specification(project_root=tmp_path)
    assert "shoe-size" in spec.terms["participants"], spec.overlay_problems
    links = tmp_path / "code" / "specification" / "mappings" / "participants"
    links.mkdir(parents=True, exist_ok=True)
    (links / "mine.json").write_text(json.dumps(
        {"local:shoe-size": {"SameAs": {"loinc": "https://loinc.org/8302-2"}}}), encoding="utf-8")
    assert "participants" in load_specification(project_root=tmp_path).mappings
    _tools("spec", "propose", "--project", str(tmp_path), "--all", "--modality", "participants", "--json")


def test_a_table_has_no_schema_to_extend(tmp_path):
    r = subprocess.run(
        [sys.executable, str(REPO / "prism_tools.py"), "spec", "local", "add-values", "--project", str(tmp_path),
         "--modality", "participants", "--field", "Technical.x", "--value", "y"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert r.returncode == 1 and "Traceback" not in r.stdout + r.stderr, r.stdout + r.stderr


def test_participants_json_written_from_the_template_keeps_the_term():
    from src.converters.survey_participants_logic import _participants_json_from_template

    out = _participants_json_from_template(columns=["participant_id", "education_level"], template=TEMPLATE)
    assert out["education_level"]["Term"] == "prism:education-level"
