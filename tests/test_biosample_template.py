import json
from pathlib import Path

from openpyxl import load_workbook

from src.biosample_template import DATA_COLUMNS, PANEL_COLUMNS, write_biosample_template

SCHEMA = Path(__file__).resolve().parents[1] / "app/schemas/stable/biosample.schema.json"


def _list_for(ws, header):
    col = [c.value for c in ws[1]].index(header) + 1
    letter = ws.cell(row=1, column=col).column_letter
    for dv in ws.data_validations.dataValidation:
        if any(letter in str(r) for r in dv.sqref.ranges):
            return dv.formula1.strip('"').split(",")
    return None


def test_template_has_both_sheets_and_schema_pulldowns(tmp_path):
    out = tmp_path / "t.xlsx"
    write_biosample_template(out)
    wb = load_workbook(out)
    assert wb.sheetnames == ["data", "panels"]
    assert tuple(c.value for c in wb["data"][1]) == DATA_COLUMNS
    assert tuple(c.value for c in wb["panels"][1]) == PANEL_COLUMNS
    tech = json.loads(SCHEMA.read_text())["properties"]["Technical"]["properties"]
    panels = wb["panels"]
    assert _list_for(panels, "SpecimenType") == tech["SpecimenType"]["enum"]
    assert _list_for(panels, "CollectionMethod") == [v for v in tech["CollectionMethod"]["enum"] if v]
    assert _list_for(panels, "Anticoagulant") == [v for v in tech["Anticoagulant"]["enum"] if v]
    assert _list_for(panels, "FastingRequired") == ["true", "false"]


def test_id_columns_are_text_so_01_stays_01(tmp_path):
    out = tmp_path / "t.xlsx"
    write_biosample_template(out)
    ws = load_workbook(out)["data"]
    for name in ("participant_id", "session", "run", "sample_id"):
        col = DATA_COLUMNS.index(name) + 1
        assert ws.cell(row=2, column=col).number_format == "@", name
        assert ws.cell(row=1000, column=col).number_format == "@", name
    assert ws.cell(row=2, column=DATA_COLUMNS.index("value") + 1).number_format != "@"
