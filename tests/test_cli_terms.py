"""prism_tools.py terms list|show|suggest: thin adapter over src.term_registry."""

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def _run(*args):
    r = subprocess.run(
        [sys.executable, str(REPO / "prism_tools.py"), "terms", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode, r.stdout


def test_terms_list_shows_seed_terms():
    code, out = _run("list")
    assert code == 0 and "prism:cortisol.saliva" in out


def test_terms_list_json():
    code, out = _run("list", "--json")
    data = json.loads(out)
    assert code == 0 and data["success"] and "prism:cortisol" in [t["TermID"] for t in data["terms"]]


def test_terms_show_prints_units():
    code, out = _run("show", "prism:cortisol.saliva")
    assert code == 0 and "nmol/L" in out


def test_terms_show_accepts_the_bare_slug():
    code, out = _run("show", "cortisol", "--json")
    assert code == 0 and json.loads(out)["term"]["TermID"] == "prism:cortisol"


def test_terms_show_unknown_id_exits_1():
    code, out = _run("show", "prism:nope", "--json")
    assert code == 1 and json.loads(out)["success"] is False


def test_terms_suggest_cort_points_to_cortisol():
    code, out = _run("suggest", "cort", "--specimen", "saliva", "--json")
    data = json.loads(out)
    assert code == 0 and data["kind"] == "suggestion" and data["similar"] == ["prism:cortisol"]


def test_terms_suggest_unknown_column():
    code, out = _run("suggest", "zzz_marker", "--json")
    data = json.loads(out)
    assert code == 0 and data["kind"] == "unknown" and data["similar"] == []
