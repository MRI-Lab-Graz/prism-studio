"""The project page opens on one score row (Required / Core / FAIR) with every section unfolded; the old overview is gone."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STUDY = (ROOT / "app/templates/includes/projects/study_metadata.html").read_text(encoding="utf-8")
META_JS = (ROOT / "app/static/js/modules/projects/metadata.js").read_text(encoding="utf-8")


def _function_body(name):
    start = META_JS.index(f"function {name}(")
    return META_JS[start:META_JS.index("\n}\n", start)]


def test_template_has_the_score_row_and_no_overview():
    assert 'id="smScoreRow"' in STUDY
    for gone in ("smFairRing", "smFairMotivation", "smFairNextAction", "smMainProgressBar", "Methods Readiness"):
        assert gone not in STUDY


def test_overview_code_is_gone_from_the_script():
    for gone in ("section-completeness-row", "smFairNextAction", "smMainProgressBar", "_updateFairNextActionHint"):
        assert gone not in META_JS


def test_score_row_is_drawn_with_the_shared_tally():
    assert re.search(r"getElementById\('smScoreRow'\)", _function_body("updateCompletenessUI"))
    assert "StudioTheme.tally" in _function_body("updateCompletenessUI")


def test_loading_a_project_unfolds_the_groups_but_no_section():
    body = _function_body("showStudyMetadataCard")
    assert "...SECTION_GROUP_BODY_IDS" in body and "SECTION_COLLAPSE_IDS" not in META_JS
    groups = set(re.findall(r"'(\w+)'", re.search(r"SECTION_GROUP_BODY_IDS = \[(.*?)\];", META_JS, re.S).group(1)))
    assert groups == set(re.findall(r'<div class="collapse" id="(sm\w+GroupBody)"', STUDY))


def test_no_section_starts_open():
    assert not re.search(r'class="collapse[^"]*\bshow\b[^"]*" id="sm', STUDY)
    assert not re.search(r'data-bs-target="#sm(Basics|Overview)" aria-expanded="true"', STUDY)
