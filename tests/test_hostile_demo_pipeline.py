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

from src.bids_entity_rewriter import BidsEntityRewriter
from src.converters.biometrics import convert_biometrics_table_to_prism_dataset
from src.converters.file_reader import read_tabular_file
from src.converters.survey import convert_survey_xlsx_to_prism_dataset
from src.hostile_demo_generator import (
    NON_MRI_DOMAINS,
    assert_text_files_never_annexed,
    generate_hostile_dataset,
)
from src.participants_backend import apply_participants_merge
from src.participants_converter import ParticipantsConverter
from src.recipe_validation import validate_recipe
from src.recipes_surveys import compute_survey_recipes
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


@pytest.mark.parametrize(
    "export_kwargs",
    [
        {"anonymize": False, "include_sourcedata": True, "include_code": True},
        {"anonymize": True, "deterministic": True, "include_code": False},
        {"anonymize": True, "exclude_subjects": {"sub-Müller"}},
        {"anonymize": True, "exclude_version_control_metadata": True},
    ],
    ids=[
        "no_anonymize_with_sourcedata",
        "deterministic_anonymized_no_code",
        "exclude_unicode_subject",
        "strip_vcs_metadata",
    ],
)
def test_export_strategy_variants_survive_hostile_dataset(
    hostile_dataset: Path, tmp_path: Path, export_kwargs: dict, request
) -> None:
    output_zip = tmp_path / f"export_{request.node.callspec.id}.zip"
    summary = _run_pipeline_stage(
        f"export_project({export_kwargs})",
        export_project,
        hostile_dataset,
        output_zip,
        **export_kwargs,
    )
    assert output_zip.exists()
    assert summary is not None


def test_entity_rewrite_detects_real_acq_collision(hostile_dataset: Path) -> None:
    rewriter = BidsEntityRewriter(hostile_dataset)
    preview = _run_pipeline_stage(
        "BidsEntityRewriter.preview (acq rename collision)",
        rewriter.preview,
        modality="func",
        entity="acq",
        operation="rename",
        current_value="Z",
        replacement="A",
    )
    assert preview["conflicts"], "renaming acq-Z to acq-A should collide with acq-A"


def test_entity_rewrite_rejects_ambiguous_bulk_delete(hostile_dataset: Path) -> None:
    """When an entity has multiple observed values, the API refuses a
    bulk delete with no current_value rather than guessing which value(s)
    to remove — this is the product's own guard against an ambiguous
    many-to-one collision, not a bug."""
    rewriter = BidsEntityRewriter(hostile_dataset)
    with pytest.raises(ValueError, match="multiple values"):
        rewriter.preview(modality="func", entity="run", operation="delete")


def test_entity_rewrite_detects_real_run_delete_collision(hostile_dataset: Path) -> None:
    rewriter = BidsEntityRewriter(hostile_dataset)
    preview = _run_pipeline_stage(
        "BidsEntityRewriter.preview (run delete collision)",
        rewriter.preview,
        modality="func",
        entity="run",
        operation="delete",
        current_value="01",
    )
    assert preview["conflicts"], (
        "deleting run-01's entity should collide with the pre-existing "
        "bare task-mem file"
    )


def test_entity_rewrite_rejects_sub_entity_with_clear_error(hostile_dataset: Path) -> None:
    rewriter = BidsEntityRewriter(hostile_dataset)
    with pytest.raises(ValueError, match="not editable"):
        rewriter.preview(
            modality="func", entity="sub", operation="rename", replacement="x"
        )


def test_hostile_recipes_are_flagged_by_validate_recipe(hostile_dataset: Path) -> None:
    import json

    recipe_dir = hostile_dataset / "code" / "recipes"
    expectations = {
        "survey/recipe-hostile-missing-taskname.json": "TaskName",
        "survey/recipe-hostile-formula-missing-items.json": "Formula",
        "survey/recipe-hostile-invalid-kind.json": "Kind must be",
        "biometrics/recipe-hostile-missing-biometric-name.json": "BiometricName",
    }
    for rel_path, expected_substring in expectations.items():
        recipe = json.loads((recipe_dir / rel_path).read_text(encoding="utf-8"))
        errors = _run_pipeline_stage(
            f"validate_recipe({rel_path})", validate_recipe, recipe, recipe_id=rel_path
        )
        assert errors, f"{rel_path} should have produced validation errors"
        assert any(expected_substring in e for e in errors), (
            f"{rel_path}: expected an error mentioning '{expected_substring}', got {errors}"
        )


