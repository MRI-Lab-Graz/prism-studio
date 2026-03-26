"""Tests for app/src/survey_version_plan.py"""

import json
import sys
from pathlib import Path

import pytest

# Make sure app/src is importable
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.survey_version_plan import (
    discover_survey_variants,
    enrich_and_save_survey_plan,
    load_survey_plan,
    resolve_version,
    resolve_version_for_file,
    save_survey_plan,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_dir(tmp_path):
    """A minimal project directory with an empty project.json."""
    pj = tmp_path / "project.json"
    pj.write_text(json.dumps({}), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def project_with_mapping(tmp_path):
    """Project with a pre-existing survey_version_mapping."""
    mapping = {
        "wellbeing-multi": {
            "default_version": "10-likert",
            "by_session": {"ses-01": "7-likert"},
            "by_run": {"run-02": "10-vas"},
            "by_session_run": {"ses-02": {"run-01": "10-vas"}},
        }
    }
    pj = tmp_path / "project.json"
    pj.write_text(json.dumps({"survey_version_mapping": mapping}), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def library_dir(tmp_path):
    """A fake official library directory with one multi-variant survey."""
    survey_dir = tmp_path / "library" / "survey"
    survey_dir.mkdir(parents=True)

    multi = {
        "Study": {
            "TaskName": "wellbeing-multi",
            "Version": "10-likert",
            "Versions": ["10-likert", "7-likert", "10-vas"],
            "VariantDefinitions": [],
        }
    }
    (survey_dir / "survey-wellbeing-multi.json").write_text(
        json.dumps(multi), encoding="utf-8"
    )

    single = {
        "Study": {
            "TaskName": "demographics",
            "Version": "1.0",
        }
    }
    (survey_dir / "survey-demographics.json").write_text(
        json.dumps(single), encoding="utf-8"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# discover_survey_variants
# ---------------------------------------------------------------------------


class TestDiscoverSurveyVariants:
    def test_returns_empty_when_no_survey_dir(self, tmp_path):
        result = discover_survey_variants(tmp_path)
        assert result == {}

    def test_discovers_multi_variant_survey(self, library_dir):
        result = discover_survey_variants(library_dir / "library")
        assert "wellbeing-multi" in result
        info = result["wellbeing-multi"]
        assert info["versions"] == ["10-likert", "7-likert", "10-vas"]
        assert info["default_version"] == "10-likert"

    def test_discovers_single_variant_survey(self, library_dir):
        result = discover_survey_variants(library_dir / "library")
        assert "demographics" in result
        info = result["demographics"]
        assert info["versions"] == ["1.0"]
        assert info["default_version"] == "1.0"

    def test_synthesises_default_version_when_missing(self, tmp_path):
        survey_dir = tmp_path / "library" / "survey"
        survey_dir.mkdir(parents=True)
        data = {"Study": {"TaskName": "no-version"}}
        (survey_dir / "survey-no-version.json").write_text(json.dumps(data))
        result = discover_survey_variants(tmp_path / "library")
        assert result["no-version"]["versions"] == ["default"]
        assert result["no-version"]["default_version"] == "default"


# ---------------------------------------------------------------------------
# load_survey_plan / save_survey_plan
# ---------------------------------------------------------------------------


class TestLoadSavePlan:
    def test_load_empty_project_returns_empty_mapping(self, project_dir):
        plan = load_survey_plan(project_dir)
        assert plan["survey_version_mapping"] == {}
        assert plan["survey_plan_settings"]["auto_discover"] is True

    def test_save_and_reload(self, project_dir):
        mapping = {
            "my-task": {
                "default_version": "v1",
                "by_session": {},
                "by_run": {},
                "by_session_run": {},
            }
        }
        save_survey_plan(project_dir, mapping)
        plan = load_survey_plan(project_dir)
        assert plan["survey_version_mapping"]["my-task"]["default_version"] == "v1"

    def test_legacy_version_key_normalised_on_load(self, tmp_path):
        """Old project.json with 'version' key should be normalised to 'default_version'."""
        pj = tmp_path / "project.json"
        pj.write_text(
            json.dumps(
                {"survey_version_mapping": {"old-task": {"version": "v-legacy"}}}
            ),
            encoding="utf-8",
        )

        plan = load_survey_plan(tmp_path)
        entry = plan["survey_version_mapping"]["old-task"]
        assert "default_version" in entry
        assert entry["default_version"] == "v-legacy"
        assert "version" not in entry

    def test_save_sets_default_settings_if_absent(self, project_dir):
        save_survey_plan(project_dir, {})
        pj = json.loads((project_dir / "project.json").read_text())
        assert "survey_plan_settings" in pj
        assert pj["survey_plan_settings"]["auto_discover"] is True


# ---------------------------------------------------------------------------
# enrich_and_save_survey_plan
# ---------------------------------------------------------------------------


class TestEnrichAndSave:
    def test_adds_new_surveys_from_library(self, project_dir, library_dir):
        result = enrich_and_save_survey_plan(project_dir, library_dir / "library")
        mapping = result["survey_version_mapping"]
        assert "wellbeing-multi" in mapping
        assert "demographics" in mapping
        assert sorted(result["added"]) == ["demographics", "wellbeing-multi"]

    def test_does_not_overwrite_existing_entries(
        self, project_with_mapping, library_dir
    ):
        result = enrich_and_save_survey_plan(
            project_with_mapping, library_dir / "library"
        )
        mapping = result["survey_version_mapping"]
        # The pre-existing entry must be unchanged
        entry = mapping["wellbeing-multi"]
        assert entry["by_session"]["ses-01"] == "7-likert"
        # Only newly discovered surveys appear in `added`
        assert "wellbeing-multi" not in result["added"]

    def test_migrates_missing_sub_keys_for_existing_entries(
        self, tmp_path, library_dir
    ):
        """Existing entries without by_session/by_run/by_session_run get those keys."""
        pj = tmp_path / "project.json"
        pj.write_text(
            json.dumps(
                {
                    "survey_version_mapping": {
                        "wellbeing-multi": {"default_version": "10-likert"}
                    }
                }
            )
        )
        enrich_and_save_survey_plan(tmp_path, library_dir / "library")
        plan = load_survey_plan(tmp_path)
        entry = plan["survey_version_mapping"]["wellbeing-multi"]
        assert entry["by_session"] == {}
        assert entry["by_run"] == {}
        assert entry["by_session_run"] == {}


# ---------------------------------------------------------------------------
# resolve_version
# ---------------------------------------------------------------------------

FULL_ENTRY = {
    "default_version": "10-likert",
    "by_session": {"ses-01": "7-likert"},
    "by_run": {"run-02": "10-vas"},
    "by_session_run": {"ses-02": {"run-01": "10-vas"}},
}


class TestResolveVersion:
    def test_session_run_beats_session(self):
        v = resolve_version(FULL_ENTRY, session="ses-02", run="run-01")
        assert v == "10-vas"

    def test_session_beats_run(self):
        # ses-01 is in by_session; run-02 is in by_run — session wins
        entry = dict(FULL_ENTRY)
        entry["by_run"] = {"run-01": "10-vas"}
        v = resolve_version(entry, session="ses-01", run="run-01")
        assert v == "7-likert"

    def test_session_only(self):
        v = resolve_version(FULL_ENTRY, session="ses-01")
        assert v == "7-likert"

    def test_run_only(self):
        v = resolve_version(FULL_ENTRY, run="run-02")
        assert v == "10-vas"

    def test_default_fallback(self):
        v = resolve_version(FULL_ENTRY, session="ses-99", run="run-99")
        assert v == "10-likert"

    def test_no_arguments_returns_default(self):
        v = resolve_version(FULL_ENTRY)
        assert v == "10-likert"

    def test_no_entry_returns_none(self):
        assert resolve_version(None) is None  # type: ignore[arg-type]
        assert resolve_version({}) is None

    def test_legacy_version_key_resolved(self):
        entry = {"version": "v-legacy"}
        assert resolve_version(entry) == "v-legacy"


# ---------------------------------------------------------------------------
# resolve_version_for_file
# ---------------------------------------------------------------------------


class TestResolveVersionForFile:
    def test_resolves_known_task(self, project_with_mapping):
        v = resolve_version_for_file(
            project_with_mapping, "wellbeing-multi", session="ses-01"
        )
        assert v == "7-likert"

    def test_returns_none_for_unknown_task(self, project_with_mapping):
        v = resolve_version_for_file(project_with_mapping, "nonexistent-task")
        assert v is None

    def test_default_fallback_via_file(self, project_with_mapping):
        v = resolve_version_for_file(project_with_mapping, "wellbeing-multi")
        assert v == "10-likert"
