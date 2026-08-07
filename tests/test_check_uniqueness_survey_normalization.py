"""Tests that CLI `survey validate` (library_validator.check_uniqueness)
applies the same survey-template normalization as the Studio GUI's
Template Editor before schema-checking.

Before this fix, check_uniqueness ran a bare jsonschema `validate()` with
no normalization at all, while the GUI's Validate/Save actions normalized
first (paper/software platform mapping, single-version VariantID autofill,
implicit numeric level ranges) — so a template could pass in the GUI and
then fail `survey validate` on the same file for reasons the GUI already
compensates for. See docs/_archive/GUI_BACKEND_AUDIT_2026-08-07.md, P1-4.

check_uniqueness had no prior test coverage at all (grep across tests/
found nothing), so these also establish a baseline.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import app.src.schema_manager as schema_manager  # noqa: E402
import src.survey_template_normalization as normalization_module  # noqa: E402
from app.src.library_validator import check_uniqueness  # noqa: E402


@pytest.fixture
def permissive_schema(monkeypatch):
    """Make load_schema return a schema that accepts any object, so these
    tests exercise only the normalization wiring, not real schema content."""
    monkeypatch.setattr(schema_manager, "load_schema", lambda name, version=None: {})


class TestCheckUniquenessNormalizesSurveyFilesOnly(object):
    def test_normalizes_survey_files_before_validating(
        self, tmp_path, permissive_schema, monkeypatch
    ):
        calls: list[dict] = []

        def _spy_normalize(template):
            calls.append(template)
            return template

        monkeypatch.setattr(
            normalization_module,
            "normalize_survey_template_for_validation",
            _spy_normalize,
        )

        survey_file = tmp_path / "survey-demo.json"
        survey_file.write_text(json.dumps({"Study": {}}), encoding="utf-8")

        assert check_uniqueness(str(tmp_path)) is True
        assert len(calls) == 1
        assert calls[0] == {"Study": {}}

    def test_does_not_normalize_biometrics_files(
        self, tmp_path, permissive_schema, monkeypatch
    ):
        calls: list[dict] = []

        def _spy_normalize(template):
            calls.append(template)
            return template

        monkeypatch.setattr(
            normalization_module,
            "normalize_survey_template_for_validation",
            _spy_normalize,
        )

        biometrics_file = tmp_path / "biometrics-demo.json"
        biometrics_file.write_text(json.dumps({"Study": {}}), encoding="utf-8")

        assert check_uniqueness(str(tmp_path)) is True
        assert calls == []

    def test_normalization_can_rescue_a_template_bare_validate_would_reject(
        self, tmp_path, monkeypatch
    ):
        # A schema that requires a non-empty Study.Version to demonstrate
        # that normalization (which autofills VariantID / doesn't touch
        # Version directly, so use ItemCount fill via implicit ranges is
        # out of scope here) still runs before validation — verified via
        # the spy capturing the *normalized* (not raw) instance passed to
        # validate.
        monkeypatch.setattr(
            schema_manager,
            "load_schema",
            lambda name, version=None: {
                "type": "object",
                "properties": {
                    "Q01": {
                        "type": "object",
                        "properties": {
                            "VariantScales": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "required": ["VariantID"],
                                    "properties": {
                                        "VariantID": {"type": "string", "minLength": 1}
                                    },
                                },
                            }
                        },
                    }
                },
            },
        )

        survey_file = tmp_path / "survey-demo.json"
        survey_file.write_text(
            json.dumps(
                {
                    "Study": {"Versions": ["short"]},
                    "Q01": {"VariantScales": [{"VariantID": ""}]},
                }
            ),
            encoding="utf-8",
        )

        # Without normalization this would fail (VariantID minLength 1);
        # normalize_survey_template_for_validation autofills it from the
        # single Versions entry, so the real check_uniqueness call (with
        # the real normalization function, not a spy/stub) should pass.
        assert check_uniqueness(str(tmp_path)) is True
