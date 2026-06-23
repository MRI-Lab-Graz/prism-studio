"""Generate a deterministic, adversarial PRISM project tree.

Builds intentionally hostile sociodemographic, biometrics, environmental/MRI,
and subject/session-id data so that real backend pipelines (participants
conversion, biometrics conversion, MRI sidecar parsing, subject rewriting,
project creation, export, recipes) can be exercised against edge cases that
real-world uploads tend to contain.

All randomness is seeded explicitly (never global state) so that a given seed
always reproduces byte-identical output, which lets ``examples/hostile_demo/``
be committed as a static, diffable snapshot.
"""

from __future__ import annotations

import csv
import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.project_manager import ProjectManager
from src.utils.io import ensure_dir, write_json

ALL_DOMAINS = {
    "sociodemo",
    "biometrics",
    "environment_mri",
    "subject_session",
    "entity_rewrite",
    "recipes",
    "input_formats",
    "survey_full_run",
    "participants_merge",
}

NON_MRI_DOMAINS = {
    "sociodemo",
    "biometrics",
    "subject_session",
    "entity_rewrite",
    "recipes",
    "input_formats",
    "survey_full_run",
    "participants_merge",
}


@dataclass
class HostileCase:
    id: str
    domain: str
    description: str
    expected_outcome: str
    location: str = ""


@dataclass
class HostileGenerationResult:
    project_root: Path
    cases: list[HostileCase] = field(default_factory=list)
    files_written: dict[str, list[str]] = field(default_factory=dict)


def _record(
    files_written: dict[str, list[str]], domain: str, relative_path: str
) -> None:
    files_written.setdefault(domain, []).append(relative_path)


# ---------------------------------------------------------------------------
# Sociodemographics
# ---------------------------------------------------------------------------


def build_hostile_participants_table(
    seed: int,
) -> tuple[pd.DataFrame, list[HostileCase]]:
    """Return a raw (pre-conversion) participants table full of edge cases.

    Columns deliberately use the raw/source-style header names a real upload
    might use (``ID``, ``age``, ...), not the canonical ``participant_id``,
    so the table is meant to be fed through
    ``ParticipantsConverter.convert_participant_data`` rather than treated as
    already-BIDS-valid.
    """
    cases: list[HostileCase] = []
    rows: list[dict[str, Any]] = []

    def add(case: HostileCase, row: dict[str, Any]) -> None:
        cases.append(case)
        rows.append(row)

    add(
        HostileCase(
            "socio_age_out_of_range",
            "sociodemo",
            "Ages outside the documented 18-100 range (-5 and 999).",
            "Converter does not crash; out-of-range values pass through for "
            "downstream BIDS-validator range checks to flag.",
        ),
        {"ID": "001", "age": -5, "sex": "F", "country_of_birth": "AT"},
    )
    rows.append({"ID": "002", "age": 999, "sex": "M", "country_of_birth": "DE"})

    add(
        HostileCase(
            "socio_sex_menstrual_conflict",
            "sociodemo",
            "sex='M' with menstrual_cycle_regularity populated (conditional "
            "field should not apply to this sex value).",
            "Value is preserved as-is (converter does not currently enforce "
            "conditional-display logic); flags a gap for the BIDS validator "
            "or UI to catch, not the converter.",
        ),
        {
            "ID": "003",
            "age": 30,
            "sex": "M",
            "menstrual_cycle_regularity": "regular",
        },
    )

    add(
        HostileCase(
            "socio_unicode_freetext",
            "sociodemo",
            "Unicode, emoji, and an RTL-override control character in free "
            "text fields.",
            "Round-trips through TSV without mangling or raising.",
        ),
        {
            "ID": "004",
            "age": 25,
            "sex": "F",
            "ethnicity_other": "Ŧëśt 测试 \U0001f9ec \u202ereversed",
            "medication_details": "Sertraline 50mg \u202eلا",
        },
    )

    add(
        HostileCase(
            "socio_empty_participant_id",
            "sociodemo",
            "Empty and whitespace-only participant id values.",
            "Rows are dropped with a 'Dropped N rows without valid "
            "participant_id' message.",
        ),
        {"ID": "", "age": 40, "sex": "F"},
    )
    rows.append({"ID": "   ", "age": 41, "sex": "M"})

    add(
        HostileCase(
            "socio_duplicate_id_case",
            "sociodemo",
            "sub-01 and SUB-01: the prefix is case-normalized to lowercase "
            "by ParticipantsConverter._normalize_participant_id, so these "
            "resolve to the identical participant_id 'sub-01'.",
            "Rows are collapsed into a single participants.tsv row via "
            "_collapse_to_bids_participants_table; conflicting non-empty "
            "values across the two rows are reported in conflicting_columns.",
        ),
        {"ID": "sub-01", "age": 50, "sex": "F", "group": "control"},
    )
    rows.append({"ID": "SUB-01", "age": 51, "sex": "F", "group": "patient"})

    add(
        HostileCase(
            "socio_distinct_case_in_label",
            "sociodemo",
            "sub-Ab vs sub-ab: case difference inside the label itself "
            "(not the 'sub-' prefix), which is NOT normalized away.",
            "Two distinct participant_id rows are kept (sub-Ab, sub-ab) — "
            "no collapsing.",
        ),
        {"ID": "sub-Ab", "age": 22, "sex": "O"},
    )
    rows.append({"ID": "sub-ab", "age": 23, "sex": "O"})

    add(
        HostileCase(
            "socio_whitespace_only_id",
            "sociodemo",
            "Participant id made only of tabs/newlines.",
            "Dropped via the same path as empty ids.",
        ),
        {"ID": "\t\n ", "age": 33, "sex": "F"},
    )

    add(
        HostileCase(
            "socio_extremely_long_id",
            "sociodemo",
            "A 300-character participant id (path-length stress for "
            "downstream sub-<id>/ses-<id>/... directory creation).",
            "Converter accepts the long label without crashing; downstream "
            "filesystem operations may hit OS path-length limits, which is "
            "the behavior under test at the pipeline stage, not here.",
        ),
        {"ID": "X" * 300, "age": 28, "sex": "F"},
    )

    add(
        HostileCase(
            "socio_non_iso_country",
            "sociodemo",
            "country_of_birth values that are not valid ISO 3166-1 "
            "alpha-2 codes.",
            "Values pass through unvalidated at the converter layer; "
            "non-ISO codes remain a BIDS-validator/UI concern.",
        ),
        {"ID": "005", "age": 35, "sex": "F", "country_of_birth": "XX"},
    )
    rows.append(
        {"ID": "006", "age": 36, "sex": "M", "country_of_birth": "ZZZZ"}
    )
    rows.append({"ID": "007", "age": 37, "sex": "F", "country_of_birth": ""})

    add(
        HostileCase(
            "socio_conflicting_conditional",
            "sociodemo",
            "medication_current='no' but medication_details populated.",
            "Contradiction passes through unflagged at the converter layer; "
            "no crash.",
        ),
        {
            "ID": "008",
            "age": 45,
            "sex": "F",
            "medication_current": "no",
            "medication_details": "Sertraline 50mg",
        },
    )

    add(
        HostileCase(
            "socio_nan_inf_numeric",
            "sociodemo",
            "NaN/inf/literal-string 'NaN' in height/weight/bmi.",
            "Numeric coercion downstream does not crash; inf/NaN do not "
            "silently become a plausible-looking number.",
        ),
        {
            "ID": "009",
            "age": 29,
            "sex": "F",
            "height": float("nan"),
            "weight": float("inf"),
            "bmi": "NaN",
        },
    )
    rows.append(
        {"ID": "010", "age": 31, "sex": "M", "height": float("-inf"), "weight": 70}
    )

    add(
        HostileCase(
            "socio_csv_injection",
            "sociodemo",
            "Spreadsheet-formula-like strings (=1+1, =cmd|'/c calc'!A1, "
            "@SUM(1+1), +1+1) in free-text fields.",
            "Values are preserved literally as text by pandas/TSV writers; "
            "verify any xlsx export path does not auto-evaluate or strip "
            "the leading character.",
        ),
        {
            "ID": "011",
            "age": 38,
            "sex": "F",
            "ethnicity_other": "=1+1",
            "employment_status": "=cmd|'/c calc'!A1",
        },
    )
    rows.append(
        {
            "ID": "012",
            "age": 39,
            "sex": "M",
            "ethnicity_other": "@SUM(1+1)",
            "employment_status": "+1+1",
        }
    )

    add(
        HostileCase(
            "socio_education_years_out_of_range",
            "sociodemo",
            "education_years outside the documented 0-30 range.",
            "Out-of-range values pass through; no crash.",
        ),
        {"ID": "013", "age": 42, "sex": "F", "education_years": -3},
    )
    rows.append({"ID": "014", "age": 43, "sex": "M", "education_years": 45})

    add(
        HostileCase(
            "socio_group_field_embedded_tab",
            "sociodemo",
            "A literal tab character embedded inside the 'group' field, "
            "destined for TSV output.",
            "pandas' TSV writer quotes/escapes the value so the TSV "
            "structure is not corrupted (column count stays correct).",
        ),
        {"ID": "015", "age": 27, "sex": "F", "group": "control\tarm"},
    )

    return pd.DataFrame(rows), cases


