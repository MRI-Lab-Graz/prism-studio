import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import jsonschema

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    build_example_sidecar,
    build_modality_artifacts,
    build_registration_md,
    build_schema,
    read_proposal,
    registration_entry,
)

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
PROPOSAL = EXAMPLE_DIR / "bloodwork.yml"
SAMPLE = EXAMPLE_DIR / "bloodwork_sample.tsv"


STABLE = Path(__file__).resolve().parents[1] / "app" / "schemas" / "stable"


TERMS = STABLE.parents[2] / "official" / "library" / "terms"


def _conventions_problems(terms_dir: Path) -> list[str]:
    """The vendored check, given Studio's terms folder (its main() looks for <repo>/terms: Ruling 13)."""
    from src.spec_overlay import _vendored

    entities = json.loads((STABLE / "entities.schema.json").read_text(encoding="utf-8"))
    return _vendored("check_modalities").check(entities, STABLE, terms_dir)


def test_the_vendored_conventions_check_passes_on_studios_copy() -> None:
    assert TERMS.is_dir() and _conventions_problems(TERMS) == []


def test_the_conventions_check_sees_a_terms_folder_without_a_declaration(tmp_path) -> None:
    shutil.copytree(TERMS, tmp_path / "terms")
    (tmp_path / "terms" / "survey").mkdir()
    shutil.rmtree(tmp_path / "terms" / "environment")
    problems = _conventions_problems(tmp_path / "terms")
    assert any(p.startswith("survey:") for p in problems) and any(p.startswith("environment:") for p in problems)


def test_registration_entry_carries_description_and_described_columns() -> None:
    p = read_proposal(PROPOSAL)
    entry = registration_entry({**p, "extensions": ["tsv"], "description": "Venous blood samples"})
    assert entry["description"] == "Venous blood samples" and entry["describedColumns"] is True
    assert registration_entry({**p, "extensions": ["json"]})["describedColumns"] is False


def test_registration_steps_point_to_prism_specification() -> None:
    p = read_proposal(PROPOSAL)
    for text in (build_registration_md(p), build_registration_md(p, {"suffixes": ["x"], "extensions": ["tsv"]})):
        assert "prism-specification" in text and "sync_specification.py --tag" in text
        assert "check_modalities.py" in text and "schemas/stable/entities.schema.json" in text
        assert "app/schemas/stable/entities.schema.json" not in text and "docs/specs/entities.md" not in text
    new = build_registration_md(p)
    assert "schemas/stable/bloodwork.schema.json" in new and "specs/bloodwork.md" in new


def test_example_sidecar_validates_against_generated_schema() -> None:
    p = read_proposal(PROPOSAL)
    sidecar = build_example_sidecar(p, today="2026-10-15")
    jsonschema.Draft7Validator(build_schema(p)).validate(sidecar)
    assert sidecar["Technical"]["FileFormat"] == "tsv"
    assert "TaskName" not in sidecar["Study"]
    assert sidecar["Metadata"]["CreationDate"] == "2026-10-15"
    assert sidecar["crp"] == {
        "Description": "C-reactive protein",
        "Units": "mg/L",
        "MinValue": 0.0,
        "DataType": "float",
        "MeasurementScale": "continuous",
        "Type": "CRP",
    }
    assert sidecar["fasting"]["AllowedValues"] == ["yes", "no"]
    assert sidecar["fasting"]["MeasurementScale"] == "boolean"
    assert "MeasurementScale" not in sidecar["sample_id"]


def test_schema_rejects_a_sidecar_column_without_units() -> None:
    p = read_proposal(PROPOSAL)
    sidecar = build_example_sidecar(p, today="2026-10-15")
    del sidecar["crp"]["Units"]
    errors = list(jsonschema.Draft7Validator(build_schema(p)).iter_errors(sidecar))
    assert errors


def test_schema_rejects_an_unknown_measurement_scale() -> None:
    p = read_proposal(PROPOSAL)
    sidecar = build_example_sidecar(p, today="2026-10-15")
    sidecar["crp"]["MeasurementScale"] = "ordinal"
    assert list(jsonschema.Draft7Validator(build_schema(p)).iter_errors(sidecar))


def test_registration_entry_and_markdown() -> None:
    p = read_proposal(PROPOSAL)
    assert registration_entry(p) == {
        "kind": "prism",
        "description": p["description"],
        "describedColumns": True,
        "suffixes": ["bloodchem"],
        "extensions": ["tsv", "json"],
        "allowedEntities": ["task", "acq", "run"],
        "optionalEntityValues": {
            "acq": {"enum": ["fasting", "nonfasting"], "allowOther": True, "otherPattern": "[a-zA-Z0-9]+"},
        },
    }
    md = build_registration_md(p)
    assert "bloodwork.schema.json" in md and "entities.schema.json" in md
    assert '"bloodwork"' in md and '"bloodchem"' in md
    assert "fixture" in md


def test_build_writes_every_artifact(tmp_path: Path) -> None:
    p = read_proposal(PROPOSAL)
    out = tmp_path / "out"
    written = build_modality_artifacts(p, SAMPLE, PROPOSAL, out)

    assert (out / "bloodwork.schema.json").is_file()
    assert (out / "example_sidecar.json").is_file()
    assert (out / "REGISTRATION.md").is_file()
    assert (out / "proposal.yml").is_file()
    assert (out / "sample.tsv").is_file()
    data = out / "fixture" / "sub-01" / "bloodwork" / "sub-01_bloodchem.tsv"
    assert data.read_bytes() == SAMPLE.read_bytes()
    assert data.with_suffix(".json").is_file()
    assert (out / "fixture" / "dataset_description.json").is_file()
    assert all(w.is_file() for w in written)
    assert data in written


def test_registration_md_step5_runs_prism_from_repository_root(tmp_path: Path) -> None:
    md = build_registration_md(read_proposal(PROPOSAL))
    assert "prism.py" in md and "repository root" in md
    assert "run from this folder" not in md


def test_fixture_sidecar_file_format_matches_compound_sample(tmp_path: Path) -> None:
    import gzip

    p = read_proposal(PROPOSAL)
    p["extensions"] = ["tsv", "tsv.gz"]
    sample = tmp_path / "SAMPLE.TSV.GZ"
    sample.write_bytes(gzip.compress(SAMPLE.read_bytes()))
    out = tmp_path / "out"
    build_modality_artifacts(p, sample, PROPOSAL, out)

    data = list((out / "fixture").rglob("*_bloodchem.tsv.gz"))
    assert len(data) == 1
    fixture_sidecar = json.loads(next((out / "fixture").rglob("*_bloodchem.json")).read_text())
    example = json.loads((out / "example_sidecar.json").read_text())
    assert fixture_sidecar["Technical"]["FileFormat"] == "tsv.gz"
    assert example["Technical"]["FileFormat"] == "tsv.gz"
    schema = json.loads((out / "bloodwork.schema.json").read_text())
    jsonschema.Draft7Validator(schema).validate(fixture_sidecar)
