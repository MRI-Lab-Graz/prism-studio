"""Regenerate official/library/survey/index.json from the instrument templates.

Run after adding/editing any survey-*.json instrument template so the
registry index (Phase 4 - roadmap) stays in sync:

    python scripts/generate_instrument_registry.py
"""

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from pathlib import Path  # noqa: E402

from src.instrument_registry import write_registry_index  # noqa: E402

SURVEY_DIR = Path(REPO_ROOT) / "official" / "library" / "survey"
INDEX_PATH = SURVEY_DIR / "index.json"


def main() -> None:
    index = write_registry_index(SURVEY_DIR, INDEX_PATH)
    count = len(index["Instruments"])
    print(f"Wrote {INDEX_PATH} ({count} instruments)")


if __name__ == "__main__":
    main()
