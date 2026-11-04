"""Every conversion lists the subjects it wrote in participants.tsv (a folder without a row fails validation)."""

import json

import pandas as pd
import pytest

from src.batch_convert import batch_convert_folder
from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
from src.converters.survey import convert_survey_file_to_prism_dataset, convert_survey_lsa_to_prism_dataset
from src.utils.io import register_subjects
from tests.lsa_fixtures import make_library, make_lsa


def _ids(root):
    lines = (root / "participants.tsv").read_text().splitlines()
    return [line.split("\t")[0] for line in lines[1:]]


def _folders(root):
    return sorted(p.name for p in root.glob("sub-*") if p.is_dir())


def test_the_given_subjects_get_a_row_and_existing_rows_stay(tmp_path):
    (tmp_path / "participants.tsv").write_text("participant_id\tage\nsub-001\t24\nsub-009\t30\n")
    register_subjects(tmp_path, ["sub-001", "sub-002"])
    assert _ids(tmp_path) == ["sub-001", "sub-002", "sub-009"]  # sub-009: screened, no folder - stays
    assert "sub-001\t24" in (tmp_path / "participants.tsv").read_text()


def test_other_folders_are_not_registered_by_a_conversion(tmp_path):
    (tmp_path / "sub-pilot").mkdir()
    register_subjects(tmp_path, ["sub-001"])
    assert _ids(tmp_path) == ["sub-001"]


def test_an_id_that_is_not_a_valid_subject_label_is_left_for_the_validator(tmp_path):
    register_subjects(tmp_path, ["sub-001", "sub-Müller", "sub-a_b", "", None])
    assert _ids(tmp_path) == ["sub-001"]


def test_nothing_is_written_for_no_subjects(tmp_path):
    register_subjects(tmp_path, [])
    assert not (tmp_path / "participants.tsv").exists()


def _survey_csv(tmp_path):
    path = tmp_path / "s.csv"
    pd.DataFrame(
        {"participant_id": ["001", "002"], "MTESTSQ001": [1, 1], "MTESTSQ002": [2, 2], "MTESTSQ003": [3, 3]}
    ).to_csv(path, index=False)
    return path


def test_survey_conversion_registers_its_subjects(tmp_path):
    out = tmp_path / "out"
    convert_survey_file_to_prism_dataset(
        input_path=_survey_csv(tmp_path), library_dir=make_library(tmp_path), output_root=out,
        survey="wellbeing", id_column="participant_id", separator=",",
    )
    assert _ids(out) == _folders(out) == ["sub-001", "sub-002"]


def test_survey_dry_run_writes_nothing(tmp_path):
    out = tmp_path / "out"
    convert_survey_file_to_prism_dataset(
        input_path=_survey_csv(tmp_path), library_dir=make_library(tmp_path), output_root=out,
        survey="wellbeing", id_column="participant_id", separator=",", dry_run=True,
    )
    assert not (out / "participants.tsv").exists()


def test_lsa_conversion_registers_its_subjects(tmp_path):
    out = tmp_path / "out"
    convert_survey_lsa_to_prism_dataset(
        input_path=make_lsa(tmp_path), library_dir=make_library(tmp_path), output_root=out,
        id_column="token", duplicate_handling="sessions",
    )
    assert _folders(out) and _ids(out) == _folders(out)


def test_biometrics_conversion_registers_its_subjects(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    (library / "biometrics-grip.json").write_text(json.dumps({"grip_left": {"unit": "kg"}, "Study": {}}))
    data = tmp_path / "data.csv"
    pd.DataFrame({"participant_id": ["001", "002"], "grip_left": [40.0, 41.0]}).to_csv(data, index=False)
    out = tmp_path / "output"
    convert_biometrics_table_to_prism_dataset(input_path=data, library_dir=library, output_root=out, skip_participants=True)
    assert _ids(out) == _folders(out) == ["sub-001", "sub-002"]


def test_batch_conversion_registers_its_subjects(tmp_path):
    src = tmp_path / "source"
    src.mkdir()
    (src / "sub-001.edf").write_bytes(b"fake edf")
    out = tmp_path / "output"
    batch_convert_folder(src, out, modality_filter="physio")
    assert _ids(out) == _folders(out)


def test_environment_conversion_registers_the_project(tmp_path, monkeypatch):
    import src.environment_conversion as ec
    import src.utils.io as io

    calls = []
    monkeypatch.setattr(io, "register_subjects", lambda root, ids, *a, **k: calls.append((str(root), sorted(set(ids)))))
    proj = tmp_path / "proj"
    proj.mkdir()
    data = tmp_path / "env.csv"
    data.write_text("a\n1\n")
    monkeypatch.setattr(ec, "_load_environment_dataframe", lambda *a, **k: pd.DataFrame({"t": ["2026-01-01 10:00:00"]}))
    monkeypatch.setattr(ec, "_fetch_environment_day", lambda *a, **k: ({"weather": {}, "air": {}, "pollen": {}}, []))
    monkeypatch.setattr(ec, "handle_validate_environment_conversion_inputs", lambda **k: None)
    monkeypatch.setattr(ec, "handle_persist_environment_outputs", lambda **k: ([], tmp_path / "x.json"))
    ec.perform_environment_conversion(
        input_path=data, filename="env.csv", suffix=".csv", separator_option="auto",
        timestamp_col="t", participant_col=None, participant_override=None,
        session_col=None, session_override=None, location_col=None, lat_col=None,
        lon_col=None, location_label_override="", lat_manual=47.0, lon_manual=15.0,
        project_path=str(proj), pilot_random_subject=False,
        log_callback=lambda *a, **k: None,
    )
    assert len(calls) == 1 and calls[0][0] == str(proj.resolve()) and calls[0][1]  # the subject of the table
