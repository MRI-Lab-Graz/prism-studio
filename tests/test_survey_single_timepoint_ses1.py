"""A project with one timepoint always gets ses-1, whatever label the data carries."""

import json
from tests.template_fixtures import dump_complete
from pathlib import Path

import pytest

from src.converters.survey import convert_survey_file_to_prism_dataset

BRS = Path(__file__).resolve().parents[1] / "official" / "library" / "survey" / "survey-brs.json"
ONE_EACH = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP002,post,1,0,2\n"
TWICE = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP001,post,4,4,3\n"


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "library" / "survey"
    lib.mkdir(parents=True)
    (lib / "survey-brs.json").write_text(dump_complete(json.loads(BRS.read_text(encoding="utf-8")), "brs"), encoding="utf-8")
    return lib


def run(tmp_path, library, csv_text, **kwargs):
    root = tmp_path / "proj"
    root.mkdir(exist_ok=True)
    (root / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "single"}}))
    src = tmp_path / "in.csv"
    src.write_text(csv_text)
    out = tmp_path / "out"
    kwargs.setdefault("session_column", "session")
    kwargs.setdefault("session", "all")
    result = convert_survey_file_to_prism_dataset(
        input_path=src, library_dir=library, output_root=out, name="t", project_path=root, **kwargs,
    )
    return out, result


def sessions(out, participant):
    return sorted(p.name for p in (out / participant).glob("ses-*"))


def test_any_label_becomes_ses_1_and_is_reported(tmp_path, library):
    out, result = run(tmp_path, library, ONE_EACH)
    assert sessions(out, "sub-P001") == ["ses-1"]
    assert sessions(out, "sub-P002") == ["ses-1"]
    warnings = " ".join(result.conversion_warnings)
    assert "'pre'" in warnings and "'post'" in warnings and "ses-1" in warnings


def test_two_labels_for_one_participant_collapse_into_the_duplicate_check(tmp_path, library):
    with pytest.raises(ValueError, match="Duplicate"):
        run(tmp_path, library, TWICE)
    assert not (tmp_path / "out" / "sub-P001").exists()


def test_a_label_of_1_is_not_reported(tmp_path, library):
    out, result = run(tmp_path, library, "participant_id,session,BRS01,BRS02,BRS03\nP001,1,3,4,2\n")
    assert sessions(out, "sub-P001") == ["ses-1"]
    assert not any("ses-1" in w and "one timepoint" in w for w in result.conversion_warnings)


REPEATED = (
    "participant_id,startdate,BRS01,BRS02,BRS03\n"
    "P001,2026-09-01 10:00:00,4,4,3\n"
    "P001,2026-03-01 10:00:00,3,4,2\n"
)


def test_numbering_repeats_by_date_cannot_make_several_sessions_in_a_one_timepoint_project(tmp_path, library):
    with pytest.raises(ValueError, match="one timepoint"):
        run(tmp_path, library, REPEATED, session_column=None, session=None, duplicate_handling="sessions")
    assert not (tmp_path / "out" / "sub-P001").exists()


def test_numbering_unique_responses_by_date_is_fine_in_a_one_timepoint_project(tmp_path, library):
    csv_text = "participant_id,startdate,BRS01,BRS02,BRS03\nP001,2026-03-01 10:00:00,3,4,2\n"
    out, _ = run(tmp_path, library, csv_text, session_column=None, session=None, duplicate_handling="sessions")
    assert sessions(out, "sub-P001") == ["ses-1"]
