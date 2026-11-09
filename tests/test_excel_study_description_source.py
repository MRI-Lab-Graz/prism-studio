"""The study description comes from the General sheet, never from item rows."""

import pandas as pd

from app.src.converters.excel_to_survey import extract_excel_templates

ITEMS = [
    {"ItemID": "ADS01", "Description_de": "Ich fuehle mich traurig", "Description_en": "I feel sad",
     "Scale": "0=no;1=yes", "Group": "ads"},
    {"ItemID": "ADS02", "Description_de": "Ich kann mich nicht konzentrieren",
     "Description_en": "I cannot concentrate", "Scale": "0=no;1=yes", "Group": "ads"},
]


def _import(tmp_path, general):
    path = tmp_path / "s.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(ITEMS).to_excel(writer, index=False, sheet_name="Items")
        if general is not None:
            pd.DataFrame([general]).to_excel(writer, index=False, sheet_name="General")
    return extract_excel_templates(excel_file=path, check_collisions=False)["ads"]


def test_general_sheet_description_wins_over_first_item(tmp_path):
    sidecar = _import(tmp_path, {
        "OriginalName_en": "Depression Scale",
        "Description_en": "A depression screening scale.",
        "Description_de": "Ein Depressions-Screening.",
    })
    assert sidecar["Study"]["Description"]["en"] == "A depression screening scale."
    assert sidecar["Study"]["Description"]["de"] == "Ein Depressions-Screening."
    assert sidecar["ADS01"]["Description"]["en"] == "I feel sad"


def _de_only(tmp_path, general):
    items = [{"ItemID": "ADS01", "Description_de": "Ich fuehle mich traurig",
              "Scale": "0=nie;1=ja", "Group": "ads"}]
    path = tmp_path / "s.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame(items).to_excel(writer, index=False, sheet_name="Items")
        pd.DataFrame([general]).to_excel(writer, index=False, sheet_name="General")
    return extract_excel_templates(excel_file=path, check_collisions=False)["ads"]["Study"]


def test_plain_general_description_is_the_study_description(tmp_path):
    study = _de_only(tmp_path, {"OriginalName_de": "Skala", "Description": "Ein Screening."})
    assert study["Description"]["de"] == "Ein Screening."


def test_german_only_template_has_no_empty_english_header(tmp_path):
    study = _de_only(tmp_path, {"OriginalName_de": "Skala"})
    assert "en" not in study["Description"]


def test_item_text_never_becomes_study_description(tmp_path):
    sidecar = _import(tmp_path, {"OriginalName_en": "Depression Scale"})
    desc = sidecar["Study"]["Description"]
    assert "I feel sad" not in str(desc) and "Ich fuehle" not in str(desc)
