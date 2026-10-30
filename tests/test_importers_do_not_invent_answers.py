"""Importers and the fixer write what the source says, never an answer of their own:
no Respondent, Creator, license or name they made up, no export settings in the template, the
schema's current version, and I18n.Languages as found in the source."""

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

from src.modality_versions import current_survey_schema_version

DATA = Path(__file__).parent / "data"


def test_current_survey_schema_version_is_the_schemas_version():
    schema = json.loads(Path("app/schemas/stable/survey.schema.json").read_text(encoding="utf-8"))
    assert current_survey_schema_version() == schema["version"]


# --- Excel ----------------------------------------------------------------------------------------


def _excel_template(tmp_path, general=None, columns=("Description_de", "Description_en")):
    from app.src.converters.excel_to_survey import extract_excel_templates

    row = {"ItemID": "ADS01", "Scale": "0=nie;1=oft", "Group": "ads"}
    row.update({c: f"text {c}" for c in columns})
    path = tmp_path / "s.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        pd.DataFrame([row]).to_excel(writer, index=False, sheet_name="Items")
        if general:
            pd.DataFrame([general]).to_excel(writer, index=False, sheet_name="General")
    return extract_excel_templates(excel_file=path, check_collisions=False)["ads"]


def test_excel_without_respondent_cell_writes_no_respondent(tmp_path):
    t = _excel_template(tmp_path)
    assert "Respondent" not in t["Technical"]
    assert "Creator" not in t["Metadata"]
    assert "LicenseID" not in t["Study"]
    assert t["Study"]["OriginalName"].get("de") != t["Study"]["TaskName"]


def test_excel_with_respondent_cell_keeps_it(tmp_path):
    assert _excel_template(tmp_path, {"Respondent": "parent"})["Technical"]["Respondent"] == "parent"


def test_excel_keeps_the_facts(tmp_path):
    t = _excel_template(tmp_path)
    assert t["Technical"]["StimulusType"] == "Questionnaire"
    assert t["Technical"]["FileFormat"] == "tsv"
    assert t["Metadata"]["CreationDate"] == date.today().isoformat()
    assert t["Metadata"]["SchemaVersion"] == current_survey_schema_version()


def test_excel_languages_are_the_sheets_language_columns(tmp_path):
    t = _excel_template(tmp_path, columns=("Description_en",))
    assert t["I18n"]["Languages"] == ["en"]
    assert t["Technical"]["Language"] == "en"
    both = _excel_template(tmp_path, columns=("Description_de", "Description_en"))
    assert both["I18n"]["Languages"] == ["de", "en"]


# --- LimeSurvey -----------------------------------------------------------------------------------

LSS = """<?xml version="1.0" encoding="UTF-8"?>
<document>
  <languages><language>de</language><language>en</language></languages>
  <surveys><rows><row><sid>1</sid><language>de</language><additional_languages>en</additional_languages></row></rows></surveys>
  <groups><rows><row><gid>1</gid><group_name>Mood</group_name><group_order>1</group_order></row></rows></groups>
  <questions><rows>
    <row><qid>10</qid><gid>1</gid><type>N</type><title>AGE</title><question>Age?</question><question_order>1</question_order><mandatory>Y</mandatory><parent_qid>0</parent_qid></row>
  </rows></questions>
</document>""".encode()


def test_lss_import_writes_no_invented_answers_and_no_export_settings():
    from src.converters.limesurvey import limesurvey_questionnaire

    t, _notes = limesurvey_questionnaire(LSS, "survey", split="survey")
    assert "Respondent" not in t["Technical"]
    assert t["Metadata"]["SchemaVersion"] == current_survey_schema_version()
    assert t["I18n"]["Languages"] == ["de", "en"]
    item = t["AGE"]
    assert item["Mandatory"] is True
    assert "questionType" not in item.get("LimeSurvey", {}) and "inputWidth" not in item.get("LimeSurvey", {})


def test_lss_import_keeps_the_column_name_of_a_matrix_row():
    from tests.test_limesurvey_languages import LS6
    from src.converters.limesurvey import limesurvey_questionnaire

    t, _ = limesurvey_questionnaire(LS6, "g1")
    assert t["M1"]["LimeSurvey"] == {"columnName": "mood[M1]"}


def test_lss_single_language_still_declares_its_language():
    from src.converters.limesurvey import limesurvey_questionnaire

    xml = LSS.replace(b"<language>de</language><language>en</language>", b"<language>en</language>").replace(
        b"<language>de</language><additional_languages>en</additional_languages>", b"<language>en</language>"
    )
    t, _ = limesurvey_questionnaire(xml, "survey", split="survey")
    assert t["I18n"]["Languages"] == ["en"]


def test_lss_single_sidecar_converter_invents_no_respondent():
    from src.converters.limesurvey import parse_lss_xml

    t = parse_lss_xml(LSS, check_collisions=False)
    assert "Respondent" not in t["Technical"]
    assert t["Metadata"]["SchemaVersion"] == current_survey_schema_version()
    assert t["I18n"]["Languages"] == [t["Technical"]["Language"]]


