"""src/ and app/src/ share file names; the coverage XML for Codecov must keep them apart.

coverage writes XML names relative to each ``source`` folder, so with sources ``src`` and
``app/src`` both ``__init__.py`` files became one entry, with one file's data under the
other's name (2026-11-25: the v1.26.2 version bump failed codecov/patch this way).
"""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_xml_report_keeps_src_and_app_src_apart(tmp_path):
    pytest.importorskip("coverage")
    env = {k: v for k, v in os.environ.items() if not k.startswith(("COV_CORE", "COVERAGE"))}
    env["COVERAGE_FILE"] = str(tmp_path / ".coverage")
    script = tmp_path / "noop.py"
    script.write_text("")
    report = tmp_path / "coverage.xml"
    for args in (
        ["run", "--source=src,app/src", str(script)],
        ["xml", "-i", "-o", str(report)],
    ):
        subprocess.run([sys.executable, "-m", "coverage", *args], cwd=ROOT, env=env, check=True)

    names = {c.get("filename") for c in ET.parse(report).iter("class")}
    assert {"src/__init__.py", "app/src/__init__.py"} <= names


def test_ci_writes_the_xml_in_its_own_step():
    # pytest-cov's --cov-report=xml uses the --cov folders as sources: the same clash.
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "--cov-report=xml" not in ci
    assert "coverage xml" in ci
