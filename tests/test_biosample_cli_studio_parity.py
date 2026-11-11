"""Studio's biosample import writes what `prism_tools biosample import` writes (THE RULE, CLAUDE.md)."""

import argparse
import io
import os
import shutil
import sys
from pathlib import Path

from flask import Flask
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from src.biosample_import import ImportResult  # noqa: E402
from src.cli.commands.biosample import cmd_biosample_import, cmd_biosample_template  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402
from test_biosample_import import _project  # noqa: E402

FLAGS = ("specimen", "overwrite", "dry_run")


def _app():
    from src.web.blueprints.conversion import conversion_bp

    app = Flask(__name__, root_path=str(ROOT / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(conversion_bp)  # the routes Studio serves
    return app


def _book(tmp_path):
    book = tmp_path / "filled.xlsx"
    cmd_biosample_template(argparse.Namespace(output=str(book)))
    wb = load_workbook(book)
    wb["data"].append(["01", "T1", "hormones", None, "s1", "08:30", "cortisol", 1, "nmol/L", None])
    wb["data"].append(["01", "T1", "hormones", None, "s1", "08:30", "dhea", 2, "nmol/L", None])
    wb["panels"].append(["hormones"])  # SpecimenType left empty: --specimen fills it
    wb.save(book)
    return book


def _files(project: Path) -> dict[str, bytes]:
    return {p.relative_to(project).as_posix(): p.read_bytes() for p in sorted(project.rglob("*")) if p.is_file()}


def _import_parser():
    _root, parsers = build_prism_tools_parsers(ROOT / "app")
    sub = [a for a in parsers["biosample"]._actions if isinstance(a, argparse._SubParsersAction)][0]
    return sub.choices["import"]


def test_studio_and_cli_write_the_same_files(tmp_path, capsys):
    book = _book(tmp_path)
    cli_project = _project(tmp_path)
    studio_project = tmp_path / "studio"
    shutil.copytree(cli_project, studio_project)
    capsys.readouterr()

    cmd_biosample_import(argparse.Namespace(input=str(book), project=str(cli_project), specimen="serum",
                                            overwrite=False, dry_run=False))
    cli_out = capsys.readouterr()

    with _app().test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(studio_project)
        response = client.post(
            "/api/biosample-import",
            data={"file": (io.BytesIO(book.read_bytes()), book.name), "specimen": "serum",
                  "overwrite": "false", "dry_run": "false"},
            content_type="multipart/form-data",
        )

    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    result = response.get_json()
    assert result["written"] and not result["errors"]
    assert _files(studio_project) == _files(cli_project)
    assert cli_out.out.splitlines() == [f"Warning: {w}" for w in result["warnings"]] + result["written"]
    assert cli_out.err.splitlines() == [f"Error: {e}" for e in result["errors"]]


def test_studio_option_defaults_match_cli_flags(tmp_path, monkeypatch):
    from src.web.blueprints import conversion_biosample_handlers as handlers

    received = {}

    def fake_import(input_path, project, specimen=None, overwrite=False, dry_run=False):
        received.update(specimen=specimen, overwrite=overwrite, dry_run=dry_run)
        return ImportResult()

    monkeypatch.setattr(handlers, "import_biosample", fake_import)
    project = _project(tmp_path)
    with _app().test_client() as client:
        with client.session_transaction() as sess:
            sess["current_project_path"] = str(project)
        response = client.post("/api/biosample-import", data={"file": (io.BytesIO(b"x"), "t.xlsx")},
                               content_type="multipart/form-data")
    assert response.status_code == 200, response.get_data(as_text=True)[:300]
    cli_defaults = {a.dest: a.default for a in _import_parser()._actions if a.dest in FLAGS}
    assert received == cli_defaults

    # the page starts with the same values: nothing checked, no specimen chosen
    app = _app()
    with app.test_request_context():
        from flask import render_template_string

        html = render_template_string("{% include 'converter_biosample.html' %}",
                                      biosample_specimen_types=["serum", "plasma"])
    for box in ("biosampleOverwrite", "biosampleDryRun"):
        tag = html[html.index(f'id="{box}"'):].split(">", 1)[0]
        assert "checked" not in tag
    assert "selected" not in html.split('id="biosampleSpecimen"', 1)[1].split("</select>", 1)[0]


def test_template_download_is_the_workbook(tmp_path):
    with _app().test_client() as client:
        response = client.get("/api/biosample-template")
    assert response.status_code == 200
    wb = load_workbook(io.BytesIO(response.data))
    assert wb.sheetnames == ["data", "panels"]
