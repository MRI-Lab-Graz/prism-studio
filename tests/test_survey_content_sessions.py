"""Survey conversion in a content project: sessions are named per participant."""

import json

import pytest

from src.converters.survey import convert_survey_lsa_to_prism_dataset
from src.project_registration import _output_session_id_fn
from src.session_assignments import set_assignment
from src.session_map import save_session_map, session_map_for_conversion
from src.session_order import SessionsNotOrderedError, set_order_entries
from tests.lsa_fixtures import make_library, make_lsa

# a and c each have two completed responses, in opposite condition order.
ROWS = [
    ["1", "a", "2026-03-01 09:00:00", "2026-03-01 09:20:00", "5", "4", "3", "5"],
    ["2", "a", "2026-09-01 10:00:00", "2026-09-01 10:20:00", "5", "2", "4", "3"],
    ["3", "c", "2026-03-02 10:00:00", "2026-03-02 10:10:00", "5", "5", "5", "5"],
    ["4", "c", "2026-09-02 10:00:00", "2026-09-02 10:10:00", "5", "3", "3", "3"],
]


def make_project(tmp_path, labels="content", order=True):
    root = tmp_path / "proj"
    root.mkdir()
    design = {"Timepoints": "multiple"}
    if labels:
        design["SessionLabels"] = labels
    (root / "project.json").write_text(json.dumps({"StudyDesign": design}))
    if order:
        set_order_entries(root, "a", {"1": "sleepdep", "2": "rested"})
        set_order_entries(root, "c", {"1": "rested", "2": "sleepdep"})
    return root


def convert(tmp_path, project, rows=ROWS):
    return convert_survey_lsa_to_prism_dataset(
        input_path=make_lsa(tmp_path, rows),
        library_dir=make_library(tmp_path),
        output_root=tmp_path / "out",
        id_column="token",
        duplicate_handling="sessions",
        project_path=project,
    )


def sessions(tmp_path, participant):
    return sorted(p.name for p in (tmp_path / "out" / participant).glob("ses-*"))


def first_session_file(tmp_path, participant, session):
    return sorted((tmp_path / "out" / participant / session).rglob("*.tsv"))[0]


def test_condition_folders_follow_each_participants_order(tmp_path):
    convert(tmp_path, make_project(tmp_path))

    assert sessions(tmp_path, "sub-a") == ["ses-rested", "ses-sleepdep"]
    assert sessions(tmp_path, "sub-c") == ["ses-rested", "ses-sleepdep"]
    # a's first (March) response was sleepdep, c's first was rested: the answers differ.
    sleepdep_a = first_session_file(tmp_path, "sub-a", "ses-sleepdep").read_text()
    sleepdep_c = first_session_file(tmp_path, "sub-c", "ses-sleepdep").read_text()
    assert sleepdep_a != sleepdep_c


def test_project_json_and_template_versions_know_the_condition_names(tmp_path):
    from src.converters import survey_core

    project = make_project(tmp_path)
    assert _output_session_id_fn(project)("sleepdep") == "ses-sleepdep"
    ids = survey_core.build_survey_id_normalizers(
        project, session_map=session_map_for_conversion(project)
    )
    pick = survey_core.session_normalizer_for_overrides(ids.normalize_ses)
    assert pick("ses-sleepdep") == "ses-sleepdep"


def test_a_participant_without_an_order_stops_before_writing(tmp_path):
    project = make_project(tmp_path, order=False)
    set_order_entries(project, "a", {"1": "sleepdep", "2": "rested"})

    with pytest.raises(SessionsNotOrderedError) as caught:
        convert(tmp_path, project)

    assert caught.value.problems == ["c: not in the session order"]
    assert not (tmp_path / "out" / "sub-a").exists()


def test_a_time_project_ignores_a_session_order_file(tmp_path):
    project = make_project(tmp_path, labels="time")
    set_order_entries(project, "a", {"1": "sleepdep", "2": "rested"})
    save_session_map(project, {"1": "pre", "2": "post"})

    convert(tmp_path, project)

    assert sessions(tmp_path, "sub-a") == ["ses-post", "ses-pre"]


THIRD_A = ["5", "a", "2026-12-01 10:00:00", "2026-12-01 10:20:00", "5", "1", "1", "1"]


def test_a_response_named_by_hand_is_final(tmp_path):
    project = make_project(tmp_path, order=False)
    set_order_entries(project, "c", {"1": "rested", "2": "sleepdep"})
    save_session_map(project, {"1": "pre"})  # a stale number map must not touch a final name
    set_assignment(project, "1", survey_id="999999", session="baseline")
    set_assignment(project, "2", survey_id="999999", session="followup")

    convert(tmp_path, project)

    assert sessions(tmp_path, "sub-a") == ["ses-baseline", "ses-followup"]
    assert sessions(tmp_path, "sub-c") == ["ses-rested", "ses-sleepdep"]


def test_a_count_mismatch_stops_until_the_extra_response_is_named(tmp_path):
    project = make_project(tmp_path)  # a has two entries, the file three completed responses
    with pytest.raises(SessionsNotOrderedError) as caught:
        convert(tmp_path, project, ROWS + [THIRD_A])
    assert caught.value.problems == ["a: 3 responses in this file, 2 in the session order"]

    set_assignment(project, "5", survey_id="999999", session="extra")
    again = tmp_path / "again"
    again.mkdir()
    convert(again, project, ROWS + [THIRD_A])

    assert sessions(again, "sub-a") == ["ses-extra", "ses-rested", "ses-sleepdep"]


def test_the_order_is_looked_up_by_the_raw_id_not_the_normalised_one(tmp_path):
    project = make_project(tmp_path, order=False)
    set_order_entries(project, "P-01", {"1": "sleepdep", "2": "rested"})  # normalised: sub-P01
    rows = [[r[0], "P-01", *r[2:]] for r in ROWS[:2]]

    convert(tmp_path, project, rows)

    assert sessions(tmp_path, "sub-P01") == ["ses-rested", "ses-sleepdep"]
