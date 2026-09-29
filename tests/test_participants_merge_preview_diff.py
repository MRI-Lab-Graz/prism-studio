"""Merge preview must show new participants and mark changed cells."""

import pandas as pd

from src.participants_backend import (
    _build_merge_preview_diff,
    normalize_participant_mapping,
    _select_merge_preview_rows,
    preview_participants_merge,
)


def _table(n):
    return pd.DataFrame(
        {"participant_id": [f"sub-{i:03d}" for i in range(1, n + 1)], "age": ["30"] * n}
    )


def test_new_row_beyond_the_limit_is_still_previewed():
    merged = _table(21)  # the new participant is last, past head(20)

    rows = _select_merge_preview_rows(merged, {"sub-021"}, 20)

    assert "sub-021" in set(rows["participant_id"])
    assert len(rows) == 21


def test_unchanged_rows_beyond_the_limit_stay_hidden():
    rows = _select_merge_preview_rows(_table(30), set(), 20)

    assert len(rows) == 20


def test_diff_lists_only_previewed_new_and_changed_cells():
    diff = _build_merge_preview_diff(
        ["sub-001", "sub-021"],
        {"sub-021"},
        {
            "sub-001": {"age": {"kind": "conflict"}},
            "sub-099": {"age": {"kind": "filled"}},
        },
    )

    assert diff["new_participants"] == ["sub-021"]
    assert set(diff["cells"]) == {"sub-001"}


def test_preview_flags_new_participant_and_conflict(tmp_path):
    existing = _table(20)
    existing.to_csv(tmp_path / "participants.tsv", sep="\t", index=False)
    incoming = _table(21)
    incoming.loc[2, "age"] = "31"  # sub-003 disagrees with the project
    src = tmp_path / "incoming.tsv"
    incoming.to_csv(src, sep="\t", index=False)

    payload = preview_participants_merge(
        tmp_path,
        src,
        normalize_participant_mapping({"participant_id": "participant_id", "age": "age"}),
        preview_limit=20,
    )

    diff = payload["preview_diff"]
    assert diff["new_participants"] == ["sub-021"]
    assert diff["cells"]["sub-003"]["age"]["kind"] == "conflict"
    assert diff["cells"]["sub-003"]["age"]["incoming_value"] == "31"
    assert "sub-021" in {row["participant_id"] for row in payload["preview_rows"]}
