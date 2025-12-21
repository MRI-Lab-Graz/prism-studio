"""
Base utilities for Excel-to-JSON conversion in PRISM.
Shared logic for survey and biometrics library generation.
"""

import re
import pandas as pd
from typing import Dict, Any, List, Optional


def norm_key(s: str) -> str:
    """Normalize a string for key matching (lowercase, no spaces/underscores)."""
    return str(s).replace(" ", "").replace("_", "").lower()


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


def parse_levels(scale_str: Any) -> Optional[Dict[str, str]]:
    """
    Parse scale string into a dictionary.
    Format expected: "1=Label A; 2=Label B" or "1=Label A, 2=Label B"
    """
    if pd.isna(scale_str) or not str(scale_str).strip():
        return None

    levels = {}
    # Split by semicolon or comma, but be careful with commas inside labels
    # Usually semicolons are safer for scales
    parts = re.split(r"[;]\s*", str(scale_str))
    if len(parts) == 1 and "," in parts[0] and "=" in parts[0]:
        # Fallback to comma if no semicolon but equals present
        parts = re.split(r"[,]\s*", str(scale_str))

    for part in parts:
        if "=" in part:
            try:
                val, label = part.split("=", 1)
                levels[val.strip()] = label.strip()
            except ValueError:
                continue
    return levels if levels else None


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


def sanitize_task_name(name: str) -> str:
    """Normalize task names for BIDS/PRISM filenames."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", str(name).strip()).strip("-")
    return cleaned.lower() or "survey"
