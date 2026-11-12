import argparse
import os
import sys

import pytest
from openpyxl import load_workbook

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app"))

from src.cli.commands.biosample import (  # noqa: E402
    cmd_biosample_import,
    cmd_biosample_migrate_wide,
    cmd_biosample_template,
)
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


def test_cli_refuses_missing_project(tmp_path, capsys):
    book = tmp_path / "t.xlsx"
    cmd_biosample_template(argparse.Namespace(output=str(book)))
    missing = tmp_path / "typo"
    with pytest.raises(SystemExit) as exc:
        cmd_biosample_import(_import_args(book, missing))
    assert exc.value.code != 0
    assert f"{missing}: not a directory" in capsys.readouterr().err
    assert not missing.exists()


LEGACY = os.path.join(os.path.dirname(__file__), "data", "biosample", "legacy_wide_blood.csv")


def _migrate_args(out, **kw):
    base = dict(input=LEGACY, output=str(out), panel="bloodhormones", specimen=None,
                id_column=None, session_column=None, overwrite=False)
    return argparse.Namespace(**{**base, **kw})


def test_cli_migrate_wide_writes_the_template_and_prints_the_report(tmp_path, capsys):
    out = tmp_path / "m.xlsx"
    cmd_biosample_migrate_wide(_migrate_args(out))
    text = capsys.readouterr().out
    assert out.is_file()
    assert text.startswith(f"Wrote {out}")
    assert "Data rows written:" in text
    assert "Assumptions:\n  " in text and "serum" in text


def test_cli_migrate_wide_refuses_an_existing_output(tmp_path, capsys):
    out = tmp_path / "m.xlsx"
    out.write_bytes(b"keep")
    with pytest.raises(SystemExit) as exc:
        cmd_biosample_migrate_wide(_migrate_args(out))
    assert exc.value.code == 1
    assert out.read_bytes() == b"keep"
    assert "Error: " in capsys.readouterr().err


def test_cli_migrate_wide_error_exits_nonzero(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cmd_biosample_migrate_wide(_migrate_args(tmp_path / "m.xlsx", input=str(tmp_path / "nope.csv")))
    assert exc.value.code == 1
    assert capsys.readouterr().err.startswith("Error: ")


def test_cli_migrate_wide_parser_defaults_equal_the_function_defaults():
    import inspect

    from src.biosample_migrate import migrate_wide
    from pathlib import Path

    from src.cli.parser import build_prism_tools_parsers

    parser, _ = build_prism_tools_parsers(Path(__file__).resolve().parent.parent)
    args = parser.parse_args(["biosample", "migrate-wide", "--input", "a", "--output", "b"])
    for name, p in inspect.signature(migrate_wide).parameters.items():
        if name not in ("input_path", "output_path"):
            assert getattr(args, name) == p.default, name
