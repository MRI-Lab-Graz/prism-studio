"""CLI `recipes formula-check|formula-latex` and the Studio routes give the same JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

APP_ROOT = Path(__file__).resolve().parents[1] / "app"
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

import src.cli.commands.recipes as recipes_cmds  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402

ITEMS = ["a", "b", "c"]
CASES = [
    ("max({a}, {b}) + {c}", ITEMS, {"a": "65", "b": "70", "c": "3"}),  # composite
    ("({a} + {b}) / {c} * 100", ITEMS, {"a": "65", "b": "70", "c": "3"}),  # relative
    ("{zzz} + 1", ITEMS, {"a": "1"}),  # unlisted name
    ("{a} + {b}", ITEMS, {"a": "1"}),  # missing value
    ("__import__('os').system('echo hi')", ITEMS, {}),  # hostile
]


@pytest.fixture()
def client():
    from flask import Flask

    from src.web.blueprints.tools import tools_bp

    app = Flask(__name__, root_path=str(APP_ROOT))
    app.register_blueprint(tools_bp)
    return app.test_client()


def _cli(fn, capsys, **kw) -> dict:
    fn(SimpleNamespace(**kw))
    return json.loads(capsys.readouterr().out)


def test_cli_and_studio_give_the_same_check_and_latex(client, capsys):
    for formula, items, values in CASES:
        cli = _cli(
            recipes_cmds.cmd_recipes_formula_check,
            capsys,
            formula=formula,
            items=",".join(items),
            values=json.dumps(values),
        )
        studio = client.post(
            "/api/recipe-builder/formula-check",
            json={"formula": formula, "items": items, "values": values},
        ).get_json()
        assert cli == studio, formula

        cli = _cli(recipes_cmds.cmd_recipes_formula_latex, capsys, formula=formula)
        studio = client.post("/api/recipe-builder/formula-latex", json={"formula": formula}).get_json()
        assert cli == studio, formula


def test_commands_are_registered():
    parser, _ = build_prism_tools_parsers(APP_ROOT)
    a = parser.parse_args(["recipes", "formula-check", "--formula", "{a}", "--items", "a", "--values", "{}"])
    assert a.kind == "formula-check"
    assert parser.parse_args(["recipes", "formula-latex", "--formula", "{a}"]).kind == "formula-latex"


def test_unreadable_values_exit_1(capsys):
    with pytest.raises(SystemExit) as exc:
        recipes_cmds.cmd_recipes_formula_check(SimpleNamespace(formula="{a}", items="a", values="not json"))
    assert exc.value.code == 1