def write_hostile_participants_raw_csv(root: Path, seed: int) -> list[HostileCase]:
    df, cases = build_hostile_participants_table(seed)
    out_dir = ensure_dir(root / "code" / "rawdata")
    out_path = out_dir / "hostile_participants_raw.csv"
    # Mixed line endings: write most rows normally, then hand-corrupt a
    # couple of line terminators and inject one mixed-encoding byte row.
    df.to_csv(out_path, index=False, lineterminator="\n")
    raw = out_path.read_bytes()
    lines = raw.split(b"\n")
    if len(lines) > 4:
        lines[2] = lines[2] + b"\r\r"  # bare CR stress
    mixed = b"\r\n".join(lines[:2]) + b"\n" + b"\n".join(lines[2:])
    out_path.write_bytes(mixed)
    return cases


# ---------------------------------------------------------------------------
# Biometrics
# ---------------------------------------------------------------------------


def build_hostile_biometrics_inputs(
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[HostileCase]]:
    """Return (codebook_df, wide_data_df, long_data_df, cases)."""
    cases: list[HostileCase] = []

    codebook_rows = [
        {
            "item_id": "resting_hr",
            "group": "fitness",
            "description": "Resting heart rate",
            "min": 60,
            "max": 100,
        },
        {
            "item_id": "resting_hr",
            "group": "vitals",
            "description": "Duplicate item_id under a different group",
            "min": 40,
            "max": 200,
        },
        {
            "item_id": "grip_strength_left",
            "group": "fitness",
            "description": "Grip strength (left)",
            "min": 0,
            "max": 80,
        },
        {
            "item_id": "vo2_max_estimated",
            "group": "fitness",
            "description": "Estimated VO2 max",
            "min": 10,
            "max": 70,
        },
    ]
    cases.append(
        HostileCase(
            "bio_duplicate_item_id_across_groups",
            "biometrics",
            "item_id 'resting_hr' appears under both 'fitness' and "
            "'vitals' groups in the codebook.",
            "Group resolution is ambiguous by design here; downstream "
            "code must pick one group deterministically or report the "
            "ambiguity, not crash or silently drop the item.",
        )
    )

    wide_rows = [
        {
            "participant_id": "sub-01",
            "session": "1",
            "resting_hr": 62,
            "grip_strength_left": 35,
            "vo2_max_estimated": 45,
            # wide AND long-style columns present simultaneously:
            "item_id": "resting_hr",
            "value": 999,
        },
        {
            "participant_id": "sub-02",
            "session": "01",
            "resting_hr": 500,  # out of codebook range
            "grip_strength_left": -10,  # out of codebook range
            "vo2_max_estimated": float("nan"),
        },
        {
            "participant_id": "sub-03",
            "session": "pre",
            "resting_hr": 70,
            "grip_strength_left": 40,
            "vo2_max_estimated": "N/A - refused",  # text in numeric field
        },
    ]
    cases.append(
        HostileCase(
            "bio_wide_long_ambiguous",
            "biometrics",
            "A row carries both wide per-item columns and a long-format "
            "item_id/value pair simultaneously.",
            "Fuzzy column detection must pick one interpretation "
            "consistently rather than double-counting the row.",
        )
    )
    cases.append(
        HostileCase(
            "bio_out_of_codebook_range",
            "biometrics",
            "resting_hr=500 and grip_strength_left=-10, both outside the "
            "codebook's documented min/max.",
            "Values pass through to the biometrics TSV; range "
            "enforcement is a validator/UI concern, not a converter crash.",
        )
    )
    cases.append(
        HostileCase(
            "bio_session_label_variants",
            "biometrics",
            "Sessions '1', '01', and 'pre' for different participants in "
            "the same file.",
            "Each session label is preserved verbatim — never coerced or "
            "treated as equal to another (CLAUDE.md session-label rule).",
        )
    )
    cases.append(
        HostileCase(
            "bio_unicode_item_values",
            "biometrics",
            "A numeric biometrics field unexpectedly contains free text "
            "('N/A - refused').",
            "Pipeline does not crash on the non-numeric value in a "
            "numeric column; it is preserved or coerced to NaN, not "
            "silently treated as 0.",
        )
    )

    long_rows = [
        {
            "participant_id": "sub-04",
            "session": "1",
            "item_id": "resting_hr",
            "value": 64,
            "instance": "trial-A",  # non-numeric instance
        },
        {
            "participant_id": "sub-04",
            "session": "1",
            "item_id": "grip_strength_left",
            "value": None,  # empty/NaN cell
            "instance": 1,
        },
        {
            "participant_id": "  Subject# 5  ",  # unrecognizable id-column noise
            "session": "1",
            "item_id": "vo2_max_estimated",
            "value": 50,
            "instance": 1,
        },
    ]
    cases.append(
        HostileCase(
            "bio_instance_non_numeric",
            "biometrics",
            "instance column contains a non-numeric value ('trial-A').",
            "Non-numeric instance values are coerced to NaN and the row "
            "is dropped from instance-pivoted output, not crashed on.",
        )
    )
    cases.append(
        HostileCase(
            "bio_nan_value_cells",
            "biometrics",
            "An empty/None value cell for an item_id.",
            "Serialized as the BIDS 'n/a' sentinel, not the literal "
            "string 'nan'.",
        )
    )
    cases.append(
        HostileCase(
            "bio_missing_participant_id_column_variants",
            "biometrics",
            "Participant id column padded with noise text instead of a "
            "recognizable header name.",
            "Column-detection fuzzy matching either recovers the column "
            "or fails with a clear, non-crashing error message.",
        )
    )

    return (
        pd.DataFrame(codebook_rows),
        pd.DataFrame(wide_rows),
        pd.DataFrame(long_rows),
        cases,
    )


