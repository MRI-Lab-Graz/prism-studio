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
    assert (
        sidecar["Study"]["Instructions"]["de"] == "Bitte beantworten Sie alle Fragen."
    )

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
    assert (
        sidecar["Study"]["Instructions"]["de"] == "Bitte beantworten Sie alle Fragen."
    )
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
        raise AssertionError(
            "Expected ValueError when only generic Description is provided"
        )


def test_extract_excel_templates_maps_paper_admin_to_paper_platform(tmp_path):
    """Import should normalize paper administration to Paper and Pencil software platform."""
    excel_path = tmp_path / "survey_paper_admin.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "PPR01",
                "Description_en": "I feel calm",
                "Scale_en": "1=not at all;2=a little;3=very much",
                "Group": "ppr",
            }
        ]
    )

    metadata_df = pd.DataFrame(
        [
            {
                "AdministrationMethod": "paper",
                "SoftwarePlatform": "Legacy/Imported",
            }
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")
        metadata_df.to_excel(writer, index=False, sheet_name="General")

    surveys = extract_excel_templates(excel_file=excel_path, check_collisions=False)

    sidecar = surveys["ppr"]
    assert sidecar["Technical"]["AdministrationMethod"] == "paper"
    assert sidecar["Technical"]["SoftwarePlatform"] == "Paper and Pencil"
    assert sidecar["Technical"].get("SoftwareVersion", "") == ""


def test_extract_excel_templates_supports_versions_and_applicable_versions(tmp_path):
    """Import should map Versions and item-level ApplicableVersions to multi-version metadata."""
    excel_path = tmp_path / "survey_multiversion.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "WB01",
                "Description_en": "I felt calm",
                "Scale_en": "1=never;2=sometimes;3=often;4=always",
                "ApplicableVersions": "10-likert;7-likert",
                "Group": "wellbeing",
            },
            {
                "ItemID": "WB02",
                "Description_en": "I felt focused",
                "Scale_en": "1=never;2=sometimes;3=often;4=always",
                "ApplicableVersions": "10-likert;7-likert",
                "Group": "wellbeing",
            },
            {
                "ItemID": "WBV01",
                "Description_en": "How calm do you feel now?",
                "MinValue": "0",
                "MaxValue": "100",
                "ApplicableVersions": "10-vas",
                "Group": "wellbeing",
            },
        ]
    )

    general_df = pd.DataFrame(
        [
            {"Field": "OriginalName_en", "Value": "Wellbeing Demo"},
            {"Field": "Version", "Value": "10-likert"},
            {"Field": "Versions", "Value": "10-likert;7-likert;10-vas"},
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")
        general_df.to_excel(writer, index=False, sheet_name="General")

    surveys = extract_excel_templates(excel_file=excel_path, check_collisions=False)
    sidecar = surveys["wellbeing"]

    assert sidecar["Study"]["Version"] == "10-likert"
    assert sidecar["Study"]["Versions"] == ["10-likert", "7-likert", "10-vas"]

    assert sidecar["WB01"]["ApplicableVersions"] == ["10-likert", "7-likert"]
    assert sidecar["WBV01"]["ApplicableVersions"] == ["10-vas"]

    variant_defs = {d["VariantID"]: d for d in sidecar["Study"]["VariantDefinitions"]}
    assert variant_defs["10-likert"]["ItemCount"] == 2
    assert variant_defs["7-likert"]["ItemCount"] == 2
    assert variant_defs["10-vas"]["ItemCount"] == 1
    assert variant_defs["10-vas"]["ScaleType"] == "vas"


def test_extract_excel_templates_reads_variants_sheet_definitions(tmp_path):
    """Import should read explicit VariantDefinitions from an optional Variants sheet."""
    excel_path = tmp_path / "survey_variants_sheet.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "Q01",
                "Description_en": "I slept well",
                "Scale_en": "1=never;2=sometimes;3=often",
                "ApplicableVersions": "short;long",
                "Group": "sleep",
            },
            {
                "ItemID": "Q02",
                "Description_en": "I woke up rested",
                "Scale_en": "1=never;2=sometimes;3=often",
                "ApplicableVersions": "long",
                "Group": "sleep",
            },
        ]
    )

    general_df = pd.DataFrame(
        [
            {"Field": "OriginalName_en", "Value": "Sleep Scale"},
            {"Field": "Version", "Value": "short"},
            {"Field": "Versions", "Value": "short;long"},
        ]
    )

    variants_df = pd.DataFrame(
        [
            {
                "Group": "sleep",
                "VariantID": "short",
                "ItemCount": "1",
                "ScaleType": "likert",
                "Description_en": "Short form",
            },
            {
                "Group": "sleep",
                "VariantID": "long",
                "ItemCount": "2",
                "ScaleType": "likert",
                "Description_en": "Long form",
            },
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")
        general_df.to_excel(writer, index=False, sheet_name="General")
        variants_df.to_excel(writer, index=False, sheet_name="Variants")

    surveys = extract_excel_templates(excel_file=excel_path, check_collisions=False)
    sidecar = surveys["sleep"]

    variant_defs = {d["VariantID"]: d for d in sidecar["Study"]["VariantDefinitions"]}
    assert variant_defs["short"]["Description"]["en"] == "Short form"
    assert variant_defs["long"]["Description"]["en"] == "Long form"
    assert variant_defs["short"]["ItemCount"] == 1
    assert variant_defs["long"]["ItemCount"] == 2


def test_extract_excel_templates_reads_item_variant_scales_from_variants_sheet(
    tmp_path,
):
    """Variants sheet item rows should map to item VariantScales overrides."""
    excel_path = tmp_path / "survey_item_variant_scales.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "WBM01",
                "Description_en": "I felt calm",
                "Scale_en": "1=never;2=rarely;3=sometimes;4=often;5=always",
                "DataType": "integer",
                "MinValue": "1",
                "MaxValue": "5",
                "ApplicableVersions": "10-likert;10-vas",
                "Group": "wellbeing",
            }
        ]
    )

    general_df = pd.DataFrame(
        [
            {"Field": "OriginalName_en", "Value": "Wellbeing Multi"},
            {"Field": "Version", "Value": "10-likert"},
            {"Field": "Versions", "Value": "10-likert;10-vas"},
        ]
    )

    variants_df = pd.DataFrame(
        [
            {
                "Group": "wellbeing",
                "ItemID": "WBM01",
                "VariantID": "10-vas",
                "ScaleType": "vas",
                "DataType": "integer",
                "MinValue": "0",
                "MaxValue": "100",
                "Scale_en": "0=not at all;100=completely",
            }
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")
        general_df.to_excel(writer, index=False, sheet_name="General")
        variants_df.to_excel(writer, index=False, sheet_name="Variants")

    surveys = extract_excel_templates(excel_file=excel_path, check_collisions=False)
    sidecar = surveys["wellbeing"]

    item = sidecar["WBM01"]
    assert item["DataType"] == "integer"
    assert item["MinValue"] == 1
    assert item["MaxValue"] == 5

    variant_scales = {entry["VariantID"]: entry for entry in item["VariantScales"]}
    assert "10-vas" in variant_scales
    assert variant_scales["10-vas"]["DataType"] == "integer"
    assert variant_scales["10-vas"]["MinValue"] == 0
    assert variant_scales["10-vas"]["MaxValue"] == 100
    assert variant_scales["10-vas"]["Levels"]["0"]["en"] == "not at all"
    assert variant_scales["10-vas"]["Levels"]["100"]["en"] == "completely"

    variant_defs = {d["VariantID"]: d for d in sidecar["Study"]["VariantDefinitions"]}
    assert variant_defs["10-vas"]["ScaleType"] == "vas"


def test_extract_excel_templates_uses_variants_when_general_version_missing(tmp_path):
    """Variants sheet should define Study.Version/Versions when General omits them."""
    excel_path = tmp_path / "survey_variants_drive_versions.xlsx"

    items_df = pd.DataFrame(
        [
            {
                "ItemID": "Q01",
                "Description_en": "I felt calm",
                "Scale_en": "1=never;2=sometimes;3=often",
                "Group": "wellbeing",
            }
        ]
    )

    # Intentionally omit Version / Versions to validate variant-driven defaults.
    general_df = pd.DataFrame(
        [
            {"Field": "OriginalName_en", "Value": "Wellbeing Multi"},
        ]
    )

    variants_df = pd.DataFrame(
        [
            {
                "Group": "wellbeing",
                "VariantID": "10-likert",
                "ItemCount": 1,
                "ScaleType": "likert",
                "Description_en": "10-item long form",
            },
            {
                "Group": "wellbeing",
                "VariantID": "7-likert",
                "ItemCount": 1,
                "ScaleType": "likert",
                "Description_en": "7-item short form",
            },
        ]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        items_df.to_excel(writer, index=False, sheet_name="Items")
        general_df.to_excel(writer, index=False, sheet_name="General")
        variants_df.to_excel(writer, index=False, sheet_name="Variants")

    surveys = extract_excel_templates(excel_file=excel_path, check_collisions=False)
    sidecar = surveys["wellbeing"]

    assert sidecar["Study"]["Versions"] == ["10-likert", "7-likert"]
    assert sidecar["Study"]["Version"] == "10-likert"
