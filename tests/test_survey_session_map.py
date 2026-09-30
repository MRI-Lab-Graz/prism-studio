"""Survey conversion in a longitudinal project uses only the user's session map."""

import json
import shutil
from pathlib import Path

import pytest

from src.converters.survey import convert_survey_file_to_prism_dataset
from src.session_map import (
    SessionMapError,
    SessionsNotMappedError,
    TimepointsNotDeclaredError,
    save_session_map,
)

BRS = Path(__file__).resolve().parents[1] / "official" / "library" / "survey" / "survey-brs.json"


@pytest.fixture
def library(tmp_path):
    lib = tmp_path / "library" / "survey"
    lib.mkdir(parents=True)
    shutil.copy(BRS, lib / "survey-brs.json")
    return lib


def project(tmp_path, timepoints="multiple"):
    root = tmp_path / "proj"
    root.mkdir(exist_ok=True)
    study = {} if timepoints is None else {"StudyDesign": {"Timepoints": timepoints}}
    (root / "project.json").write_text(json.dumps(study))
    return root


def convert(tmp_path, library, csv_text, proj=None, **kwargs):
    src = tmp_path / "in.csv"
    src.write_text(csv_text)
    out = tmp_path / "out"
    convert_survey_file_to_prism_dataset(
        input_path=src,
        library_dir=library,
        output_root=out,
        name="t",
        session_column=kwargs.pop("session_column", "session"),
        session=kwargs.pop("session", "all"),  # the GUI's "All sessions"; None imports only the first session
        project_path=proj,
        **kwargs,
    )
    return out


def sessions(out, participant):
    return sorted(p.name for p in (out / participant).glob("ses-*"))


LONG = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP001,post,4,4,3\nP002,pre,1,0,2\n"


def test_unmapped_labels_block_and_nothing_is_written(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1"})
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, LONG, proj)
    assert info.value.labels == ["post"]
    assert not (tmp_path / "out" / "sub-P001").exists()


def test_declared_multiple_without_a_map_file_blocks_every_label(tmp_path, library):
    proj = project(tmp_path)
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, LONG, proj)
    assert info.value.labels == ["pre", "post"]


def test_mapped_labels_become_the_users_session_names(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1", "post": "2"})
    out = convert(tmp_path, library, LONG, proj)
    assert sessions(out, "sub-P001") == ["ses-1", "ses-2"]
    assert sessions(out, "sub-P002") == ["ses-1"]


def test_two_source_labels_may_share_one_session(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"T0": "1", "pre": "1"})
    csv_text = "participant_id,session,BRS01,BRS02,BRS03\nP001,T0,3,4,2\nP002,pre,1,0,2\n"
    out = convert(tmp_path, library, csv_text, proj)
    assert sessions(out, "sub-P001") == ["ses-1"] and sessions(out, "sub-P002") == ["ses-1"]


def test_numeric_session_column_matches_integer_keys(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"1": "a", "2": "b"})
    csv_text = "participant_id,session,BRS01,BRS02,BRS03\nP001,1,3,4,2\nP001,2,4,4,3\n"
    out = convert(tmp_path, library, csv_text, proj)
    assert sessions(out, "sub-P001") == ["ses-a", "ses-b"]  # never ses-10


def test_zero_padded_label_is_not_the_unpadded_key(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"1": "a"})
    csv_text = "participant_id,session,BRS01,BRS02,BRS03\nP001,01,3,4,2\n"
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, csv_text, proj)
    assert info.value.labels == ["01"]


def test_blank_session_cell_blocks_instead_of_becoming_ses_1(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1"})
    csv_text = "participant_id,session,BRS01,BRS02,BRS03\nP001,pre,3,4,2\nP002,,1,0,2\n"
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, csv_text, proj)
    assert info.value.labels == [""]


def test_no_session_source_is_refused_in_a_longitudinal_project(tmp_path, library):
    proj = project(tmp_path)
    csv_text = "participant_id,BRS01,BRS02,BRS03\nP001,3,4,2\n"
    with pytest.raises(SessionMapError, match="session"):
        convert(tmp_path, library, csv_text, proj, session_column=None)


def test_chosen_session_must_be_mapped_and_imports_only_its_rows(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1"})
    out = convert(tmp_path, library, LONG, proj, session="pre")
    assert sessions(out, "sub-P001") == ["ses-1"]


def test_duplicate_handling_sessions_is_refused_because_it_invents_names(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1"})
    with pytest.raises(SessionMapError, match="invents"):
        convert(tmp_path, library, LONG, proj, duplicate_handling="sessions")


def test_undeclared_project_is_refused_with_the_declare_message(tmp_path, library):
    with pytest.raises(TimepointsNotDeclaredError):
        convert(tmp_path, library, LONG, project(tmp_path, timepoints=None))


def test_single_timepoint_project_keeps_todays_behaviour(tmp_path, library):
    out = convert(tmp_path, library, LONG, project(tmp_path, "single"))
    assert sessions(out, "sub-P001") == ["ses-post", "ses-pre"]


def test_without_a_project_nothing_changes(tmp_path, library):
    out = convert(tmp_path, library, LONG, proj=None)
    assert sessions(out, "sub-P001") == ["ses-post", "ses-pre"]


def test_undeclared_project_without_any_session_source_converts_as_before(tmp_path, library):
    csv_text = "participant_id,BRS01,BRS02,BRS03\nP001,3,4,2\n"
    out = convert(
        tmp_path, library, csv_text, project(tmp_path, timepoints=None),
        session_column=None, session=None,
    )
    assert sessions(out, "sub-P001") == ["ses-1"]


def test_no_session_choice_imports_every_session_in_a_longitudinal_project(tmp_path, library):
    """Callers that pass no session (CLI, API) must not silently get only the first session."""
    proj = project(tmp_path)
    save_session_map(proj, {"pre": "1", "post": "2"})
    out = convert(tmp_path, library, LONG, proj, session=None)
    assert sessions(out, "sub-P001") == ["ses-1", "ses-2"]


def test_no_session_choice_still_names_every_unmapped_label(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"post": "2"})
    with pytest.raises(SessionsNotMappedError) as info:
        convert(tmp_path, library, LONG, proj, session=None)
    assert info.value.labels == ["pre"]