def write_hostile_biometrics_inputs(root: Path, seed: int) -> list[HostileCase]:
    codebook_df, wide_df, long_df, cases = build_hostile_biometrics_inputs(seed)
    out_dir = ensure_dir(root / "code" / "rawdata")
    codebook_df.to_csv(out_dir / "hostile_biometrics_codebook.csv", index=False)
    wide_df.to_csv(out_dir / "hostile_biometrics_data_wide.csv", index=False)
    long_df.to_csv(out_dir / "hostile_biometrics_data_long.csv", index=False)
    return cases


# ---------------------------------------------------------------------------
# Environment / MRI
# ---------------------------------------------------------------------------


def build_hostile_environment_mri_tree(root: Path, seed: int) -> list[HostileCase]:
    cases: list[HostileCase] = []

    def write_sidecar(sub: str, ses: str, modality: str, stem: str, payload: dict) -> str:
        mod_dir = ensure_dir(root / sub / ses / modality)
        path = mod_dir / f"{stem}.json"
        write_json(path, payload)
        return path.relative_to(root).as_posix()

    loc = write_sidecar(
        "sub-env01",
        "ses-01",
        "anat",
        "sub-env01_ses-01_T1w",
        {"SeriesDescription": "T1w"},
    )
    cases.append(
        HostileCase(
            "env_missing_acquisition_datetime",
            "environment_mri",
            "Sidecar has no AcquisitionDateTime and no Date/Time or "
            "StudyDate/Time fallback fields.",
            "parse_sidecar_timestamp returns None cleanly; row is "
            "skipped, no exception.",
            loc,
        )
    )

    loc = write_sidecar(
        "sub-env01",
        "ses-01",
        "func",
        "sub-env01_ses-01_task-rest_bold",
        {"AcquisitionDateTime": "2026-13-45T99:99:99"},
    )
    cases.append(
        HostileCase(
            "env_malformed_acquisition_datetime",
            "environment_mri",
            "AcquisitionDateTime with an invalid month/day/hour "
            "(2026-13-45T99:99:99).",
            "Timestamp parsing fails gracefully (returns None), not an "
            "unhandled ValueError.",
            loc,
        )
    )

    loc = write_sidecar(
        "sub-env02",
        "ses-01",
        "func",
        "sub-env02_ses-01_task-dst_bold",
        {"AcquisitionDateTime": "2026-03-29T02:30:00"},
    )
    cases.append(
        HostileCase(
            "env_dst_crossing",
            "environment_mri",
            "Timestamp at 2026-03-29T02:30:00, inside the Europe/Vienna "
            "spring-forward DST transition window.",
            "Parses to a concrete datetime without raising on the "
            "ambiguous/nonexistent local time.",
            loc,
        )
    )

    loc = write_sidecar(
        "sub-env03",
        "ses-01",
        "anat",
        "sub-env03_ses-01_T1w",
        {"AcquisitionDate": "2024-02-29", "AcquisitionTime": "10:00:00"},
    )
    cases.append(
        HostileCase(
            "env_leap_day_valid",
            "environment_mri",
            "AcquisitionDate=2024-02-29 (a real leap day).",
            "Parses successfully to 2024-02-29T10:00:00.",
            loc,
        )
    )
    loc = write_sidecar(
        "sub-env03",
        "ses-02",
        "anat",
        "sub-env03_ses-02_T1w",
        {"AcquisitionDate": "2026-02-29", "AcquisitionTime": "10:00:00"},
    )
    cases.append(
        HostileCase(
            "env_leap_day_invalid",
            "environment_mri",
            "AcquisitionDate=2026-02-29 — 2026 is not a leap year, so "
            "this date does not exist.",
            "Parsing fails gracefully (returns None), not an unhandled "
            "exception.",
            loc,
        )
    )

    loc = write_sidecar(
        "sub-env04",
        "ses-01",
        "anat",
        "sub-env04_ses-01_T1w",
        {
            "AcquisitionDateTime": "2026-02-26T14:30:00",
            "InstitutionName": "MUG",
        },
    )
    cases.append(
        HostileCase(
            "env_missing_institution_address",
            "environment_mri",
            "InstitutionName present, InstitutionAddress absent.",
            "extract_sidecar_location falls back to InstitutionName "
            "without raising.",
            loc,
        )
    )

    loc = write_sidecar(
        "sub-env05",
        "ses-01",
        "anat",
        "sub-env05_ses-01_T1w",
        {
            "AcquisitionDate": "2026-02-26",
            "AcquisitionTime": "14:30:00",
            "StudyDate": "2026-02-20",
            "StudyTime": "08:00:00",
        },
    )
    cases.append(
        HostileCase(
            "env_conflicting_study_vs_acquisition_date",
            "environment_mri",
            "StudyDate (2026-02-20) differs from AcquisitionDate "
            "(2026-02-26) by 6 days in the same sidecar.",
            "AcquisitionDate/Time takes precedence over StudyDate/Time; "
            "the two are not averaged or merged.",
            loc,
        )
    )

    loc = write_sidecar(
        "sub-env06",
        "ses-01",
        "anat",
        "sub-env06_ses-01_T1w",
        {"AcquisitionDateTime": "2026-02-26T14:30:2.5"},
    )
    cases.append(
        HostileCase(
            "env_subsecond_fraction_single_digit",
            "environment_mri",
            "Seconds field is a single-digit fractional value "
            "('...T14:30:2.5') instead of zero-padded ('02.5').",
            "Seconds are zero-padded before parsing; no ValueError.",
            loc,
        )
    )

    loc = write_sidecar(
        "sub-env07",
        "ses-01",
        "anat",
        "sub-env07_ses-01_T1w",
        {"AcquisitionDateTime": "2026-02-26T14:30:00Z"},
    )
    write_sidecar(
        "sub-env07",
        "ses-02",
        "anat",
        "sub-env07_ses-02_T1w",
        {"AcquisitionDateTime": "2026-02-26T14:30:00"},
    )
    cases.append(
        HostileCase(
            "env_timezone_naive_vs_aware_mix",
            "environment_mri",
            "One sidecar uses a 'Z'-suffixed UTC timestamp, another (same "
            "subject, different session) uses a naive local timestamp.",
            "Both parse independently without raising; they are not "
            "silently treated as the same instant.",
            loc,
        )
    )

    weather_dir = ensure_dir(root / "code" / "rawdata")
    weather_path = weather_dir / "hostile_environment_weather_extremes.csv"
    weather_rows = [
        {
            "subject_id": "sub-env08",
            "session_id": "ses-01",
            "filename": "sub-env08_ses-01_T1w.nii.gz",
            "relative_time": 0,
            "temp_c": -89.2,
            "apparent_temp_c": -95.0,
            "humidity_pct": 100,
            "pressure_hpa": 1080,
            "aqi": 99999,
            "pm25_ug_m3": "",
            "pm10_ug_m3": float("nan"),
        },
        {
            "subject_id": "sub-env08",
            "session_id": "ses-02",
            "filename": "sub-env08_ses-02_T1w.nii.gz",
            "relative_time": 1,
            "temp_c": 56.7,
            "apparent_temp_c": 60.0,
            "humidity_pct": 0,
            "pressure_hpa": 870,
            "aqi": -5,
            "pm25_ug_m3": 0,
            "pm10_ug_m3": 0,
        },
    ]
    pd.DataFrame(weather_rows).to_csv(weather_path, index=False)
    cases.append(
        HostileCase(
            "env_weather_extremes",
            "environment_mri",
            "Synthetic weather rows with values outside any real-world "
            "record (temp_c=-89.2, aqi=99999, pm25_ug_m3 empty/NaN) — "
            "written directly to avoid live Open-Meteo API calls in tests.",
            "Downstream binning (hour_to_bin/season_code/etc.) does not "
            "raise on extreme or missing numeric values.",
            weather_path.relative_to(root).as_posix(),
        )
    )

    return cases


