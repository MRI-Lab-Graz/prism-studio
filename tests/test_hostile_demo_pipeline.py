"""Run the hostile demo dataset through real backend pipelines.

Each test exercises one pipeline stage against deliberately adversarial
input and asserts the stage survives without an unhandled exception, and
without silently violating one of the repository's hard invariants
(text files never annexed, session labels never coerced).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.hostile_demo_generator import (
    assert_text_files_never_annexed,
    generate_hostile_dataset,
)
from src.participants_converter import ParticipantsConverter
from src.subject_code_rewriter import SubjectCodeRewriter
from src.web.blueprints.conversion_environment_mri_scan_helpers import (
    discover_mri_acquisition_rows,
    extract_sidecar_location,
    parse_sidecar_timestamp,
)
from src.web.export_project import export_project


def _run_pipeline_stage(label, fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001 - intentionally broad: see module docstring
        pytest.fail(f"{label} raised unexpectedly: {exc!r}", pytrace=True)


@pytest.fixture(scope="module")
def hostile_dataset(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("hostile_demo")
    result = generate_hostile_dataset(root / "demo", seed=1, use_datalad=False)
    return result.project_root


def test_participants_conversion_survives_hostile_input(hostile_dataset: Path) -> None:
    converter = ParticipantsConverter(hostile_dataset)
    source = hostile_dataset / "code" / "rawdata" / "hostile_participants_raw.csv"
    mapping = {
        "version": "1.0",
        "mappings": {
            "participant_id": {
                "source_column": "ID",
                "standard_variable": "participant_id",
            },
            "age": {"source_column": "age", "standard_variable": "age"},
            "sex": {"source_column": "sex", "standard_variable": "sex"},
            "group": {"source_column": "group", "standard_variable": "group"},
        },
    }

    success, output_df, messages = _run_pipeline_stage(
        "ParticipantsConverter.convert_participant_data",
        converter.convert_participant_data,
        source,
        mapping,
    )

    assert success is True
    assert output_df is not None
    assert "participant_id" in output_df.columns
    assert output_df["participant_id"].iloc[0] == "sub-001"

    # socio_duplicate_id_case: sub-01 and SUB-01 collapse to one row.
    ids = list(output_df["participant_id"])
    assert ids.count("sub-01") == 1

    # socio_distinct_case_in_label: sub-Ab and sub-ab remain distinct.
    assert "sub-Ab" in ids
    assert "sub-ab" in ids

    # socio_empty_participant_id / socio_whitespace_only_id: dropped, not crashed.
    assert any("Dropped" in m for m in messages)


def test_mri_sidecar_parsing_survives_hostile_timestamps(hostile_dataset: Path) -> None:
    rows = _run_pipeline_stage(
        "discover_mri_acquisition_rows", discover_mri_acquisition_rows, hostile_dataset
    )
    assert isinstance(rows, list)
    assert len(rows) > 0

    env_dir = hostile_dataset / "sub-env01" / "ses-01"
    malformed = env_dir / "func" / "sub-env01_ses-01_task-rest_bold.json"
    missing = env_dir / "anat" / "sub-env01_ses-01_T1w.json"

    import json

    malformed_sidecar = json.loads(malformed.read_text(encoding="utf-8"))
    missing_sidecar = json.loads(missing.read_text(encoding="utf-8"))

    assert (
        _run_pipeline_stage(
            "parse_sidecar_timestamp(malformed)",
            parse_sidecar_timestamp,
            malformed_sidecar,
        )
        is None
    )
    assert (
        _run_pipeline_stage(
            "parse_sidecar_timestamp(missing)", parse_sidecar_timestamp, missing_sidecar
        )
        is None
    )

    leap_valid = json.loads(
        (
            hostile_dataset
            / "sub-env03"
            / "ses-01"
            / "anat"
            / "sub-env03_ses-01_T1w.json"
        ).read_text(encoding="utf-8")
    )
    leap_invalid = json.loads(
        (
            hostile_dataset
            / "sub-env03"
            / "ses-02"
            / "anat"
            / "sub-env03_ses-02_T1w.json"
        ).read_text(encoding="utf-8")
    )
    assert (
        _run_pipeline_stage(
            "parse_sidecar_timestamp(leap_valid)", parse_sidecar_timestamp, leap_valid
        )
        is not None
    )
    assert (
        _run_pipeline_stage(
            "parse_sidecar_timestamp(leap_invalid)",
            parse_sidecar_timestamp,
            leap_invalid,
        )
        is None
    )

    institution_only_name = json.loads(
        (
            hostile_dataset
            / "sub-env04"
            / "ses-01"
            / "anat"
            / "sub-env04_ses-01_T1w.json"
        ).read_text(encoding="utf-8")
    )
    location = _run_pipeline_stage(
        "extract_sidecar_location", extract_sidecar_location, institution_only_name
    )
    assert location  # falls back to InstitutionName without raising


def test_subject_rewrite_distinguishes_case_only_rename_from_real_collision(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    # Use case-distinct names (not mere case variants of each other) so the
    # test doesn't depend on the host filesystem's case sensitivity: the
    # point is to verify a genuine two-subjects-into-one-target collision is
    # still flagged, as distinct from the case-only-rename non-collision
    # already covered by tests/test_subject_code_rewriter.py.
    for sub in ("sub-01", "sub-99"):
        func_dir = project_root / sub / "ses-01" / "func"
        func_dir.mkdir(parents=True)
        (func_dir / f"{sub}_ses-01_task-rest_bold.json").write_text(
            "{}", encoding="utf-8"
        )

    rewriter = SubjectCodeRewriter(project_root)

    # sub-99 -> sub-01 while sub-01 already exists as a separate directory
    # IS a real collision.
    preview = _run_pipeline_stage(
        "SubjectCodeRewriter.preview (real collision)",
        rewriter.preview,
        explicit_mapping={"sub-99": "sub-01"},
        allow_many_to_one=False,
    )
    assert preview["conflicts"], "expected a reported conflict for a genuine collision"


def test_many_to_one_merge_with_allow_flag(hostile_dataset: Path) -> None:
    rewriter = SubjectCodeRewriter(hostile_dataset)
    mapping = {
        "sub-AAA": "sub-merged",
        "sub-aaa": "sub-merged",
        "sub-Aaa": "sub-merged",
    }
    preview = _run_pipeline_stage(
        "SubjectCodeRewriter.preview (many-to-one)",
        rewriter.preview,
        explicit_mapping=mapping,
        allow_many_to_one=True,
    )
    assert preview["conflicts"] == []


def test_session_labels_never_coerced(hostile_dataset: Path) -> None:
    subject_dir = hostile_dataset / "sub-sess01"
    sessions = sorted(p.name for p in subject_dir.iterdir() if p.is_dir())
    assert sessions == ["ses-01", "ses-1", "ses-pre"]


@pytest.mark.parametrize("use_datalad", [False, True])
def test_project_creation_with_and_without_datalad(
    tmp_path: Path, use_datalad: bool
) -> None:
    domains = {"sociodemo"}
    if use_datalad:
        with patch(
            "src.project_manager.subprocess.run",
            return_value=Mock(returncode=0, stdout="", stderr=""),
        ), patch(
            "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
            return_value=False,
        ), patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad"):
            result = _run_pipeline_stage(
                "generate_hostile_dataset(use_datalad=True)",
                generate_hostile_dataset,
                tmp_path / "demo",
                seed=1,
                domains=domains,
                use_datalad=True,
            )
    else:
        result = _run_pipeline_stage(
            "generate_hostile_dataset(use_datalad=False)",
            generate_hostile_dataset,
            tmp_path / "demo",
            seed=1,
            domains=domains,
            use_datalad=False,
        )

    assert result.project_root.exists()
    violations = assert_text_files_never_annexed(result.project_root)
    assert violations == []


def test_export_runs_against_hostile_dataset(hostile_dataset: Path, tmp_path: Path) -> None:
    output_zip = tmp_path / "export.zip"
    summary = _run_pipeline_stage(
        "export_project",
        export_project,
        hostile_dataset,
        output_zip,
        anonymize=True,
        include_derivatives=False,
        include_sourcedata=False,
        include_code=True,
    )
    assert output_zip.exists()
    assert summary is not None
