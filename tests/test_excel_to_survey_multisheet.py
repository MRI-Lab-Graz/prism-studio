"""Tests for multi-sheet survey Excel imports."""

import pandas as pd

from app.src.converters.excel_to_survey import extract_excel_templates


def test_extract_excel_templates_supports_split_item_and_metadata_sheets(tmp_path):
    """Import should support item fields in one sheet and general metadata in another."""
    excel_path = tmp_path / "survey_split.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "ADS01",
                "Description_de": "Ich fuehle mich traurig",
                "Scale": "0=nie;1=selten;2=manchmal;3=haeufig",
                "Group": "ads",
                "Session": "1",
                "Run": "1",
            },
            {
                "ItemID": "ADS02",
                "Description_de": "Ich habe Schwierigkeiten, mich zu konzentrieren",
                "Scale": "0=nie;1=selten;2=manchmal;3=haeufig",
                "Group": "ads",
                "Session": "1",
                "Run": "1",
            },
        ]
    )

    metadata_df = pd.DataFrame(
        [
            {
                "OriginalName_de": "Allgemeine Depressionsskala",
                "OriginalName_en": "General Depression Scale",
                "ShortName": "ADS",
                "Version_de": "1",
                "Version_en": "1",
                "Citation": "Hautzinger & Bailer (1993)",
                "Construct": "Depression",
                "Instructions_de": "Bitte beantworten Sie alle Fragen.",
            }
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")
        metadata_df.to_excel(writer, index=False, sheet_name="General")

    surveys = extract_excel_templates(excel_file=excel_path, check_collisions=False)

    assert "ads" in surveys
    sidecar = surveys["ads"]

    assert sidecar["Study"]["OriginalName"]["de"] == "Allgemeine Depressionsskala"
    assert sidecar["Study"]["OriginalName"]["en"] == "General Depression Scale"
    assert sidecar["Study"]["ShortName"] == "ADS"
    assert sidecar["Study"]["Version"]["de"] == "1"
    assert sidecar["Study"]["Version"]["en"] == "1"
    assert sidecar["Study"]["Citation"] == "Hautzinger & Bailer (1993)"
    assert sidecar["Study"]["Construct"]["de"] == "Depression"
    assert sidecar["Study"]["Instructions"]["de"] == "Bitte beantworten Sie alle Fragen."

    assert sidecar["ADS01"]["RunHint"] == "run-1"
    assert sidecar["ADS02"]["RunHint"] == "run-1"


def test_extract_excel_templates_supports_additional_languages(tmp_path):
    """Import should preserve language columns beyond de/en."""
    excel_path = tmp_path / "survey_multilang.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "ADS01",
                "Description_de": "Ich fuehle mich traurig",
                "Description_en": "I feel sad",
                "Description_fr": "Je me sens triste",
                "Scale_de": "0=nie;1=selten;2=manchmal;3=haeufig",
                "Scale_en": "0=never;1=rarely;2=sometimes;3=often",
                "Scale_fr": "0=jamais;1=rarement;2=parfois;3=souvent",
                "Group": "ads",
            }
        ]
    )

    metadata_df = pd.DataFrame(
        [
            {
                "OriginalName_de": "Allgemeine Depressionsskala",
                "OriginalName_en": "General Depression Scale",
                "OriginalName_fr": "Echelle generale de depression",
                "Instructions_de": "Bitte beantworten Sie alle Fragen.",
                "Instructions_en": "Please answer all questions.",
                "Instructions_fr": "Veuillez repondre a toutes les questions.",
                "Version_de": "1",
                "Version_en": "1",
                "Version_fr": "1",
            }
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")
        metadata_df.to_excel(writer, index=False, sheet_name="General")

    surveys = extract_excel_templates(excel_file=excel_path, check_collisions=False)

    sidecar = surveys["ads"]
    assert "fr" in sidecar["I18n"]["Languages"]
    assert sidecar["Study"]["OriginalName"]["fr"] == "Echelle generale de depression"
    assert (
        sidecar["Study"]["Instructions"]["fr"]
        == "Veuillez repondre a toutes les questions."
    )
    assert sidecar["ADS01"]["Description"]["fr"] == "Je me sens triste"
    assert sidecar["ADS01"]["Levels"]["0"]["fr"] == "jamais"


def test_extract_excel_templates_supports_transposed_general_sheet(tmp_path):
    """Import should support General sheet as Field/Value rows."""
    excel_path = tmp_path / "survey_transposed_general.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "ADS01",
                "Description_de": "Ich fuehle mich traurig",
                "Description_en": "I feel sad",
                "Scale_de": "0=nie;1=selten;2=manchmal;3=haeufig",
                "Scale_en": "0=never;1=rarely;2=sometimes;3=often",
                "Group": "ads",
                "Run": "1",
            }
        ]
    )

    general_transposed_df = pd.DataFrame(
        [
            {
                "Field": "OriginalName_de",
                "Value": "Allgemeine Depressionsskala",
                "Required": "yes",
                "Notes": "",
            },
            {
                "Field": "OriginalName_en",
                "Value": "General Depression Scale",
                "Required": "yes",
                "Notes": "",
            },
            {
                "Field": "Instructions_de",
                "Value": "Bitte beantworten Sie alle Fragen.",
                "Required": "",
                "Notes": "",
            },
            {
                "Field": "Instructions_en",
                "Value": "Please answer all questions.",
                "Required": "",
                "Notes": "",
            },
            {
                "Field": "I18nLanguages",
                "Value": "de;en",
                "Required": "",
                "Notes": "",
            },
            {
                "Field": "I18nDefaultLanguage",
                "Value": "de",
                "Required": "",
                "Notes": "",
            },
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")
        general_transposed_df.to_excel(writer, index=False, sheet_name="General")

    surveys = extract_excel_templates(excel_file=excel_path, check_collisions=False)
    sidecar = surveys["ads"]

    assert sidecar["Study"]["OriginalName"]["de"] == "Allgemeine Depressionsskala"
    assert sidecar["Study"]["OriginalName"]["en"] == "General Depression Scale"
    assert sidecar["Study"]["Instructions"]["de"] == "Bitte beantworten Sie alle Fragen."
    assert sidecar["Study"]["Instructions"]["en"] == "Please answer all questions."
    assert sidecar["I18n"]["DefaultLanguage"] == "de"


def test_extract_excel_templates_requires_language_specific_item_description(tmp_path):
    """Generic Description column is ignored; Description_de or Description_en is required."""
    excel_path = tmp_path / "survey_mono.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "daf01",
                "Description": "Manchmal kann ich dem Verlangen, eine andere Person zu schlagen, nicht widerstehen.",
                "Scale": "1=Trifft nicht zu; 2=Trifft eher zu; 3=Trifft voll zu",
                "Group": "daf",
            },
            {
                "ItemID": "daf02",
                "Description": "Ich sage es meinen Freunden offen, wenn ich anderer Meinung bin als sie.",
                "Scale": "1=Trifft nicht zu; 2=Trifft eher zu; 3=Trifft voll zu",
                "Group": "daf",
            },
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")

    try:
        extract_excel_templates(excel_file=excel_path, check_collisions=False)
    except ValueError as exc:
        assert "Description_de/Description_en" in str(exc)
    else:
        raise AssertionError("Expected ValueError when only generic Description is provided")
