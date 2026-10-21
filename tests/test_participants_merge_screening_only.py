"""Merge: ticked participants go into the screening-only group, nothing is removed."""

import json

from src.participants_backend import (
    apply_participants_merge,
    normalize_participant_mapping,
    preview_participants_merge,
)
from src.participants_levels import check_participants_levels

MAPPING = normalize_participant_mapping({"participant_id": "participant_id", "age": "age"})


def _project(tmp_path, tsv, schema=None):
    project = tmp_path / "proj"
    project.mkdir()
    (project / "participants.tsv").write_text(tsv, encoding="utf-8")
    (project / "participants.json").write_text(
        json.dumps(schema or {"participant_id": {"Description": "id"}, "age": {"Description": "Age"}}),
        encoding="utf-8",
    )
    source = tmp_path / "in.csv"
    source.write_text("participant_id,age\n1,30\n2,40\n3,50\n", encoding="utf-8")
    return project, source


def _groups(project):
    lines = (project / "participants.tsv").read_text(encoding="utf-8").splitlines()
    head = lines[0].split("\t")
    return {row.split("\t")[0]: row.split("\t")[head.index("group")] for row in lines[1:]}


def test_ticked_participants_get_the_group_and_nobody_is_removed(tmp_path):
    project, source = _project(tmp_path, "participant_id\tage\nsub-1\t30\n")
    apply_participants_merge(project, source, MAPPING, screening_only_ids=["sub-3"])
    assert _groups(project) == {"sub-1": "n/a", "sub-2": "n/a", "sub-3": "screening-only"}


def test_a_ticked_participant_loses_a_real_group_value(tmp_path):
    project, source = _project(
        tmp_path, "participant_id\tage\tgroup\nsub-1\t30\tcontrol\nsub-2\t40\tcontrol\n",
        {"participant_id": {}, "age": {}, "group": {"Levels": {"control": "control"}}},
    )
    apply_participants_merge(project, source, MAPPING, screening_only_ids=["sub-2"])
    assert _groups(project)["sub-1"] == "control"
    assert _groups(project)["sub-2"] == "screening-only"


def test_an_unticked_participant_is_released_but_real_groups_stay(tmp_path):
    project, source = _project(
        tmp_path, "participant_id\tage\tgroup\nsub-1\t30\tcontrol\nsub-2\t40\tscreening-only\n",
        {"participant_id": {}, "age": {}, "group": {"Levels": {"control": "control", "screening-only": "x"}}},
    )
    apply_participants_merge(project, source, MAPPING, screening_only_ids=[])
    assert _groups(project)["sub-1"] == "control"
    assert _groups(project)["sub-2"] == "n/a"


def test_without_a_decision_the_group_column_is_left_alone(tmp_path):
    project, source = _project(tmp_path, "participant_id\tage\tgroup\nsub-1\t30\tscreening-only\n")
    apply_participants_merge(project, source, MAPPING)
    assert _groups(project)["sub-1"] == "screening-only"


def test_the_group_gets_value_labels_so_the_levels_check_stays_quiet(tmp_path):
    project, source = _project(tmp_path, "participant_id\tage\nsub-1\t30\n")
    apply_participants_merge(project, source, MAPPING, screening_only_ids=["sub-3"])
    levels = json.loads((project / "participants.json").read_text())["group"]["Levels"]
    assert "screening-only" in levels
    assert not [i for i in check_participants_levels(str(project)) if "'group'" in i[1]]


def test_preview_lists_every_source_participant_with_folder_and_current_group(tmp_path):
    project, source = _project(
        tmp_path, "participant_id\tage\tgroup\nsub-1\t30\tcontrol\n",
        {"participant_id": {}, "age": {}, "group": {"Levels": {"control": "control"}}},
    )
    (project / "sub-1").mkdir()
    payload = preview_participants_merge(project, source, MAPPING, screening_only_ids=["sub-3"])
    assert payload["screening_candidates"] == [
        {"participant_id": "sub-1", "has_folder": True, "group": "control"},
        {"participant_id": "sub-2", "has_folder": False, "group": ""},
        {"participant_id": "sub-3", "has_folder": False, "group": ""},
    ]
    assert "group" in payload["columns"]


def test_nobody_ticked_adds_no_group_column(tmp_path):
    project, source = _project(tmp_path, "participant_id\tage\nsub-1\t30\n")
    apply_participants_merge(project, source, MAPPING, screening_only_ids=[])
    assert "group" not in (project / "participants.tsv").read_text()
    assert "group" not in json.loads((project / "participants.json").read_text())