# ---------------------------------------------------------------------------
# Subject / session IDs
# ---------------------------------------------------------------------------


def build_hostile_subject_session_layout(root: Path, seed: int) -> list[HostileCase]:
    cases: list[HostileCase] = []

    def write_minimal_func(sub: str, ses: str) -> str:
        mod_dir = ensure_dir(root / sub / ses / "func")
        path = mod_dir / f"{sub}_{ses}_task-rest_bold.json"
        write_json(path, {"TaskName": "rest"})
        return path.relative_to(root).as_posix()

    # Note: true co-existing case-variant directories (sub-01 vs SUB-01) are
    # impossible to stage on a case-insensitive filesystem (default on
    # macOS/Windows) — the second mkdir silently lands inside the first. So
    # this case is exercised in the pytest stress suite via
    # SubjectCodeRewriter.preview(explicit_mapping=...) against a real
    # dataset, not by physically creating colliding directories here.
    loc1 = write_minimal_func("sub-01", "ses-01")
    cases.append(
        HostileCase(
            "subj_case_collision_no_merge",
            "subject_session",
            "A subject directory 'sub-01' that a rewrite plan targets via "
            "a pure case-only rename (e.g. from 'SUB-01').",
            "SubjectCodeRewriter must not treat a pure case-only rename "
            "as colliding with itself, but must still detect genuine "
            "collisions when a distinct, unrelated subject maps to the "
            "same target (see tests/test_hostile_demo_pipeline.py).",
            loc1,
        )
    )

    loc_many = write_minimal_func("sub-AAA", "ses-01")
    cases.append(
        HostileCase(
            "subj_many_to_one_merge_candidate",
            "subject_session",
            "A subject directory 'sub-AAA' used as one of three sources "
            "(alongside hypothetical 'sub-aaa', 'sub-Aaa') that would "
            "collapse to the same case-insensitive target under a rewrite "
            "rule. Real co-existing case-variant directories cannot be "
            "staged on a case-insensitive filesystem, so the merge path "
            "is exercised via explicit_mapping in the pipeline tests.",
            "Rewriting with allow_many_to_one=False reports conflicts; "
            "with allow_many_to_one=True, directories are merged without "
            "data loss.",
            loc_many,
        )
    )

    loc = write_minimal_func("sub-Muller", "ses-01")
    # Separately drop a real non-ASCII directory the rewriter's
    # sub-[A-Za-z0-9]+ token pattern will not recognize as a subject token.
    nonascii_dir = ensure_dir(root / "sub-Müller" / "ses-01" / "func")
    nonascii_path = nonascii_dir / "sub-Müller_ses-01_task-rest_bold.json"
    write_json(nonascii_path, {"TaskName": "rest"})
    cases.append(
        HostileCase(
            "subj_non_ascii_id",
            "subject_session",
            "Subject directory 'sub-Müller' (non-ASCII character in "
            "the label).",
            "The rewriter's subject-token regex (sub-[A-Za-z0-9]+) does "
            "not match non-ASCII labels, so this directory is silently "
            "skipped by rewrite operations rather than crashing — a "
            "known gap to be aware of, not a pipeline failure.",
            nonascii_path.relative_to(root).as_posix(),
        )
    )

    for ses in ("ses-1", "ses-01", "ses-pre"):
        write_minimal_func("sub-sess01", ses)
    cases.append(
        HostileCase(
            "sess_no_coercion_1_vs_01_vs_pre",
            "subject_session",
            "Same subject (sub-sess01) with three sessions literally "
            "named ses-1, ses-01, and ses-pre.",
            "All three remain distinct, exact-string session labels "
            "throughout every pipeline stage (participants, biometrics, "
            "environment, recipes, export) — never coerced or treated as "
            "equal, per the repository's session-label rule.",
        )
    )

    # Kept just under the common 255-byte per-component filesystem limit
    # (macOS/Linux) so the directory can actually be created — the point is
    # to stress unusually long labels, not to hit an unrelated OS ceiling.
    long_id = "sub-" + ("Z" * 200)
    write_minimal_func(long_id, "ses-01")
    cases.append(
        HostileCase(
            "subj_extremely_long_subject_id",
            "subject_session",
            "A 204-character subject directory name.",
            "Filesystem path creation succeeds; downstream pipeline code "
            "does not silently truncate the id.",
        )
    )

    return cases


# ---------------------------------------------------------------------------
# BIDS entity rewriting (task/acq/run, distinct from subject rewriting)
# ---------------------------------------------------------------------------


def build_hostile_entity_rewrite_targets(root: Path, seed: int) -> list[HostileCase]:
    cases: list[HostileCase] = []

    def write_func(sub: str, ses: str, stem_suffix: str) -> str:
        mod_dir = ensure_dir(root / sub / ses / "func")
        path = mod_dir / f"{sub}_{ses}_{stem_suffix}_bold.json"
        write_json(path, {"TaskName": stem_suffix.split("_")[0].split("-")[-1]})
        return path.relative_to(root).as_posix()

    loc_a = write_func("sub-ent01", "ses-01", "task-rest_acq-A")
    loc_b = write_func("sub-ent01", "ses-01", "task-rest_acq-Z")
    cases.append(
        HostileCase(
            "entity_acq_rename_real_collision",
            "entity_rewrite",
            "Two files for the same subject/task differing only in the "
            "'acq' entity value (acq-A, acq-Z) — distinct values, not a "
            "case variant, so this is staffable on any filesystem.",
            "BidsEntityRewriter.preview(entity='acq', operation='rename', "
            "current_value='Z', replacement='A') must report a conflict: "
            "renaming acq-Z to acq-A would collide with the existing "
            "acq-A file.",
            f"{loc_a}, {loc_b}",
        )
    )

    loc_r1 = write_func("sub-ent02", "ses-01", "task-mem_run-01")
    loc_r2 = write_func("sub-ent02", "ses-01", "task-mem_run-02")
    loc_r3 = write_func("sub-ent02", "ses-01", "task-mem")
    cases.append(
        HostileCase(
            "entity_run_delete_real_collision",
            "entity_rewrite",
            "Two run values (run-01, run-02) for task-mem, plus a third "
            "file for the same task that already has no 'run' entity at "
            "all — deleting run-01's entity would collide with the "
            "pre-existing bare file.",
            "BidsEntityRewriter has no many-to-one merge option (unlike "
            "the subject rewriter); preview(entity='run', "
            "operation='delete', current_value='01') must report a "
            "conflict against the pre-existing bare task-mem file rather "
            "than silently overwriting it. Note: deleting 'run' with no "
            "current_value at all is rejected up front with a clear "
            "ValueError ('part has multiple values') precisely because "
            "the entity has more than one observed value — the API "
            "refuses the ambiguous bulk case outright.",
            f"{loc_r1}, {loc_r2}, {loc_r3}",
        )
    )

    cases.append(
        HostileCase(
            "entity_sub_not_editable",
            "entity_rewrite",
            "An attempt to rewrite the 'sub' entity through the generic "
            "BIDS entity rewriter instead of the dedicated subject "
            "rewriter.",
            "BidsEntityRewriter.preview(entity='sub', ...) raises a clear "
            "ValueError ('Part _sub is not editable here...'), not an "
            "unhandled exception or a silent no-op.",
            loc_a,
        )
    )

    return cases


