"""NeuroBagel annotations must be user-approved, never auto-applied."""

import pandas as pd

from src.participant_columns import _generate_neurobagel_schema


def test_default_schema_has_no_neurobagel_annotations():
    df = pd.DataFrame(
        {
            "participant_id": ["sub-01", "sub-02", "sub-03"],
            "age": [28, 34, 22],
            "sex": [1, 2, 4],
            "handedness": [1, 1, 2],
        }
    )

    schema = _generate_neurobagel_schema(df, "participant_id")

    for col, field in schema.items():
        annotations = field.get("Annotations", {})
        assert "IsAbout" not in annotations, col
        assert "Levels" not in annotations, col
        assert "Format" not in annotations, col
        assert "Unit" not in field, col

    # Raw codes are kept as-is, never relabelled (e.g. 1 -> Male).
    assert schema["sex"]["Levels"] == {"1": "1", "2": "2", "4": "4"}
