"""Security/safety tests for src/recipes_formula_engine.py's AST-based
Formula evaluator (recipe Scores[].Formula, e.g. "{Q1} - {Q2}").

This module had zero prior test coverage. Recipe JSON files are ordinary
text that can arrive in a shared/uploaded dataset, so the evaluator must
never grant code execution and must never let an adversarial expression
hang the process or exhaust memory — both confirmed real before the fixes
this file pins.
"""

from __future__ import annotations

import time

import pytest

from src.recipes_formula_engine import _safe_eval_formula_expression


@pytest.mark.parametrize(
    "expression",
    [
        '__import__("os").system("echo pwned")',
        'open("/etc/passwd").read()',
        "().__class__.__bases__[0]",
        "[x for x in range(10**9)]",
        "lambda: 1",
        '(lambda: __import__("os"))()',
        "1; import os",
        "globals()",
        "locals()",
        "__builtins__",
        "a:=5",
    ],
)
def test_formula_engine_blocks_code_execution_escapes(expression: str) -> None:
    """None of these must execute anything or raise an uncaught
    exception — the evaluator degrades unsupported expressions to None."""
    assert _safe_eval_formula_expression(expression) is None


@pytest.mark.parametrize(
    "expression",
    [
        "2**99999999",
        "99999**999999999",
        "(-1)**99999999999",
    ],
)
def test_formula_engine_rejects_oversized_exponents_quickly(expression: str) -> None:
    """Regression guard: a recipe Formula is evaluated once per
    participant row. Before the exponent-magnitude guard existed,
    expressions like these took multiple seconds (and grew without
    bound) per call, and `99999**999999999` produced an integer too
    large for float() to convert — raising an uncaught OverflowError
    instead of degrading to None like every other unsupported case."""
    start = time.monotonic()
    result = _safe_eval_formula_expression(expression)
    elapsed = time.monotonic() - start
    assert result is None
    assert elapsed < 1.0, f"formula evaluation took {elapsed:.2f}s, expected < 1s"


def test_formula_engine_allows_realistic_psychometric_exponents() -> None:
    assert _safe_eval_formula_expression("3**2") == 9.0
    assert _safe_eval_formula_expression("2**10") == 1024.0


def test_formula_engine_supports_whitelisted_math_functions() -> None:
    assert _safe_eval_formula_expression("sqrt(16)") == 4.0
    assert _safe_eval_formula_expression("round(3.7)") == 4.0
    assert _safe_eval_formula_expression("max(1, 2, 3)") == 3.0


def test_formula_engine_supports_basic_arithmetic() -> None:
    assert _safe_eval_formula_expression("10 - 4") == 6.0
    assert _safe_eval_formula_expression("2 + 3 * 4") == 14.0


def test_formula_engine_returns_none_for_empty_or_malformed_input() -> None:
    assert _safe_eval_formula_expression("") is None
    assert _safe_eval_formula_expression("   ") is None
    assert _safe_eval_formula_expression("this is not an expression !!") is None
