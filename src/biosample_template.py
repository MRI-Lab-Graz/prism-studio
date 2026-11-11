"""Excel template for biosample data; pull-downs come from the biosample schema."""

import json
from pathlib import Path

from openpyxl import Workbook
from openpyxl.worksheet.datavalidation import DataValidation

DATA_COLUMNS = ("participant_id", "session", "panel", "run", "sample_id",
                "collection_time", "analyte", "value", "unit", "comment")
PANEL_COLUMNS = ("panel", "SpecimenType", "CollectionMethod", "Anticoagulant",
                 "FastingRequired", "StorageTemperature", "Laboratory",
                 "AssayMethod", "AssayKit", "Description")

_SCHEMA = Path(__file__).resolve().parents[1] / "app/schemas/stable/biosample.schema.json"
_ROWS = 1000  # pull-downs cover this many panel rows


def write_biosample_template(path: Path) -> None:
    tech = json.loads(_SCHEMA.read_text(encoding="utf-8"))["properties"]["Technical"]["properties"]
    wb = Workbook()
    data = wb.active
    data.title = "data"
    data.append(list(DATA_COLUMNS))
    panels = wb.create_sheet("panels")
    panels.append(list(PANEL_COLUMNS))
    lists = {name: [v for v in tech[name]["enum"] if v]
             for name in ("SpecimenType", "CollectionMethod", "Anticoagulant")}
    lists["FastingRequired"] = ["true", "false"]
    for name, values in lists.items():
        letter = panels.cell(row=1, column=PANEL_COLUMNS.index(name) + 1).column_letter
        dv = DataValidation(type="list", formula1='"%s"' % ",".join(values), allow_blank=True)
        dv.add(f"{letter}2:{letter}{_ROWS}")
        panels.add_data_validation(dv)
    wb.save(path)