# ---------------------------------------------------------------------------
# Recipe definitions (survey + biometrics scoring)
# ---------------------------------------------------------------------------


def build_hostile_recipe_definitions(root: Path, seed: int) -> list[HostileCase]:
    cases: list[HostileCase] = []

    survey_dir = ensure_dir(root / "code" / "recipes" / "survey")
    biometrics_dir = ensure_dir(root / "code" / "recipes" / "biometrics")

    missing_taskname = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"Name": "Missing TaskName recipe"},
        "Scores": [
            {"Name": "total", "Items": ["Q1", "Q2"], "Method": "mean"}
        ],
    }
    path = survey_dir / "recipe-hostile-missing-taskname.json"
    write_json(path, missing_taskname)
    cases.append(
        HostileCase(
            "recipe_missing_survey_taskname",
            "recipes",
            "A survey recipe with Kind='survey' but no Survey.TaskName.",
            "validate_recipe() returns a non-empty error list "
            "('Survey.TaskName must be a non-empty string'); does not "
            "raise.",
            path.relative_to(root).as_posix(),
        )
    )

    formula_missing_items = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {"TaskName": "hostile-formula"},
        "Scores": [
            {
                "Name": "derived_total",
                "Items": ["Q1", "Q2"],
                "Method": "formula",
                "Formula": "{Q1} + {Q2} + {Q3}",
            }
        ],
    }
    path = survey_dir / "recipe-hostile-formula-missing-items.json"
    write_json(path, formula_missing_items)
    cases.append(
        HostileCase(
            "recipe_formula_references_missing_item",
            "recipes",
            "A formula-based score whose Formula references {Q3}, which "
            "is not listed in Items.",
            "validate_recipe() flags the unsubstituted placeholder rather "
            "than letting it reach scoring (where it would be silently "
            "left as the literal string '{Q3}').",
            path.relative_to(root).as_posix(),
        )
    )

    invalid_kind = {
        "RecipeVersion": "1.0",
        "Kind": "spreadsheet",
        "Scores": [],
    }
    path = survey_dir / "recipe-hostile-invalid-kind.json"
    write_json(path, invalid_kind)
    cases.append(
        HostileCase(
            "recipe_invalid_kind",
            "recipes",
            "A recipe whose Kind is neither 'survey' nor 'biometrics'.",
            "validate_recipe() reports \"Kind must be 'survey' or "
            "'biometrics'\".",
            path.relative_to(root).as_posix(),
        )
    )

    biometrics_missing_name = {
        "RecipeVersion": "1.0",
        "Kind": "biometrics",
        "Biometrics": {},
        "Scores": [{"Name": "fitness_total", "Items": ["resting_hr"], "Method": "mean"}],
    }
    path = biometrics_dir / "recipe-hostile-missing-biometric-name.json"
    write_json(path, biometrics_missing_name)
    cases.append(
        HostileCase(
            "recipe_biometrics_missing_name",
            "recipes",
            "A biometrics recipe with an empty Biometrics object (no "
            "BiometricName).",
            "validate_recipe() reports the missing BiometricName field.",
            path.relative_to(root).as_posix(),
        )
    )

    return cases


# ---------------------------------------------------------------------------
# Input format diversity (encodings, spreadsheet formats)
# ---------------------------------------------------------------------------


def write_hostile_input_format_variants(root: Path, seed: int) -> list[HostileCase]:
    cases: list[HostileCase] = []
    out_dir = ensure_dir(root / "code" / "rawdata")

    df, _ = build_hostile_participants_table(seed)
    # Rows 0-1 (socio_age_out_of_range) are plain ASCII; later rows carry
    # the deliberately unicode/RTL free text used for the sociodemo domain,
    # which can't round-trip through latin-1 — keep this subset ASCII-only
    # so the encoding stress below is isolated to the encoding itself.
    df_small = df.head(2)

    utf16_path = out_dir / "hostile_participants_utf16.csv"
    utf16_path.write_text(df_small.to_csv(index=False), encoding="utf-16")
    cases.append(
        HostileCase(
            "input_utf16_encoded_csv",
            "input_formats",
            "A participants CSV encoded as UTF-16 instead of UTF-8.",
            "read_tabular_file's encoding fallback chain "
            "(utf-8-sig -> utf-8 -> latin-1 -> cp1252) does not include "
            "utf-16, so this either fails with a clear, catchable error "
            "or is misread as a single garbled column — not a silent "
            "successful-but-wrong parse treated as valid data.",
            utf16_path.relative_to(root).as_posix(),
        )
    )

    latin1_path = out_dir / "hostile_participants_latin1.csv"
    raw_text = df_small.to_csv(index=False)
    # Force a genuinely non-UTF-8 byte sequence (e.g. 'Ä' in Latin-1) so the
    # fallback chain's later candidates are actually exercised.
    raw_text = raw_text.replace("001", "M\xfcller-001")
    latin1_path.write_bytes(raw_text.encode("latin-1"))
    cases.append(
        HostileCase(
            "input_latin1_encoded_csv",
            "input_formats",
            "A participants CSV containing Latin-1-only byte sequences "
            "(invalid as UTF-8).",
            "read_tabular_file falls back to latin-1/cp1252 and parses "
            "successfully without raising.",
            latin1_path.relative_to(root).as_posix(),
        )
    )

    _, wide_df, _, _ = build_hostile_biometrics_inputs(seed)
    xlsx_df = wide_df.copy()
    xlsx_df["vo2_max_estimated"] = xlsx_df["vo2_max_estimated"].astype(object)
    xlsx_df.loc[0, "vo2_max_estimated"] = "=1+1"  # formula-like cell value
    xlsx_path = out_dir / "hostile_biometrics_data_wide.xlsx"
    xlsx_df.to_excel(xlsx_path, index=False, engine="openpyxl")
    cases.append(
        HostileCase(
            "input_xlsx_with_formula_like_cell",
            "input_formats",
            "A biometrics .xlsx cell holding a spreadsheet-formula-like "
            "string ('=1+1'), written via pandas.DataFrame.to_excel "
            "(openpyxl engine) the same way an end user's exported "
            "CSV-injection payload would arrive.",
            "KNOWN RISK, not a safe pass: openpyxl writes a string "
            "starting with '=' as a live formula cell with no cached "
            "value, so pandas.read_excel reads it back as NaN, not the "
            "literal text. Any PRISM code path that writes raw "
            "user-supplied strings to .xlsx via to_excel/openpyxl "
            "silently turns CSV-injection payloads into live formulas — "
            "flag for follow-up (escape leading =/+/-/@ before writing, "
            "or write via a text-formatted cell).",
            xlsx_path.relative_to(root).as_posix(),
        )
    )

    return cases


