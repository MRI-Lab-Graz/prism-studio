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

import openpyxl
import pandas as pd

from .excel_base import detect_language, read_excel_sheets
from .excel_to_survey import extract_excel_templates
from src.converters.template_import import TEMPLATE_SECTIONS

RESERVED_TOPLEVEL = TEMPLATE_SECTIONS
DESCRIPTION_ALIASES = {"description", "question", "item", "item text", "text", "label", "questiontext"}


_LANG_SUFFIX = re.compile(r"[_-][a-z]{2,3}$")


def _is_language_description(h):
    """True for Description_<lang> style headers (any language, not just en/de)."""
    return bool(_LANG_SUFFIX.search(h)) and _LANG_SUFFIX.sub("", h) in DESCRIPTION_ALIASES


def _has_plain_unlabeled_description(header):
    """True if header has a bare Description-like column with no language suffix."""
    norm = [str(h).strip().lower() for h in header]
    return any(h in DESCRIPTION_ALIASES for h in norm) and not any(_is_language_description(h) for h in norm)


def _autolabel_description_column(path: Path) -> None:
    """For simple codebooks with only a plain 'Description' column (no language
    suffix), rename it to Description_<lang> in place, using a whole-column
    language heuristic. A workbook that already has a language-suffixed Description
    column is left untouched. In a multi-sheet workbook (e.g. Template + Help)
    the first sheet with a plain Description is the one renamed.
    """
    is_text = path.suffix.lower() in (".csv", ".tsv")
    sep = "\t" if path.suffix.lower() == ".tsv" else ","
    if is_text:
        sheets = {"": pd.read_csv(path, sep=sep, header=None, dtype=str, keep_default_na=False)}
    else:
        sheets = read_excel_sheets(path)

    headers = {n: [str(c) if c is not None else "" for c in df.iloc[0].tolist()] for n, df in sheets.items() if not df.empty}
    if any(_is_language_description(x.strip().lower()) for h in headers.values() for x in h):
        return
    name = next((n for n, h in headers.items() if _has_plain_unlabeled_description(h)), None)
    if name is None:
        return

    df = sheets[name]
    norm = [h.strip().lower() for h in headers[name]]
    col_idx = next(i for i, h in enumerate(norm) if h in DESCRIPTION_ALIASES)
    lang = detect_language(df.iloc[1:, col_idx].tolist())

    if is_text:
        df.iat[0, col_idx] = f"Description_{lang}"
        df.to_csv(path, index=False, header=False, sep=sep)
    else:
        wb = openpyxl.load_workbook(path)
        wb[name].cell(row=1, column=col_idx + 1).value = f"Description_{lang}"
        wb.save(path)


def parse_excel_groups(file_bytes: bytes, filename: str, problems: list | None = None) -> dict:
    """Parse an Excel/CSV/TSV codebook into {prefix: full_prism_sidecar}."""
    suffix = Path(filename).suffix.lower() or ".xlsx"
    # A directory, not NamedTemporaryFile: Windows refuses to reopen a file that is still open.
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / f"codebook{suffix}"
        tmp_path.write_bytes(file_bytes)
        _autolabel_description_column(tmp_path)
        return extract_excel_templates(str(tmp_path), check_collisions=False, problems=problems)


def group_notes(template: dict, problems: list) -> list:
    """The import problems that belong to one group's items."""
    return [p for p in problems if p.split(":", 1)[0] in template]


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
