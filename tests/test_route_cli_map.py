"""THE RULE (CLAUDE.md), route by route: every Studio route that changes something names the CLI command that does the same.

`tests/route_cli_map.json` has one entry per mutating route (endpoint name):
  "cli: <prism_tools command>"   Studio triggers that command (checked against the real parser)
  "prism: <prism.py command>"    the validator entry point
  "exempt: <reason>"             project setup, GUI state, job control, file picker: no CLI by design
  "open"                         no command known yet: a divergence. The count may only shrink.
A new route fails here until it is listed, so a feature cannot ship Studio-only by accident.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP_FILE = Path(__file__).with_name("route_cli_map.json")
MAX_OPEN = 32  # lower this when an "open" route gets its command; never raise it
MUTATING = {"POST", "PUT", "PATCH", "DELETE"}


@pytest.fixture(scope="module")
def mutating_endpoints():
    sys.path.insert(0, str(ROOT / "app"))
    spec = importlib.util.spec_from_file_location("prism_studio_routes", ROOT / "app" / "prism-studio.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # Flask locates app/static via the registered module
    spec.loader.exec_module(module)
    return {r.endpoint for r in module.app.url_map.iter_rules() if r.methods & MUTATING}


@pytest.fixture(scope="module")
def route_map():
    return json.loads(MAP_FILE.read_text(encoding="utf-8"))


def _cli_commands():
    from src.cli.parser import build_prism_tools_parsers

    def walk(parser, prefix=()):
        subs = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
        if not subs:
            yield " ".join(prefix)
        for action in subs:
            for name, sub in action.choices.items():
                yield from walk(sub, prefix + (name,))

    parser, _ = build_prism_tools_parsers(ROOT / "app")
    return set(walk(parser))


def test_every_mutating_route_is_listed(mutating_endpoints, route_map):
    missing = sorted(mutating_endpoints - set(route_map))
    assert not missing, f"new Studio route(s) without a CLI command; add to {MAP_FILE.name}: {missing}"


def test_no_entry_for_a_route_that_is_gone(mutating_endpoints, route_map):
    assert not sorted(set(route_map) - mutating_endpoints)


def test_named_cli_commands_exist(route_map):
    known = _cli_commands()
    bad = {e: v for e, v in route_map.items() if v.startswith("cli: ") and v[5:] not in known}
    assert not bad, bad


def test_every_entry_is_a_known_kind_with_a_reason(route_map):
    bad = {e: v for e, v in route_map.items() if not (v == "open" or v.split(": ", 1)[0] in ("cli", "prism", "exempt") and v.split(": ", 1)[1:] != [""])}
    assert not bad, bad


def test_routes_without_a_command_only_shrink(route_map):
    open_routes = sorted(e for e, v in route_map.items() if v == "open")
    assert len(open_routes) <= MAX_OPEN, f"{len(open_routes)} routes have no CLI command (max {MAX_OPEN}): {open_routes}"