# ---------------------------------------------------------------------------
# Full survey run: a freshly-generated random survey template + hostile
# response-table import variants + a scoring recipe exercised across every
# output format.
# ---------------------------------------------------------------------------


def build_random_survey_template(seed: int) -> tuple[str, dict[str, Any], list[str]]:
    """Generate a brand-new (not from official/library) single-variant
    survey template, purely for stress-testing import/scoring — not a real
    instrument."""
    rng = random.Random(seed)
    task_name = f"rndsurvey{seed % 1000}"
    item_count = rng.randint(5, 8)
    item_codes = [f"{task_name.upper()}{i + 1:02d}" for i in range(item_count)]

    template: dict[str, Any] = {
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "csv",
            "Language": "en",
            "Respondent": "self",
        },
        "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2026-06-21"},
        "Study": {
            "OriginalName": {"en": f"Randomly Generated Test Survey {seed}"},
            "ShortName": task_name.upper(),
            "Authors": ["hostile_demo_generator"],
            "Year": 2026,
            "ItemCount": item_count,
            "License": {"en": "Synthetic test fixture, not a real instrument"},
            "Source": "generated for testing",
            "Instructions": {"en": "Synthetic test survey — for pipeline testing only."},
        },
    }
    for code in item_codes:
        template[code] = {
            "Description": {"en": f"Synthetic test item {code}"},
            "Reversed": False,
            "Levels": {
                "0": {"en": "Never"},
                "1": {"en": "Rarely"},
                "2": {"en": "Sometimes"},
                "3": {"en": "Often"},
                "4": {"en": "Always"},
            },
            "DataType": "integer",
            "MinValue": 0,
            "MaxValue": 4,
            "ScaleType": "likert",
        }
    return task_name, template, item_codes


def build_hostile_survey_response_variants(
    task_name: str, item_codes: list[str], seed: int
) -> list[tuple[str, bytes, HostileCase]]:
    """Return (filename, raw_bytes, case) tuples — each file isolates one
    hostile import scenario for the survey response converter
    (SurveyResponsesConverter.convert_xlsx, which despite the name also
    reads .csv/.tsv)."""
    rng = random.Random(seed)
    variants: list[tuple[str, bytes, HostileCase]] = []

    def likert_row(pid: str, **overrides: Any) -> dict[str, Any]:
        row = {"participant_id": pid}
        for code in item_codes:
            row[code] = overrides.get(code, rng.randint(0, 4))
        return row

    # Clean baseline — sanity check the template/items round-trip at all.
    clean_rows = [likert_row(f"sub-{i:02d}") for i in range(1, 6)]
    clean_csv = pd.DataFrame(clean_rows).to_csv(index=False)
    variants.append(
        (
            "survey_clean_baseline.csv",
            clean_csv.encode("utf-8"),
            HostileCase(
                "survey_clean_baseline",
                "survey_full_run",
                "5 clean rows with in-range Likert values, no hostile content.",
                "Converts successfully with no warnings; sanity baseline for "
                "the other variants.",
            ),
        )
    )

    # Exact duplicate rows (identical participant_id, identical answers).
    exact_dup_rows = clean_rows[:3] + [dict(clean_rows[0])]
    exact_dup_csv = pd.DataFrame(exact_dup_rows).to_csv(index=False)
    variants.append(
        (
            "survey_exact_duplicate_rows.csv",
            exact_dup_csv.encode("utf-8"),
            HostileCase(
                "survey_exact_duplicate_rows",
                "survey_full_run",
                "The same participant_id appears twice with identical answers.",
                "duplicate_handling='error' raises a clear ValueError naming "
                "the duplicated id; 'keep_first'/'keep_last' silently drop "
                "the extra row instead of crashing.",
            ),
        )
    )

    # Conflicting duplicate rows (same id, different answers each time).
    conflict_pid = "sub-conflict"
    conflicting_dup_rows = [
        likert_row(conflict_pid, **{item_codes[0]: 1}),
        likert_row(conflict_pid, **{item_codes[0]: 4}),
    ]
    conflicting_dup_csv = pd.DataFrame(conflicting_dup_rows).to_csv(index=False)
    variants.append(
        (
            "survey_conflicting_duplicate_rows.csv",
            conflicting_dup_csv.encode("utf-8"),
            HostileCase(
                "survey_conflicting_duplicate_rows",
                "survey_full_run",
                "The same participant_id appears twice with DIFFERENT "
                "answers for the same item — a genuine data conflict, not "
                "just a redundant row.",
                "duplicate_handling='error' raises before either answer set "
                "is silently chosen; 'keep_first'/'keep_last' deterministically "
                "pick one without crashing, but discard real information.",
            ),
        )
    )

    # Multi-session rows: same participant_id, different session — must NOT
    # be treated as a duplicate.
    session_rows = [
        {**likert_row("sub-multisession"), "session": "ses-1"},
        {**likert_row("sub-multisession"), "session": "ses-2"},
    ]
    session_csv = pd.DataFrame(session_rows).to_csv(index=False)
    variants.append(
        (
            "survey_multi_session_same_participant.csv",
            session_csv.encode("utf-8"),
            HostileCase(
                "survey_multi_session_same_participant",
                "survey_full_run",
                "Same participant_id across two different session values "
                "(ses-1, ses-2) — a legitimate repeated-measures design.",
                "Converter's composite duplicate key is (id, session, run), "
                "so this must NOT raise as a duplicate even under "
                "duplicate_handling='error'. By design, one convert() call "
                "processes one session at a time (matching the documented "
                "wellbeing_multi_demo workflow): a single call without an "
                "explicit session= auto-filters to the first detected "
                "session only, silently leaving later sessions unconverted "
                "with no error — the caller must repeat the call once per "
                "session (session='ses-1', then session='ses-2') to import "
                "all of them.",
            ),
        )
    )

    # Out-of-range item value (template levels are 0-4).
    out_of_range_rows = [likert_row("sub-oor", **{item_codes[0]: 99})]
    out_of_range_csv = pd.DataFrame(out_of_range_rows).to_csv(index=False)
    variants.append(
        (
            "survey_out_of_range_value.csv",
            out_of_range_csv.encode("utf-8"),
            HostileCase(
                "survey_out_of_range_value",
                "survey_full_run",
                f"{item_codes[0]}=99, far outside the template's documented "
                "0-4 Levels range.",
                "Raises SurveyValueOutOfBoundsError (a clean, structured "
                "ValueError) rather than silently accepting an "
                "uninterpretable response code.",
            ),
        )
    )

    # Missing/empty cell for one item on one row.
    missing_rows = [likert_row(f"sub-miss{i}") for i in range(1, 3)]
    missing_rows[0][item_codes[-1]] = ""
    missing_csv = pd.DataFrame(missing_rows).to_csv(index=False)
    variants.append(
        (
            "survey_missing_cell.csv",
            missing_csv.encode("utf-8"),
            HostileCase(
                "survey_missing_cell",
                "survey_full_run",
                f"Empty cell for {item_codes[-1]} on one row.",
                "Converts successfully; the missing cell is recorded as the "
                "dataset's missing-value token, not coerced to 0 or dropped "
                "as a whole row.",
            ),
        )
    )

    # Extra unmapped column the template doesn't define.
    unmapped_rows = [
        {**likert_row(f"sub-extra{i}"), "interviewer_comments": "looked tired, asked to repeat Q3"}
        for i in range(1, 3)
    ]
    unmapped_csv = pd.DataFrame(unmapped_rows).to_csv(index=False)
    variants.append(
        (
            "survey_unmapped_extra_column.csv",
            unmapped_csv.encode("utf-8"),
            HostileCase(
                "survey_unmapped_extra_column",
                "survey_full_run",
                "An 'interviewer_comments' free-text column with no "
                "matching template item, including a comma inside the "
                "free-text value itself (quoted by the CSV writer).",
                "unknown='warn' (default) surfaces the column in "
                "unknown_columns rather than silently dropping or crashing "
                "on the embedded comma — the CSV quoting must round-trip "
                "correctly through the parser.",
            ),
        )
    )

    # Genuinely malformed delimiters: tab characters mixed into a
    # comma-delimited file, producing an inconsistent column count per row.
    header = "participant_id," + ",".join(item_codes)
    good_row = "sub-malformed1," + ",".join(str(rng.randint(0, 4)) for _ in item_codes)
    bad_row = "sub-malformed2\t" + "\t".join(str(rng.randint(0, 4)) for _ in item_codes)
    malformed_text = "\n".join([header, good_row, bad_row]) + "\n"
    variants.append(
        (
            "survey_mixed_tab_comma_delimiters.csv",
            malformed_text.encode("utf-8"),
            HostileCase(
                "survey_mixed_tab_comma_delimiters",
                "survey_full_run",
                "A .csv file where one row uses tab characters instead of "
                "commas, producing a row that doesn't split into the same "
                "number of columns as the header.",
                "KNOWN GAP, not a safe pass: the whole-file delimiter is "
                "sniffed once from the header, so the tab-delimited row "
                "parses as a single unsplit value in the participant_id "
                "column. That value is then alphanumeric-sanitized "
                "(tabs/digits concatenated), producing a garbled but "
                "plausible-looking id (e.g. 'sub-malformed2410144') with "
                "every real item answer silently lost — no error, no "
                "warning, no row dropped. Flag for follow-up: per-row "
                "column-count validation against the header before "
                "accepting a row.",
            ),
        )
    )

    return variants


