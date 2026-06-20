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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from src.project_manager import ProjectManager
from src.utils.io import ensure_dir, write_json

ALL_DOMAINS = {"sociodemo", "biometrics", "environment_mri", "subject_session"}


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
            "ethnicity_other": "Ŧëśt 测试 \U0001f9ec ‮reversed",
            "medication_details": "Sertraline 50mg ‮لا",
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

    return result