def test_xlsx_formula_like_cell_is_not_silently_evaluated_to_a_number(
    hostile_dataset: Path,
) -> None:
    """Documents a real finding, not a designed-safe behavior.

    openpyxl writes a string starting with '=' as a live formula cell with
    no cached value, so pandas.read_excel reads it back as NaN rather than
    the literal text '=1+1'. The only thing this test guards against is
    the *worse* outcome — the formula silently evaluating to the number 2
    and being treated as legitimate numeric data. Any PRISM xlsx writer
    that passes raw user strings to to_excel/openpyxl should escape a
    leading =/+/-/@ before writing; see HostileCase
    'input_xlsx_with_formula_like_cell' for the open follow-up.
    """
    xlsx_path = (
        hostile_dataset / "code" / "rawdata" / "hostile_biometrics_data_wide.xlsx"
    )
    result = _run_pipeline_stage(
        "read_tabular_file(hostile .xlsx)", read_tabular_file, xlsx_path, kind="xlsx"
    )
    first_value = result.df.loc[0, "vo2_max_estimated"]
    assert first_value != 2, (
        "the formula must not have been silently evaluated to the number 2"
    )


def test_latin1_csv_is_recovered_by_encoding_fallback(hostile_dataset: Path) -> None:
    latin1_path = (
        hostile_dataset / "code" / "rawdata" / "hostile_participants_latin1.csv"
    )
    result = _run_pipeline_stage(
        "read_tabular_file(latin-1 csv)", read_tabular_file, latin1_path, kind="csv"
    )
    assert result.encoding_used in {"latin-1", "cp1252"}
    assert len(result.df) > 0


_FULL_SWEEP_PARTICIPANTS_MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "ID", "standard_variable": "participant_id"},
        "age": {"source_column": "age", "standard_variable": "age"},
        "sex": {"source_column": "sex", "standard_variable": "sex"},
    },
}
_FULL_SWEEP_MERGE_MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "ID", "standard_variable": "participant_id"},
        "age": {"source_column": "age", "standard_variable": "age"},
        "group": {"source_column": "group", "standard_variable": "group"},
    },
}


