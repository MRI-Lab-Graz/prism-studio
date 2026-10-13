"""Survey conversion: duplicate_handling='sessions' numbers by date."""

import pandas as pd
import pytest

from src.converters.survey_core import _handle_duplicate_ids
from src.session_map import SessionsNotMappedError, save_session_map
from test_survey_session_map import convert, library, project, sessions  # noqa: F401


def _numbered(df):
    out, ses_col, _ = _handle_duplicate_ids(
        df=df, res_id_col="token", duplicate_handling="sessions",
        normalize_sub_fn=lambda v: v,
    )
    return out, ses_col


def test_sessions_mode_orders_by_startdate():
    df = pd.DataFrame({
        "token": ["a", "a"],
        "startdate": ["2026-09-01 10:00:00", "2026-03-01 10:00:00"],
        "q1": ["late", "early"],
    })
    out, ses_col = _numbered(df)
    assert dict(zip(out["q1"], out[ses_col])) == {"early": "1", "late": "2"}


def test_sessions_mode_without_dates_keeps_file_order():
    df = pd.DataFrame({"token": ["a", "a"], "q1": ["first", "second"]})
    out, ses_col = _numbered(df)
    assert [str(v) for v in out[ses_col]] == ["1", "2"]


REPEATED = (
    "participant_id,startdate,BRS01,BRS02,BRS03\n"
    "P001,2026-09-01 10:00:00,4,4,3\n"
    "P001,2026-03-01 10:00:00,3,4,2\n"
)


def test_sessions_mode_in_longitudinal_project_goes_through_the_session_map(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"1": "pre", "2": "post"})
    out = convert(
        tmp_path, library, REPEATED, proj,
        session_column=None, session=None, duplicate_handling="sessions",
    )
    assert sessions(out, "sub-P001") == ["ses-post", "ses-pre"]


def test_sessions_mode_in_longitudinal_project_requires_mapping(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"1": "pre"})
    with pytest.raises(SessionsNotMappedError) as info:
        convert(
            tmp_path, library, REPEATED, proj,
            session_column=None, session=None, duplicate_handling="sessions",
        )
    assert info.value.labels == ["2"]


def test_sessions_mode_without_repeats_still_needs_a_session_source(tmp_path, library):
    proj = project(tmp_path)
    save_session_map(proj, {"x": "pre"})  # the generated label "1" is not mapped
    single_wave = "participant_id,startdate,BRS01,BRS02,BRS03\nP001,2026-03-01,3,4,2\n"
    with pytest.raises(SessionsNotMappedError) as info:
        convert(
            tmp_path, library, single_wave, proj,
            session_column=None, session=None, duplicate_handling="sessions",
        )
    assert info.value.labels == ["1"]


def test_dated_sessions_win_over_a_typed_session_id(tmp_path, library):
    """The GUI always sends a Session ID; it must not flatten the date-numbered sessions."""
    out = convert(
        tmp_path, library, REPEATED, None,
        session_column=None, session="1", duplicate_handling="sessions",
    )
    assert sessions(out, "sub-P001") == ["ses-1", "ses-2"]
