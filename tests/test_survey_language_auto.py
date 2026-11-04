"""Studio sends language 'auto' when no language is chosen; it must never reach the sidecar (issue 220)."""

import json

import pandas as pd

from src.converters.survey import convert_survey_file_to_prism_dataset
from tests.lsa_fixtures import make_library


def _convert(tmp_path, language):
    src = tmp_path / "s.csv"
    pd.DataFrame({"participant_id": ["001"], "MTESTSQ001": [1], "MTESTSQ002": [2], "MTESTSQ003": [3]}).to_csv(src, index=False)
    out = tmp_path / "out"
    convert_survey_file_to_prism_dataset(
        input_path=src, library_dir=make_library(tmp_path), output_root=out,
        survey="wellbeing", id_column="participant_id", separator=",", language=language,
    )
    return json.loads(next(out.glob("task-*_survey.json")).read_text())


def test_auto_keeps_the_templates_own_language(tmp_path):
    assert _convert(tmp_path, "auto")["Technical"]["Language"] == "en"


def test_an_explicit_language_is_still_written(tmp_path):
    assert _convert(tmp_path, "de")["Technical"]["Language"] == "de"
