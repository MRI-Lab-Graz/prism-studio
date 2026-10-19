"""Conversions pin the modality versions they wrote (project.json SchemaVersions)."""

import json
from pathlib import Path
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


def _datalad_copy(tmp_path, monkeypatch, *, pre_pinned=False, save_raises=False, save_result=None):
    """DataLad-branch copy of a survey file; returns (result, recorded save calls)."""
    import src.datalad_project_copy as dpc

    proj = tmp_path / "proj"
    (proj / ".datalad").mkdir(parents=True)
    pins = {"SchemaVersions": {"survey": "1.0.0"}} if pre_pinned else {}
    (proj / "project.json").write_text(json.dumps(pins))
    src = tmp_path / "sub-01_task-x_survey.tsv"
    src.write_text("a\n1\n")
    dst = proj / "sub-01" / "survey" / src.name

    def fake_mutation(root, **kw):
        dst.parent.mkdir(parents=True)
        dst.write_text("a\n1\n")
        return {"run": {"stdout": json.dumps({"copied_count": 1, "copied_paths": [str(dst.relative_to(proj))]})}}

    saves = []

    def fake_save(root, **kw):
        saves.append(kw)
        if save_raises:
            raise RuntimeError("save failed")
        return save_result if save_result is not None else {"success": True}

    monkeypatch.setattr(dpc, "run_tracked_mutation", fake_mutation)
    monkeypatch.setattr(dpc, "run_datalad_save", fake_save)
    result = dpc.copy_files_into_project(dataset_root=proj, copy_pairs=[(src, dst)], run_message="PRISM: copy")
    return result, saves


def test_datalad_copy_commits_project_json_after_pinning(tmp_path, monkeypatch):
    result, saves = _datalad_copy(tmp_path, monkeypatch)
    assert result["copied_count"] == 1
    assert len(saves) == 1 and saves[0]["paths"] == ["project.json"] and saves[0]["recursive"] is False


def test_datalad_copy_save_failure_only_warns(tmp_path, monkeypatch, capsys):
    result, saves = _datalad_copy(tmp_path, monkeypatch, save_raises=True)
    assert result["copied_count"] == 1
    assert "project.json" in capsys.readouterr().err


def test_datalad_copy_does_not_save_when_nothing_was_pinned(tmp_path, monkeypatch):
    _, saves = _datalad_copy(tmp_path, monkeypatch, pre_pinned=True)
    assert saves == []


def test_datalad_copy_unsuccessful_save_result_warns(tmp_path, monkeypatch, capsys):
    result, saves = _datalad_copy(tmp_path, monkeypatch, save_result={"success": False, "message": "boom"})
    assert result["copied_count"] == 1
    err = capsys.readouterr().err
    assert "project.json" in err and "boom" in err


def _physio_args(tmp_path):
    from argparse import Namespace

    src = tmp_path / "in" / "sub-01" / "ses-1"
    src.mkdir(parents=True)
    (src / "a.raw").write_bytes(b"RAW")
    return Namespace(input=str(tmp_path / "in"), output=str(tmp_path / "out"), task="rest",
                     suffix="physio", sampling_rate=None)


def _fake_varioport(monkeypatch, *, write):
    def fake(input_path, output_edf, output_json, **k):
        if write:
            Path(output_edf).write_bytes(b"x" * 20000)
            Path(output_json).write_text("{}", encoding="utf-8")

    monkeypatch.setattr("src.cli.commands.convert.convert_varioport", fake)


def test_convert_physio_pins_the_output(tmp_path, monkeypatch, pinned_roots):
    from src.cli.commands.convert import cmd_convert_physio

    _fake_varioport(monkeypatch, write=True)
    cmd_convert_physio(_physio_args(tmp_path))
    assert pinned_roots == [str(tmp_path / "out")]


def test_convert_physio_nothing_converted_does_not_pin(tmp_path, monkeypatch, pinned_roots):
    from src.cli.commands.convert import cmd_convert_physio

    _fake_varioport(monkeypatch, write=False)
    cmd_convert_physio(_physio_args(tmp_path))
    assert pinned_roots == []
