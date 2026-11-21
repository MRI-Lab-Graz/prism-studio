"""Studio keeps only the DataLad parts that need PRISM/BIDS knowledge; syncing, server copies, getting data and
publishing are Worldline Desktop's job (docs/superpowers/plans/2026-11-21-datalad-to-worldline.md)."""

import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# "status" stays: Studio's /api/projects/datalad/state (navbar count and page) runs the same function.
KEPT_DATALAD_COMMANDS = {"doctor", "identity", "enable", "save", "status"}
GONE_ROUTE_PREFIXES = ("/api/projects/datalad-server/",)
GONE_ROUTES = {
    "/api/projects/datalad/put-on-server",
    "/api/projects/datalad/get-data",
    "/api/projects/datalad/open-from-server",
    "/api/projects/datalad/status-deep",
    "/api/projects/datalad/update",
}
KEPT_ROUTES = {
    "/api/projects/datalad/save",
    "/api/projects/datalad/enable",
    "/api/projects/datalad/preflight",
    "/api/projects/datalad/doctor",
    "/api/projects/datalad/state",
    "/api/projects/datalad/remove-scans-tsv",
    "/api/settings/git-identity",
}


@pytest.fixture(scope="module")
def rules():
    sys.path.insert(0, str(ROOT / "app"))
    spec = importlib.util.spec_from_file_location("prism_studio_routes", ROOT / "app" / "prism-studio.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return {r.rule for r in module.app.url_map.iter_rules()}


def _top_level_commands(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    return {}


def test_generic_datalad_commands_are_gone():
    from src.cli.parser import build_prism_tools_parsers

    parser, _ = build_prism_tools_parsers(ROOT / "app")
    top = _top_level_commands(parser)
    assert "publish" not in top
    assert set(_top_level_commands(top["datalad"])) == KEPT_DATALAD_COMMANDS


def test_generic_datalad_routes_are_gone(rules):
    assert not {r for r in rules if r.startswith(GONE_ROUTE_PREFIXES)}
    assert not (GONE_ROUTES & rules)
    assert KEPT_ROUTES <= rules


def test_nothing_in_the_frontend_calls_a_deleted_route():
    """A deleted route must not leave a button behind that calls it."""
    needles = [*GONE_ROUTE_PREFIXES, *GONE_ROUTES, "/api/projects/datalad/get-latest", "prismPublish"]
    found = {}
    for base in (ROOT / "app" / "static" / "js", ROOT / "app" / "templates"):
        for path in base.rglob("*"):
            if path.suffix not in {".js", ".html"} or path.name.endswith(".test.js"):
                continue
            text = path.read_text(encoding="utf-8")
            hits = [n for n in needles if n in text]
            if hits:
                found[str(path.relative_to(ROOT))] = hits
    assert not found, found