def build_hostile_survey_recipe(
    task_name: str, item_codes: list[str]
) -> tuple[dict[str, Any], HostileCase]:
    recipe = {
        "RecipeVersion": "1.0",
        "Kind": "survey",
        "Survey": {
            "Name": f"Random test survey ({task_name})",
            "TaskName": task_name,
            "Description": "Synthetic recipe generated for hostile-demo pipeline testing.",
        },
        "Scores": [
            {
                "Name": f"{task_name}_total",
                "Description": "Mean of all items",
                "Items": list(item_codes),
                "Method": "mean",
                "Range": {"min": 0, "max": 4},
            },
            {
                "Name": f"{task_name}_first_minus_last",
                "Description": "Formula score referencing the first and last item",
                "Items": [item_codes[0], item_codes[-1]],
                "Method": "formula",
                "Formula": f"{{{item_codes[0]}}} - {{{item_codes[-1]}}}",
            },
        ],
    }
    case = HostileCase(
        "survey_recipe_mean_and_formula_scores",
        "survey_full_run",
        "A recipe combining a plain 'mean' score and a 'formula' score "
        "over the freshly generated random survey's items.",
        "validate_recipe() reports no errors; compute_survey_recipes() "
        "produces correct scores across every supported out_format "
        "(flat, prism, csv, xlsx, sav).",
    )
    return recipe, case


def write_hostile_survey_assets(root: Path, seed: int) -> list[HostileCase]:
    cases: list[HostileCase] = []

    task_name, template, item_codes = build_random_survey_template(seed)

    library_dir = ensure_dir(root / "code" / "library" / "survey")
    write_json(library_dir / f"survey-{task_name}.json", template)

    rawdata_dir = ensure_dir(root / "code" / "rawdata")
    for filename, raw_bytes, case in build_hostile_survey_response_variants(
        task_name, item_codes, seed
    ):
        (rawdata_dir / filename).write_bytes(raw_bytes)
        case.location = f"code/rawdata/{filename}"
        cases.append(case)

    recipes_dir = ensure_dir(root / "code" / "recipes" / "survey")
    recipe, recipe_case = build_hostile_survey_recipe(task_name, item_codes)
    recipe_path = recipes_dir / f"recipe-{task_name}.json"
    write_json(recipe_path, recipe)
    recipe_case.location = recipe_path.relative_to(root).as_posix()
    cases.append(recipe_case)

    return cases


# ---------------------------------------------------------------------------
# participants.tsv merge: cross-source matching, including subject IDs that
# differ only by case between independently-uploaded sources.
# ---------------------------------------------------------------------------


