"""
Excel/CSV/TSV survey-template importer for the Template Editor.

Thin wrapper around excel_to_survey.extract_excel_templates — the same
well-tested multi-sheet parser used by the Converter's bulk import (Items/
General/Variants sheets, explicit "Group" column, or prefix-based grouping
as a fallback). check_collisions=False disables the item-registry
collision/version-merge machinery entirely (it's only relevant to the
Converter's bulk library-building workflow, and would otherwise read/write
the project's item library as a side effect of a stateless "preview groups"
call, which is unsafe here).
"""

import re
import tempfile
from pathlib import Path

import pandas as pd

from .excel_base import detect_language
from .excel_to_survey import extract_excel_templates

RESERVED_TOPLEVEL = {
    "Technical",
    "Study",
    "Metadata",
    "I18n",
    "LimeSurvey",
    "Scoring",
    "Normative",
}
DESCRIPTION_ALIASES = {"description", "question", "item", "item text", "text", "label", "questiontext"}


def _has_plain_unlabeled_description(header):
    """True if header has a bare Description-like column with no _en/_de suffix."""
    norm = [str(h).strip().lower() for h in header]
    has_plain = any(h in DESCRIPTION_ALIASES for h in norm)
    has_suffixed = any(
        re.sub(r"_(en|de)$", "", h) in DESCRIPTION_ALIASES and h.endswith(("_en", "_de"))
        for h in norm
    )
    return has_plain and not has_suffixed


def _autolabel_description_column(path: Path) -> None:
    """For simple single-sheet codebooks with only a plain 'Description' column
    (no _en/_de suffix), rename it to Description_<lang> in place, using a
    whole-file language heuristic. The official multi-sheet Items/General/
    Variants format already uses explicit _en/_de columns, so multi-sheet
    workbooks are left untouched.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, header=None, dtype=str, keep_default_na=False)
    elif suffix == ".tsv":
        df = pd.read_csv(path, sep="\t", header=None, dtype=str, keep_default_na=False)
    else:
        sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=str)
        if len(sheets) != 1:
            return
        df = next(iter(sheets.values()))

    if df.empty:
        return

    header = [str(c) if c is not None else "" for c in df.iloc[0].tolist()]
    if not _has_plain_unlabeled_description(header):
        return

    norm = [str(h).strip().lower() for h in header]
    col_idx = next(i for i, h in enumerate(norm) if h in DESCRIPTION_ALIASES)
    texts = df.iloc[1:, col_idx].tolist()
    lang = detect_language(texts)
    df.iat[0, col_idx] = f"Description_{lang}"

    if suffix == ".csv":
        df.to_csv(path, index=False, header=False)
    elif suffix == ".tsv":
        df.to_csv(path, index=False, header=False, sep="\t")
    else:
        df.to_excel(path, index=False, header=False)


def parse_excel_groups(file_bytes: bytes, filename: str) -> dict:
    """Parse an Excel/CSV/TSV codebook into {prefix: full_prism_sidecar}."""
    suffix = Path(filename).suffix.lower() or ".xlsx"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(file_bytes)
        tmp.flush()
        tmp_path = Path(tmp.name)
        _autolabel_description_column(tmp_path)
        return extract_excel_templates(str(tmp_path), check_collisions=False)


def summarize_groups(groups: dict) -> list:
    """Build a lightweight summary list for the group-picker UI."""
    summaries = []
    for prefix, template in sorted(groups.items()):
        item_keys = [k for k in template if k not in RESERVED_TOPLEVEL]
        summaries.append(
            {
                "prefix": prefix,
                "item_count": len(item_keys),
                "sample_vars": item_keys[:5],
            }
        )
    return summaries
