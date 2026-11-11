import argparse
import os
import sys

import pytest
from openpyxl import load_workbook

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app"))

from src.cli.commands.biosample import cmd_biosample_import, cmd_biosample_template  # noqa: E402
from test_biosample_import import STEM, _project  # noqa: E402


def _import_args(book, project):
    return argparse.Namespace(input=str(book), project=str(project), specimen=None,
                              overwrite=False, dry_run=False)


def test_cli_template_then_import_round_trip(tmp_path, capsys):
    book = tmp_path / "t.xlsx"
    cmd_biosample_template(argparse.Namespace(output=str(book)))
    wb = load_workbook(book)
    wb["data"].append(["01", "T1", "hormones", None, "s1", "08:30", "cortisol", 1, "nmol/L", None])
    wb["panels"].append(["hormones", "serum"])
    wb.save(book)
    project = _project(tmp_path)

    cmd_biosample_import(_import_args(book, project))
    assert (project / f"{STEM}.tsv").is_file()
    assert (project / f"{STEM}.json").is_file()

    (tmp_path / "x").mkdir()
    other = _project(tmp_path / "x")
    cmd_biosample_import(argparse.Namespace(input=str(book), project=str(other), specimen=None,
                                            overwrite=False, dry_run=True))
    assert not (other / f"{STEM}.tsv").exists()
    assert f"would write {STEM}.tsv" in capsys.readouterr().out


def test_cli_refuses_without_specimen(tmp_path, capsys):
    book = tmp_path / "t.xlsx"
    cmd_biosample_template(argparse.Namespace(output=str(book)))
    wb = load_workbook(book)
    wb["data"].append(["01", "T1", "hormones", None, "s1", "08:30", "cortisol", 1, "nmol/L", None])
    wb["panels"].append(["hormones"])  # no SpecimenType
    wb.save(book)
    project = _project(tmp_path)
    with pytest.raises(SystemExit) as exc:
        cmd_biosample_import(_import_args(book, project))
    assert exc.value.code != 0
    assert not (project / "sub-01").exists()
