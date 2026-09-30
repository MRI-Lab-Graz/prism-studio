"""Merge session resolution must treat session labels as exact strings.

"1", "01" and "1.0" are different sessions (CLAUDE.md: never normalize them).
"""

from pathlib import Path

import pytest

from src.participants_backend import (
    apply_participants_merge,
    normalize_participant_mapping,
    preview_participants_merge,
)

MAPPING = normalize_participant_mapping({"participant_id": "participant_id", "age": "age"})


def _project(tmp_path: Path, incoming_csv: str):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "participants.tsv").write_text(
        "participant_id\tage\nsub-1\t30\n", encoding="utf-8"
    )
    source = tmp_path / "in.csv"
    source.write_text(incoming_csv, encoding="utf-8")
    return project, source


def _decision(session):
    return {"age": {"action": "pick_session", "session": session, "session_column": "session"}}


# sub-2 is new to the project, so its picked value flows straight into participants.tsv.
TWO_LOOKALIKE_SESSIONS = "participant_id,session,age\n2,1,31\n2,01,32\n"


def test_lookalike_session_labels_stay_two_sessions(tmp_path):
    project, source = _project(tmp_path, TWO_LOOKALIKE_SESSIONS)

    payload = preview_participants_merge(project, source, MAPPING, separator=",")

    candidate = payload["session_resolution_candidates"][0]
    assert candidate["available_sessions"] == ["01", "1"]
    assert payload["session_resolution_blockers"] == []


@pytest.mark.parametrize("chosen, expected_age", [("01", "32"), ("1", "31")])
def test_picking_a_label_uses_exactly_that_sessions_value(tmp_path, chosen, expected_age):
    project, source = _project(tmp_path, TWO_LOOKALIKE_SESSIONS)

    payload = preview_participants_merge(
        project, source, MAPPING, separator=",",
        session_resolution_decisions=_decision(chosen),
    )

    assert payload["session_resolution_candidates"][0]["selected_session"] == chosen
    assert payload["can_apply"] is True
    apply_participants_merge(
        project, source, MAPPING, separator=",",
        session_resolution_decisions=_decision(chosen),
    )
    rows = (project / "participants.tsv").read_text().splitlines()
    ages = {row.split("\t")[0]: row.split("\t")[1] for row in rows[1:]}
    assert ages == {"sub-1": "30", "sub-2": expected_age}


def test_a_label_that_is_not_in_the_file_is_not_rewritten_into_one_that_is(tmp_path):
    project, source = _project(tmp_path, "participant_id,session,age\n2,1,31\n2,2,32\n")

    payload = preview_participants_merge(
        project, source, MAPPING, separator=",",
        session_resolution_decisions=_decision("01"),
    )

    # "01" is not a session of this file, so the decision must stay unresolved.
    assert payload["session_resolution_required"] is True
    assert payload["session_resolution_candidates"][0]["selected_session"] == "01"
