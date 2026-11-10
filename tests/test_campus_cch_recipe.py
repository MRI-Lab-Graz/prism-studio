"""The campus course's CCH recipe scores the course's test data: P001 answered 2,3,3,3,2,1,1,1 | 2,1,3,1."""
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

from tests.template_fixtures import complete

ROOT = Path(__file__).resolve().parent.parent
CAMPUS = ROOT / "examples" / "campus_course"
FREQ = ["never", "rarely", "sometimes", "often", "always"]
AGREE = ["strongly disagree", "disagree", "neutral", "agree", "strongly agree"]


def _scale(words):
    return {
        "Levels": {str(i): {"en": w} for i, w in enumerate(words, 1)}, "Unit": "ordinal", "DataType": "integer",
        "MinValue": 1.0, "MaxValue": 5.0, "AllowedValues": [1, 2, 3, 4, 5],
    }


def _cch_template():
    items = {f"cch{i:02d}": {"Description": {"en": f"item {i}"}, **_scale(FREQ if i <= 8 else AGREE)} for i in range(1, 13)}
    items["cch13"] = {"Description": {"en": "cups"}, "Unit": "count", "DataType": "integer", "MinValue": 0.0, "MaxValue": 15.0}
    items["cch14"] = {"Description": {"en": "decaf"}, "Unit": "ordinal", "DataType": "integer", "MinValue": 0.0, "MaxValue": 1.0,
                      "Levels": {"0": {"en": "no"}, "1": {"en": "yes"}}, "AllowedValues": [0, 1]}
    return complete({"Study": {"TaskName": "cch", "OriginalName": {"en": "Campus Coffee Habits"}}, **items}, "cch")


def _run(*args):
    result = subprocess.run([sys.executable, str(ROOT / "app" / "prism_tools.py"), *args], capture_output=True, text=True,
                            encoding="utf-8", cwd=str(ROOT), timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr


def test_recipe_scores_the_campus_data(tmp_path):
    library = tmp_path / "lib"
    library.mkdir()
    (library / "survey-cch.json").write_text(json.dumps(_cch_template()), encoding="utf-8")
    dataset = tmp_path / "ds"
    _run("survey", "convert", "--input", str(CAMPUS / "raw_data" / "cch_responses.xlsx"), "--library", str(library),
         "--output", str(dataset), "--id-column", "participant_id", "--session-column", "session", "--session", "baseline")
    recipes = dataset / "code" / "recipes" / "survey"
    recipes.mkdir(parents=True)
    shutil.copy(CAMPUS / "recipe-cch.json", recipes)

    _run("recipes", "surveys", "--prism", str(dataset), "--format", "csv")

    out = next(dataset.glob("derivatives/survey/*/prism_survey_dataset_cch.csv"))
    rows = {r["participant_id"]: r for r in csv.DictReader(out.open(encoding="utf-8"))}
    assert len(rows) == 320
    assert {k: rows["sub-P001"][k] for k in ("Habit", "Attitude", "Total")} == {"Habit": "16", "Attitude": "7", "Total": "23"}
