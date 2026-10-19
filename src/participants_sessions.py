"""Session helpers for the participants importer (longitudinal source files).

Session labels are free-form strings ("1", "01" and "baseline" are different
labels): they are compared exactly and never normalized. The one concession is
a whole-number float such as ``1.0``, a spreadsheet data-type artifact of the
integer ``1``, not a different label.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

try:
    import pandas as pd
except (
    ImportError
):  # the standalone validator image has no pandas; session_label needs none
    pd = None  # type: ignore[assignment]

_SESSION_COLUMN_ALIASES = {"ses", "session", "sessionid", "visit", "timepoint", "wave"}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return False
    if pd is not None:
        return bool(pd.isna(value))
    return value != value  # NaN is the only missing scalar left without pandas


def session_label(value: Any) -> str:
    """Exact string label of a session cell ('' for missing)."""
    if _is_missing(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _looks_like_session_column(name: Any) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "", str(name).strip().lower())
    return normalized in _SESSION_COLUMN_ALIASES or normalized.startswith("session")


def _natural_key(label: str) -> tuple[Any, ...]:
    # re.split keeps text at even and digit runs at odd positions, so keys of
    # different labels always compare str-with-str and int-with-int. The label
    # itself is the final tie-break ("01" vs "1"), which keeps the order stable.
    parts = re.split(r"(\d+)", label)
    return (tuple(int(p) if i % 2 else p for i, p in enumerate(parts)), label)


def sort_session_labels(labels: Iterable[str]) -> list[str]:
    """Session labels in natural string order; the labels are never converted.

    Digit runs inside the text compare by size ("2" < "10", "ses-2" < "ses-10");
    nothing is parsed as a decimal or exponent.
    """
    return sorted(labels, key=_natural_key)


def find_session_candidates(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Session-like columns that hold at least two different session labels."""
    candidates: list[dict[str, Any]] = []
    for column in df.columns:
        if not _looks_like_session_column(column):
            continue
        labels = {session_label(value) for value in df[column]}
        labels.discard("")
        if len(labels) >= 2:
            candidates.append(
                {"column": str(column), "values": sort_session_labels(labels)}
            )
    return candidates


def filter_rows_to_session(df: pd.DataFrame, column: str, value: str) -> pd.DataFrame:
    """Rows whose ``column`` holds exactly the session label ``value``."""
    if column not in df.columns:
        raise ValueError(f"Session column '{column}' not found in the file")
    mask = df[column].map(session_label) == str(value).strip()
    if not mask.any():
        raise ValueError(f"Session '{value}' not found in column '{column}'")
    return df[mask].copy()


def scope_to_session(
    df: pd.DataFrame, column: str = "", value: str = ""
) -> tuple[list[dict[str, Any]], pd.DataFrame]:
    """Session candidates of the whole file plus the rows of the chosen session.

    Without both ``column`` and ``value`` every row is kept. Used by the GUI
    preview and the CLI so both apply the same rule.
    """
    candidates = find_session_candidates(df)
    if column and value:
        df = filter_rows_to_session(df, column, value)
    return candidates, df


def sanitize_session_token(value: Any) -> str:
    """Session label as it appears inside a column name (``age@ses-<token>``)."""
    token = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip())
    token = re.sub(r"-+", "-", token).strip("-")
    return (token or "unknown").lower()


def _non_empty(values: Iterable[Any]) -> list[Any]:
    return [v for v in values if not _is_missing(v) and str(v).strip() != ""]


def find_repeat_conflicts(
    df: pd.DataFrame, id_column: str, columns: Iterable[str]
) -> list[str]:
    """Columns whose non-empty values differ between rows of the same participant.

    Identical repeats are not conflicts: they collapse to one row without any
    question. A conflict is a value that changes between a participant's rows
    (e.g. age across sessions).
    """
    conflicts = []
    for column in columns:
        if column == id_column or column not in df.columns:
            continue
        varies = df.groupby(id_column, sort=False)[column].apply(
            lambda values: len({str(v).strip() for v in _non_empty(values)}) > 1
        )
        if varies.any():
            conflicts.append(str(column))
    return conflicts


