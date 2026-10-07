"""The prism-validator wheel (PyPI): CLI-only, no Studio code, shares the repo version."""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_validator_wheel.py"

# Anything Studio-only: GUI, converters, project/file management, the Studio CLI.
STUDIO_ONLY = (
    "/web/",
    "/cli/",
    "/templates/",
    "/static/",
    "project_manager",
    "participants_backend",
    "batch_convert",
    "converters/survey.py",
    "converters/excel_to_survey",
)


@pytest.fixture(scope="module")
def wheel(tmp_path_factory):
    out = tmp_path_factory.mktemp("wheel")
    subprocess.run([sys.executable, str(BUILD), "--out", str(out)], check=True)
    return next(out.glob("prism_validator-*.whl"))


def test_wheel_has_validator_entry_and_schemas(wheel):
    names = zipfile.ZipFile(wheel).namelist()
    assert "prism_validator/app/prism.py" in names
    assert any(n.startswith("prism_validator/app/schemas/stable/") for n in names)
    assert any(n.endswith("entry_points.txt") for n in names)
    assert "prism_validator/app/src/citation_cff.py" in names
    assert "prism_validator/app/schemas/citation_cff/schema.json" in names


def test_wheel_contains_no_studio_only_files(wheel):
    names = zipfile.ZipFile(wheel).namelist()
    leaked = [n for n in names if any(s in n for s in STUDIO_ONLY)]
    assert not leaked, leaked


def test_wheel_version_is_the_repo_version(wheel):
    src = (ROOT / "src" / "__init__.py").read_text(encoding="utf-8")
    version = re.search(r'__version__ = "([^"]+)"', src).group(1)
    assert wheel.name.startswith(f"prism_validator-{version}-")


def test_installed_wheel_runs_in_clean_venv(wheel, tmp_path):
    venv = tmp_path / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    bindir = venv / ("Scripts" if sys.platform == "win32" else "bin")
    subprocess.run(
        [str(bindir / "python"), "-m", "pip", "install", "-q", str(wheel)], check=True
    )
    exe = str(bindir / "prism-validator")
    version = subprocess.run([exe, "--version"], capture_output=True, text=True)
    assert version.returncode == 0, version.stderr
    # Real validation of an (empty) dataset: exercises the lazy imports too.
    (tmp_path / "ds").mkdir()
    run = subprocess.run([exe, str(tmp_path / "ds")], capture_output=True, text=True)
    assert "Import error" not in run.stdout + run.stderr
    assert "ModuleNotFoundError" not in run.stdout + run.stderr
    assert run.returncode == 1  # validation errors, not a crash
    # A project.json triggers the lazy procedure_validator import (issue #162).
    ds = tmp_path / "ds_project"
    ds.mkdir()
    (ds / "dataset_description.json").write_text(
        '{"Name":"Test","BIDSVersion":"1.9.0","DatasetType":"raw"}'
    )
    (ds / "project.json").write_text(
        '{"name":"Test","Basics":{"DatasetName":"Test"},'
        '"Sessions":[{"id":"ses-1","label":"Session 1","tasks":[]}],"TaskDefinitions":{}}'
    )
    run = subprocess.run([exe, str(ds)], capture_output=True, text=True)
    out = run.stdout + run.stderr
    assert "No module named" not in out, out
    assert "Validation failed with error" not in out, out
    assert run.returncode in (0, 1), out
    # CITATION.cff is validated without Studio code (no bogus PRISM303).
    (ds / "CITATION.cff").write_text(
        "cff-version: 1.2.0\nmessage: m\ntitle: T\n"
        "authors:\n  - family-names: Doe\n    given-names: J\n"
        "version: 1.0.0\ndate-released: 2026-01-01\n"
    )
    run = subprocess.run([exe, str(ds)], capture_output=True, text=True)
    out = run.stdout + run.stderr
    assert "PRISM303" not in out, out
    assert "No module named" not in out, out
    (ds / "CITATION.cff").write_text(
        "cff-version: 1.2.0\nmessage: m\n"
        "authors:\n  - family-names: Doe\n    given-names: J\n"
    )
    run = subprocess.run([exe, str(ds)], capture_output=True, text=True)
    out = run.stdout + run.stderr
    assert "PRISM303" in out and "'title' is a required property" in out, out
    assert "No module named" not in out, out


def test_wheel_metadata_has_pypi_page_fields(wheel):
    zf = zipfile.ZipFile(wheel)
    meta = zf.read(next(n for n in zf.namelist() if n.endswith("/METADATA"))).decode()
    assert "Project-URL: Homepage" in meta
    assert "Project-URL: Issues" in meta
    assert "Classifier: Programming Language :: Python :: 3" in meta
    assert "Classifier: License :: OSI Approved :: GNU Affero" in meta


def test_publish_workflow_tolerates_a_rerun_of_the_same_tag():
    """Re-pushing a tag (to re-run the Studio release) must not turn PyPI's
    'File already exists' into a red failure."""
    wf = (ROOT / ".github" / "workflows" / "pypi-validator.yml").read_text(encoding="utf-8")
    assert "skip-existing: true" in wf
