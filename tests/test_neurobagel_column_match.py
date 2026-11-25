"""A column gets a standard label only when its name is that variable's name or alias, not merely contains it."""

import pandas as pd
import pytest

from src.participant_columns import _generate_neurobagel_schema


def _field(column):
    df = pd.DataFrame({"participant_id": ["sub-01", "sub-02"], column: ["de", "en"]})
    return _generate_neurobagel_schema(df, "participant_id")[column]


@pytest.mark.parametrize("column", ["native_language", "language", "age_at_onset", "subgroup", "hand_grip", "sussex_site", "race", "education_years"])
def test_a_name_that_only_contains_a_variable_name_is_not_that_variable(column):
    field = _field(column)
    assert field["Description"] == f"{column} (auto-detected)"
    assert field["Annotations"]["VariableType"] == "Categorical"


@pytest.mark.parametrize("column, label", [
    ("Age", "Age"), ("Alter", "Age"), ("Geschlecht", "Sex"), ("biological_sex", "Sex"),
    ("education_level", "Education Level"), ("Händigkeit", "Handedness"), ("subject", "Subject ID"),
    ("Age_years", "Age"), ("age (years)", "Age"), ("Alter_Jahre", "Age"), ("subject_id", "Subject ID"),
    ("dominant_hand", "Handedness"),
])
def test_names_and_aliases_still_match(column, label):
    assert _field(column)["Description"] == label
