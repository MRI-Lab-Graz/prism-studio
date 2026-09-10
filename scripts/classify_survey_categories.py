"""One-off: write Study.Category into every official/library/survey/survey-*.json.

Mapping is the explicit ShortName -> Category dict from
docs/superpowers/specs/2026-09-09-survey-instrument-categorization-design.md
("Full instrument -> category mapping"), not inferred at run-time. Run once;
re-running is a no-op once every file already carries its Category.
"""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = REPO_ROOT / "official" / "library" / "survey"

CATEGORY_SHORT_NAMES = {
    "Personality & Individual Differences": [
        "AISS",
        "BFI-S",
        "BHPS",
        "BIS",
        "BSRI",
        "CCM-S",
        "Grit-S",
        "HSQ",
        "ISC",
        "SAPS",
        "SHYNESS",
        "TIPI",
        "TYPE-D",
        "ZKPQ",
    ],
    "Mood, Anxiety & Clinical Screening": [
        "AAI",
        "BITe",
        "CIA",
        "CUDOS",
        "DASS",
        "DASS-21",
        "ERQ",
        "GAD-7",
        "GPTS",
        "GTPS",
        "O-LIFE",
        "OCI-R",
        "PHQ-9",
        "PIOS",
        "PSS",
        "RRS",
        "SPQ",
    ],
    "Well-being & Life Satisfaction": [
        "BRCS",
        "BRS",
        "FS",
        "GQ-6",
        "LOT-R",
        "MHC-SF",
        "OHQ",
        "PTS",
        "SPANE",
        "SWLS",
        "WB-MULTI",
        "WB",
        "WHO-5",
    ],
    "Social, Relationships & Attachment": [
        "ARD",
        "BSAS",
        "CCSS",
        "LAS",
        "LONELINESS-3",
        "PN-SMD",
        "SAAM",
        "SF-MJS",
        "SWLLS",
        "TRUST",
        "UPLAS",
    ],
    "Addictive & Problematic Behaviors": [
        "BFAS",
        "CUDQ",
        "DMQ-R",
        "GAS",
        "NMP-Q",
        "PIU",
        "PIUQ",
        "SMD",
        "SOS",
    ],
    "Self-Concept & Self-Esteem": [
        "BES",
        "GSE",
        "HS",
        "ROSENBERG",
        "SCSR",
        "SOC-3",
        "SSES",
    ],
    "Aggression, Antisocial & Dark Traits": [
        "AGG-A",
        "BPAQ",
        "CABS",
        "HSNS",
        "LiES",
        "LSRP",
        "SD3",
        "VAST",
    ],
    "Cognitive & Executive Function": [
        "CFS",
        "EI",
        "NCS-6",
        "REI",
        "TSIS",
        "webexec",
    ],
    "Autism & Neurodevelopmental": ["AQ10"],
    "Sleep, Health & Physical": ["CIRENS", "EHI", "GSQS", "HSC-7", "SQS"],
    "Beliefs, Values & Worldview": [
        "CNS",
        "CSJAS",
        "GAENE",
        "MASLOW",
        "MATE",
        "SBS-10",
        "SKEP",
    ],
    "Educational & Occupational": [
        "AMAS",
        "BES-ALT",
        "BURNOUT",
        "GP",
        "MASI",
        "PCI",
        "TAI-5",
    ],
}


def _normalize(short_name: str) -> str:
    return short_name.upper().replace("-", "").replace(" ", "")


SHORT_NAME_TO_CATEGORY = {
    _normalize(short_name): category
    for category, short_names in CATEGORY_SHORT_NAMES.items()
    for short_name in short_names
}


def classify_library(library_dir: Path) -> list[str]:
    """Write Study.Category into every survey-*.json; return files with no mapping."""
    unmapped = []
    for path in sorted(library_dir.glob("survey-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        study = data.get("Study")
        if not isinstance(study, dict):
            continue

        short_name = study.get("ShortName", "")
        category = SHORT_NAME_TO_CATEGORY.get(_normalize(short_name))
        if category is None:
            unmapped.append(path.name)
            continue

        reordered = {}
        for key, value in study.items():
            reordered[key] = value
            if key == "ShortName":
                reordered["Category"] = category
        if "Category" not in reordered:
            reordered["Category"] = category
        data["Study"] = reordered

        path.write_text(
            json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    return unmapped


if __name__ == "__main__":
    unmapped_files = classify_library(LIBRARY_DIR)
    if unmapped_files:
        raise SystemExit(f"No category mapping for: {unmapped_files}")
    print(f"Classified {len(list(LIBRARY_DIR.glob('survey-*.json')))} templates.")
