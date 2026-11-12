import os
from pathlib import Path

import pytest

from src.biosample_migrate import (
    MigrationError,
    detect_analytes,
    read_legacy_wide,
    repair_mojibake,
)

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


def test_detects_24_analyte_groups():
    groups, _ = detect_analytes(list(read_legacy_wide(FIXTURE).columns))
    assert len(groups) == 24
    by_name = {g.name: g for g in groups}
    assert by_name["Free Testosterone"].flag is None
    assert by_name["Free Testosterone"].unit == "Free Testosterone Unit"
    assert by_name["Prolaktin"].value == "Prolaktin Results"
    # double space in the header is kept in the column name, one space in the match
    assert by_name["Levonorgestrel"].flag == "Levonorgestrel  clin. Significant? (if yes:+comment)"


def test_other_columns_are_patient_and_visit():
    _, other = detect_analytes(list(read_legacy_wide(FIXTURE).columns))
    assert other == ["Patient No.", "Visit"]


def test_results_without_unit_still_a_group():
    groups, other = detect_analytes(["id", "pH   RESULTS", "Unit of care"])
    assert [(g.name, g.value, g.unit, g.flag) for g in groups] == [("pH", "pH   RESULTS", None, None)]
    assert other == ["id", "Unit of care"]


def test_duplicate_analyte_keeps_first_group():
    groups, other = detect_analytes(["A Results", "A Unit", "A Results", "B Results"])
    assert [g.name for g in groups] == ["A", "B"]
    assert other == ["A Results"]


# --- Task 3: migrate to the template -------------------------------------------------

from openpyxl import load_workbook  # noqa: E402

from src.biosample_migrate import migrate_wide  # noqa: E402
from src.biosample_template import DATA_COLUMNS, PANEL_COLUMNS  # noqa: E402


def _sheet(path, name):
    wb = load_workbook(path)
    try:
        rows = [list(r) for r in wb[name].iter_rows(values_only=True)]
    finally:
        wb.close()
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:] if any(v is not None for v in r)]


