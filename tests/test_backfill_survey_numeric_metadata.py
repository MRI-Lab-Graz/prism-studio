from pathlib import Path

from app.src.maintenance.backfill_survey_numeric_metadata import (
    backfill_survey_data,
    backfill_survey_file,
)


def test_backfill_sets_integer_and_bounds_for_contiguous_levels() -> None:
    payload = {
        "Study": {"TaskName": "demo"},
        "Q01": {
            "Levels": {
                "0": {"en": "Never"},
                "1": {"en": "Sometimes"},
                "2": {"en": "Often"},
            }
        },
    }

    changes = backfill_survey_data(payload)

    assert len(changes) == 1
    assert payload["Q01"]["DataType"] == "integer"
    assert payload["Q01"]["MinValue"] == 0
    assert payload["Q01"]["MaxValue"] == 2
    assert payload["Q01"].get("ScaleType") is None


def test_backfill_can_optionally_set_likert_scale_type() -> None:
    payload = {
        "Study": {"TaskName": "demo"},
        "Q01": {
            "Levels": {
                "1": {"en": "Strongly disagree"},
                "2": {"en": "Disagree"},
                "3": {"en": "Neutral"},
                "4": {"en": "Agree"},
                "5": {"en": "Strongly agree"},
            }
        },
    }

    changes = backfill_survey_data(payload, apply_scale_type=True)

    assert len(changes) == 1
    assert payload["Q01"]["ScaleType"] == "likert"


def test_backfill_can_apply_frequency_scale_heuristic() -> None:
    payload = {
        "Study": {"TaskName": "demo"},
        "Q01": {
            "Levels": {
                "0": {"en": "{score=0} never"},
                "1": {"en": "{score=1} 1 time"},
                "2": {"en": "{score=2} 2 times"},
                "3": {"en": "{score=3} 3 times or more"},
            }
        },
    }

    changes = backfill_survey_data(
        payload,
        apply_scale_type_heuristic=True,
        strip_level_score_annotations=True,
    )

    assert len(changes) == 1
    assert payload["Q01"]["ScaleType"] == "frequency"
    assert payload["Q01"]["Levels"]["2"]["en"] == "2 times"


def test_backfill_can_apply_binary_scale_heuristic() -> None:
    payload = {
        "Study": {"TaskName": "demo"},
        "Q01": {
            "Levels": {
                "0": {"en": "False"},
                "1": {"en": "True"},
            }
        },
    }

    changes = backfill_survey_data(payload, apply_scale_type_heuristic=True)

    assert len(changes) == 1
    assert payload["Q01"]["ScaleType"] == "binary"


def test_backfill_can_apply_vas_scale_heuristic() -> None:
    payload = {
        "Study": {"TaskName": "demo"},
        "Q01": {
            "DataType": "integer",
            "MinValue": 0,
            "MaxValue": 100,
            "Unit": "points",
            "Levels": {
                "0": {"en": "Not at all"},
                "100": {"en": "Completely"},
            },
        },
    }

    changes = backfill_survey_data(payload, apply_scale_type_heuristic=True)

    assert len(changes) == 1
    assert payload["Q01"]["ScaleType"] == "vas"


def test_backfill_can_apply_likert_scale_heuristic() -> None:
    payload = {
        "Study": {"TaskName": "demo"},
        "Q01": {
            "Levels": {
                "1": {"en": "Strongly disagree"},
                "2": {"en": "Disagree"},
                "3": {"en": "Neutral"},
                "4": {"en": "Agree"},
                "5": {"en": "Strongly agree"},
            }
        },
    }

    changes = backfill_survey_data(payload, apply_scale_type_heuristic=True)

    assert len(changes) == 1
    assert payload["Q01"]["ScaleType"] == "likert"


def test_backfill_updates_variant_scales() -> None:
    payload = {
        "Study": {"TaskName": "demo"},
        "Q01": {
            "VariantScales": [
                {
                    "VariantID": "short",
                    "Levels": {
                        "1": {"en": "Low"},
                        "2": {"en": "Medium"},
                        "3": {"en": "High"},
                    },
                }
            ]
        },
    }

    changes = backfill_survey_data(payload)

    assert len(changes) == 1
    entry = payload["Q01"]["VariantScales"][0]
    assert entry["DataType"] == "integer"
    assert entry["MinValue"] == 1
    assert entry["MaxValue"] == 3


def test_backfill_file_writes_sanitized_levels(tmp_path: Path) -> None:
    path = tmp_path / "survey-demo.json"
    path.write_text(
        '{\n  "Study": {"TaskName": "demo"},\n  "Q01": {\n    "Levels": {\n      "0": {"en": "{score=0} Never"},\n      "1": {"en": "{score=1} Often"}\n    }\n  }\n}\n',
        encoding="utf-8",
    )

    report = backfill_survey_file(path, strip_level_score_annotations=True)
    rendered = path.read_text(encoding="utf-8")

    assert report.changed is True
    assert "{score=" not in rendered
    assert '"0": {"en": "Never"}' in rendered


def test_backfill_file_writes_updated_json(tmp_path: Path) -> None:
    path = tmp_path / "survey-demo.json"
    path.write_text(
        '{\n  "Study": {"TaskName": "demo"},\n  "Q01": {\n    "Levels": {\n      "0": {"en": "Never"},\n      "1": {"en": "Often"}\n    }\n  }\n}\n',
        encoding="utf-8",
    )

    report = backfill_survey_file(path)
    rendered = path.read_text(encoding="utf-8")

    assert report.changed is True
    assert '"DataType": "integer"' in rendered
    assert '"MinValue": 0' in rendered
    assert '"MaxValue": 1' in rendered
