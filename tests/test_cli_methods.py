"""CLI: methods generate (md/html/docx/tex)."""

import json
import sys
import zipfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

PROJECT = {
    "Basics": {"Name": "Demo", "Authors": ["A. Author"], "Keywords": ["stress"]},
    "StudyDesign": {"Type": "cross-sectional", "Timepoints": "single"},
    "TaskDefinitions": {"ads": {"modality": "survey", "description": "Distress scale"}},
}


def _run_cli(argv):
    from src.cli.entrypoint import main

    old = sys.argv
    sys.argv = ["prism_tools.py", *argv]
    try:
        main()
    finally:
        sys.argv = old


@pytest.fixture
def project(tmp_path):
    (tmp_path / "project.json").write_text(json.dumps(PROJECT), encoding="utf-8")
    return tmp_path


def test_tex_output_file(project):
    out = project / "m.tex"
    _run_cli(["methods", "generate", "--project", str(project), "--format", "tex", "--output", str(out)])
    assert out.read_text(encoding="utf-8").startswith("\\documentclass")


def test_md_prints_to_stdout(project, capsys):
    _run_cli(["methods", "generate", "--project", str(project)])
    assert "cross sectional design" in capsys.readouterr().out


def test_docx_requires_output(project, capsys):
    with pytest.raises(SystemExit) as exc:
        _run_cli(["methods", "generate", "--project", str(project), "--format", "docx"])
    assert exc.value.code == 2
    assert "--output" in capsys.readouterr().out


def test_docx_written(project):
    pytest.importorskip("docx")
    out = project / "m.docx"
    _run_cli(["methods", "generate", "--project", str(project), "--format", "docx", "--output", str(out)])
    assert zipfile.is_zipfile(out)


def test_missing_project_exits_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        _run_cli(["methods", "generate", "--project", str(tmp_path)])
    assert exc.value.code == 2


def test_bib_format(project, tmp_path, monkeypatch):
    from src import methods_project

    real = methods_project.build_methods

    def fake(*a, **k):
        r = real(*a, **k)
        r.template_data = {"ads": {"Study": {"References": [{"Citation": "Smith, J. (2020). T."}]}}}
        return r

    monkeypatch.setattr("src.cli.commands.methods.build_methods", fake)
    out = project / "refs.bib"
    _run_cli(["methods", "generate", "--project", str(project), "--format", "bib", "--output", str(out)])
    assert "@misc{smith2020" in out.read_text(encoding="utf-8")