def _tiny(tmp_path, text, name="in.csv"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


@pytest.mark.parametrize("columns, groups, other", [
    (["id", "X Unit", "A Results"], [("A", None, None)], ["id", "X Unit"]),
    (["id", "X clin. Significant?", "A Results"], [("A", None, None)], ["id", "X clin. Significant?"]),
    (["Estradiol Results", "ESTRADIOL unit"], [("Estradiol", "ESTRADIOL unit", None)], []),
])
def test_orphan_unit_and_flag_columns_are_no_group(columns, groups, other):
    found, rest = detect_analytes(columns)
    assert [(g.name, g.unit, g.flag) for g in found] == groups
    assert rest == other


def test_data_rows_hold_the_cell_text_untouched(tmp_path):
    out = tmp_path / "out.xlsx"
    migrate_wide(FIXTURE, out)
    rows = _sheet(out, "data")
    assert list(rows[0]) == list(DATA_COLUMNS)
    by = {(r["participant_id"], r["session"], r["analyte"]): r for r in rows}
    assert by[("s001", "T0", "Progesterone")]["value"] == "<0,05"
    assert by[("s001", "T3", "Cortisol")]["value"] == "2.0099999999999998"
    assert by[("s001", "T0", "Estradiol")]["unit"] == "pg/ml"
    assert any(r["session"] == "T4.1" for r in rows)
    assert all(r["panel"] == "bloodhormones" for r in rows)
    assert all(r["run"] is None and r["sample_id"] is None and r["collection_time"] is None for r in rows)
    assert all(isinstance(r["participant_id"], str) and isinstance(r["value"], str) for r in rows)


def test_empty_visits_are_skipped_and_listed(tmp_path):
    rep = migrate_wide(FIXTURE, tmp_path / "out.xlsx")
    assert rep.rows_read == 12
    assert len(rep.rows_skipped_empty) == 3
    assert all(" T" in s and s.split()[0] in ("s001", "s002") for s in rep.rows_skipped_empty)
    sessions = {(r["participant_id"], r["session"]) for r in _sheet(tmp_path / "out.xlsx", "data")}
    assert not {tuple(s.split()) for s in rep.rows_skipped_empty} & sessions
    assert rep.data_rows == len(_sheet(tmp_path / "out.xlsx", "data")) == 9 * 9  # 9 visits with data, 9 analytes with data


def test_empty_analytes_are_dropped_and_listed(tmp_path):
    rep = migrate_wide(FIXTURE, tmp_path / "out.xlsx")
    for name in ("AR", "COMT", "BDNF", "Ethinylestradiol", "Levonorgestrel"):
        assert name in rep.analytes_dropped_empty
        assert name not in rep.analytes_mapped
    assert "Free Testosterone" in rep.analytes_mapped
    assert len(rep.analytes_mapped) + len(rep.analytes_dropped_empty) == 24
    assert not set(rep.analytes_dropped_empty) & {r["analyte"] for r in _sheet(tmp_path / "out.xlsx", "data")}


def test_units_are_repaired_and_reported(tmp_path):
    rep = migrate_wide(FIXTURE, tmp_path / "out.xlsx")
    units = {r["unit"] for r in _sheet(tmp_path / "out.xlsx", "data") if r["analyte"] == "Prolaktin"}
    assert units == {"µU/ml"}
    assert len(rep.unit_repairs) == 1 and "µU/ml" in rep.unit_repairs[0]


def test_specimen_default_is_serum_and_assumed(tmp_path):
    rep = migrate_wide(FIXTURE, tmp_path / "a.xlsx")
    panels = _sheet(tmp_path / "a.xlsx", "panels")
    assert list(panels[0]) == list(PANEL_COLUMNS)
    assert [(p["panel"], p["SpecimenType"]) for p in panels] == [("bloodhormones", "serum")]
    assert any("serum" in a and "unverified" in a for a in rep.assumptions)
    rep = migrate_wide(FIXTURE, tmp_path / "b.xlsx", specimen="plasma")
    assert _sheet(tmp_path / "b.xlsx", "panels")[0]["SpecimenType"] == "plasma"
    assert rep.assumptions == []


def test_invalid_specimen_is_an_error(tmp_path):
    with pytest.raises(MigrationError, match="blood"):
        migrate_wide(FIXTURE, tmp_path / "out.xlsx", specimen="blood")
    assert not (tmp_path / "out.xlsx").exists()


def test_missing_unit_column_warns(tmp_path):
    src = _tiny(tmp_path, "id,visit,pH Results\ns1,T0,7.4\n")
    rep = migrate_wide(src, tmp_path / "out.xlsx")
    assert [(r["analyte"], r["unit"]) for r in _sheet(tmp_path / "out.xlsx", "data")] == [("pH", None)]
    assert any("pH" in w and "unit" in w for w in rep.warnings)


def test_duplicate_participant_session_warns(tmp_path):
    src = _tiny(tmp_path, "id,visit,A Results,A Unit\ns1,T0,1,mg\ns1,T0,2,mg\ns2,T0,3,mg\n")
    rep = migrate_wide(src, tmp_path / "out.xlsx")
    assert any("s1 T0" in w and "twice" in w for w in rep.warnings)
    assert not any("s2" in w for w in rep.warnings)


def test_text_in_a_value_cell_is_copied_as_written(tmp_path):
    src = _tiny(tmp_path, "id,visit,A Results,A Unit\ns1,T0, n.a. ,mg\ns1,T1,-,mg\n")
    migrate_wide(src, tmp_path / "out.xlsx")
    assert [r["value"] for r in _sheet(tmp_path / "out.xlsx", "data")] == ["n.a.", "-"]


def test_invalid_panel_name_is_an_error(tmp_path):
    with pytest.raises(MigrationError, match="blood-hormones"):
        migrate_wide(FIXTURE, tmp_path / "out.xlsx", panel="blood-hormones")
    assert not (tmp_path / "out.xlsx").exists()


def test_id_and_session_columns_must_be_determinable(tmp_path):
    src = _tiny(tmp_path, "id,visit,site,A Results\ns1,T0,G,1\n")
    with pytest.raises(MigrationError) as exc:
        migrate_wide(src, tmp_path / "out.xlsx")
    assert all(c in str(exc.value) for c in ("id", "visit", "site"))
    assert "--id-column" in str(exc.value)
    rep = migrate_wide(src, tmp_path / "out.xlsx", id_column="id", session_column="visit")
    assert rep.data_rows == 1
    with pytest.raises(MigrationError, match="nope"):
        migrate_wide(src, tmp_path / "x.xlsx", id_column="nope", session_column="visit")


def test_no_groups_is_a_migration_error(tmp_path):
    src = _tiny(tmp_path, "id,visit,score\ns1,T0,1\n")
    with pytest.raises(MigrationError) as exc:
        migrate_wide(src, tmp_path / "out.xlsx")
    assert all(c in str(exc.value) for c in ("id", "visit", "score"))


def test_existing_output_is_refused_without_overwrite(tmp_path):
    out = tmp_path / "out.xlsx"
    out.write_bytes(b"keep")
    with pytest.raises(MigrationError, match="exists"):
        migrate_wide(FIXTURE, out)
    assert out.read_bytes() == b"keep"
    migrate_wide(FIXTURE, out, overwrite=True)
    assert _sheet(out, "data")


def test_migrated_template_imports_into_a_project(tmp_path):
    import json

    from src.biosample_import import import_biosample

    out = tmp_path / "out.xlsx"
    rep = migrate_wide(FIXTURE, out)
    root = tmp_path / "proj"
    (root / "code").mkdir(parents=True)
    (root / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": "multiple"}}), encoding="utf-8")
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.10.1", "DatasetType": "raw"}), encoding="utf-8")
    (root / "participants.tsv").write_text("participant_id\nsub-s001\nsub-s002\n", encoding="utf-8")
    smap = {f"T{i}": str(i) for i in range(7)} | {"T4.1": "41", "T4.2": "42"}
    (root / "code" / "session_map.json").write_text(json.dumps(smap), encoding="utf-8")

    res = import_biosample(out, root)
    assert res.errors == []
    visits = {(r["participant_id"], r["session"]) for r in _sheet(out, "data")}
    tsvs = sorted(p for p in res.written if p.endswith(".tsv"))
    assert tsvs == sorted(
        f"sub-{pid}/ses-{smap[ses]}/biosample/sub-{pid}_ses-{smap[ses]}_biosample-bloodhormones_biosample.tsv"
        for pid, ses in visits)
    assert len(tsvs) == rep.rows_read - len(rep.rows_skipped_empty)
    stem = root / "sub-s001/ses-0/biosample/sub-s001_ses-0_biosample-bloodhormones_biosample"
    head, row = stem.with_suffix(".tsv").read_text(encoding="utf-8").splitlines()
    assert dict(zip(head.split("\t"), row.split("\t")))["estradiol"] == "<LOD"
    side = json.loads(stem.with_suffix(".json").read_text(encoding="utf-8"))
    assert side["estradiol"]["LowerLimitOfDetection"] == 5.0
    assert side["Technical"]["SpecimenType"] == "serum"


def test_missing_output_folder_is_refused_and_nothing_created(tmp_path):
    from src.biosample_migrate import migrate_wide

    out = tmp_path / "nope" / "m.xlsx"
    with pytest.raises(MigrationError, match="not a directory"):
        migrate_wide(FIXTURE, out)
    assert not out.parent.exists()


def test_failed_write_with_overwrite_keeps_the_old_file(tmp_path, monkeypatch):
    from openpyxl.workbook.workbook import Workbook

    from src.biosample_migrate import migrate_wide

    out = tmp_path / "m.xlsx"
    out.write_bytes(b"keep")

    def boom(self, filename):
        raise OSError("disk full")

    monkeypatch.setattr(Workbook, "save", boom)
    with pytest.raises(MigrationError, match="cannot write"):
        migrate_wide(FIXTURE, out, overwrite=True)
    assert out.read_bytes() == b"keep"
    assert list(tmp_path.iterdir()) == [out]


# --- Final review fixes ---------------------------------------------------------------


def test_comment_or_unit_without_value_warns_and_is_not_dropped_empty(tmp_path):
    src = _tiny(tmp_path, "Patient No.,Visit,A Results,A Unit,A clin. significant,B Results,B Unit\n"
                          "s1,T0,,,haemolysed,2,mg\ns1,T1,,mg,,3,mg\ns1,T2,,,lipaemic,,\n")
    rep = migrate_wide(src, tmp_path / "out.xlsx")
    assert "s1 T0 A: comment 'haemolysed' has no value, not written" in rep.warnings
    assert "s1 T1 A: unit 'mg' has no value, not written" in rep.warnings
    assert "s1 T2 A: comment 'lipaemic' has no value, not written" in rep.warnings  # skipped row too
    assert "A" not in rep.analytes_dropped_empty and "A" not in rep.analytes_mapped
    assert [r["analyte"] for r in _sheet(tmp_path / "out.xlsx", "data")] == ["B", "B"]


def test_many_comments_without_value_are_one_summary_warning(tmp_path):
    rows = "".join(f"s{i},T0,,bad,1\n" for i in range(20))
    src = _tiny(tmp_path, "id,visit,A Results,A clin. significant,B Results\n" + rows)
    rep = migrate_wide(src, tmp_path / "out.xlsx")
    hits = [w for w in rep.warnings if "no value" in w]
    assert len(hits) == 1 and "20" in hits[0] and "s0 T0 A" in hits[0]


def test_columns_outside_the_groups_are_named_when_not_migrated(tmp_path):
    src = _tiny(tmp_path, "id,visit,Date,Empty,X Unit,A Results,A Results,a results,A Unit\n"
                          "s1,T0,2020-01-01,,mg,1,9,8,mg\n")
    rep = migrate_wide(src, tmp_path / "out.xlsx", id_column="id", session_column="visit")
    assert "columns not migrated: Date, X Unit, A Results.1, a results" in rep.warnings
    assert not any("Empty" in w for w in rep.warnings)


def test_header_names_equal_after_stripping_are_a_migration_error(tmp_path):
    with pytest.raises(MigrationError, match="duplicate column names: A Results"):
        read_legacy_wide(_tiny(tmp_path, "id,visit,A Results,A Results \ns1,T0,1,2\n"))


def test_duplicate_header_names_in_the_quirk_file_are_a_migration_error(tmp_path):
    p = tmp_path / "q.csv"
    p.write_text('"id\tvisit\tA Results\tA Results "\r\n"s1\tT0\t1\t2"\r\n', encoding="utf-8")
    with pytest.raises(MigrationError, match="duplicate column names: A Results"):
        read_legacy_wide(p)


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_unwritable_output_folder_is_a_migration_error(tmp_path):
    folder = tmp_path / "ro"
    folder.mkdir()
    folder.chmod(0o555)
    try:
        if os.access(folder, os.W_OK):
            pytest.skip("process can write to a read-only folder (root?)")
        with pytest.raises(MigrationError, match="cannot write"):
            migrate_wide(FIXTURE, folder / "out.xlsx")
    finally:
        folder.chmod(0o755)


def test_filled_value_with_empty_unit_warns_once_per_analyte(tmp_path):
    src = _tiny(tmp_path, "id,visit,A Results,A Unit\ns1,T0,1,mg\ns1,T1,2,\ns2,T1,3, \n")
    rep = migrate_wide(src, tmp_path / "out.xlsx")
    hits = [w for w in rep.warnings if w.startswith("A: no unit")]
    assert hits == ["A: no unit in 2 row(s) (e.g. s1 T1, s2 T1); the importer will use the unit of the other rows"]


@pytest.mark.parametrize("name", ["out.csv", "out.xls", "out"])
def test_output_must_be_xlsx(tmp_path, name):
    with pytest.raises(MigrationError, match=r"\.xlsx"):
        migrate_wide(tmp_path / "missing.csv", tmp_path / name)  # refused before the input is read
    assert list(tmp_path.iterdir()) == []


def test_output_suffix_is_case_insensitive(tmp_path):
    migrate_wide(FIXTURE, tmp_path / "out.XLSX")
    assert (tmp_path / "out.XLSX").is_file()


@pytest.mark.skipif(os.name == "nt", reason="POSIX permissions")
def test_output_file_mode_follows_the_umask(tmp_path):
    old = os.umask(0o022)
    try:
        migrate_wide(FIXTURE, tmp_path / "out.xlsx")
    finally:
        os.umask(old)
    assert (tmp_path / "out.xlsx").stat().st_mode & 0o777 == 0o644


def test_id_and_session_cells_are_stripped_only(tmp_path):
    src = _tiny(tmp_path, "id,visit,A Results,A Unit\n s1 , T4.1 ,1,mg\ns1,T4.1,2,mg\n 01 ,01,3,mg\n")
    rep = migrate_wide(src, tmp_path / "out.xlsx")
    assert any("s1 T4.1" in w and "twice" in w for w in rep.warnings)
    rows = _sheet(tmp_path / "out.xlsx", "data")
    assert [(r["participant_id"], r["session"]) for r in rows] == [("s1", "T4.1"), ("s1", "T4.1"), ("01", "01")]
