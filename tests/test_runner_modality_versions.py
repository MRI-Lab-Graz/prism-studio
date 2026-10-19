import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app" / "src"))

import runner  # noqa: E402
from src.modality_versions import ModalityVersionError  # noqa: E402


@pytest.fixture
def schema_dir(tmp_path):
    dest = tmp_path / "schemas"
    shutil.copytree(REPO / "app" / "schemas", dest)
    stable = json.loads((dest / "stable" / "survey.schema.json").read_text())
    current = stable["version"]
    old = dict(stable, version="0.9.0")
    (dest / "archive" / "survey").mkdir(parents=True)
    (dest / "archive" / "survey" / "0.9.0.schema.json").write_text(json.dumps(old))
    return str(dest), current


def _project(tmp_path: Path, pins=None) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    payload = {"Metadata": {"SchemaVersion": "1.0.0"}}
    if pins is not None:
        payload["SchemaVersions"] = pins
    (root / "project.json").write_text(json.dumps(payload))
    return root


def test_no_pins_means_latest(tmp_path, schema_dir):
    sdir, current = schema_dir
    schemas, sources = runner._load_schemas(_project(tmp_path), None, None, sdir)
    assert schemas["survey"]["_validator_info"]["schema_version"] == current
    assert set(sources.values()) == {"latest"}


def test_project_pin_selects_the_archived_version(tmp_path, schema_dir):
    sdir, _ = schema_dir
    schemas, sources = runner._load_schemas(_project(tmp_path, {"survey": "0.9.0"}), None, None, sdir)
    assert schemas["survey"]["_validator_info"]["schema_version"] == "0.9.0"
    assert sources["survey"] == "project.json"


def test_cli_override_beats_the_pin(tmp_path, schema_dir):
    sdir, current = schema_dir
    schemas, sources = runner._load_schemas(
        _project(tmp_path, {"survey": "0.9.0"}), None, {"survey": current}, sdir)
    assert schemas["survey"]["_validator_info"]["schema_version"] == current
    assert sources["survey"] == "cli"


def test_pins_are_ignored_on_a_legacy_base_but_overrides_apply(tmp_path, schema_dir):
    sdir, _ = schema_dir
    root = _project(tmp_path, {"survey": "0.9.0"})
    _, sources = runner._load_schemas(root, "v0.2", None, sdir)
    assert sources["survey"] == "latest"
    _, sources = runner._load_schemas(root, "v0.2", {"survey": "0.9.0"}, sdir)
    assert sources["survey"] == "cli"


def test_broken_or_missing_project_json_means_latest(tmp_path, schema_dir):
    sdir, current = schema_dir
    root = tmp_path / "p2"
    root.mkdir()
    (root / "project.json").write_text("{not json")
    schemas, _ = runner._load_schemas(root, None, None, sdir)
    assert schemas["survey"]["_validator_info"]["schema_version"] == current


def test_unavailable_pinned_version_is_an_error(tmp_path, schema_dir):
    sdir, _ = schema_dir
    with pytest.raises(ModalityVersionError, match="0.9.0"):
        runner._load_schemas(_project(tmp_path, {"survey": "7.7.7"}), None, None, sdir)


def test_validate_dataset_reports_an_unavailable_pin_as_one_error(tmp_path, monkeypatch, schema_dir):
    sdir, _ = schema_dir
    monkeypatch.setattr(runner, "_default_schema_dir", lambda: sdir)
    root = _project(tmp_path, {"survey": "7.7.7"})
    issues, _ = runner.validate_dataset(str(root), run_bids=False)
    assert [i for i in issues if i[0] == "ERROR" and "7.7.7" in i[1]]


def test_validator_info_records_where_each_version_came_from(tmp_path, monkeypatch, schema_dir):
    sdir, _ = schema_dir
    monkeypatch.setattr(runner, "_default_schema_dir", lambda: sdir)
    root = _project(tmp_path, {"survey": "0.9.0"})
    _, stats = runner.validate_dataset(str(root), run_bids=False)
    assert stats.validator_info["prism_schema_sources"]["survey"] == "project.json"
    assert stats.validator_info["prism_schema_versions"]["survey"] == "0.9.0"
