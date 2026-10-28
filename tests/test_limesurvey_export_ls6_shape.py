"""The exported .lss has the shape of a LimeSurvey 6 export: DBVersion 636 and the structural
columns LimeSurvey 6 writes for questions, sub-questions and question texts. Checked by
importing the same survey into LimeSurvey 6 as 415 and as 636 (identical summaries: 1 survey,
2 languages, 2 groups, 10 questions, 8 attributes, 14 answers, 12 sub-questions)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

import defusedxml.ElementTree as DET  # noqa: E402

LIBRARY = Path(__file__).resolve().parent.parent / "official" / "library" / "survey"

# Values LimeSurvey 6 itself writes for these columns
QUESTION_COLUMNS = {"same_script": "0"}
SUBQUESTION_COLUMNS = {"other": "N", "mandatory": "N", "encrypted": "N", "same_script": "0"}
QUESTION_TEXT_COLUMNS = {"script": ""}


def _export(kind, tmp_path):
    from src.limesurvey_exporter import generate_lss, generate_lss_from_customization
    from src.survey_customizer import build_customizer_groups

    path = tmp_path / "survey-mood.json"
    path.write_text(json.dumps({
        "Study": {"OriginalName": "Mood"},
        "a": {"Description": "A", "Levels": {"1": "no", "2": "yes"}},
        "b": {"Description": "B", "Levels": {"1": "no", "2": "yes"}},
        "c": {"Description": "C", "InputType": "text"},
    }), encoding="utf-8")
    files = [str(path), str(LIBRARY / "survey-phq9.json")]
    if kind == "quick":
        xml = generate_lss(files, matrix_mode=True)
    else:
        xml = generate_lss_from_customization(build_customizer_groups([{"path": f} for f in files], "en"), matrix_mode=True)
    return DET.fromstring(xml)


@pytest.mark.parametrize("kind", ["quick", "customizer"])
def test_dbversion_is_the_limesurvey_6_one(kind, tmp_path):
    assert _export(kind, tmp_path).findtext("DBVersion") == "636"


@pytest.mark.parametrize("kind", ["quick", "customizer"])
@pytest.mark.parametrize(
    "section, columns",
    [("questions", QUESTION_COLUMNS), ("subquestions", SUBQUESTION_COLUMNS), ("question_l10ns", QUESTION_TEXT_COLUMNS)],
)
def test_every_row_has_the_structural_columns(kind, section, columns, tmp_path):
    rows = _export(kind, tmp_path).findall(f"{section}/rows/row")
    assert rows, section
    for row in rows:
        assert {name: row.findtext(name) for name in columns} == {n: v or "" for n, v in columns.items()}, section


def test_existing_values_are_not_overwritten(tmp_path):
    """The hidden PRISMMETA question already has its own values; the shared columns only fill gaps."""
    root = _export("quick", tmp_path)
    meta = [q for q in root.findall("questions/rows/row") if q.findtext("title").startswith("PRISMMETA")]
    assert meta and all(q.findtext("mandatory") == "N" and q.findtext("relevance") == "0" for q in meta)
    assert all(len(q.findall("same_script")) == 1 for q in meta)
