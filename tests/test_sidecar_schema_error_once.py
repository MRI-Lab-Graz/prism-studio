"""A broken sidecar is one problem, not one per data file; an outdated pin is named."""

import json

from src.modality_versions import _write_pins
from src.runner import validate_dataset


def test_sidecar_schema_error_is_reported_once_and_names_the_newer_schema(tmp_path):
    (tmp_path / "dataset_description.json").write_text(json.dumps({"Name": "x", "BIDSVersion": "1.10.1"}))
    (tmp_path / "project.json").write_text("{}")
    _write_pins(tmp_path, {"biometrics": "1.1.3"}, {"biometrics": "1.1.3"})
    (tmp_path / "task-cmj_biometrics.json").write_text(json.dumps({"Study": {"Category": "muscular-power"}}))
    for sub in ("sub-01", "sub-02", "sub-03"):
        folder = tmp_path / sub / "biometrics"
        folder.mkdir(parents=True)
        (folder / f"{sub}_task-cmj_biometrics.tsv").write_text("height\n1\n")

    issues, _stats = validate_dataset(str(tmp_path), run_bids=False)

    schema_errors = [str(i[1]) for i in issues if "cmj_biometrics.json schema error" in str(i[1])]
    assert len(schema_errors) == 1, schema_errors
    assert "modality-version update" in schema_errors[0]
