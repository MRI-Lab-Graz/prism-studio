"""The formula help block lives in one place (the template) and its examples must work."""

import ast
import re
from pathlib import Path

import pytest

from src.recipes_formula_tools import check_formula, formula_to_latex

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = (ROOT / "app/templates/recipe_builder.html").read_text(encoding="utf-8")
SCRIPT = (ROOT / "app/static/js/recipe_builder.js").read_text(encoding="utf-8")


def _examples():
    match = re.search(r"\{%\s*set formula_examples = (\[.*?\])\s*%\}", TEMPLATE, re.S)
    assert match, "formula_examples list missing at the top of recipe_builder.html"
    return ast.literal_eval(match.group(1))


def test_template_has_collapsed_help_block_with_examples_and_pointer():
    assert "How formulas and best-of work" in TEMPLATE
    assert re.search(r"help_panel\('How formulas and best-of work',[^%]*false", TEMPLATE)
    assert "for ex in formula_examples" in TEMPLATE
    assert TEMPLATE.count("see 'How formulas and best-of work'") == 1
    assert "docs/RECIPES.md" in TEMPLATE


def test_examples_cover_the_brief():
    formulas = " ".join(ex["formula"] for ex in _examples())
    for needle in ("ybt_ant_left", "leg_length_left", "**2", "ifelse(", "ybt_comp_right"):
        assert needle in formulas


@pytest.mark.parametrize("ex", _examples(), ids=lambda e: e["formula"])
def test_every_example_formula_parses_and_evaluates(ex):
    assert formula_to_latex(ex["formula"])["ok"] is True
    result = check_formula(ex["formula"], ex["items"], ex["values"])
    assert result["ok"] is True, result["message"]


def test_example_value_inputs_have_a_visible_label():
    assert "Example values (to test the formula; the check below uses them)" in SCRIPT
    fill = SCRIPT[SCRIPT.index("function fillSamples()") :]
    fill = fill[: fill.index("const showError")]
    assert "createElement('label')" in fill
    assert "label.textContent = name" in fill
    assert "style.width = '110px'" not in fill
