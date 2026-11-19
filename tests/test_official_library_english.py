"""Descriptive metadata of every official non-survey template is English; only OriginalName, ShortName and Instructions may carry other languages.

Same rule as the survey header (check_library in prism-specification) and the editor (StudioTheme.offersMultilingual).
"""

import json
from pathlib import Path

import pytest

LIB = Path(__file__).resolve().parent.parent / "official" / "library"
HEADER = {
    "Study": ("Description", "Reliability", "Validity", "Citation", "TargetPopulation", "ExclusionCriteria",
              "WarmupProtocol", "EstimatedDuration"),
    "Technical": ("Equipment",),
    "Scoring": ("ScoringMethod", "CutoffsSource", "NormsSource"),
    "Normative": ("ReferencePopulation", "ReferenceSource"),
}
HEADER_SECTIONS = {"I18n", "Metadata", *HEADER}
FILES = sorted(p for m in ("biometrics", "biosample", "environment") for p in (LIB / m).glob("*.json"))


def _not_english(value):
    return isinstance(value, dict) and set(value) - {"en", "min", "max"}


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_descriptive_metadata_is_english_only(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    bad = [f"{s}.{f}" for s, fields in HEADER.items() for f in fields if _not_english((data.get(s) or {}).get(f))]
    bad += [f"{k}.Description" for k, v in data.items()
            if k not in HEADER_SECTIONS and isinstance(v, dict) and _not_english(v.get("Description"))]
    assert not bad, f"{path.name}: write these in English only: {bad}"
