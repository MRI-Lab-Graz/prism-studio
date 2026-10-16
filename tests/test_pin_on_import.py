"""Conversions pin the modality versions they wrote (project.json SchemaVersions)."""

import json
import pandas as pd
import pytest

import src.modality_versions as mv
from src.batch_convert import batch_convert_folder
from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
from src.converters.survey import (
    convert_survey_file_to_prism_dataset,
    convert_survey_lsa_to_prism_dataset,
)
from tests.lsa_fixtures import make_library, make_lsa


@pytest.fixture
def pinned_roots(monkeypatch):
    calls = []
    monkeypatch.setattr(mv, "pin_after_import", lambda root: calls.append(str(root)))
    return calls


def _survey_csv(tmp_path):
    path = tmp_path / "s.csv"
    pd.DataFrame(
        {"participant_id": ["001"], "MTESTSQ001": [1], "MTESTSQ002": [2], "MTESTSQ003": [3]}
    ).to_csv(path, index=False)
    return path


def _survey_file(tmp_path, **kw):
    return convert_survey_file_to_prism_dataset(
        input_path=_survey_csv(tmp_path),
        library_dir=make_library(tmp_path),
        output_root=tmp_path / "out",
        survey="wellbeing",
        id_column="participant_id",
        separator=",",
        **kw,
    )


def _lsa(tmp_path, **kw):
    return convert_survey_lsa_to_prism_dataset(
        input_path=make_lsa(tmp_path),
        library_dir=make_library(tmp_path),
        output_root=tmp_path / "out",
        id_column="token",
        duplicate_handling="sessions",
        **kw,
    )


def test_survey_file_pins(tmp_path, pinned_roots):
    _survey_file(tmp_path)
    assert pinned_roots == [str(tmp_path / "out")]


def test_survey_file_dry_run_does_not_pin(tmp_path, pinned_roots):
    _survey_file(tmp_path, dry_run=True)
    assert pinned_roots == []


def test_survey_lsa_pins(tmp_path, pinned_roots):
    _lsa(tmp_path)
    assert pinned_roots == [str(tmp_path / "out")]


def test_survey_lsa_dry_run_does_not_pin(tmp_path, pinned_roots):
    _lsa(tmp_path, dry_run=True)
    assert pinned_roots == []


def test_biometrics_pins(tmp_path, pinned_roots):
    library = tmp_path / "library"
    library.mkdir()
    (library / "biometrics-grip.json").write_text(json.dumps({"grip_left": {"unit": "kg"}, "Study": {}}))
    data = tmp_path / "data.csv"
    pd.DataFrame({"participant_id": ["001"], "grip_left": [40.0]}).to_csv(data, index=False)
    out = tmp_path / "output"

    convert_biometrics_table_to_prism_dataset(input_path=data, library_dir=library, output_root=out)

    assert pinned_roots == [str(out.resolve())]


def test_batch_convert_pins(tmp_path, pinned_roots):
    src = tmp_path / "source"
    src.mkdir()
    (src / "sub-001_task-rest.edf").write_bytes(b"fake edf")
    out = tmp_path / "output"

    batch_convert_folder(src, out, modality_filter="physio")

    assert pinned_roots == [str(out)]


def test_batch_convert_dry_run_does_not_pin(tmp_path, pinned_roots):
    src = tmp_path / "source"
    src.mkdir()
    (src / "sub-001_task-rest.edf").write_bytes(b"fake edf")

    batch_convert_folder(src, tmp_path / "output", modality_filter="physio", dry_run=True)

    assert pinned_roots == []


def _run_environment(monkeypatch, tmp_path, *, persist):
    """perform_environment_conversion with the table/provider work stubbed out."""
    import src.environment_conversion as ec

    proj = tmp_path / "proj"
    proj.mkdir()
    data = tmp_path / "env.csv"
    data.write_text("a\n1\n")
    monkeypatch.setattr(ec, "_load_environment_dataframe", lambda *a, **k: pd.DataFrame({"t": ["2026-01-01 10:00:00"]}))
    monkeypatch.setattr(ec, "_fetch_environment_day", lambda *a, **k: ({"weather": {}, "air": {}, "pollen": {}}, []))
    monkeypatch.setattr(ec, "handle_validate_environment_conversion_inputs", lambda **k: None)
    monkeypatch.setattr(ec, "handle_persist_environment_outputs", persist)
    ec.perform_environment_conversion(
        input_path=data, filename="env.csv", suffix=".csv", separator_option="auto",
        timestamp_col="t", participant_col=None, participant_override=None,
        session_col=None, session_override=None, location_col=None, lat_col=None,
        lon_col=None, location_label_override="", lat_manual=47.0, lon_manual=15.0,
        project_path=str(proj), pilot_random_subject=False,
        log_callback=lambda *a, **k: None,
    )
    return proj


def test_environment_conversion_pins_the_project(tmp_path, monkeypatch, pinned_roots):
    proj = _run_environment(monkeypatch, tmp_path, persist=lambda **k: ([], tmp_path / "x.json"))
    assert pinned_roots == [str(proj.resolve())]


def test_failed_environment_conversion_does_not_pin(tmp_path, monkeypatch, pinned_roots):
    def boom(**k):
        raise ValueError("write failed")

    with pytest.raises(ValueError):
        _run_environment(monkeypatch, tmp_path, persist=boom)
    assert pinned_roots == []


def _copy_project(tmp_path):
    from src.datalad_project_copy import copy_files_into_project

    proj = tmp_path / "proj"
    (proj).mkdir()
    (proj / "project.json").write_text("{}")
    f = tmp_path / "sub-01_task-x_survey.tsv"
    f.write_text("a\n1\n")
    return proj, f, copy_files_into_project


def test_copy_into_project_pins_copied_modality(tmp_path):
    proj, f, copy = _copy_project(tmp_path)
    r = copy(
        dataset_root=proj,
        copy_pairs=[(f, proj / "sub-01" / "survey" / f.name)],
        run_message="m",
    )
    assert r["copied_count"] == 1
    assert mv.read_pins(proj)[0] == {"survey": mv.current_version("survey")}


def test_copy_nothing_leaves_project_json_untouched(tmp_path, pinned_roots):
    proj, _, copy = _copy_project(tmp_path)
    before = (proj / "project.json").read_text()
    assert copy(dataset_root=proj, copy_pairs=[], run_message="m")["copied_count"] == 0
    assert (proj / "project.json").read_text() == before
    assert pinned_roots == []


def test_real_pin_records_the_current_survey_version(tmp_path):
    (tmp_path / "project.json").write_text("{}")
    sub = tmp_path / "sub-01" / "survey"
    sub.mkdir(parents=True)
    (sub / "sub-01_task-x_survey.tsv").write_text("a\n1\n")

    mv.pin_after_import(tmp_path)

    assert mv.read_pins(tmp_path)[0]["survey"] == mv.current_version("survey")
