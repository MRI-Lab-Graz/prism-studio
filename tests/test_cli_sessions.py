"""CLI: sessions review / set / unset."""

import json
import subprocess
import sys
from pathlib import Path

from tests.lsa_fixtures import make_lsa

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRISM_TOOLS_APP = PROJECT_ROOT / "app" / "prism_tools.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(PRISM_TOOLS_APP), "sessions", *args],
        capture_output=True, text=True, encoding="utf-8", cwd=str(PROJECT_ROOT), timeout=60,
    )


def _project(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    return project


def test_review_lists_every_response_with_its_session(tmp_path):
    result = _run("review", "--input", str(make_lsa(tmp_path)), "--id-column", "token", "--json")

    payload = json.loads(result.stdout)
    by_id = {r["response_id"]: r for r in payload["rows"]}
    assert (by_id["2"]["session"], by_id["2"]["reason"]) == ("1", "auto")
    assert (by_id["1"]["session"], by_id["1"]["reason"]) == (None, "incomplete")
    assert any("No completed response for: b" in w for w in payload["warnings"])


def test_set_then_review_shows_the_override_and_unset_removes_it(tmp_path):
    project = _project(tmp_path)
    source = str(make_lsa(tmp_path))

    assert _run("set", "--project", str(project), "--response", "4", "--session", "pre").returncode == 0
    payload = json.loads(_run("review", "--input", source, "--id-column", "token",
                              "--project", str(project), "--json").stdout)
    row = {r["response_id"]: r for r in payload["rows"]}["4"]
    assert (row["session"], row["reason"]) == ("pre", "override")

    assert _run("unset", "--project", str(project), "--response", "4").returncode == 0
    payload = json.loads(_run("review", "--input", source, "--id-column", "token",
                              "--project", str(project), "--json").stdout)
    assert {r["response_id"]: r for r in payload["rows"]}["4"]["session"] is None


def test_set_needs_skip_or_a_session(tmp_path):
    result = _run("set", "--project", str(_project(tmp_path)), "--response", "4")

    assert result.returncode == 2
    assert "exactly one" in (result.stdout + result.stderr).lower()


def test_review_prints_a_readable_table_without_json(tmp_path):
    result = _run("review", "--input", str(make_lsa(tmp_path)), "--id-column", "token")

    assert result.returncode == 0
    assert "response" in result.stdout and "left out" in result.stdout