def build_hostile_participants_merge_assets(
    seed: int,
) -> list[tuple[str, pd.DataFrame, HostileCase]]:
    """Return (filename, dataframe, case) tuples for the participants-merge
    domain. The first file becomes the baseline participants.tsv (via a
    normal participants conversion); the rest are merged into it via
    preview_participants_merge/apply_participants_merge — the same
    functions the Participants Merge UI/CLI call."""
    variants: list[tuple[str, pd.DataFrame, HostileCase]] = []

    initial_df = pd.DataFrame(
        [
            {"ID": "sub-100", "age": 25, "sex": "F"},
            {"ID": "sub-101", "age": 30, "sex": "M"},
            # Deliberately mixed-case label (not just prefix) to probe
            # cross-source case sensitivity once a second source arrives.
            {"ID": "sub-Ab", "age": 22, "sex": "F"},
        ]
    )
    variants.append(
        (
            "participants_merge_initial_source.csv",
            initial_df,
            HostileCase(
                "participants_merge_initial_source",
                "participants_merge",
                "Baseline participants source (3 rows) converted first to "
                "create the project's participants.tsv, before any merge.",
                "Converts cleanly via ParticipantsConverter; becomes the "
                "'existing' side of every merge scenario below.",
            ),
        )
    )

    incoming_df = pd.DataFrame(
        [
            # Exact match on an existing id: age unchanged (no conflict),
            # adds a brand-new 'group' column.
            {"ID": "sub-101", "age": 30, "group": "control"},
            # Brand-new participant not in the initial source.
            {"ID": "sub-102", "age": 28, "group": "patient"},
            # Same physical-looking id as the existing 'sub-Ab', but with a
            # different case in the LABEL itself (not just the 'sub-'
            # prefix). Independent uploads from two different sources (e.g.
            # a clinician's spreadsheet vs. a lab's export) commonly drift
            # like this.
            {"ID": "sub-ab", "age": 22, "group": "control"},
        ]
    )
    variants.append(
        (
            "participants_merge_incoming_source.csv",
            incoming_df,
            HostileCase(
                "participants_merge_cross_source_case_sensitivity",
                "participants_merge",
                "A second, independent source merged into the existing "
                "participants.tsv: sub-101 matches exactly (gets a new "
                "'group' column merged in), sub-102 is a new participant, "
                "and sub-ab is offered as if it were the existing sub-Ab "
                "but differs in label case.",
                "Merge ID matching is exact-string set intersection on the "
                "already-normalized id (only the 'sub-'/'SUB-' prefix is "
                "case-normalized; the label itself is never "
                "case-folded) — there is no fuzzy or case-insensitive "
                "matching. sub-101 lands in matched_participants; sub-102 "
                "and sub-ab BOTH land in new_participants (sub-ab is "
                "correctly treated as a distinct subject from sub-Ab, "
                "never silently merged). This is confirmed, correct, "
                "by-design behavior at the participants.tsv layer. "
                "IMPORTANT CAVEAT found via this exact scenario: importing "
                "actual modality data (biometrics/survey) for sub-Ab and "
                "sub-ab in the SAME run used to silently corrupt data — on "
                "the case-insensitive filesystems that ship by default on "
                "macOS and Windows, both ids resolve to the identical "
                "on-disk directory, so the second participant written "
                "silently overwrote the first's file with no error. Fixed: "
                "convert_biometrics_table_to_prism_dataset and "
                "convert_survey_xlsx_to_prism_dataset now both call "
                "src.cross_platform.describe_case_insensitive_id_collisions "
                "before writing anything and raise a clear ValueError "
                "instead (see tests/test_hostile_demo_pipeline.py::"
                "test_biometrics_conversion_rejects_case_only_differing_ids "
                "and the equivalent survey test).",
            ),
        )
    )

    conflicting_df = pd.DataFrame(
        [
            {"ID": "sub-103", "age": 40, "group": "control"},
            # Same id, different age, within the SAME incoming source.
            {"ID": "sub-103", "age": 41, "group": "control"},
        ]
    )
    variants.append(
        (
            "participants_merge_incoming_conflicting_duplicates.csv",
            conflicting_df,
            HostileCase(
                "participants_merge_incoming_internal_conflict",
                "participants_merge",
                "The incoming source itself has two rows for sub-103 with "
                "different ages — a genuine conflict within a single "
                "upload, before any comparison against the existing table.",
                "preview_participants_merge()/apply_participants_merge() "
                "raise a clear ValueError naming the conflicting column "
                "('non-unique values for the selected ID column... "
                "Conflicting selected columns: age') rather than silently "
                "picking one value — stricter than ParticipantsConverter's "
                "own 'keep first non-empty value' collapsing for the same "
                "shape of input.",
            ),
        )
    )

    return variants


def write_hostile_participants_merge_assets(root: Path, seed: int) -> list[HostileCase]:
    cases: list[HostileCase] = []
    rawdata_dir = ensure_dir(root / "code" / "rawdata")
    for filename, df, case in build_hostile_participants_merge_assets(seed):
        df.to_csv(rawdata_dir / filename, index=False)
        case.location = f"code/rawdata/{filename}"
        cases.append(case)
    return cases


def assert_text_files_never_annexed(root: Path) -> list[str]:
    """Return a list of relative paths that violate the never-annex policy.

    A text-extension file violates the policy if it is a symlink whose
    target lives under .git/annex/objects.
    """
    text_suffixes = {
        ".csv",
        ".tsv",
        ".json",
        ".jsonl",
        ".ndjson",
        ".txt",
        ".xml",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".md",
        ".xlsx",
        ".xls",
        ".ods",
    }
    violations: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() and not path.is_symlink():
            continue
        if path.suffix.lower() not in text_suffixes:
            continue
        if path.is_symlink():
            target = str(path.resolve())
            if ".git/annex/objects" in target.replace("\\", "/"):
                violations.append(path.relative_to(root).as_posix())
    return violations


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def generate_hostile_dataset(
    output_root: Path,
    *,
    seed: int = 20260620,
    domains: set[str] | None = None,
    use_datalad: bool = False,
    name: str = "hostile_demo",
) -> HostileGenerationResult:
    output_root = Path(output_root).resolve()
    selected = ALL_DOMAINS if not domains else (domains & ALL_DOMAINS)

    manager = ProjectManager()
    create_result = manager.create_project(
        str(output_root), {"name": name, "use_datalad": use_datalad}
    )
    if not create_result.get("success", False):
        raise RuntimeError(
            f"Failed to create base project at {output_root}: "
            f"{create_result.get('error')}"
        )

    result = HostileGenerationResult(project_root=output_root)

    if "sociodemo" in selected:
        cases = write_hostile_participants_raw_csv(output_root, seed)
        result.cases.extend(cases)
        _record(
            result.files_written,
            "sociodemo",
            "code/rawdata/hostile_participants_raw.csv",
        )

    if "biometrics" in selected:
        cases = write_hostile_biometrics_inputs(output_root, seed)
        result.cases.extend(cases)
        for fname in (
            "hostile_biometrics_codebook.csv",
            "hostile_biometrics_data_wide.csv",
            "hostile_biometrics_data_long.csv",
        ):
            _record(result.files_written, "biometrics", f"code/rawdata/{fname}")

    if "environment_mri" in selected:
        cases = build_hostile_environment_mri_tree(output_root, seed)
        result.cases.extend(cases)
        for case in cases:
            if case.location:
                _record(result.files_written, "environment_mri", case.location)

    if "subject_session" in selected:
        cases = build_hostile_subject_session_layout(output_root, seed)
        result.cases.extend(cases)
        for case in cases:
            if case.location:
                _record(result.files_written, "subject_session", case.location)

    if "entity_rewrite" in selected:
        cases = build_hostile_entity_rewrite_targets(output_root, seed)
        result.cases.extend(cases)
        for case in cases:
            if case.location:
                _record(result.files_written, "entity_rewrite", case.location)

    if "recipes" in selected:
        cases = build_hostile_recipe_definitions(output_root, seed)
        result.cases.extend(cases)
        for case in cases:
            if case.location:
                _record(result.files_written, "recipes", case.location)

    if "input_formats" in selected:
        cases = write_hostile_input_format_variants(output_root, seed)
        result.cases.extend(cases)
        for case in cases:
            if case.location:
                _record(result.files_written, "input_formats", case.location)

    if "survey_full_run" in selected:
        cases = write_hostile_survey_assets(output_root, seed)
        result.cases.extend(cases)
        for case in cases:
            if case.location:
                _record(result.files_written, "survey_full_run", case.location)

    if "participants_merge" in selected:
        cases = write_hostile_participants_merge_assets(output_root, seed)
        result.cases.extend(cases)
        for case in cases:
            if case.location:
                _record(result.files_written, "participants_merge", case.location)

    return result
