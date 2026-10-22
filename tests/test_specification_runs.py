"""validate_dataset runs under its own specification (phase 0, Task 2)."""

import json
import os
import sys
import threading
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))
sys.path.insert(0, os.path.dirname(__file__))

from runner import validate_dataset  # noqa: E402
from src.specification import current_specification, official_specification  # noqa: E402
from test_specification import stand_in  # noqa: E402


def _project(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "T", "BIDSVersion": "1.10.1", "DatasetType": "raw", "Authors": ["A", "B"]}), encoding="utf-8")
    (root / "participants.tsv").write_text("participant_id\nsub-01\n", encoding="utf-8")
    return root


def _probe(seen):
    def callback(current, total, message, file_path=None):
        seen.append(current_specification())
    return callback


def test_validate_dataset_runs_under_the_given_specification(tmp_path):
    spec, seen = stand_in(tmp_path / "rules"), []
    validate_dataset(str(_project(tmp_path / "p")), specification=spec, progress_callback=_probe(seen))
    assert seen and all(s is spec for s in seen)
    assert current_specification() is official_specification()  # reset after the run


def test_without_one_the_run_uses_the_official_rules_and_terms_with_the_project_schemas(tmp_path):
    seen, official = [], official_specification()
    validate_dataset(str(_project(tmp_path / "p")), progress_callback=_probe(seen))
    assert seen and all(s.rules is official.rules and s.terms == official.terms and s.schemas == official.schemas for s in seen)


def test_a_run_in_a_worker_thread_uses_its_own_specification(tmp_path):
    spec, seen = stand_in(tmp_path / "rules"), []
    worker = threading.Thread(
        target=lambda: validate_dataset(str(_project(tmp_path / "p")), specification=spec, progress_callback=_probe(seen)))
    worker.start()
    worker.join()
    assert seen and all(s is spec for s in seen)
    assert current_specification() is official_specification()


def test_an_exception_in_the_run_still_resets_the_specification(tmp_path):
    spec = stand_in(tmp_path / "rules")

    def boom(current, total, message, file_path=None):
        raise RuntimeError("boom")

    try:
        validate_dataset(str(_project(tmp_path / "p")), specification=spec, progress_callback=boom)
    except RuntimeError:
        pass
    assert current_specification() is official_specification()


def test_schema_pins_still_select_the_same_schemas(tmp_path):
    project = _project(tmp_path / "p")
    (project / "project.json").write_text(json.dumps({"SchemaVersions": {"biosample": "1.0.0"}}), encoding="utf-8")
    _issues, stats = validate_dataset(str(project))
    versions = stats.validator_info["prism_schema_versions"]
    assert versions["biosample"] == "1.0.0" and versions["survey"] != "1.0.0"
    assert stats.validator_info["prism_schema_sources"]["biosample"] == "project.json"
