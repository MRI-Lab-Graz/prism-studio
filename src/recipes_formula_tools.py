"""Check a recipe formula against sample values, and render it as LaTeX.

Both reuse the formula engine's evaluator and allow-lists; nothing here widens what
the engine accepts.
"""

from __future__ import annotations

import ast
import math
import re

from src.recipes_formula_engine import (
    _SAFE_FORMULA_BINOPS,
    _SAFE_FORMULA_CMPOPS,
    _SAFE_FORMULA_FUNCTIONS,
    _SAFE_FORMULA_MATH_FUNCTIONS,
    _SAFE_FORMULA_UNARYOPS,
    _check_safe_power_operands,
    _evaluate_formula_ast,
    _format_numeric_cell,
    _resolve_formula_placeholder,
    _safe_eval_formula_expression,
)

_PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def check_formula(formula: str, items: list[str], values: dict[str, str]) -> dict:
    """Evaluate ``formula`` the way scoring does, for one row of sample ``values``.

    ``values`` are the numbers the formula sees, i.e. after any reverse-coding;
    Transforms.Invert and MinValid are not applied here. As in scoring, one missing
    listed item empties the result even if the formula does not use it."""
    try:
        return _check(str(formula or ""), items, values)
    except Exception as exc:  # e.g. RecursionError on absurdly nested input
        return _fail(f"The formula cannot be calculated ({type(exc).__name__}).")


def _check(expr: str, items: list[str], values: dict[str, str]) -> dict:
    for name in dict.fromkeys(_PLACEHOLDER.findall(expr)):
        if name not in items:
            return _fail(f"{{{name}}} is not in this score's Items list.")
    texts: dict[str, str] = {}
    for name in items:
        token = _resolve_formula_placeholder(name, values, set(), None, None)
        if token is None:
            typed = str(values.get(name) or "").strip()
            if not typed:
                return _fail(f"Type an example value for {name} in the box below the formula to test it.")
            return _fail(f"The example value for {name} ({typed}) is not a number.")
        if token.startswith('"'):  # typed text the engine keeps as a string
            texts.setdefault(name, str(values.get(name)).strip())
        expr = expr.replace(f"{{{name}}}", token)
    result = _safe_eval_formula_expression(expr)
    if result is not None:
        return {"ok": True, "result": _format_numeric_cell(result), "message": ""}
    for name, typed in texts.items():
        return _fail(f"The example value for {name} ({typed}) is not a number.")
    try:  # the engine returns None for every failure; re-run to name the reason
        _evaluate_formula_ast(ast.parse(expr.strip(), mode="eval"))
    except ZeroDivisionError:
        return _fail("Division by zero.")
    except SyntaxError:
        return _fail("The formula is not a valid expression.")
    except (ValueError, OverflowError, TypeError) as exc:
        return _fail(f"The formula cannot be calculated: {exc}")
    return _fail("The formula does not give a finite number.")


def _fail(message: str) -> dict:
    return {"ok": False, "result": None, "message": message}


_BIN = {ast.Add: ("+", 1), ast.Sub: ("-", 1), ast.Mult: (r"\cdot", 2), ast.Mod: (r"\bmod", 2)}
_CMP = {ast.Eq: "=", ast.NotEq: r"\neq", ast.Lt: "<", ast.LtE: r"\leq", ast.Gt: ">", ast.GtE: r"\geq"}
_FUNC = {
    "max": r"\max", "min": r"\min", "sum": r"\sum", "round": r"\operatorname{round}",
    "exp": r"\exp", "log": r"\ln",
}


_ARITY = {"ifelse": (3, 3), "abs": (1, 1), "sqrt": (1, 1), "exp": (1, 1), "log": (1, 2), "round": (1, 2)}


def _name(raw: str) -> str:
    return r"\text{" + raw.replace("\\", "").replace("_", r"\_").replace("{", "").replace("}", "") + "}"


def _prec(node: ast.AST) -> int:
    if isinstance(node, ast.BinOp):
        return _BIN[type(node.op)][1] if type(node.op) in _BIN else 3
    return 9 if not isinstance(node, (ast.BoolOp, ast.Compare, ast.IfExp, ast.UnaryOp)) else 0


