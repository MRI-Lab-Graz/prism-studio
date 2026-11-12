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
