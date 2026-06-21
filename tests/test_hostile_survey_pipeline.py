"""Full survey run: random template + hostile response-table import variants
+ recipe scoring across every export format.

Exercises the real production functions the Survey Converter and Recipe
Builder UIs call: SurveyResponsesConverter (via
convert_survey_xlsx_to_prism_dataset) and compute_survey_recipes.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.converters.survey import convert_survey_xlsx_to_prism_dataset
from src.converters.survey_processing import SurveyValueOutOfBoundsError
from src.hostile_demo_generator import generate_hostile_dataset
from src.recipe_validation import validate_recipe
from src.recipes_surveys import compute_survey_recipes


def _run_pipeline_stage(label, fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001 - intentionally broad: see module docstring
        pytest.fail(f"{label} raised unexpectedly: {exc!r}", pytrace=True)


@pytest.fixture(scope="module")
def survey_dataset(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("hostile_survey")
    result = generate_hostile_dataset(
        root / "demo", seed=1, domains={"survey_full_run"}, use_datalad=False
    )
    return result.project_root


@pytest.fixture
def library_dir(survey_dataset: Path) -> Path:
    return survey_dataset / "code" / "library" / "survey"


@pytest.fixture
def rawdata_dir(survey_dataset: Path) -> Path:
    return survey_dataset / "code" / "rawdata"


def test_clean_baseline_imports_successfully(tmp_path, library_dir, rawdata_dir):
    out = tmp_path / "out"
    result = _run_pipeline_stage(
        "convert clean baseline",
        convert_survey_xlsx_to_prism_dataset,
        input_path=rawdata_dir / "survey_clean_baseline.csv",
        library_dir=library_dir,
        output_root=out,
        name="hostile-survey",
    )
    assert result.tasks_included == ["rndsurvey1"]
    assert result.unknown_columns == []
    assert (out / "sub-01" / "ses-1" / "survey").exists()


def test_exact_duplicate_rows_error_mode_raises_clean_error(
    tmp_path, library_dir, rawdata_dir
):
    with pytest.raises(ValueError, match="Duplicate entries"):
        convert_survey_xlsx_to_prism_dataset(
            input_path=rawdata_dir / "survey_exact_duplicate_rows.csv",
            library_dir=library_dir,
            output_root=tmp_path / "out",
            name="hostile-survey",
            duplicate_handling="error",
        )


def test_exact_duplicate_rows_keep_first_succeeds(tmp_path, library_dir, rawdata_dir):
    result = _run_pipeline_stage(
        "convert exact duplicates (keep_first)",
        convert_survey_xlsx_to_prism_dataset,
        input_path=rawdata_dir / "survey_exact_duplicate_rows.csv",
        library_dir=library_dir,
        output_root=tmp_path / "out",
        name="hostile-survey",
        duplicate_handling="keep_first",
    )
    assert result.tasks_included == ["rndsurvey1"]


def test_conflicting_duplicate_rows_error_mode_raises_before_picking_an_answer(
    tmp_path, library_dir, rawdata_dir
):
    """The two rows disagree on an item value — 'error' must refuse rather
    than silently picking one answer over the other."""
    with pytest.raises(ValueError, match="Duplicate entries"):
        convert_survey_xlsx_to_prism_dataset(
            input_path=rawdata_dir / "survey_conflicting_duplicate_rows.csv",
            library_dir=library_dir,
            output_root=tmp_path / "out",
            name="hostile-survey",
            duplicate_handling="error",
        )


def test_conflicting_duplicate_rows_keep_last_resolves_deterministically(
    tmp_path, library_dir, rawdata_dir
):
    result = _run_pipeline_stage(
        "convert conflicting duplicates (keep_last)",
        convert_survey_xlsx_to_prism_dataset,
        input_path=rawdata_dir / "survey_conflicting_duplicate_rows.csv",
        library_dir=library_dir,
        output_root=tmp_path / "out",
        name="hostile-survey",
        duplicate_handling="keep_last",
    )
    assert result.tasks_included == ["rndsurvey1"]


def test_multi_session_same_participant_requires_one_call_per_session(
    tmp_path, library_dir, rawdata_dir
):
    """By design (matching the documented wellbeing_multi_demo workflow),
    one convert() call processes one session at a time. Without an
    explicit session=, it silently auto-filters to the first detected
    session — this test pins that exact behavior, then shows the correct
    two-call workflow that imports both sessions."""
    source = rawdata_dir / "survey_multi_session_same_participant.csv"

    single_call_result = _run_pipeline_stage(
        "convert multi-session without explicit session=",
        convert_survey_xlsx_to_prism_dataset,
        input_path=source,
        library_dir=library_dir,
        output_root=tmp_path / "out_default",
        name="hostile-survey",
        session_column="session",
        duplicate_handling="error",
    )
    assert single_call_result.detected_sessions == ["ses-1", "ses-2"]
    # Only the first session was actually written despite both being detected.
    assert (tmp_path / "out_default" / "sub-multisession" / "ses-1").exists()
    assert not (tmp_path / "out_default" / "sub-multisession" / "ses-2").exists()

    for session in ("ses-1", "ses-2"):
        _run_pipeline_stage(
            f"convert multi-session with session={session}",
            convert_survey_xlsx_to_prism_dataset,
            input_path=source,
            library_dir=library_dir,
            output_root=tmp_path / "out_per_session",
            name="hostile-survey",
            session_column="session",
            session=session,
            duplicate_handling="error",
            force=True,
        )

    assert (tmp_path / "out_per_session" / "sub-multisession" / "ses-1").exists()
    assert (tmp_path / "out_per_session" / "sub-multisession" / "ses-2").exists()


def test_out_of_range_value_raises_structured_error(tmp_path, library_dir, rawdata_dir):
    with pytest.raises(SurveyValueOutOfBoundsError):
        convert_survey_xlsx_to_prism_dataset(
            input_path=rawdata_dir / "survey_out_of_range_value.csv",
            library_dir=library_dir,
            output_root=tmp_path / "out",
            name="hostile-survey",
        )


def test_missing_cell_converts_without_crashing(tmp_path, library_dir, rawdata_dir):
    result = _run_pipeline_stage(
        "convert missing cell",
        convert_survey_xlsx_to_prism_dataset,
        input_path=rawdata_dir / "survey_missing_cell.csv",
        library_dir=library_dir,
        output_root=tmp_path / "out",
        name="hostile-survey",
    )
    assert result.tasks_included == ["rndsurvey1"]


def test_unmapped_extra_column_is_surfaced_not_dropped_silently(
    tmp_path, library_dir, rawdata_dir
):
    """The unmapped column's value also contains an embedded comma —
    confirms the CSV quoting round-trips correctly through the parser."""
    result = _run_pipeline_stage(
        "convert with unmapped column",
        convert_survey_xlsx_to_prism_dataset,
        input_path=rawdata_dir / "survey_unmapped_extra_column.csv",
        library_dir=library_dir,
        output_root=tmp_path / "out",
        name="hostile-survey",
        unknown="warn",
    )
    assert "interviewer_comments" in result.unknown_columns


def test_mixed_tab_comma_delimiters_known_gap_garbles_one_row(
    tmp_path, library_dir, rawdata_dir
):
    """Regression pin for a known gap (see HostileCase
    'survey_mixed_tab_comma_delimiters'): a row using the wrong delimiter
    is not rejected and not recovered — it's silently absorbed into a
    garbled participant_id with its real answers lost. This test does not
    assert that's *correct*, only that today's actual behavior hasn't
    silently changed to something worse (e.g. evaluating into another
    real subject's data)."""
    out = tmp_path / "out"
    result = _run_pipeline_stage(
        "convert mixed delimiters",
        convert_survey_xlsx_to_prism_dataset,
        input_path=rawdata_dir / "survey_mixed_tab_comma_delimiters.csv",
        library_dir=library_dir,
        output_root=out,
        name="hostile-survey",
    )
    assert result.tasks_included == ["rndsurvey1"]
    well_formed_dirs = [
        p.name for p in out.iterdir() if p.is_dir() and p.name.startswith("sub-malformed1")
    ]
    assert well_formed_dirs == ["sub-malformed1"]
    # The malformed row must not have landed inside sub-malformed1's data,
    # nor silently vanished — it shows up as its own (garbled) subject.
    garbled_dirs = [
        p.name
        for p in out.iterdir()
        if p.is_dir() and p.name.startswith("sub-malformed2")
    ]
    assert len(garbled_dirs) == 1
    assert garbled_dirs[0] != "sub-malformed2"


@pytest.mark.parametrize("out_format", ["flat", "prism", "csv", "xlsx", "sav"])
def test_recipe_computes_correct_scores_in_every_export_format(
    tmp_path, survey_dataset: Path, library_dir, rawdata_dir, out_format: str
):
    out = tmp_path / f"out_{out_format}"
    convert_survey_xlsx_to_prism_dataset(
        input_path=rawdata_dir / "survey_clean_baseline.csv",
        library_dir=library_dir,
        output_root=out,
        name="hostile-survey",
    )

    import shutil

    shutil.copytree(survey_dataset / "code" / "recipes", out / "code" / "recipes")

    recipe = next((survey_dataset / "code" / "recipes" / "survey").glob("recipe-*.json"))
    import json

    errors = validate_recipe(json.loads(recipe.read_text(encoding="utf-8")))
    assert errors == []

    result = _run_pipeline_stage(
        f"compute_survey_recipes(out_format={out_format})",
        compute_survey_recipes,
        prism_root=out,
        repo_root=out,
        out_format=out_format,
        modality="survey",
    )
    assert result.written_files >= 1

    task_name = "rndsurvey1"
    if out_format == "flat":
        df = pd.read_csv(result.flat_out_path, sep="\t")
    elif out_format == "prism":
        # One file per subject in this layout; read sub-01's directly.
        sub01_file = next(result.out_root.glob(f"{task_name}/sub-01/**/*.tsv"))
        df = pd.read_csv(sub01_file, sep="\t")
        df["participant_id"] = "sub-01"
    elif out_format == "csv":
        df = pd.read_csv(next(result.out_root.glob("*.csv")))
    elif out_format == "xlsx":
        df = pd.read_excel(next(result.out_root.glob("*.xlsx")))
    else:  # sav
        import pyreadstat

        df, _meta = pyreadstat.read_sav(str(next(result.out_root.glob("*.sav"))))

    sub01_total = df.loc[df["participant_id"] == "sub-01", f"{task_name}_total"]
    assert len(sub01_total) == 1

    raw = pd.read_csv(rawdata_dir / "survey_clean_baseline.csv")
    item_cols = [c for c in raw.columns if c != "participant_id"]
    expected_mean = raw.loc[raw["participant_id"] == "sub-01", item_cols].iloc[0].mean()
    assert sub01_total.iloc[0] == pytest.approx(expected_mean)


def test_survey_conversion_rejects_case_only_differing_ids(
    tmp_path, library_dir, rawdata_dir
):
    """Regression guard for a real, severe finding: on case-insensitive
    filesystems (default macOS/Windows), 'sub-Ab' and 'sub-ab' resolve to
    the identical on-disk directory. Before this check existed, the
    second participant processed silently overwrote the first's survey
    .tsv with no error — confirmed real data loss, not just a theoretical
    risk. Same root cause and fix as the biometrics converter."""
    import json

    template_path = next(library_dir.glob("survey-*.json"))
    template = json.loads(template_path.read_text(encoding="utf-8"))
    real_item_codes = [
        k for k in template if k not in {"Technical", "Metadata", "Study"}
    ]

    rows = [
        {"participant_id": "sub-Ab", **{c: 1 for c in real_item_codes}},
        {"participant_id": "sub-ab", **{c: 4 for c in real_item_codes}},
    ]
    collision_csv = tmp_path / "case_collision.csv"
    pd.DataFrame(rows).to_csv(collision_csv, index=False)

    with pytest.raises(ValueError, match="differ only by case"):
        convert_survey_xlsx_to_prism_dataset(
            input_path=collision_csv,
            library_dir=library_dir,
            output_root=tmp_path / "out",
            name="hostile-survey",
        )
