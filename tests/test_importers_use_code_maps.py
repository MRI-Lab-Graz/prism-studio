"""Every importer that takes participant IDs from data uses the project's code maps, or is a listed gap."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_MAPS = re.compile(r"load_code_maps|_apply_participant_ids")

USES_CODE_MAPS = ["app/src/converters/survey.py"]

KNOWN_GAPS = {  # the feature is complete when this is empty (second plan)
    "src/batch_convert.py": "batch file import takes sub- from the file name or its own column",
    "src/converters/biometrics.py": "biometrics import takes the participant column as it is",
    "src/environment_conversion.py": "environment import takes the participant column as it is",
    "src/project_registration.py": "registers files under the IDs it is given",
    "src/biosample_import.py": "biosample import takes the participant column as it is",
    "src/participants_backend.py": "participants import takes the ID column as it is",
}


def test_importers_marked_as_using_code_maps_do():
    for rel in USES_CODE_MAPS:
        assert CODE_MAPS.search((ROOT / rel).read_text(encoding="utf-8")), rel


def test_gaps_are_real_files_that_do_not_use_them_yet():
    for rel in KNOWN_GAPS:
        assert not CODE_MAPS.search((ROOT / rel).read_text(encoding="utf-8")), f"{rel}: move it to USES_CODE_MAPS"
