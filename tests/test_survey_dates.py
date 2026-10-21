"""Survey start dates identify people: no shared export may contain them."""

import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

from src.survey_dates import (  # noqa: E402
    SURVEY_DATE_COLUMN,
    drop_survey_date_sidecar,
    drop_survey_date_tsv,
    has_survey_date,
    strip_survey_dates_in_tree,
)

TSV = "participant_id\tSurveyStartDate\tSurveyStartTime\tq1\nsub-01\t2025-03-04\t10:15:00\t3\n"


def test_drop_column_in_the_middle():
    assert drop_survey_date_tsv(TSV) == "participant_id\tSurveyStartTime\tq1\nsub-01\t10:15:00\t3\n"


def test_drop_column_when_last():
    assert drop_survey_date_tsv("a\tSurveyStartDate\nx\t2025-01-01\n") == "a\nx\n"


def test_tsv_without_the_column_is_unchanged():
    assert drop_survey_date_tsv("a\tb\n1\t2\n") == "a\tb\n1\t2\n"


def test_drop_sidecar_key():
    assert drop_survey_date_sidecar({"SurveyStartDate": {}, "q1": {}}) == {"q1": {}}


def test_has_survey_date(tmp_path):
    (tmp_path / "a.tsv").write_text(TSV, encoding="utf-8")
    (tmp_path / "b.tsv").write_text("a\tb\n1\t2\n", encoding="utf-8")
    assert has_survey_date(tmp_path / "a.tsv") and not has_survey_date(tmp_path / "b.tsv")


def _project(tmp_path: Path) -> Path:
    root = tmp_path / "study"
    survey = root / "sub-001" / "survey"
    survey.mkdir(parents=True)
    (root / "participants.tsv").write_text("participant_id\nsub-001\n", encoding="utf-8")
    (survey / "sub-001_task-x_survey.tsv").write_text(TSV.replace("sub-01", "sub-001"), encoding="utf-8")
    (survey / "sub-001_task-x_survey.json").write_text(
        json.dumps({SURVEY_DATE_COLUMN: {"Units": "date"}, "q1": {}}), encoding="utf-8"
    )
    (root / "task-x_survey.json").write_text(json.dumps({SURVEY_DATE_COLUMN: {}, "q1": {}}), encoding="utf-8")
    return root


@pytest.mark.parametrize("anonymize", [True, False])
def test_zip_export_drops_survey_date(tmp_path, anonymize):
    from src.web.export_project import export_project

    out = tmp_path / "out.zip"
    export_project(
        project_path=_project(tmp_path), output_zip=out, anonymize=anonymize,
        include_derivatives=False, include_code=False, include_analysis=False,
    )
    with zipfile.ZipFile(out) as z:
        names = [n for n in z.namelist() if n.endswith((".tsv", ".json")) and "survey" in n]
        assert names
        for name in names:
            assert SURVEY_DATE_COLUMN not in z.read(name).decode("utf-8"), name
        assert any("SurveyStartTime" in z.read(n).decode("utf-8") for n in names if n.endswith(".tsv"))


@patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
def test_plain_folder_export_drops_survey_date_and_keeps_source(_which, tmp_path):
    from src.project_manager import ProjectManager

    project = _project(tmp_path)
    result = ProjectManager().export_project_to_plain_folder(project, output_root=tmp_path / "exports")
    assert result.get("success"), result
    out = Path(result["output_path"])
    for path in out.rglob("*"):
        if path.is_file() and path.suffix in (".tsv", ".json"):
            assert SURVEY_DATE_COLUMN not in path.read_text(encoding="utf-8"), path
    assert SURVEY_DATE_COLUMN in (project / "sub-001" / "survey" / "sub-001_task-x_survey.tsv").read_text(encoding="utf-8")


def test_strip_replaces_symlink_without_touching_target(tmp_path):
    target = tmp_path / "real.tsv"
    target.write_text(TSV, encoding="utf-8")
    survey = tmp_path / "copy" / "survey"
    survey.mkdir(parents=True)
    link = survey / "sub-01_task-x_survey.tsv"
    link.symlink_to(target)
    assert strip_survey_dates_in_tree(tmp_path / "copy") == 1
    assert not link.is_symlink()
    assert SURVEY_DATE_COLUMN not in link.read_text(encoding="utf-8")
    assert target.read_text(encoding="utf-8") == TSV


def test_phenotype_bridge_drops_survey_date(tmp_path):
    from src.converters.phenotype_export import collect_phenotype_bridge_files

    survey = tmp_path / "sub-01" / "ses-1" / "survey"
    survey.mkdir(parents=True)
    (survey / "sub-01_ses-1_task-x_survey.tsv").write_text(
        "SurveyStartDate\tq1\n2025-03-04\t3\n", encoding="utf-8"
    )
    files = collect_phenotype_bridge_files(tmp_path).files
    assert files
    for f in files:
        assert SURVEY_DATE_COLUMN not in f.dataframe.columns
        assert SURVEY_DATE_COLUMN not in f.sidecar


def _with_ledger(root: Path) -> Path:
    (root / "code").mkdir()
    (root / "code" / "survey_imports.json").write_text(
        '{"responses": {"sub-001": {"ses-1": ["2025-03-04 10:15:00", "seed", "token"]}}}', encoding="utf-8"
    )
    (root / "code" / "analysis.R").write_text("x <- 1\n", encoding="utf-8")
    return root


def test_zip_export_leaves_out_the_survey_import_ledger(tmp_path):
    from src.web.export_project import export_project

    out = tmp_path / "out.zip"
    export_project(
        project_path=_with_ledger(_project(tmp_path)), output_zip=out, anonymize=False,
        include_derivatives=False, include_code=True, include_analysis=False,
    )
    with zipfile.ZipFile(out) as z:
        assert any(n.endswith("analysis.R") for n in z.namelist())
        assert not any(n.endswith("survey_imports.json") for n in z.namelist())


@patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
def test_plain_folder_export_leaves_out_the_survey_import_ledger(_which, tmp_path):
    from src.project_manager import ProjectManager

    project = _with_ledger(_project(tmp_path))
    result = ProjectManager().export_project_to_plain_folder(project, output_root=tmp_path / "exports")
    out = Path(result["output_path"])
    assert (out / "code" / "analysis.R").exists()
    assert not (out / "code" / "survey_imports.json").exists()
