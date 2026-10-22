"""Term registry: shipped terms (parent = analyte, child = analyte in one specimen).

JSON only (the validator image has no pandas). Spec:
docs/superpowers/specs/2026-10-22-biosample-term-registry-design.md
"""

from __future__ import annotations

import json
from pathlib import Path

DEFAULT_TERMS_ROOT = Path(__file__).resolve().parents[1] / "official" / "library" / "terms"


def load_registry(modality: str = "biosample", root: Path | None = None) -> dict[str, dict]:
    """Map each term file's stem (the local part of its TermID) to the parsed term.

    A missing folder gives an empty registry; unreadable files are skipped
    (check_registry is the place that reports problems).
    """
    folder = Path(root or DEFAULT_TERMS_ROOT) / modality
    registry: dict[str, dict] = {}
    for path in sorted(folder.glob("*.json")):
        try:
            term = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(term, dict):
            registry[path.stem] = term
    return registry
