import csv
import datetime as dt

import pytest
from openpyxl import Workbook

from src.biosample_template import DATA_COLUMNS, PANEL_COLUMNS
from src.biosample_template_reader import normalise_value, read_template


def _book(tmp_path, data, panels=None, data_header=DATA_COLUMNS):
    wb = Workbook()
    ws = wb.active
    ws.title = "data"
    ws.append(list(data_header))
    for r in data:
        ws.append(list(r))
    if panels is not None:
        p = wb.create_sheet("panels")
        p.append(list(PANEL_COLUMNS))
        for r in panels:
            p.append(list(r))
    out = tmp_path / "t.xlsx"
    wb.save(out)
    return out


def _row(pid="01", ses="1", panel="crp", run=None, sid="s1", t="08:30", analyte="CRP",
         value=1, unit="mg/L", comment=None):
    return (pid, ses, panel, run, sid, t, analyte, value, unit, comment)


def _panel(name="crp", spec="serum"):
    return (name, spec) + (None,) * 8


@pytest.mark.parametrize("raw,expected", [
    ("<5", ("<LOD", 5.0)), ("<0,05", ("<LOD", 0.05)), (2.0099999999999998, ("2.01", None)),
    ("2,5 ", ("2.5", None)), (3, ("3", None)), (None, ("n/a", None)), ("", ("n/a", None)),
    ("n/a", ("n/a", None)), ("<LOD", ("<LOD", None)), ("<LLOQ", ("<LLOQ", None)),
    (">ULOQ", (">ULOQ", None)),
])
def test_normalise_value(raw, expected):
    assert normalise_value(raw) == expected


@pytest.mark.parametrize("raw", ["abc", dt.datetime(2020, 1, 2), dt.date(2020, 1, 2), ">5", True])
def test_normalise_value_rejects(raw):
    with pytest.raises(ValueError):
        normalise_value(raw)


def test_reads_rows_and_panels(tmp_path):
    p = _book(tmp_path, [_row(value="<5"), _row(sid="s2", value="<2"), _row(sid="s3", value=2.0099999999999998)],
              [_panel()])
    rows, panels, problems = read_template(p)
    assert problems == []
    assert [r["value"] for r in rows] == ["<LOD", "<LOD", "2.01"]
    assert panels["crp"]["SpecimenType"] == "serum"
    assert panels["crp"]["limits"] == {"CRP": [5.0, 2.0]}


def test_session_is_exact_string(tmp_path):
    p = _book(tmp_path, [_row(ses=1), _row(sid="b", ses="01"), _row(sid="c", ses="T4.1")], [_panel()])
    rows, _, problems = read_template(p)
    assert problems == []
    assert [r["session"] for r in rows] == ["1", "01", "T4.1"]


def test_unknown_and_missing_columns(tmp_path):
    header = [c for c in DATA_COLUMNS if c != "analyte"] + ["extra"]
    rows, _, problems = read_template(_book(tmp_path, [], [_panel()], header))
    assert rows == []
    assert any("data" in m and "extra" in m for m in problems)
    assert any("data" in m and "analyte" in m for m in problems)


def test_missing_panels_sheet_needs_specimen(tmp_path):
    p = _book(tmp_path, [_row()])
    _, _, problems = read_template(p)
    assert any("panels" in m and "specimen" in m.lower() for m in problems)
    _, panels, problems = read_template(p, specimen="serum")
    assert problems == [] and panels["crp"]["SpecimenType"] == "serum"


def test_empty_specimen_is_a_problem(tmp_path):
    _, _, problems = read_template(_book(tmp_path, [_row()], [_panel(spec=None)]))
    assert any("panels" in m and "row 2" in m and "SpecimenType" in m for m in problems)


def test_date_in_collection_time_and_value_are_errors(tmp_path):
    p = _book(tmp_path, [_row(t=dt.datetime(2020, 1, 2, 8, 30)), _row(sid="b", t=dt.time(8, 5)),
                         _row(sid="c", value=dt.datetime(2020, 1, 2))], [_panel()])
    rows, _, problems = read_template(p)
    assert len(problems) == 2
    assert "data" in problems[0] and "row 2" in problems[0] and "collection_time" in problems[0]
    assert "row 4" in problems[1] and "value" in problems[1]
    assert rows[0]["collection_time"] == "08:05"


