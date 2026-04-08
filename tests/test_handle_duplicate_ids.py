"""Tests for _handle_duplicate_ids composite-key duplicate detection.

The key invariant: rows with the same participant ID but different session
or run values are LEGITIMATE multi-session/multi-run observations, not
duplicates.  True duplicates are only rows where (id, session, run) all match.
"""

from __future__ import annotations

import pytest
import pandas as pd

from app.src.converters.survey_core import _handle_duplicate_ids


def _norm(v: str) -> str:
    """Minimal normaliser that mirrors _normalize_sub_id behaviour."""
    v = str(v).strip()
    if not v.startswith("sub-"):
        v = f"sub-{v}"
    return v


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_df(**cols) -> pd.DataFrame:
    return pd.DataFrame(cols)


# ---------------------------------------------------------------------------
# No-duplicate cases (must not raise, must not warn)
# ---------------------------------------------------------------------------


def test_same_id_different_sessions_not_a_duplicate() -> None:
    """hsub01/pre + hsub01/post should be accepted when session col is known."""
    df = _make_df(
        Code=["hsub01", "hsub01", "hsub02", "hsub02"],
        session=["pre", "post", "pre", "post"],
        score=[1, 2, 3, 4],
    )
    result_df, ses_override, warnings = _handle_duplicate_ids(
        df=df,
        res_id_col="Code",
        duplicate_handling="error",
        normalize_sub_fn=_norm,
        res_ses_col="session",
    )
    assert ses_override is None
    assert warnings == []
    assert len(result_df) == 4


def test_same_id_different_runs_not_a_duplicate() -> None:
    """hsub01/run1 + hsub01/run2 should be accepted when run col is known."""
    df = _make_df(
        Code=["hsub01", "hsub01"],
        run=["run-1", "run-2"],
        score=[10, 20],
    )
    result_df, ses_override, warnings = _handle_duplicate_ids(
        df=df,
        res_id_col="Code",
        duplicate_handling="error",
        normalize_sub_fn=_norm,
        res_run_col="run",
    )
    assert ses_override is None
    assert warnings == []
    assert len(result_df) == 2


def test_same_id_different_session_and_run_not_a_duplicate() -> None:
    """All four (id, ses, run) combos unique → no duplicates."""
    df = _make_df(
        Code=["s01", "s01", "s01", "s01"],
        session=["ses-1", "ses-1", "ses-2", "ses-2"],
        run=["run-1", "run-2", "run-1", "run-2"],
        score=[1, 2, 3, 4],
    )
    result_df, _, warnings = _handle_duplicate_ids(
        df=df,
        res_id_col="Code",
        duplicate_handling="error",
        normalize_sub_fn=_norm,
        res_ses_col="session",
        res_run_col="run",
    )
    assert warnings == []
    assert len(result_df) == 4


# ---------------------------------------------------------------------------
# True-duplicate cases (same id AND same session AND same run)
# ---------------------------------------------------------------------------


def test_true_duplicate_same_id_same_session_raises() -> None:
    """Same (id, session) twice is a real duplicate → error mode should raise."""
    df = _make_df(
        Code=["hsub01", "hsub01"],
        session=["pre", "pre"],
        score=[1, 2],
    )
    with pytest.raises(ValueError, match="Duplicate entries"):
        _handle_duplicate_ids(
            df=df,
            res_id_col="Code",
            duplicate_handling="error",
            normalize_sub_fn=_norm,
            res_ses_col="session",
        )


def test_true_duplicate_same_id_same_session_keep_first() -> None:
    df = _make_df(
        Code=["hsub01", "hsub01", "hsub02"],
        session=["pre", "pre", "pre"],
        score=[1, 2, 3],
    )
    result_df, _, warnings = _handle_duplicate_ids(
        df=df,
        res_id_col="Code",
        duplicate_handling="keep_first",
        normalize_sub_fn=_norm,
        res_ses_col="session",
    )
    assert len(result_df) == 2
    assert len(warnings) == 1


def test_true_duplicate_no_session_col_still_detected() -> None:
    """Without session/run cols, fall back to id-only duplicate detection."""
    df = _make_df(
        Code=["hsub01", "hsub01", "hsub02"],
        score=[1, 2, 3],
    )
    with pytest.raises(ValueError, match="Duplicate entries"):
        _handle_duplicate_ids(
            df=df,
            res_id_col="Code",
            duplicate_handling="error",
            normalize_sub_fn=_norm,
        )


# ---------------------------------------------------------------------------
# Run col detection via _resolve_id_and_session_cols
# ---------------------------------------------------------------------------


def test_resolve_id_and_session_cols_detects_run_column() -> None:
    from app.src.converters.survey_participants_logic import (
        _resolve_id_and_session_cols,
    )

    df = _make_df(
        Code=["s01", "s01"],
        session=["pre", "post"],
        run=["run-1", "run-2"],
        score=[1, 2],
    )
    id_col, ses_col, run_col = _resolve_id_and_session_cols(
        df=df,
        id_column="Code",
        session_column=None,
    )
    assert id_col == "Code"
    assert ses_col == "session"
    assert run_col == "run"


def test_resolve_id_and_session_cols_run_col_none_when_absent() -> None:
    from app.src.converters.survey_participants_logic import (
        _resolve_id_and_session_cols,
    )

    df = _make_df(
        Code=["s01", "s02"],
        session=["pre", "pre"],
        score=[1, 2],
    )
    _, _, run_col = _resolve_id_and_session_cols(
        df=df,
        id_column="Code",
        session_column=None,
    )
    assert run_col is None
