"""
Base utilities for Excel-to-JSON conversion in PRISM.
Shared logic for survey and biometrics library generation.
"""

import re
import warnings
import pandas as pd
from typing import Dict, Any, List, Optional

from ..utils.naming import norm_key, sanitize_task_name

__all__ = [
    "norm_key",
    "sanitize_task_name",
    "find_column_idx",
    "clean_variable_name",
    "parse_levels",
    "level_problems",
    "detect_language",
    "read_excel_sheets",
]


def read_excel_sheets(path) -> Dict[str, "pd.DataFrame"]:
    """Read every sheet of an .xlsx as raw (unheadered) string DataFrames.

    Suppresses openpyxl's "Data Validation extension is not supported" warning.
    It fires when a workbook's data validations were upgraded to the newer x14
    extension format by Excel/Numbers/LibreOffice on save (common for our
    dropdown-guided import templates once a researcher opens and re-saves one).
    openpyxl's reader can't parse that format and drops it — harmless here,
    since this function only reads cell values, never validation metadata.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Data Validation extension is not supported.*",
            category=UserWarning,
        )
        return pd.read_excel(path, sheet_name=None, header=None, dtype=str)


def find_column_idx(header: List[str], aliases: set) -> Optional[int]:
    """Find the index of a column in the header based on a set of aliases."""
    header_norm = [norm_key(h) for h in header]
    aliases_norm = {norm_key(a) for a in aliases}
    for i, val in enumerate(header_norm):
        if val in aliases_norm:
            return i
    return None


def clean_variable_name(name: Any) -> str:
    """Clean variable name to be used as a key."""
    return str(name).strip()


def _level_parts(text: str) -> List[str]:
    """Split a scale cell into "code=label" parts.

    ";" always separates. A "," separates only in front of the next "code=",
    so commas inside a label ("0,5 years", "yes, but ...") stay.
    """
    parts = re.split(r";\s*", text)
    if len(parts) == 1 and "=" in text:
        parts = re.split(r",\s*(?=[^,;=\s]+\s*=)", text)
    return parts


def _strip_bare_codes(code: str, label: str) -> str:
    """Drop the unlabeled codes of an anchor scale: "0 = never, 1, 2, 3"."""
    match = re.fullmatch(r"(\D*)(\d+)", code)
    if not match:
        return label
    head, *rest = re.split(r",\s*", label)
    prefix, number = match[1], int(match[2])
    for step in (1, -1):
        if rest == [f"{prefix}{number + step * i}" for i in range(1, len(rest) + 1)]:
            return head
    return label


def parse_levels(scale_str: Any) -> Optional[Dict[str, str]]:
    """
    Parse scale string into a dictionary.
    Format expected: "1=Label A; 2=Label B" or "1=Label A, 2=Label B"
    """
    if pd.isna(scale_str) or not str(scale_str).strip():
        return None

    levels = {}
    for part in _level_parts(str(scale_str)):
        if "=" in part:
            code, label = part.split("=", 1)
            levels[code.strip()] = _strip_bare_codes(code.strip(), label.strip())
    return levels if levels else None


def level_problems(scale_str: Any) -> List[str]:
    """What an import of this scale cell would lose or blur."""
    levels = parse_levels(scale_str)
    if not levels:
        return []
    parts = _level_parts(str(scale_str))
    problems = [
        f"text '{part.strip()}' has no code and is ignored"
        for part in parts
        if "=" not in part and part.strip() and not part.strip().isdigit()
    ]
    codes = [p.split("=", 1)[0].strip() for p in parts if "=" in p]
    problems += [
        f"code '{c}' is defined twice, only the last label is kept"
        for c in sorted({c for c in codes if codes.count(c) > 1})
    ]
    labels = list(levels.values())
    problems += [
        f"label '{label}' contains '=': is a second answer inside it?"
        for label in labels
        if "=" in label
    ]
    problems += [
        f"several codes have the same label '{label}'"
        for label in sorted({x for x in labels if x and labels.count(x) > 1})
    ]
    return problems


def detect_language(texts: List[str]) -> str:
    """Tiny heuristic: flag German if umlauts/ß or common tokens are present."""
    combined = " ".join([str(t) for t in texts if pd.notna(t)]).lower()
    if not combined.strip():
        return "en"

    if re.search(r"[\u00e4\u00f6\u00fc\u00df]", combined):
        return "de"

    german_tokens = [
        " nicht ",
        " oder ",
        " keine ",
        " während ",
        " immer ",
        " selten ",
        " häufig ",
    ]
    padded = f" {combined} "
    if any(token in padded for token in german_tokens):
        return "de"

    return "en"
