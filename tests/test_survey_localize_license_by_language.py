"""Study.LicenseByLanguage is keyed by language but is data, not a translation: localizing keeps it."""

import json
from pathlib import Path

from jsonschema import Draft7Validator

from src.survey_localize import _localize_survey_template

ROOT = Path(__file__).resolve().parents[1]


def test_license_by_language_keeps_its_language_keys():
    template = {
        "Study": {
            "License": "public domain",
            "LicenseByLanguage": {"de": {"License": {"en": "CC", "de": "CC (de)"}, "LicenseID": "Proprietary"}},
        }
    }

    study = _localize_survey_template(template, "de")["Study"]

    assert study["LicenseByLanguage"] == {"de": {"License": "CC (de)", "LicenseID": "Proprietary"}}


def test_localized_dass21_study_license_data_stays_schema_valid():
    template = json.loads((ROOT / "official/library/survey/survey-dass21.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "app/schemas/stable/survey.schema.json").read_text(encoding="utf-8"))
    rule = schema["properties"]["Study"]["properties"]["LicenseByLanguage"]

    for lang in ("de", "en"):
        localized = _localize_survey_template(template, lang)["Study"]["LicenseByLanguage"]
        assert list(localized) == ["de"]
        # the localized sidecar holds one string per field, so License.en is no longer an object
        assert not [e.message for e in Draft7Validator(schema).evolve(schema=rule).iter_errors(localized)]
