"""How sociodemographic data behaves when columns arrive from several
independent, real-world sources: the lab's own intake form, a second
team's socioeconomic spreadsheet, and a third collaborator's handedness
export — each adding new columns and, in some cases, new participants.

Exercises the real production functions the Participants Converter and
Participants Merge UI/CLI call: ParticipantsConverter.convert_participant_data
(to build the baseline participants.tsv) and
preview_participants_merge/apply_participants_merge (src/participants_backend.py)
for folding each subsequent source in.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.participants_backend import apply_participants_merge, preview_participants_merge
from src.participants_converter import ParticipantsConverter


def _run_pipeline_stage(label, fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001 - intentionally broad: see module docstring
        pytest.fail(f"{label} raised unexpectedly: {exc!r}", pytrace=True)


def _mapping(**columns: str) -> dict:
    """Build a participants-converter mapping dict: source_column ==
    standard_variable for every kwarg, plus the always-required id column
    mapped from 'ID'."""
    mappings = {
        "participant_id": {"source_column": "ID", "standard_variable": "participant_id"},
    }
    for standard_variable, source_column in columns.items():
        mappings[standard_variable] = {
            "source_column": source_column,
            "standard_variable": standard_variable,
        }
    return {"version": "1.0", "mappings": mappings}


@pytest.fixture
def three_source_project(tmp_path: Path) -> Path:
    """A project whose participants.tsv has been built from one baseline
    source and enriched by merging two further, independent sources."""
    root = tmp_path / "project"
    root.mkdir()

    # Source 1: the lab's own intake form (age, sex) for 5 participants.
    source1 = root / "source1_intake.csv"
    pd.DataFrame(
        [
            {"ID": "sub-001", "age": 24, "sex": "F"},
            {"ID": "sub-002", "age": 31, "sex": "M"},
            {"ID": "sub-003", "age": 27, "sex": "F"},
            {"ID": "sub-004", "age": 45, "sex": "M"},
            {"ID": "sub-005", "age": 22, "sex": "F"},
        ]
    ).to_csv(source1, index=False)

    converter = ParticipantsConverter(root)
    success, df, _messages = _run_pipeline_stage(
        "convert source1 (baseline intake)",
        converter.convert_participant_data,
        source1,
        _mapping(age="age", sex="sex"),
    )
    assert success is True
    df.to_csv(root / "participants.tsv", sep="\t", index=False)

    # Source 2: a different team's socioeconomic spreadsheet — enriches two
    # existing participants (sub-002, sub-003) and introduces two brand-new
    # ones (sub-006, sub-007) this team recruited independently.
    source2 = root / "source2_socioeconomic.csv"
    pd.DataFrame(
        [
            {"ID": "sub-002", "education_level": "Bachelor", "employment_status": "employed"},
            {"ID": "sub-003", "education_level": "Master", "employment_status": "student"},
            {"ID": "sub-006", "education_level": "PhD", "employment_status": "employed"},
            {"ID": "sub-007", "education_level": "Highschool", "employment_status": "unemployed"},
        ]
    ).to_csv(source2, index=False)
    _run_pipeline_stage(
        "merge source2 (socioeconomic)",
        apply_participants_merge,
        root,
        source2,
        _mapping(education_level="education_level", employment_status="employment_status"),
    )

    # Source 3: a third collaborator's export — enriches two more existing
    # participants (sub-001, sub-004) and introduces one more new one
    # (sub-008).
    source3 = root / "source3_handedness.csv"
    pd.DataFrame(
        [
            {"ID": "sub-001", "handedness": "R", "country_of_residence": "AT"},
            {"ID": "sub-004", "handedness": "L", "country_of_residence": "DE"},
            {"ID": "sub-008", "handedness": "R", "country_of_residence": "CH"},
        ]
    ).to_csv(source3, index=False)
    _run_pipeline_stage(
        "merge source3 (handedness)",
        apply_participants_merge,
        root,
        source3,
        _mapping(handedness="handedness", country_of_residence="country_of_residence"),
    )

    return root


def _read_participants(root: Path) -> pd.DataFrame:
    return pd.read_csv(root / "participants.tsv", sep="\t", dtype=str, keep_default_na=False)


def test_final_table_has_the_union_of_every_source_column(three_source_project: Path) -> None:
    df = _read_participants(three_source_project)
    assert list(df.columns) == [
        "participant_id",
        "age",
        "sex",
        "education_level",
        "employment_status",
        "handedness",
        "country_of_residence",
    ]


def test_final_table_has_the_union_of_every_source_participant(
    three_source_project: Path,
) -> None:
    df = _read_participants(three_source_project)
    assert sorted(df["participant_id"]) == [f"sub-{i:03d}" for i in (1, 2, 3, 4, 5, 6, 7, 8)]


def test_participant_only_in_baseline_has_na_for_later_columns(
    three_source_project: Path,
) -> None:
    df = _read_participants(three_source_project)
    row = df.loc[df["participant_id"] == "sub-005"].iloc[0]
    assert row["age"] == "22"
    assert row["education_level"] == "n/a"
    assert row["handedness"] == "n/a"


def test_participant_only_in_a_later_source_has_na_for_baseline_columns(
    three_source_project: Path,
) -> None:
    df = _read_participants(three_source_project)
    row = df.loc[df["participant_id"] == "sub-008"].iloc[0]
    assert row["age"] == "n/a"
    assert row["handedness"] == "R"
    assert row["country_of_residence"] == "CH"


def test_participant_enriched_by_every_source_has_all_columns_populated(
    three_source_project: Path,
) -> None:
    """sub-001 only appears in sources 1 and 3, not 2 — confirms columns
    from a source a participant was never part of correctly stay distinct
    from columns that source genuinely left empty."""
    df = _read_participants(three_source_project)
    row = df.loc[df["participant_id"] == "sub-001"].iloc[0]
    assert row["age"] == "24"
    assert row["sex"] == "F"
    assert row["education_level"] == "n/a"  # never in source 2
    assert row["handedness"] == "R"  # from source 3
    assert row["country_of_residence"] == "AT"


def test_preview_before_merge_reports_matched_new_and_existing_only(
    three_source_project: Path,
) -> None:
    """A 4th source, previewed (not yet applied): enriches one already-
    multi-source participant, leaves several existing-only, and adds one
    genuinely new participant — confirms the preview's three-way
    classification stays correct after two prior merges, not just on a
    freshly-converted table."""
    source4 = three_source_project / "source4_contact.csv"
    pd.DataFrame(
        [
            {"ID": "sub-001", "contact_email": "p001@example.org"},
            {"ID": "sub-009", "contact_email": "p009@example.org"},
        ]
    ).to_csv(source4, index=False)

    preview = _run_pipeline_stage(
        "preview source4 (contact info)",
        preview_participants_merge,
        three_source_project,
        source4,
        _mapping(contact_email="contact_email"),
    )
    assert preview["matched_participants"] == ["sub-001"]
    assert preview["new_participants"] == ["sub-009"]
    assert set(preview["existing_only_participants"]) == {
        "sub-002",
        "sub-003",
        "sub-004",
        "sub-005",
        "sub-006",
        "sub-007",
        "sub-008",
    }
    assert preview["can_apply"] is True


def test_bare_numeric_ids_from_a_later_source_match_existing_zero_padded_participants(
    three_source_project: Path,
) -> None:
    """A 4th source spelling participant ids as bare numbers ("1", "9")
    instead of the project's established "sub-001" convention must still be
    recognized as those same existing participants (and the genuinely new
    one correctly added as sub-9, not silently zero-padded) -- not create
    duplicate sub-1/sub-9 rows alongside the real ones."""
    source4 = three_source_project / "source4_contact.csv"
    pd.DataFrame(
        [
            {"ID": "1", "contact_email": "p001@example.org"},
            {"ID": "9", "contact_email": "p009@example.org"},
        ]
    ).to_csv(source4, index=False)

    preview = _run_pipeline_stage(
        "preview source4 (bare numeric ids)",
        preview_participants_merge,
        three_source_project,
        source4,
        _mapping(contact_email="contact_email"),
    )
    assert preview["matched_participants"] == ["sub-001"]
    assert preview["new_participants"] == ["sub-9"]

    apply_payload = _run_pipeline_stage(
        "apply source4 (bare numeric ids)",
        apply_participants_merge,
        three_source_project,
        source4,
        _mapping(contact_email="contact_email"),
    )
    assert apply_payload["action"] == "apply"

    df = _read_participants(three_source_project)
    ids = set(df["participant_id"])
    assert "sub-001" in ids
    assert "sub-1" not in ids
    assert "sub-9" in ids

    row_001 = df.loc[df["participant_id"] == "sub-001"].iloc[0]
    assert row_001["contact_email"] == "p001@example.org"


def test_conflicting_value_from_a_later_source_blocks_apply_until_resolved(
    three_source_project: Path,
) -> None:
    """A 4th source re-reporting a DIFFERENT age for an already-merged
    participant must be flagged as a real conflict and refused, not
    silently overwrite the original intake-form value."""
    source4 = three_source_project / "source4_conflicting_age.csv"
    pd.DataFrame(
        [
            {"ID": "sub-001", "age": 99},  # conflicts with the real age=24
            {"ID": "sub-005", "age": 22},  # matches existing value, no conflict
        ]
    ).to_csv(source4, index=False)

    preview = _run_pipeline_stage(
        "preview source4 (conflicting age)",
        preview_participants_merge,
        three_source_project,
        source4,
        _mapping(age="age"),
    )
    assert preview["can_apply"] is False
    assert preview["conflicts"] == [
        {
            "participant_id": "sub-001",
            "column": "age",
            "existing_value": "24",
            "incoming_value": "99",
        }
    ]

    with pytest.raises(ValueError, match="not apply-ready"):
        apply_participants_merge(
            three_source_project,
            source4,
            _mapping(age="age"),
        )

    # Unaffected by the refused merge attempt: participants.tsv must be
    # left exactly as the three earlier, successful merges produced it.
    df = _read_participants(three_source_project)
    assert df.loc[df["participant_id"] == "sub-001", "age"].iloc[0] == "24"
