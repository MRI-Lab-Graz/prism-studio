"""Remove survey start dates from data that leaves the lab.

``SurveyStartDate`` (written by the LimeSurvey import, used for session timing) identifies
people, so every shared export drops the column and its sidecar entry through these helpers.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

SURVEY_DATE_COLUMN = "SurveyStartDate"
# Import ledger with each response's start date, seed and LimeSurvey token (src/survey_existing.py).
IMPORT_LEDGER_PARTS = ("code", "survey_imports.json")


def has_survey_date(tsv_path: Path) -> bool:
    """True when the TSV's header row has the survey date column."""
    try:
        with open(tsv_path, "r", encoding="utf-8", newline="") as fh:
            return SURVEY_DATE_COLUMN in fh.readline().rstrip("\r\n").split("\t")
    except (OSError, UnicodeDecodeError):
        return False


def drop_survey_date_tsv(text: str) -> str:
    """TSV text without the survey date column (text without it is returned unchanged)."""
    rows = list(csv.reader(io.StringIO(text), delimiter="\t"))
    if not rows or SURVEY_DATE_COLUMN not in rows[0]:
        return text
    keep = [i for i, name in enumerate(rows[0]) if name != SURVEY_DATE_COLUMN]
    out = io.StringIO()
    writer = csv.writer(out, delimiter="\t", lineterminator="\n")
    writer.writerows([[row[i] for i in keep if i < len(row)] for row in rows])
    return out.getvalue()


def drop_survey_date_sidecar(data: dict) -> dict:
    data.pop(SURVEY_DATE_COLUMN, None)
    return data


def _rewrite(path: Path, text: str) -> None:
    path.unlink()  # a symlink (e.g. annex) must not write through to the source
    path.write_text(text, encoding="utf-8", newline="")


def strip_survey_dates_in_tree(root: Path) -> int:
    """Strip the date in place from every survey TSV and sidecar under ``root`` (an export copy); returns files changed."""
    changed = 0
    for path in sorted(Path(root).rglob("*")):
        try:
            if not path.is_file():
                continue
            if path.suffix == ".tsv" and "survey" in path.parent.parts:
                text = path.read_text(encoding="utf-8")
                new = drop_survey_date_tsv(text)
            elif path.suffix == ".json" and path.stem.endswith("_survey"):
                text = path.read_text(encoding="utf-8")
                data = json.loads(text)
                if not isinstance(data, dict) or SURVEY_DATE_COLUMN not in data:
                    continue
                new = json.dumps(drop_survey_date_sidecar(data), indent=2, ensure_ascii=False)
            else:
                continue
        except (OSError, UnicodeDecodeError, ValueError):
            continue
        if new != text:
            _rewrite(path, new)
            changed += 1
    return changed
