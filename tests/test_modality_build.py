import importlib.util
import json
import os
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


def _load_verify_repo_module():
    module_path = Path(__file__).with_name("verify_repo.py")
    spec = importlib.util.spec_from_file_location("verify_repo", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_schema_passes_the_modality_conventions_check(tmp_path: Path, capsys) -> None:
    p = read_proposal(PROPOSAL)
    schema_dir = tmp_path / "app" / "schemas" / "stable"
    schema_dir.mkdir(parents=True)
    (schema_dir / "bloodwork.schema.json").write_text(json.dumps(build_schema(p)), encoding="utf-8")

    verify_repo = _load_verify_repo_module()
    verify_repo.COMMUNITY_MODALITY_SCHEMAS = {"bloodwork"}
    verify_repo.check_modality_schema_conventions(str(tmp_path))
    out = capsys.readouterr().out

    assert "[✗]" not in out
    assert "follow PRISM conventions" in out


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
        "suffixes": ["bloodchem"],
        "extensions": ["tsv", "json"],
        "allowedEntities": ["task", "acq", "run"],
        "optionalEntityValues": {
            "acq": {"enum": ["fasting", "nonfasting"], "allowOther": True, "otherPattern": "[a-zA-Z0-9]+"},
        },
    }
    md = build_registration_md(p)
    assert "app/schemas/stable/bloodwork.schema.json" in md
    assert "entities.schema.json" in md
    assert "COMMUNITY_MODALITY_SCHEMAS" in md
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
