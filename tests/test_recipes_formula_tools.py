import pytest

from src.recipes_formula_tools import check_formula, formula_to_latex


def test_check_y_balance_composite():
    r = check_formula("({a}+{b}+{c})/3", ["a", "b", "c"], {"a": "65", "b": "72", "c": "70"})
    assert r["ok"] and r["result"] == "69" and r["message"] == ""


def test_check_relative_composite():
    r = check_formula(
        "({a}+{b})/(2*{leg})*100", ["a", "b", "leg"], {"a": "65", "b": "72", "leg": "90"}
    )
    assert r["ok"] and r["result"] == "76.11111111111111"


def test_check_name_not_in_items():
    r = check_formula("{x}+1", ["a"], {"a": "1"})
    assert not r["ok"] and "{x}" in r["message"] and "Items" in r["message"]


@pytest.mark.parametrize("bad", ["n/a", ""])
def test_check_missing_value(bad):
    r = check_formula("{a}+{b}", ["a", "b"], {"a": "1", "b": bad})
    assert not r["ok"] and r["result"] is None and "b" in r["message"]


@pytest.mark.parametrize("f", ["1/({a}-{a})", "log({a}-{a})"])
def test_check_division_by_zero_and_log_zero(f):
    r = check_formula(f, ["a"], {"a": "3"})
    assert not r["ok"] and r["result"] is None and r["message"]


HOSTILE = ["__import__('os')", "{a}.real", "{a}**99999"]


@pytest.mark.parametrize("f", HOSTILE)
def test_check_refuses_code(f):
    r = check_formula(f, ["a"], {"a": "2"})
    assert not r["ok"] and r["result"] is None and r["message"]


def test_latex_fraction_and_names():
    r = formula_to_latex("({ybt_ant_right}+{ybt_pm_right})/3")
    assert r == {
        "ok": True,
        "latex": r"\frac{\text{ybt\_ant\_right}+\text{ybt\_pm\_right}}{3}",
        "message": "",
    }


def test_latex_power_max_sqrt_ifelse():
    assert formula_to_latex("{a}**2")["latex"] == r"\text{a}^{2}"
    assert formula_to_latex("max({a},{b})")["latex"] == r"\max\left(\text{a},\text{b}\right)"
    assert formula_to_latex("sqrt({a})")["latex"] == r"\sqrt{\text{a}}"
    out = formula_to_latex("ifelse({a}>1,1,0)")["latex"]
    assert r"\begin{cases}" in out and r"\text{a}>1" in out
    assert formula_to_latex("2*({a}+1)")["latex"] == r"2\cdot\left(\text{a}+1\right)"


@pytest.mark.parametrize("f", HOSTILE + ["[1,2]", "open('x')", "{a}<<2"])
def test_latex_rejects_what_engine_rejects(f):
    r = formula_to_latex(f)
    assert not r["ok"] and r["latex"] is None and r["message"]


@pytest.mark.parametrize(
    "f",
    ["ifelse({a}>1,1)", "abs({a},{b})", "max()", "sqrt()", "'x'", "1e400", "{a}+'x'",
     "1+" * 3000 + "1", "-" * 3000 + "1"],
    ids=lambda f: f[:20],
)
def test_latex_never_raises_and_refuses(f):
    r = formula_to_latex(f)
    assert r["ok"] is False and r["latex"] is None and r["message"]


@pytest.mark.parametrize("f", ["1+" * 3000 + "1", "-" * 3000 + "1"], ids=lambda f: f[:5])
def test_check_deep_nesting_is_a_message(f):
    r = check_formula(f, ["a"], {"a": "1"})
    assert r["ok"] is False and r["message"]


def test_check_unused_missing_item_empties_result():
    r = check_formula("{a}*2", ["a", "b"], {"a": "1", "b": ""})
    assert not r["ok"] and r["result"] is None and "b" in r["message"]