def _tex(node: ast.AST, names: dict[str, str]) -> str:  # noqa: C901
    t = lambda n: _tex(n, names)  # noqa: E731
    paren = lambda n, p: rf"\left({t(n)}\right)" if _prec(n) < p else t(n)  # noqa: E731
    if isinstance(node, ast.Expression):
        return t(node.body)
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
            raise ValueError("Unsupported constant")
        return repr(v)
    if isinstance(node, ast.Name):
        if node.id not in names:
            raise ValueError(f"Unknown name {node.id}")
        return _name(names[node.id])
    if isinstance(node, ast.BinOp):
        if type(node.op) not in _SAFE_FORMULA_BINOPS:
            raise ValueError("Unsafe binary operator")
        if isinstance(node.op, ast.Div):
            return rf"\frac{{{t(node.left)}}}{{{t(node.right)}}}"
        if isinstance(node.op, ast.Pow):
            if isinstance(node.right, ast.Constant):
                _check_safe_power_operands(node.right.value)
            return rf"{paren(node.left, 4)}^{{{t(node.right)}}}"
        sym, p = _BIN[type(node.op)]
        right = paren(node.right, p + 1)
        return f"{paren(node.left, p)}{sym}{right}"
    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _SAFE_FORMULA_UNARYOPS:
            raise ValueError("Unsafe unary operator")
        return ("-" if isinstance(node.op, ast.USub) else "+") + paren(node.operand, 2)
    if isinstance(node, ast.Compare):
        if any(type(o) not in _SAFE_FORMULA_CMPOPS for o in node.ops):
            raise ValueError("Unsafe comparison operator")
        out = t(node.left)
        for o, c in zip(node.ops, node.comparators):
            out += _CMP[type(o)] + t(c)
        return out
    if isinstance(node, ast.BoolOp):
        sep = r"\land " if isinstance(node.op, ast.And) else r"\lor "
        return sep.join(rf"\left({t(v)}\right)" for v in node.values)
    if isinstance(node, ast.IfExp):
        return _cases(node.test, node.body, node.orelse, names)
    if isinstance(node, ast.Call):
        return _call(node, names)
    raise ValueError(f"Unsafe expression component: {type(node).__name__}")


def _cases(test, yes, no, names) -> str:
    return (r"\begin{cases}" + _tex(yes, names) + r"&\text{if } " + _tex(test, names)
            + r"\\" + _tex(no, names) + r"&\text{otherwise}\end{cases}")


def _call(node: ast.Call, names) -> str:
    if node.keywords:
        raise ValueError("Keyword arguments are not supported")
    f = node.func
    if isinstance(f, ast.Name) and f.id in _SAFE_FORMULA_FUNCTIONS:
        fname = f.id
    elif (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
          and f.value.id == "math" and f.attr in _SAFE_FORMULA_MATH_FUNCTIONS):
        fname = f.attr
    else:
        raise ValueError("Unsafe function call")
    lo, hi = _ARITY.get(fname, (1, None))
    if len(node.args) < lo or (hi is not None and len(node.args) > hi):
        raise ValueError(f"Wrong number of arguments for {fname}()")
    args = [_tex(a, names) for a in node.args]
    if fname == "ifelse":
        return _cases(node.args[0], node.args[1], node.args[2], names)
    if fname == "sqrt" and len(args) == 1:
        return rf"\sqrt{{{args[0]}}}"
    if fname == "abs" and len(args) == 1:
        return rf"\left|{args[0]}\right|"
    return rf"{_FUNC[fname]}\left({','.join(args)}\right)"


def formula_to_latex(formula: str) -> dict:
    """Render a formula as LaTeX; refuses anything the engine's evaluator refuses."""
    text = str(formula or "")
    names: dict[str, str] = {}

    def swap(m: re.Match) -> str:
        key = f"PRISMITEM{len(names)}"
        names[key] = m.group(1)
        return key

    try:
        return {"ok": True, "latex": _tex(ast.parse(_PLACEHOLDER.sub(swap, text).strip(), mode="eval"), names), "message": ""}
    except SyntaxError:
        msg = "The formula is not a valid expression."
    except ValueError as exc:
        msg = f"The formula cannot be shown: {exc}"
    except Exception as exc:  # e.g. RecursionError, never let the helper raise
        msg = f"The formula cannot be shown ({type(exc).__name__})."
    return {"ok": False, "latex": None, "message": msg}


def validate_formula_args(formula, items=(), values=None) -> str | None:
    """One English sentence when the arguments have the wrong shape, else None (CLI and Studio share it)."""
    if not isinstance(formula, str):
        return "The formula must be a string."
    if not isinstance(items, (list, tuple)) or not all(isinstance(i, str) for i in items):
        return "The items must be a list of strings."
    if not isinstance(values or {}, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in (values or {}).items()
    ):
        return "The values must be an object of strings."
    return None
