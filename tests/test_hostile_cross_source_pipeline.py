"""participants.tsv merge: cross-source matching, including subject IDs that
differ only by case between independently-uploaded sources.

Exercises the real production functions the Participants Merge UI/CLI call:
ParticipantsConverter.convert_participant_data (to build the baseline
participants.tsv) and preview_participants_merge/apply_participants_merge
(src/participants_backend.py) for merging a second source in.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.hostile_demo_generator import generate_hostile_dataset
from src.participants_backend import apply_participants_merge, preview_participants_merge
from src.participants_converter import ParticipantsConverter


def _run_pipeline_stage(label, fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as exc:  # noqa: BLE001 - intentionally broad: see module docstring
        pytest.fail(f"{label} raised unexpectedly: {exc!r}", pytrace=True)


_INITIAL_MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "ID", "standard_variable": "participant_id"},
        "age": {"source_column": "age", "standard_variable": "age"},
        "sex": {"source_column": "sex", "standard_variable": "sex"},
    },
}

_INCOMING_MAPPING = {
    "version": "1.0",
    "mappings": {
        "participant_id": {"source_column": "ID", "standard_variable": "participant_id"},
        "age": {"source_column": "age", "standard_variable": "age"},
        "group": {"source_column": "group", "standard_variable": "group"},
    },
}


@pytest.fixture(scope="module")
def merge_dataset(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("hostile_merge")
    result = generate_hostile_dataset(
        root / "demo", seed=1, domains={"participants_merge"}, use_datalad=False
    )
    return result.project_root


@pytest.fixture
def rawdata_dir(merge_dataset: Path) -> Path:
    return merge_dataset / "code" / "rawdata"


@pytest.fixture
def project_with_baseline(tmp_path, rawdata_dir):
    """A fresh project (not the module-scoped fixture) with the initial
    source already converted into participants.tsv — each test gets its
    own copy since merge tests mutate participants.tsv."""
    root = tmp_path / "project"
    result = generate_hostile_dataset(
        root, seed=1, domains={"participants_merge"}, use_datalad=False
    )
    project_root = result.project_root
    rawdata = project_root / "code" / "rawdata"

    converter = ParticipantsConverter(project_root)
    success, df, _messages = _run_pipeline_stage(
        "convert initial participants source",
        converter.convert_participant_data,
        rawdata / "participants_merge_initial_source.csv",
        _INITIAL_MAPPING,
    )
    assert success is True
    df.to_csv(project_root / "participants.tsv", sep="\t", index=False)
    return project_root, rawdata


def test_initial_source_converts_with_label_case_preserved(project_with_baseline):
    project_root, _rawdata = project_with_baseline
    participants = (project_root / "participants.tsv").read_text(encoding="utf-8")
    assert "sub-Ab" in participants
    assert "sub-ab" not in participants


def test_merge_preview_matches_exact_id_only(project_with_baseline):
    project_root, rawdata = project_with_baseline
    payload = _run_pipeline_stage(
        "preview_participants_merge",
        preview_participants_merge,
        project_root,
        rawdata / "participants_merge_incoming_source.csv",
        _INCOMING_MAPPING,
    )
    assert payload["matched_participants"] == ["sub-101"]
    assert payload["can_apply"] is True
    assert payload["conflicts"] == []


def test_merge_preview_treats_case_differing_id_as_new_not_matched(
    project_with_baseline,
):
    """sub-ab (incoming) must never be matched against the existing
    sub-Ab — only the 'sub-'/'SUB-' prefix is case-normalized, never the
    label itself. This is the cross-source case-sensitivity guarantee."""
    project_root, rawdata = project_with_baseline
    payload = _run_pipeline_stage(
        "preview_participants_merge",
        preview_participants_merge,
        project_root,
        rawdata / "participants_merge_incoming_source.csv",
        _INCOMING_MAPPING,
    )
    assert "sub-ab" in payload["new_participants"]
    assert "sub-ab" not in payload["matched_participants"]
    assert "sub-Ab" in payload["existing_only_participants"]


def test_merge_apply_adds_new_participants_and_merges_matched(project_with_baseline):
    project_root, rawdata = project_with_baseline
    result = _run_pipeline_stage(
        "apply_participants_merge",
        apply_participants_merge,
        project_root,
        rawdata / "participants_merge_incoming_source.csv",
        _INCOMING_MAPPING,
    )
    assert result["merged_participant_count"] == 5

    import pandas as pd

    df = pd.read_csv(
        project_root / "participants.tsv", sep="\t", dtype=str, keep_default_na=False
    )
    ids = set(df["participant_id"])
    # Original three plus two genuinely new (sub-102, sub-ab) — sub-Ab and
    # sub-ab coexist as distinct rows, never collapsed into one.
    assert ids == {"sub-100", "sub-101", "sub-Ab", "sub-102", "sub-ab"}

    matched_row = df.loc[df["participant_id"] == "sub-101"].iloc[0]
    assert matched_row["group"] == "control"
    untouched_row = df.loc[df["participant_id"] == "sub-Ab"].iloc[0]
    assert untouched_row["group"] == "n/a"


def test_merge_rejects_internally_conflicting_incoming_duplicates(
    project_with_baseline,
):
    project_root, rawdata = project_with_baseline
    with pytest.raises(ValueError, match="non-unique values"):
        preview_participants_merge(
            project_root,
            rawdata / "participants_merge_incoming_conflicting_duplicates.csv",
            _INCOMING_MAPPING,
        )
