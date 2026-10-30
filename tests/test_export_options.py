"""Project export: the options, the file name and the validation gate are one backend function for Studio and the CLI."""

from pathlib import Path

import pytest

from src import export_options as eo


def test_the_defaults_are_a_standard_anonymized_export_with_code_and_derivatives():
    kwargs = eo.build_export_kwargs({})
    assert kwargs["anonymize"] is True and kwargs["mask_questions"] is True
    assert (kwargs["include_derivatives"], kwargs["include_code"]) == (True, True)
    assert (kwargs["include_sourcedata"], kwargs["include_analysis"]) == (False, False)
    assert kwargs["id_length"] == 8 and kwargs["deterministic"] is True
    assert kwargs["exclude_subjects"] is None and kwargs["scrub_mri_json"] is False


def test_the_upload_ready_preset_leaves_out_everything_but_the_data_and_strips_version_control():
    kwargs = eo.build_export_kwargs({"export_preset": "upload_ready", "include_code": True, "include_sourcedata": True})
    assert not any(kwargs[k] for k in ("include_derivatives", "include_sourcedata", "include_code", "include_analysis"))
    assert kwargs["exclude_version_control_metadata"] is True


@pytest.mark.parametrize("data, expected", [
    ({"repository_mode": "datalad_preserving"}, False),
    ({"repository_mode": "datalad_free"}, True),
    ({"repository_mode": "git_lfs"}, True),
    ({"exclude_version_control_metadata": True}, True),  # the older flag, when no repository mode is given
    ({}, False),
])
def test_version_control_metadata_follows_the_repository_mode(data, expected):
    assert eo.build_export_kwargs(data)["exclude_version_control_metadata"] is expected


def test_scope_filters_are_cleaned_and_empty_ones_become_none():
    kwargs = eo.build_export_kwargs({
        "exclude_subjects": [" sub-01 ", "", "sub-02"], "exclude_acq": {"anat": ["a", ""], "": ["x"], "func": []},
        "scrub_mri_json": True, "scrub_mri_json_groups": [" A ", ""],
    })
    assert kwargs["exclude_subjects"] == {"sub-01", "sub-02"} and kwargs["exclude_sessions"] is None
    assert kwargs["exclude_acq"] == {"anat": {"a"}}
    assert kwargs["scrub_mri_json_groups"] == {"a"} and kwargs["clean_nifti_gzip_headers"] is True


def test_the_zip_name_says_whether_it_is_anonymized_or_upload_ready():
    assert eo.export_zip_name("study", True, "standard") == "study_anonymized_export.zip"
    assert eo.export_zip_name("study", False, "upload_ready") == "study_upload_ready_export.zip"


@pytest.mark.parametrize("mode, flags", [("both", (True, True)), ("bids", (True, False)), ("prism", (False, True)), ("ignore", (False, False)), ("none", (False, False)), ("???", (True, True))])
def test_validation_modes(mode, flags):
    assert eo.export_validation_flags(mode) == flags


def _run(tmp_path, monkeypatch, validation_error, data=None):
    calls = {"validated": 0, "exported": 0}
    monkeypatch.setattr(eo, "run_pre_export_validation", lambda *a: calls.__setitem__("validated", calls["validated"] + 1) or validation_error)
    monkeypatch.setattr(eo, "export_project", lambda **kw: calls.__setitem__("exported", calls["exported"] + 1))
    result = eo.run_project_export(tmp_path, tmp_path / "x.zip", data or {})
    return calls, result


def test_an_export_is_blocked_when_validation_finds_errors(tmp_path, monkeypatch):
    with pytest.raises(eo.ExportBlocked, match="Export blocked"):
        _run(tmp_path, monkeypatch, "Export blocked: 2 errors")
    # and nothing was exported


def test_an_export_runs_after_a_clean_validation(tmp_path, monkeypatch):
    calls, _ = _run(tmp_path, monkeypatch, None)
    assert calls == {"validated": 1, "exported": 1}


def test_ignoring_validation_skips_it(tmp_path, monkeypatch):
    calls, _ = _run(tmp_path, monkeypatch, "would block", {"validation_mode": "ignore"})
    assert calls == {"validated": 0, "exported": 1}


def test_a_cancelled_export_stops_before_validating(tmp_path, monkeypatch):
    import threading

    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(eo, "export_project", lambda **kw: pytest.fail("exported after cancel"))
    with pytest.raises(InterruptedError):
        eo.run_project_export(tmp_path, tmp_path / "x.zip", {}, cancelled_flag=cancel)
