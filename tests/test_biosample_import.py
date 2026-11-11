import datetime as dt
import json
import os
import sys

from openpyxl import Workbook

from src.biosample_import import import_biosample
from src.biosample_template import DATA_COLUMNS, PANEL_COLUMNS

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))


def _book(tmp_path, data, panels=(("hormones", "serum") + (None,) * 8,)):
    wb = Workbook()
    ws = wb.active
    ws.title = "data"
    ws.append(list(DATA_COLUMNS))
    for r in data:
        ws.append(list(r))
    p = wb.create_sheet("panels")
    p.append(list(PANEL_COLUMNS))
    for r in panels:
        p.append(list(r))
    out = tmp_path / "t.xlsx"
    wb.save(out)
    return out


def _row(pid="01", ses="T1", panel="hormones", run=None, sid="s1", t="08:30", analyte="cortisol",
         value=1, unit="nmol/L"):
    return (pid, ses, panel, run, sid, t, analyte, value, unit, None)


def _project(tmp_path, timepoints="multiple", participants=("sub-01", "sub-02")):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.json").write_text(json.dumps({"StudyDesign": {"Timepoints": timepoints}}), encoding="utf-8")
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.10.1", "DatasetType": "raw"}), encoding="utf-8")
    (root / "participants.tsv").write_text("participant_id\n" + "\n".join(participants) + "\n", encoding="utf-8")
    if timepoints == "multiple":
        (root / "code").mkdir()
        (root / "code" / "session_map.json").write_text(json.dumps({"T1": "1", "T2": "2"}), encoding="utf-8")
    return root


STEM = "sub-01/ses-1/biosample/sub-01_ses-1_biosample-hormones_biosample"


def test_writes_one_tsv_and_sidecar_per_subject_session_panel(tmp_path):
    book = _book(tmp_path, [
        _row(), _row(analyte="Free Testosterone", value="<5", unit="pmol/L"),
        _row(sid="s2", t="09:00", value=2), _row(pid="02"), _row(ses="T2"),
    ])
    project = _project(tmp_path)
    res = import_biosample(book, project)
    assert res.errors == []
    assert sorted(res.written) == sorted([
        f"{STEM}.tsv", f"{STEM}.json",
        "sub-02/ses-1/biosample/sub-02_ses-1_biosample-hormones_biosample.tsv",
        "sub-02/ses-1/biosample/sub-02_ses-1_biosample-hormones_biosample.json",
        "sub-01/ses-2/biosample/sub-01_ses-2_biosample-hormones_biosample.tsv",
        "sub-01/ses-2/biosample/sub-01_ses-2_biosample-hormones_biosample.json",
    ])
    assert (project / f"{STEM}.tsv").read_text(encoding="utf-8") == (
        "sample_id\tcollection_time\tcortisol\tfree_testosterone\n"
        "s1\t08:30\t1\t<LOD\n"
        "s2\t09:00\t2\tn/a\n"
    )
    side = json.loads((project / f"{STEM}.json").read_text(encoding="utf-8"))
    assert side["Technical"] == {"SpecimenType": "serum"}
    assert side["Study"] == {"BiosampleName": "hormones"}
    assert side["Metadata"] == {"SchemaVersion": "1.1.0", "CreationDate": dt.date.today().isoformat()}
    assert side["cortisol"] == {"Description": "cortisol", "Units": "nmol/L", "Term": "prism:cortisol.serum"}
    assert side["free_testosterone"]["LowerLimitOfDetection"] == 5.0
    assert side["free_testosterone"]["Term"] == "prism:free-testosterone.serum"


def test_two_runs_give_two_files(tmp_path):
    book = _book(tmp_path, [_row(run=1), _row(run=2, value=3)])
    res = import_biosample(book, _project(tmp_path))
    assert res.errors == []
    assert sorted(p for p in res.written if p.endswith(".tsv")) == [
        "sub-01/ses-1/biosample/sub-01_ses-1_biosample-hormones_run-1_biosample.tsv",
        "sub-01/ses-1/biosample/sub-01_ses-1_biosample-hormones_run-2_biosample.tsv",
    ]


def test_duplicate_measurement_is_an_error(tmp_path):
    book = _book(tmp_path, [_row(), _row(value=2)])
    project = _project(tmp_path)
    res = import_biosample(book, project)
    assert res.written == []
    assert any("rows 2 and 3" in e and "cortisol" in e for e in res.errors), res.errors
    assert not (project / "sub-01").exists()


def test_reader_problems_stop_the_import(tmp_path):
    book = _book(tmp_path, [_row(), _row(panel="other")])
    project = _project(tmp_path)
    res = import_biosample(book, project)
    assert res.written == [] and any("other" in e for e in res.errors)
    assert not (project / "sub-01").exists()


