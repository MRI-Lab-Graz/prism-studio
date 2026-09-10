import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIBRARY_DIR = REPO_ROOT / "official" / "library" / "survey"
SCHEMA_PATH = REPO_ROOT / "app" / "schemas" / "stable" / "survey.schema.json"


def _category_enum():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return set(schema["properties"]["Study"]["properties"]["Category"]["enum"])


def test_every_official_survey_template_has_a_valid_category():
    allowed = _category_enum()
    files = sorted(LIBRARY_DIR.glob("survey-*.json"))
    assert files, "expected official survey templates to exist"

    missing_or_invalid = []
    for path in files:
        study = json.loads(path.read_text(encoding="utf-8")).get("Study", {})
        category = study.get("Category")
        if category not in allowed:
            missing_or_invalid.append((path.name, category))

    assert not missing_or_invalid, (
        f"{len(missing_or_invalid)} official survey template(s) missing a valid "
        f"Study.Category: {missing_or_invalid}"
    )
