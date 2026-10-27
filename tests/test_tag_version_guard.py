"""A pushed `v*` tag that is not the package version (a spec tag typed in the
wrong repo, 2026-10-27) must stop every tag-triggered workflow before it
publishes anything (PyPI, ghcr.io image, release page)."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ci" / "check_tag_version.py"
WORKFLOWS = ROOT / ".github" / "workflows"


def _run(tag):
    return subprocess.run(
        [sys.executable, str(SCRIPT), tag], capture_output=True, text=True
    ).returncode


def _version():
    spec = importlib.util.spec_from_file_location("v", ROOT / "src" / "__init__.py")
    import re

    return re.search(
        r'__version__ = "([^"]+)"', (ROOT / "src" / "__init__.py").read_text()
    ).group(1)


def test_current_version_tag_passes():
    assert _run(f"v{_version()}") == 0


@pytest.mark.parametrize("tag", ["v1.4.1", "1.22.0", "v0.0.0", ""])
def test_other_tags_fail(tag):
    assert _run(tag) != 0


def _tag_triggered():
    for wf in sorted(WORKFLOWS.glob("*.yml")):
        data = yaml.safe_load(wf.read_text(encoding="utf-8"))
        on = data.get("on", data.get(True)) or {}
        if "tags" in (on.get("push") or {}):
            yield wf.name, data


@pytest.mark.parametrize("name,data", list(_tag_triggered()), ids=lambda x: x if isinstance(x, str) else "")
def test_every_tag_workflow_runs_the_guard_first(name, data):
    for job in data["jobs"].values():
        if "needs" in job:
            continue
        steps = [
            s
            for s in job["steps"]
            if not s.get("uses", "").startswith(("actions/checkout", "actions/setup-python"))
        ]
        first = steps[0]
        assert "check_tag_version.py" in first.get("run", ""), (name, first)