def test_lsq_import_has_no_export_settings():
    from src.converters.limesurvey import parse_lsq_xml

    lsq = """<?xml version="1.0" encoding="UTF-8"?>
<document><languages><language>de</language></languages>
<questions><rows><row><qid>1</qid><gid>1</gid><type>N</type><title>Q1</title><question>Wie alt?</question><question_order>1</question_order><mandatory>N</mandatory><parent_qid>0</parent_qid></row></rows></questions>
</document>""".encode()
    t = parse_lsq_xml(lsq)
    assert "Respondent" not in t["Technical"]
    assert t["I18n"]["Languages"] == ["de"]
    assert "questionType" not in t["Q1"].get("LimeSurvey", {})


# --- Pavlovia / phenotype ---------------------------------------------------------------------------


def test_pavlovia_import_invents_no_respondent_and_declares_its_language():
    from src.converters.pavlovia_import import pavlovia_questionnaire_template

    survey = json.loads((DATA / "pavlovia_survey.json").read_text(encoding="utf-8"))
    t = pavlovia_questionnaire_template(survey, "p2", language="de")
    assert "Respondent" not in t["Technical"]
    assert t["Metadata"]["SchemaVersion"] == current_survey_schema_version()
    assert t["I18n"]["Languages"] == ["de"]
    assert t["Study"]["ItemCount"] == 2


def test_pavlovia_import_without_language_omits_it():
    from src.converters.pavlovia_import import pavlovia_questionnaire_template

    survey = json.loads((DATA / "pavlovia_survey.json").read_text(encoding="utf-8"))
    t = pavlovia_questionnaire_template(survey, "p2")
    assert "I18n" not in t and "Language" not in t["Technical"]


def test_phenotype_import_invents_no_respondent_license_or_name(tmp_path):
    from src.converters.phenotype_import import import_phenotype_file

    tsv = tmp_path / "wellbeing.tsv"
    pd.DataFrame([{"participant_id": "sub-01", "session_id": "ses-01", "WB01": 3}]).to_csv(
        tsv, sep="\t", index=False, lineterminator="\n"
    )
    root = tmp_path / "project"
    root.mkdir()
    import_phenotype_file(tsv, root)
    t = json.loads((root / "task-wellbeing_survey.json").read_text(encoding="utf-8"))
    assert "Respondent" not in t["Technical"] and "Language" not in t["Technical"]
    assert "LicenseID" not in t["Study"] and "OriginalName" not in t["Study"]
    assert "I18n" not in t  # the file names no language: never invented
    assert t["Metadata"]["SchemaVersion"] == current_survey_schema_version()


# --- survey_io localization path, dataset sidecar --------------------------------------------------


def test_survey_io_sidecar_invents_no_respondent_license_or_name(tmp_path):
    import importlib

    survey_io = importlib.import_module("src.converters.survey_io")
    survey_io._write_task_sidecars(
        tasks_with_data={"pss"},
        dataset_root=tmp_path,
        templates={"pss": {"json": {"Study": {"TaskName": "pss"}}}},
        task_acq_map={"pss": None},
        language="en",
        force=True,
        technical_overrides=None,
        missing_token="n/a",
        localize_survey_template_fn=lambda template, language: template,
        inject_missing_token_fn=lambda template, token: template,
        apply_technical_overrides_fn=lambda template, overrides: template,
        strip_internal_keys_fn=lambda template: template,
        write_json_fn=lambda path, payload: path.write_text(json.dumps(payload), encoding="utf-8"),
    )
    t = json.loads((tmp_path / "task-pss_survey.json").read_text(encoding="utf-8"))
    assert "Respondent" not in t["Technical"]
    assert "LicenseID" not in t["Study"] and "OriginalName" not in t["Study"]
    assert t["Technical"]["Language"] == "en"
    assert t["Metadata"]["SchemaVersion"] == current_survey_schema_version()


def test_dataset_sidecar_strips_export_settings_but_keeps_data():
    from src.converters.survey import _strip_internal_keys

    out = _strip_internal_keys(
        {"_x": 1, "Q1": {"LimeSurvey": {"questionType": "N", "columnName": "Q1[a]", "answerCodes": {"1": "a"}}}}
    )
    assert "_x" not in out
    assert out["Q1"]["LimeSurvey"] == {"columnName": "Q1[a]", "answerCodes": {"1": "a"}}


# --- project template from the official library -------------------------------------------------------


def test_project_template_from_official_invents_no_respondent_or_license():
    from src.survey_template_sources import prepare_project_survey_template_from_official

    out = prepare_project_survey_template_from_official({"Technical": {}, "Study": {}}, task="pss")
    assert "Respondent" not in out["Technical"]
    assert "LicenseID" not in out["Study"]


# --- fixer -----------------------------------------------------------------------------------------


def test_fixer_stub_leaves_respondent_and_language_out_and_reports_them(tmp_path):
    from app.src.fixer import DatasetFixer

    (tmp_path / "dataset_description.json").write_text("{}", encoding="utf-8")
    d = tmp_path / "sub-01" / "survey"
    d.mkdir(parents=True)
    (d / "sub-01_task-x_survey.tsv").write_text("a\n1\n", encoding="utf-8")
    fixes = [f for f in DatasetFixer(str(tmp_path), dry_run=True).analyze() if f.issue_code == "PRISM201"]
    assert fixes
    stub = json.loads(fixes[0].details["content"])
    assert "Respondent" not in stub["Technical"] and "Language" not in stub["Technical"]
    assert stub["Metadata"]["SchemaVersion"] == current_survey_schema_version()
    assert re.search(r"Respondent", fixes[0].description) and re.search(r"Language", fixes[0].description)
