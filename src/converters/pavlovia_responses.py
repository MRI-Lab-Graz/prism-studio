"""Pavlovia survey responses (the CSV download) -> one clean wide table for ``survey convert``.

A download carries bookkeeping columns (``responseId``, ``_rt`` reaction times, ...), no participant or
session column, and one column per question - under a ``block/`` prefix when the survey was run inside a
block, and under an older name when a question was renamed. This step settles all of that against the
survey (``survey-*.json`` from Pavlovia) and says what it did; the result goes to the normal converter
with ``--id-column participant_id --session-column session``.
"""

from __future__ import annotations

import re

import pandas as pd

from src.converters.pavlovia_import import _flatten, _label, _pages

_PREFIX = re.compile(r"^[^/]+/")


def _split_rename(spec: str) -> tuple[str, str]:
    old, sep, new = spec.partition("=")
    if not (sep and old.strip() and new.strip()):
        raise ValueError(f"Invalid rename '{spec}': use OLD=NEW")
    return old.strip(), new.strip()


def _merge_columns(df: pd.DataFrame, elements: dict, rename: dict, notes: list[str]) -> pd.DataFrame:
    """One column per question: the plain column first, then the block/ and renamed ones fill its gaps."""
    sources: dict[str, list[str]] = {}
    unknown = []
    for col in df.columns:
        if col.endswith("_rt"):
            continue
        plain = _PREFIX.sub("", col)
        target = rename.get(plain, plain)
        if target in elements:
            sources.setdefault(target, []).append(col)
        elif col not in _BOOKKEEPING:
            unknown.append(col)
    if unknown:
        notes.append(f"Columns not in the survey were dropped: {', '.join(unknown)}")
    out = {}
    for target, cols in sources.items():
        cols.sort(key=lambda c: c != target)  # the column that already has the question's name leads
        merged = df[cols[0]].copy()
        for col in cols[1:]:
            both = (merged != "") & (df[col] != "")
            if (clash := int((both & (merged != df[col])).sum())):
                notes.append(f"'{target}': {clash} row(s) had different answers in {cols[0]} and {col}; kept {cols[0]}")
            merged = merged.where(merged != "", df[col])
        out[target] = merged
    return pd.DataFrame(out, index=df.index)


_BOOKKEEPING = {"surveyId", "responseId", "experimentId", "sessionToken", "participant", "responseDate",
                "isComplete", "surveyStatus", "length_ch", "expanded"}


def prepare_pavlovia_responses(
    df: pd.DataFrame,
    survey: dict,
    *,
    id_columns: list[str],
    id_pad: int = 0,
    session_column: str | None = None,
    rename: list[str] = (),
) -> tuple[pd.DataFrame, list[str]]:
    """(wide table with ``participant_id`` and ``session``, notes on everything that was changed or left out).

    The participant is ``id_columns`` joined, every part after the first zero-padded to ``id_pad`` digits (the
    survey asks for "the last 3 digits"); an empty part takes the survey's own default value. The session is
    the text the participant saw for the stored choice. Rows without any answer are dropped; ``isComplete`` is
    not used (an unfinished row can hold every answer). Every dropped row is counted once, with its reason."""
    elements = {el["name"]: el for page in _pages(survey) for el in _flatten(page.get("elements", []))}
    notes: list[str] = []
    df = df.fillna("").astype(str)
    if "responseDate" in df:  # earliest first: keep_first / keep_last of the converter then mean earliest / latest
        df = df.sort_values("responseDate", kind="stable").reset_index(drop=True)
    origin = df["experimentId"] if "experimentId" in df else pd.Series("", index=df.index)
    wide = _merge_columns(df, elements, dict(map(_split_rename, rename)), notes)
    structural = [*id_columns, *([session_column] if session_column else [])]
    for col in structural:
        if col not in wide.columns:
            raise ValueError(f"Column '{col}' is not in the responses (nor under a block/ prefix or a --rename)")
    for name, el in elements.items():
        if el.get("type") == "boolean" and name in wide:
            wide[name] = wide[name].str.lower()

    dropped = pd.Series(False, index=wide.index)

    def drop(mask: pd.Series, why: str) -> None:
        nonlocal dropped
        if n := int((mask & ~dropped).sum()):
            notes.append(f"{n} row(s) dropped: {why}")
            dropped |= mask

    drop((wide[[c for c in wide.columns if c not in structural]] == "").all(axis=1), "no answers")
    defaults = {c: elements[c]["defaultValue"] for c in id_columns if elements.get(c, {}).get("defaultValue") is not None}
    for col in id_columns:
        if col not in defaults:
            drop(wide[col] == "", f"no {col}")
    for col, default in defaults.items():
        empty = (wide[col] == "") & ~dropped
        stored = (wide[col] != "").groupby(origin).transform("any")  # the experiment writes this field at all
        drop(empty & stored, f"no {col}")
        empty &= ~dropped
        if empty.any():
            by_experiment = ", ".join(f"{n} of experiment {e or '?'}" for e, n in origin[empty].value_counts().items())
            notes.append(f"{int(empty.sum())} row(s) had no {col}: the survey default {default} was used ({by_experiment})")
            wide.loc[empty, col] = str(default)
    if id_pad:
        for col in id_columns[1:]:
            for value in sorted(set(wide.loc[~dropped, col])):
                if not (value.isdigit() and len(value) <= id_pad):
                    drop(wide[col] == value, f"'{value}' in {col} is not a number of at most {id_pad} digits")

    wide["session"] = ""
    if session_column:
        choices = elements.get(session_column, {}).get("choices")
        labels = dict(map(_label, choices)) if choices else None
        for value in sorted(set(wide.loc[~dropped, session_column])):
            if labels is None:
                wide.loc[wide[session_column] == value, "session"] = value
            elif value in labels:
                wide.loc[wide[session_column] == value, "session"] = labels[value]
            else:
                drop(wide[session_column] == value, f"session '{value}' is not one of the survey's choices")

    parts = [wide[id_columns[0]], *(wide[c].str.zfill(id_pad) for c in id_columns[1:])]
    wide.insert(0, "participant_id", parts[0].str.cat(parts[1:], sep="") if len(parts) > 1 else parts[0])
    items = [c for c in wide.columns if c not in (*structural, "participant_id", "session")]
    filled = (wide[items] != "").sum(axis=1)
    covered = pd.Series(False, index=wide.index)
    for _key, rows in wide[~dropped].groupby(["participant_id", "session"]):
        for i in rows.index:  # all its answers, with the same values, are in a fuller row (or an earlier equal one)
            mine = wide.loc[i, items] != ""
            covered[i] = any(
                (filled[j], -j) > (filled[i], -i) and (wide.loc[j, items][mine] == wide.loc[i, items][mine]).all()
                for j in rows.index if j != i
            )
    drop(covered, "all answers are in another row of the same participant and session")
    for (participant, session), rows in wide[~dropped].groupby(["participant_id", "session"]):
        if len(rows) > 1:
            notes.append(f"{participant}, session {session}: {len(rows)} rows with different answers (choose with "
                         "survey convert --duplicate-handling keep_first|keep_last)")
    wide = wide[~dropped].reset_index(drop=True)
    return wide[["participant_id", "session", *[c for c in wide.columns if c not in ("participant_id", "session")]]], notes