@pytest.mark.parametrize("use_datalad", [False, True])
def test_full_non_mri_sweep_with_and_without_datalad(tmp_path: Path, use_datalad: bool) -> None:
    """End-to-end: generate every non-MRI hostile domain, import
    participants + survey + biometrics into the same project, merge a
    second participants source in (cross-source case sensitivity), export,
    and score a recipe — run twice, once per DataLad mode, as two fully
    separate test invocations (not just project-creation in isolation)."""
    datalad_patches = []
    if use_datalad:
        datalad_patches = [
            patch(
                "src.project_manager.subprocess.run",
                return_value=Mock(returncode=0, stdout="", stderr=""),
            ),
            patch(
                "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
                return_value=False,
            ),
            patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad"),
        ]
    for p in datalad_patches:
        p.start()
    try:
        result = _run_pipeline_stage(
            "generate_hostile_dataset(NON_MRI_DOMAINS)",
            generate_hostile_dataset,
            tmp_path / "demo",
            seed=1,
            domains=NON_MRI_DOMAINS,
            use_datalad=use_datalad,
        )
    finally:
        for p in datalad_patches:
            p.stop()

    project_root = result.project_root
    assert set(result.files_written.keys()) == NON_MRI_DOMAINS
    assert assert_text_files_never_annexed(project_root) == []

    rawdata = project_root / "code" / "rawdata"

    # 1) Participants: convert the clean initial source into participants.tsv.
    converter = ParticipantsConverter(project_root)
    success, participants_df, _messages = _run_pipeline_stage(
        "ParticipantsConverter.convert_participant_data",
        converter.convert_participant_data,
        rawdata / "participants_merge_initial_source.csv",
        _FULL_SWEEP_PARTICIPANTS_MAPPING,
    )
    assert success is True
    participants_df.to_csv(project_root / "participants.tsv", sep="\t", index=False)

    # 2) Survey: import the clean baseline response table for the randomly
    # generated survey, into the same project root.
    library_dir = project_root / "code" / "library" / "survey"
    survey_result = _run_pipeline_stage(
        "convert_survey_xlsx_to_prism_dataset",
        convert_survey_xlsx_to_prism_dataset,
        input_path=rawdata / "survey_clean_baseline.csv",
        library_dir=library_dir,
        output_root=project_root,
        name="full-non-mri-sweep",
        force=True,
        skip_participants=True,
    )
    assert survey_result.tasks_included

    # 3) Biometrics: clean, minimal import using the official fitness
    # template (the hostile_demo biometrics domain's own raw files are
    # deliberately adversarial and already covered by dedicated tests —
    # this sweep exercises a normal, successful biometrics import
    # alongside the hostile content the other domains generated).
    official_template = (
        Path(__file__).resolve().parents[1]
        / "official"
        / "library"
        / "biometrics"
        / "biometrics-fitness.json"
    )
    biometrics_library = project_root / "code" / "library" / "biometrics"
    biometrics_library.mkdir(parents=True, exist_ok=True)
    (biometrics_library / "biometrics-fitness.json").write_bytes(
        official_template.read_bytes()
    )
    biometrics_csv = rawdata / "full_sweep_biometrics_clean.csv"
    import pandas as pd

    pd.DataFrame(
        [
            {"participant_id": "sub-100", "resting_hr": 65, "grip_strength_left": 35},
            {"participant_id": "sub-101", "resting_hr": 70, "grip_strength_left": 38},
        ]
    ).to_csv(biometrics_csv, index=False)
    biometrics_result = _run_pipeline_stage(
        "convert_biometrics_table_to_prism_dataset",
        convert_biometrics_table_to_prism_dataset,
        input_path=biometrics_csv,
        library_dir=biometrics_library,
        output_root=project_root,
        force=True,
        skip_participants=True,
    )
    assert biometrics_result.tasks_included == ["fitness"]

    # 4) Merge a second, independent participants source in — exercises
    # cross-source subject-id case sensitivity in the same full sweep.
    merge_result = _run_pipeline_stage(
        "apply_participants_merge",
        apply_participants_merge,
        project_root,
        rawdata / "participants_merge_incoming_source.csv",
        _FULL_SWEEP_MERGE_MAPPING,
    )
    assert merge_result["merged_participant_count"] == 5

    # 5) Recipe scoring against the survey data just imported.
    recipes_dir = project_root / "code" / "recipes" / "survey"
    # NON_MRI_DOMAINS also includes the "recipes" domain, which deliberately
    # writes invalid recipe-hostile-*.json files into this same folder to
    # test validate_recipe() in isolation — compute_survey_recipes()
    # validates every file in its recipe_dir up front and refuses to run
    # at all if any of them are invalid, so for this step we point it at a
    # separate directory containing only the real, valid survey_full_run
    # recipe (copied over), keeping the hostile ones in place for the
    # structural checks above.
    recipe_path = next(
        p for p in recipes_dir.glob("recipe-*.json") if "hostile" not in p.name
    )
    assert validate_recipe(__import__("json").loads(recipe_path.read_text())) == []
    valid_recipe_dir = project_root / "code" / "recipes" / "survey_valid_only"
    valid_recipe_dir.mkdir(parents=True, exist_ok=True)
    (valid_recipe_dir / recipe_path.name).write_bytes(recipe_path.read_bytes())
    recipe_result = _run_pipeline_stage(
        "compute_survey_recipes",
        compute_survey_recipes,
        prism_root=project_root,
        repo_root=project_root,
        recipe_dir=str(valid_recipe_dir),
        out_format="flat",
        modality="survey",
    )
    assert recipe_result.written_files >= 1

    # 6) Export the fully-assembled project.
    output_zip = tmp_path / "export.zip"
    _run_pipeline_stage(
        "export_project",
        export_project,
        project_root,
        output_zip,
        anonymize=True,
        include_derivatives=True,
        include_code=True,
    )
    assert output_zip.exists()

    # Parity: identical seed/inputs must produce the identical final
    # participant set regardless of DataLad mode.
    participants_final = pd.read_csv(
        project_root / "participants.tsv", sep="\t", dtype=str, keep_default_na=False
    )
    assert set(participants_final["participant_id"]) == {
        "sub-100",
        "sub-101",
        "sub-Ab",
        "sub-102",
        "sub-ab",
    }
    assert assert_text_files_never_annexed(project_root) == []


def test_biometrics_conversion_rejects_case_only_differing_ids(tmp_path: Path) -> None:
    """Regression guard for a real, severe finding: on case-insensitive
    filesystems (default macOS/Windows), 'sub-Ab' and 'sub-ab' resolve to
    the identical on-disk directory. Before this check existed, the
    second participant processed silently overwrote the first's
    biometrics .tsv with no error — confirmed real data loss, not just a
    theoretical risk."""
    import pandas as pd

    library_dir = tmp_path / "library"
    library_dir.mkdir()
    official_template = (
        Path(__file__).resolve().parents[1]
        / "official"
        / "library"
        / "biometrics"
        / "biometrics-fitness.json"
    )
    (library_dir / "biometrics-fitness.json").write_bytes(official_template.read_bytes())

    data_csv = tmp_path / "data.csv"
    pd.DataFrame(
        [
            {"participant_id": "sub-Ab", "resting_hr": 60},
            {"participant_id": "sub-ab", "resting_hr": 99},
        ]
    ).to_csv(data_csv, index=False)

    from src.converters.biometrics import convert_biometrics_table_to_prism_dataset

    with pytest.raises(ValueError, match="differ only by case"):
        convert_biometrics_table_to_prism_dataset(
            input_path=data_csv,
            library_dir=library_dir,
            output_root=tmp_path / "out",
            skip_participants=True,
        )