def test_column_without_term_or_unit_is_an_error(tmp_path):
    res = import_biosample(_book(tmp_path, [_row(analyte="mystery", unit=None)]), _project(tmp_path))
    assert res.written == [] and any("mystery" in e for e in res.errors)


def test_unit_differing_from_term_is_an_info(tmp_path):
    res = import_biosample(_book(tmp_path, [_row(unit="ug/dL")]), _project(tmp_path))
    assert res.errors == []
    assert any("ug/dL" in w and "nmol/L" in w for w in res.warnings)


def test_reimport_refused_then_identical_with_overwrite(tmp_path):
    book = _book(tmp_path, [_row(), _row(analyte="crp", value="<0,5", unit="mg/L")])
    project = _project(tmp_path)
    first = import_biosample(book, project)
    assert first.errors == []
    before = {p: (project / p).read_bytes() for p in first.written}

    again = import_biosample(book, project)
    assert again.written == []
    assert sorted(again.skipped) == sorted(first.written)
    assert again.errors and "--overwrite" in again.errors[0]

    forced = import_biosample(book, project, overwrite=True)
    assert forced.errors == []
    assert {p: (project / p).read_bytes() for p in forced.written} == before


def test_unknown_participant_written_with_warning(tmp_path):
    project = _project(tmp_path, participants=("sub-02",))
    before = (project / "participants.tsv").read_text(encoding="utf-8")
    res = import_biosample(_book(tmp_path, [_row()]), project)
    assert res.errors == []
    assert f"{STEM}.tsv" in res.written
    assert any("sub-01" in w and "participants.tsv" in w for w in res.warnings)
    assert (project / "participants.tsv").read_text(encoding="utf-8") == before


def test_dry_run_writes_nothing(tmp_path):
    project = _project(tmp_path)
    res = import_biosample(_book(tmp_path, [_row()]), project, dry_run=True)
    assert res.errors == []
    assert sorted(res.written) == [f"{STEM}.json", f"{STEM}.tsv"]
    assert not (project / "sub-01").exists()


def test_single_timepoint_project_maps_session_and_reports_it(tmp_path):
    project = _project(tmp_path, timepoints="single")
    res = import_biosample(_book(tmp_path, [_row(ses="pre")]), project)
    assert res.errors == []
    assert f"{STEM}.tsv" in res.written
    assert any("'pre'" in w and "ses-1" in w for w in res.warnings)


def test_empty_session_in_multiple_project_is_an_error(tmp_path):
    res = import_biosample(_book(tmp_path, [_row(ses=None)]), _project(tmp_path))
    assert res.written == [] and res.errors


def test_written_files_pass_the_validator(tmp_path):
    from runner import validate_dataset

    book = _book(tmp_path, [
        _row(), _row(analyte="crp", value="<0,5", unit="mg/L"), _row(analyte="mystery", value=4, unit="U/L"),
    ], panels=(("hormones", "serum", "venipuncture", "none", "true", "-80", "Lab", "ELISA", "Kit", "Serum hormones"),))
    project = _project(tmp_path)
    res = import_biosample(book, project)
    assert res.errors == []
    side = json.loads((project / f"{STEM}.json").read_text(encoding="utf-8"))
    assert side["Technical"]["FastingRequired"] is True and side["Technical"]["StorageTemperature"] == -80
    assert side["Study"]["Description"] == "Serum hormones"
    issues, _ = validate_dataset(str(project))
    errors = [i for i in issues if i[0] == "ERROR" and "biosample" in " ".join(str(x) for x in i).lower()]
    assert errors == [], errors


def test_run_must_be_a_number(tmp_path):
    for run in ("a", "T1"):
        (tmp_path / run).mkdir()
        project = _project(tmp_path / run)
        res = import_biosample(_book(tmp_path / run, [_row(run=run)]), project)
        assert res.written == [] and any("row 2" in e and repr(run) in e for e in res.errors), res.errors
        assert not (project / "sub-01").exists()


def test_overwrite_keeps_the_existing_creation_date(tmp_path):
    book = _book(tmp_path, [_row()])
    project = _project(tmp_path)
    first = import_biosample(book, project)
    side = project / f"{STEM}.json"
    data = json.loads(side.read_text(encoding="utf-8"))
    data["Metadata"]["CreationDate"] = "2020-01-02"
    side.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    before = {p: (project / p).read_bytes() for p in first.written}

    forced = import_biosample(book, project, overwrite=True)
    assert forced.errors == []
    assert {p: (project / p).read_bytes() for p in forced.written} == before


def test_missing_project_folder_is_refused(tmp_path):
    book = _book(tmp_path, [_row()])
    missing = tmp_path / "typo"
    res = import_biosample(book, missing)
    assert res.errors == [f"{missing}: not a directory"]
    assert res.written == []
    assert not missing.exists()