def split_columns_by_session(
    df: pd.DataFrame,
    labels: pd.Series,
    columns: Iterable[str],
    id_column: str = "participant_id",
) -> pd.DataFrame:
    """One column per session (``age@ses-1``) for ``columns``, one row per participant.

    ``labels`` holds each row's exact session label (aligned with ``df``).
    Rows without a label are ignored. Raises ValueError when two labels would
    name the same column or one participant has different values in one session.
    """
    labels = labels.map(session_label)
    names: dict[str, str] = {}  # token -> label that claimed it
    for label in sort_session_labels(set(labels) - {""}):
        token = sanitize_session_token(label)
        if names.setdefault(token, label) != label:
            raise ValueError(
                f"Session labels {names[token]!r} and {label!r} would name the same column "
                f"(@ses-{token}). Rename one of them in the source file."
            )
    ids = list(dict.fromkeys(df[id_column]))
    wide: dict[str, pd.Series] = {}
    for column in columns:
        for token, label in names.items():
            values: dict[Any, Any] = {}
            for pid, group in df[labels == label].groupby(id_column, sort=False):
                found = _non_empty(group[column])
                if len({str(v).strip() for v in found}) > 1:
                    raise ValueError(
                        f"ID {pid} has different values for '{column}' within session {label!r}."
                    )
                if found:
                    values[pid] = found[0]
            wide[f"{column}@ses-{token}"] = pd.Series(values, dtype=object).reindex(ids)
    return pd.DataFrame(wide, index=ids)


def _outcomes(
    df: pd.DataFrame,
    id_column: str,
    date_column: str,
    response_id_column: str,
    decisions: dict | None,
) -> tuple[pd.DataFrame, list[str]]:
    """Per-response outcome shared by numbering and the review table.

    Returns (res, warnings). ``res`` is indexed like ``df`` with
    participant, response_id, when, completed, lastpage, session (str | None), reason.
    """
    if (
        date_column == "startdate"
        and date_column not in df.columns
        and "datestamp" in df.columns
    ):
        date_column = "datestamp"  # LimeSurvey exports without "Save start time"
    for column in (id_column, date_column):
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in the file")
    decisions = decisions or {}

    def _parse(column: str) -> pd.Series:
        # format="mixed": otherwise pandas infers one format from the first value
        # and silently turns "2026-03-01 10:00:00" after "2026-03-01" into NaT.
        return pd.to_datetime(
            df[column].replace("", None), errors="coerce", format="mixed"
        )

    when = _parse(date_column)
    if date_column == "startdate" and "datestamp" in df.columns:
        when = when.fillna(_parse("datestamp"))

    blank = pd.Series("", index=df.index)
    res = pd.DataFrame(
        {
            "participant": df[id_column].map(session_label),  # same form for 1.0 and "1"
            "response_id": df[response_id_column].map(session_label)
            if response_id_column in df.columns
            else blank,
            "when": when,
            "completed": df["submitdate"].map(session_label) != ""
            if "submitdate" in df.columns
            else pd.Series(True, index=df.index),
            "lastpage": df["lastpage"].map(session_label)
            if "lastpage" in df.columns
            else blank,
        },
        index=df.index,
    )
    res["session"] = None
    res["reason"] = ""

    for i, row in res.iterrows():
        decision = decisions.get(row["response_id"]) if row["response_id"] else None
        if decision and decision.get("skip"):
            res.at[i, "reason"] = "skipped"
        elif decision and decision.get("session"):
            res.at[i, "session"] = session_label(decision["session"])
            res.at[i, "reason"] = "override"
        elif row["completed"]:
            res.at[i, "reason"] = "auto"
        elif decision and decision.get("include"):
            res.at[i, "reason"] = "included"
        else:
            res.at[i, "reason"] = "incomplete"

    auto = res[res["reason"].isin(["auto", "included"])]
    no_date = auto[auto["when"].isna()]
    undated = sorted(set(no_date["participant"]))
    if undated:
        inc = no_date[no_date["reason"] == "included"]
        extra = (
            f" Undated: response(s) {', '.join(sorted(inc['response_id'], key=_natural_key))} (included)."
            if len(inc) else ""
        )
        raise ValueError(
            f"No usable '{date_column}' for ID(s): {', '.join(undated[:10])}.{extra} "
            "Fix these responses in LimeSurvey before numbering sessions."
        )
    ordered = auto.sort_values(["participant", "when"], kind="stable")
    res.loc[ordered.index, "session"] = (
        ordered.groupby("participant").cumcount() + 1
    ).astype(str)

    assigned = res[res["session"].notna()]
    clash = assigned[assigned.duplicated(["participant", "session"], keep=False)]
    if not clash.empty:
        lines = [
            f"ID {pid}: session {label!r} on responses {', '.join(group['response_id'])}"
            for (pid, label), group in clash.groupby(["participant", "session"])
        ]
        raise ValueError(
            "One participant would get the same session label twice; fix it with "
            "`sessions set`/`sessions unset`: " + "; ".join(lines)
        )

    warnings = [
        f"Sessions numbered by {date_column} (completed responses only): "
        f"{len(assigned)} of {len(res)} responses kept."
    ]
    applied = res[res["reason"].isin(["skipped", "override", "included"])]
    if len(applied):
        def _ids(frame):
            return ", ".join(sorted(frame["response_id"], key=_natural_key))
        parts = []
        skipped = applied[applied["reason"] == "skipped"]
        if len(skipped):
            parts.append(f"skipped {_ids(skipped)}")
        for label, group in applied[applied["reason"] == "override"].groupby("session", sort=True):
            parts.append(f"session {label!r} for {_ids(group)}")
        included = applied[applied["reason"] == "included"]
        if len(included):
            parts.append(f"included {_ids(included)}")
        warnings.append("Saved decisions applied: " + "; ".join(parts) + ".")
    left_out = res[res["session"].isna()]
    incomplete = left_out[left_out["reason"] == "incomplete"]
    if len(incomplete):
        warnings.append(f"{len(incomplete)} incomplete response(s) left out (no submitdate).")
    without = sorted(set(res["participant"]) - set(assigned["participant"]))
    if without:
        warnings.append("No completed response for: " + ", ".join(without[:10]))
    known = set(res["response_id"])
    stale = sorted(str(k) for k in decisions if str(k) not in known)
    if stale:
        warnings.append(
            "Ignored decisions for responses not in this file: " + ", ".join(stale)
        )
    counts = assigned.groupby("participant").size().value_counts().sort_index(ascending=False)
    if len(counts) > 1:
        parts = [
            f"{n} IDs x {k} sessions" if i == 0 else f"{n} x {k}"
            for i, (k, n) in enumerate(counts.items())
        ]
        warnings.append("Uneven session counts: " + ", ".join(parts))
    return res, warnings


