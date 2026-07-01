"""Tests for the Excel/CSV/TSV codebook importer used by the Template Editor.

This wraps excel_to_survey.extract_excel_templates (check_collisions=False),
so these tests cover the parts specific to this module: the plain-Description
auto-language-labeling preprocessing, and the group-summary helper. Full
multi-sheet (Items/General/Variants) parsing correctness is already covered
by test_excel_to_survey_multisheet.py.
"""

import io

import pandas as pd

from app.src.converters.excel_template_import import parse_excel_groups, summarize_groups


def _write_xlsx(rows):
    """rows[0] is the header row; all rows are written verbatim (no extra pandas header)."""
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, header=False)
    return buf.getvalue()


def test_parse_excel_groups_supports_explicit_language_columns():
    header = ["Variable name", "Description_de", "Description_en", "Scaling"]
    rows = [
        header,
        ["gender", "Geschlecht", "Gender", "1=weiblich;2=maennlich"],
        ["age", "Alter in Jahren", "Age in years", "None"],
    ]
    file_bytes = _write_xlsx(rows)

    groups = parse_excel_groups(file_bytes, "codebook.xlsx")

    assert set(groups.keys()) == {"gender", "age"}
    gender_item = groups["gender"]["gender"]
    assert gender_item["Description"] == {"de": "Geschlecht", "en": "Gender"}
    assert gender_item["Levels"] == {"1": "weiblich", "2": "maennlich"}
    assert "Levels" not in groups["age"]["age"]


def test_parse_excel_groups_auto_labels_plain_description_column_by_language():
    header = ["Variable name", "Description", "Scaling"]
    rows = [
        header,
        ["gender", "Bitte geben Sie an: männlich oder weiblich", "1=weiblich,2=maennlich"],
        ["job", "Derzeit ausgeuebter Beruf", "None"],
    ]
    file_bytes = _write_xlsx(rows)

    groups = parse_excel_groups(file_bytes, "codebook.xlsx")

    assert groups["gender"]["gender"]["Description"] == {
        "de": "Bitte geben Sie an: männlich oder weiblich"
    }


def test_parse_excel_groups_keeps_fully_bracketed_description_intact():
    header = ["Variable name", "Description_de", "Scaling"]
    rows = [
        header,
        [
            "BIG5_E1",
            "[Ich bin eher zurueckhaltend, reserviert]",
            "1=trifft nicht zu;2=trifft zu",
        ],
    ]
    file_bytes = _write_xlsx(rows)

    groups = parse_excel_groups(file_bytes, "codebook.xlsx")

    assert groups["big"]["BIG5_E1"]["Description"]["de"] == (
        "[Ich bin eher zurueckhaltend, reserviert]"
    )


def test_parse_excel_groups_falls_back_to_variable_prefix_without_group_column():
    header = ["Variable name", "Description_en"]
    rows = [
        header,
        ["ADS1", "Item 1"],
        ["ADS2", "Item 2"],
        ["BDI_1", "Item A"],
    ]
    file_bytes = _write_xlsx(rows)

    groups = parse_excel_groups(file_bytes, "codebook.xlsx")

    assert set(groups.keys()) == {"ads", "bdi"}


def test_parse_excel_groups_honors_explicit_group_column_over_prefix():
    header = ["Variable name", "Group", "Description_en"]
    rows = [
        header,
        ["test001", "test", "Item 1"],
        ["test002", "ads", "Item 2"],
    ]
    file_bytes = _write_xlsx(rows)

    groups = parse_excel_groups(file_bytes, "codebook.xlsx")

    assert set(groups.keys()) == {"test", "ads"}
    assert "test001" in groups["test"]
    assert "test002" in groups["ads"]


def test_parse_excel_groups_csv_input():
    csv_bytes = (
        "Variable name,Description_en,Scaling\n"
        "gender,Gender,\"1=female;2=male\"\n"
    ).encode("utf-8")

    groups = parse_excel_groups(csv_bytes, "codebook.csv")

    assert groups["gender"]["gender"]["Description"] == {"en": "Gender"}
    assert groups["gender"]["gender"]["Levels"] == {"1": "female", "2": "male"}


def test_summarize_groups_reports_counts_and_samples_excluding_reserved_keys():
    groups = {
        "big": {
            "Technical": {},
            "Study": {},
            "Metadata": {},
            "I18n": {},
            "BIG5_E1": {},
            "BIG5_E2": {},
        },
        "age": {"Technical": {}, "Study": {}, "Metadata": {}, "I18n": {}, "age": {}},
    }

    summary = summarize_groups(groups)

    assert summary == [
        {"prefix": "age", "item_count": 1, "sample_vars": ["age"]},
        {"prefix": "big", "item_count": 2, "sample_vars": ["BIG5_E1", "BIG5_E2"]},
    ]
