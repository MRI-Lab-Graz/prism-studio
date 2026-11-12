from pathlib import Path

import pytest

from src.biosample_migrate import MigrationError, read_legacy_wide, repair_mojibake

FIXTURE = Path(__file__).parent / "data/biosample/legacy_wide_blood.csv"


def test_reads_the_quirk_file_as_73_columns():
    df = read_legacy_wide(FIXTURE)
    assert len(df.columns) == 73
    assert list(df.columns[:2]) == ["Patient No.", "Visit"]
    assert len(df) == 12
    assert df.iloc[4]["Visit"] == "T4.1"
    assert df.iloc[0]["Estradiol Results"] == "<5"
    assert df.iloc[0]["Prolaktin Unit"] == "¬µU/ml"


def test_reads_a_plain_comma_csv_and_a_tab_file_normally(tmp_path):
    for name, sep in (("a.csv", ","), ("b.tsv", "\t")):
        p = tmp_path / name
        p.write_text(f"id{sep}visit{sep}x Results\ns1{sep}T0{sep}<0.5\n", encoding="utf-8")
        df = read_legacy_wide(p)
        assert list(df.columns) == ["id", "visit", "x Results"]
        assert df.iloc[0].tolist() == ["s1", "T0", "<0.5"]


def test_reads_xlsx_as_text(tmp_path):
    import pandas as pd

    p = tmp_path / "c.xlsx"
    pd.DataFrame({"id": ["s1"], "visit": ["T4.1"], "x Results": ["<0,05"]}).to_excel(p, index=False)
    assert read_legacy_wide(p).iloc[0].tolist() == ["s1", "T4.1", "<0,05"]


def test_repair_mojibake():
    assert repair_mojibake("¬µU/ml") == "µU/ml"
    assert repair_mojibake("pg/ml") == "pg/ml"
    assert repair_mojibake("ng/ml") == "ng/ml"
    assert repair_mojibake("µU/ml") == "µU/ml"  # cannot round-trip: unchanged


def test_unreadable_file_is_a_migration_error(tmp_path):
    with pytest.raises(MigrationError):
        read_legacy_wide(tmp_path / "missing.csv")
    empty = tmp_path / "empty.csv"
    empty.write_text("")
    with pytest.raises(MigrationError):
        read_legacy_wide(empty)


def test_quirk_detection_does_not_depend_on_reader_error_text(monkeypatch):
    import src.converters.file_reader as fr

    real = fr._rewrite_tokenization_error
    monkeypatch.setattr(fr, "_rewrite_tokenization_error", lambda *a: "other wording")
    assert len(read_legacy_wide(FIXTURE).columns) == 73
    monkeypatch.setattr(fr, "_rewrite_tokenization_error", real)


def test_quirk_file_is_read_without_the_normal_path_error(monkeypatch):
    import src.biosample_migrate as m

    calls = []
    real = m.read_tabular_file
    monkeypatch.setattr(m, "read_tabular_file", lambda *a, **k: (calls.append(k), real(*a, **k))[1])
    read_legacy_wide(FIXTURE)
    assert calls and all(k.get("separator") == "\x1f" for k in calls)


def test_empty_cells_are_empty_strings_and_ids_stay_text_in_xlsx(tmp_path):
    from openpyxl import Workbook

    p = tmp_path / "d.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["id", "visit", "x Results"])
    ws.append(["007", "T0", None])
    wb.save(p)
    df = read_legacy_wide(p)
    assert df.iloc[0].tolist() == ["007", "T0", ""]
    q = tmp_path / "e.csv"
    q.write_text("id,visit,x Results\n007,T0,\n")
    assert read_legacy_wide(q).iloc[0].tolist() == ["007", "T0", ""]


def test_row_with_surplus_fields_is_an_error_but_empty_surplus_is_fine(tmp_path):
    p = tmp_path / "q.csv"
    p.write_bytes(b'"id\tvisit"\r\n"s1\tT0\t\t"\r\n"s2\tT1\tjunk"\r\n')
    with pytest.raises(MigrationError, match="row 2"):
        read_legacy_wide(p)
    p.write_bytes(b'"id\tvisit"\r\n"s1\tT0\t\t"\r\n"s2"\r\n')
    assert read_legacy_wide(p).values.tolist() == [["s1", "T0"], ["s2", ""]]