def test_two_units_for_one_analyte_in_a_panel(tmp_path):
    p = _book(tmp_path, [_row(unit="mg/L"), _row(sid="b", unit="mg/dL")], [_panel()])
    _, _, problems = read_template(p)
    assert any("CRP" in m and "mg/L" in m and "mg/dL" in m for m in problems)


def test_csv_uses_specimen(tmp_path):
    p = tmp_path / "t.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(DATA_COLUMNS)
        w.writerow(_row(value="2,5"))
    rows, panels, problems = read_template(p, specimen="plasma")
    assert problems == [] and rows[0]["value"] == "2.5" and panels["crp"]["SpecimenType"] == "plasma"
    assert read_template(p)[2]


def test_bad_file_does_not_raise(tmp_path):
    p = tmp_path / "t.xlsx"
    p.write_text("not a workbook")
    assert read_template(p)[2]


def test_csv_row_wider_than_header_is_a_problem(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(",".join(DATA_COLUMNS) + "\n01,1,crp,,s1,08:30,CRP,1,5,mg/L,\n", encoding="utf-8")
    rows, _, problems = read_template(p, specimen="serum")
    assert rows == []
    assert problems == ["data row 2: more cells than columns; quote decimals or use the .xlsx"]


def test_csv_cell_under_empty_header_is_a_problem(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text(",".join(DATA_COLUMNS) + ",\n01,1,crp,,s1,08:30,CRP,1,mg/L,,x\n", encoding="utf-8")
    _, _, problems = read_template(p, specimen="serum")
    assert problems == ["data row 2: more cells than columns; quote decimals or use the .xlsx"]


def test_xlsx_cell_under_empty_header_is_a_problem(tmp_path):
    p = _book(tmp_path, [_row() + ("stray",)], [_panel() + ("stray",)])
    _, _, problems = read_template(p)
    assert "data row 2: more cells than columns; quote decimals or use the .xlsx" in problems
    assert "panels row 2: more cells than columns; quote decimals or use the .xlsx" in problems


def test_workbook_is_closed(tmp_path, monkeypatch):
    import src.biosample_template_reader as reader

    closed = []
    real = reader.load_workbook

    def spy(*a, **k):
        wb = real(*a, **k)
        orig = wb.close
        wb.close = lambda: (closed.append(True), orig())
        return wb

    monkeypatch.setattr(reader, "load_workbook", spy)
    read_template(_book(tmp_path, [_row()], [_panel()]))
    assert closed == [True]


@pytest.mark.parametrize("raw,expected", [
    (2.0099999999999998, "2.01"), (123456789.123, "123456789.123"), (1e-12, "1e-12"),
])
def test_fmt_keeps_precision(raw, expected):
    assert normalise_value(raw) == (expected, None)


def test_duplicate_panel_name_is_a_problem(tmp_path):
    _, _, problems = read_template(_book(tmp_path, [_row()], [_panel(), _panel(spec="plasma")]))
    assert any("panels rows 2 and 3" in m and "crp" in m for m in problems), problems


def test_text_time_is_parsed_and_reformatted(tmp_path):
    p = _book(tmp_path, [_row(t="8:30"), _row(sid="b", t="99:99"), _row(sid="c", t="25:61"),
                         _row(sid="d", t="08:30:00")], [_panel()])
    rows, _, problems = read_template(p)
    assert rows[0]["collection_time"] == "08:30"
    assert [m.split(":")[0] for m in problems] == ["data row 3", "data row 4", "data row 5"]
    assert all("collection_time" in m for m in problems)


def test_limits_are_kept_per_cell(tmp_path):
    rows, _, _ = read_template(_book(tmp_path, [_row(value="<5"), _row(sid="b", value=2)], [_panel()]))
    assert [r["limit"] for r in rows] == [5.0, None]