def number_sessions_by_date(
    df: pd.DataFrame,
    id_column: str,
    date_column: str = "startdate",
    session_column: str = "session",
    decisions: dict | None = None,
    response_id_column: str = "id",
) -> tuple[pd.DataFrame, list[str]]:
    """Give each participant's *completed* responses sessions "1", "2", ... by date.

    For repeated-measures exports without a session indicator (LimeSurvey).
    Incomplete responses (empty ``submitdate``) are left out, and listed in the
    warnings; ``decisions`` (``{response_id: {"skip": True} | {"session": label}}``)
    override the automatic rule. Rows are never merged. The returned frame holds
    only the responses that got a session.
    """
    if session_column in df.columns:
        raise ValueError(
            f"The file already has a '{session_column}' column; use it as the session column instead."
        )
    res, warnings = _outcomes(df, id_column, date_column, response_id_column, decisions)
    if len(res) and res["session"].isna().all():
        raise ValueError(
            f"No response gets a session ({len(res)} response(s): all incomplete or skipped). "
            "Run `sessions review` to see why."
        )
    kept = res[res["session"].notna()].sort_values(["participant", "when"], kind="stable")
    out = df.loc[kept.index].copy()
    out[session_column] = kept["session"]
    return out.reset_index(drop=True), warnings


def session_assignment_table(
    df: pd.DataFrame,
    id_column: str,
    date_column: str = "startdate",
    decisions: dict | None = None,
    response_id_column: str = "id",
) -> tuple[list[dict], list[str]]:
    """One row per response for review: what session it gets and why."""
    res, warnings = _outcomes(df, id_column, date_column, response_id_column, decisions)
    rows = [
        {
            "participant": r["participant"],
            "response_id": r["response_id"],
            "date": "" if pd.isna(r["when"]) else str(r["when"]),
            "completed": bool(r["completed"]),
            "lastpage": r["lastpage"],
            "session": r["session"],
            "reason": r["reason"],
        }
        for _, r in res.sort_values(["participant", "when"], kind="stable").iterrows()
    ]
    return rows, warnings
