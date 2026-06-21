from __future__ import annotations

import ast
import json
import math
import operator
from typing import Any

_SAFE_FORMULA_BINOPS: dict[type[ast.operator], Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Real psychometric/biometric formulas never need exponents beyond a handful
# (squaring, cubing, BMI-style ratios). Recipe Formula strings are ordinary
# JSON text that can arrive in a shared/uploaded dataset, and this engine
# evaluates each one once per participant row — an unbounded exponent like
# `99999 ** 999999999` is a real, confirmed CPU/memory exhaustion vector
# (multi-second hang on a single call, multiplied by every row scored),
# even though the AST whitelist already blocks code-injection escapes.
_MAX_FORMULA_POW_EXPONENT_MAGNITUDE = 1000


def _check_safe_power_operands(exponent: Any) -> None:
    try:
        exponent_value = abs(float(exponent))
    except (TypeError, ValueError, OverflowError):
        raise ValueError("Unsafe exponent") from None
    if exponent_value > _MAX_FORMULA_POW_EXPONENT_MAGNITUDE:
        raise ValueError(
            "Exponent magnitude exceeds the safe limit "
            f"({_MAX_FORMULA_POW_EXPONENT_MAGNITUDE})"
        )

_SAFE_FORMULA_UNARYOPS: dict[type[ast.unaryop], Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_SAFE_FORMULA_CMPOPS: dict[type[ast.cmpop], Any] = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
}

_SAFE_FORMULA_BOOLOPS: dict[type[ast.boolop], Any] = {
    ast.And: all,
    ast.Or: any,
}

_SAFE_FORMULA_FUNCTIONS: dict[str, Any] = {
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sum": sum,
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
    "ifelse": lambda condition, true_value, false_value: (
        true_value if bool(condition) else false_value
    ),
}

_SAFE_FORMULA_MATH_FUNCTIONS: dict[str, Any] = {
    "sqrt": math.sqrt,
    "exp": math.exp,
    "log": math.log,
}


def _evaluate_formula_ast(node: ast.AST) -> Any:
    if isinstance(node, ast.Expression):
        return _evaluate_formula_ast(node.body)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float, str)):
            raise ValueError("Unsupported constant")
        return node.value

    ast_num = getattr(ast, "Num", None)
    if ast_num is not None and isinstance(node, ast_num):
        return node.n

    if isinstance(node, ast.BinOp):
        op = _SAFE_FORMULA_BINOPS.get(type(node.op))
        if op is None:
            raise ValueError("Unsafe binary operator")
        left = _evaluate_formula_ast(node.left)
        right = _evaluate_formula_ast(node.right)
        if isinstance(node.op, ast.Pow):
            _check_safe_power_operands(right)
        return op(left, right)

    if isinstance(node, ast.UnaryOp):
        op = _SAFE_FORMULA_UNARYOPS.get(type(node.op))
        if op is None:
            raise ValueError("Unsafe unary operator")
        operand = _evaluate_formula_ast(node.operand)
        return op(operand)

    if isinstance(node, ast.Compare):
        if not node.ops or len(node.ops) != len(node.comparators):
            raise ValueError("Invalid comparison expression")
        left = _evaluate_formula_ast(node.left)
        for op_node, comparator in zip(node.ops, node.comparators):
            op = _SAFE_FORMULA_CMPOPS.get(type(op_node))
            if op is None:
                raise ValueError("Unsafe comparison operator")
            right = _evaluate_formula_ast(comparator)
            if not op(left, right):
                return False
            left = right
        return True

    if isinstance(node, ast.BoolOp):
        op = _SAFE_FORMULA_BOOLOPS.get(type(node.op))
        if op is None:
            raise ValueError("Unsafe boolean operator")
        values = [_evaluate_formula_ast(value) for value in node.values]
        return op(bool(v) for v in values)

    if isinstance(node, ast.IfExp):
        test = _evaluate_formula_ast(node.test)
        if bool(test):
            return _evaluate_formula_ast(node.body)
        return _evaluate_formula_ast(node.orelse)

    if isinstance(node, ast.List):
        return [_evaluate_formula_ast(element) for element in node.elts]

    if isinstance(node, ast.Tuple):
        return tuple(_evaluate_formula_ast(element) for element in node.elts)

    if isinstance(node, ast.Call):
        if node.keywords:
            raise ValueError("Keyword arguments are not supported")

        function = None
        if isinstance(node.func, ast.Name):
            function = _SAFE_FORMULA_FUNCTIONS.get(node.func.id)
        elif (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "math"
        ):
            function = _SAFE_FORMULA_MATH_FUNCTIONS.get(node.func.attr)

        if function is None:
            raise ValueError("Unsafe function call")

        args = [_evaluate_formula_ast(arg) for arg in node.args]
        return function(*args)

    raise ValueError(f"Unsafe expression component: {type(node).__name__}")


def _safe_eval_formula_expression(expression: str) -> float | None:
    text = str(expression or "").strip()
    if not text:
        return None

    try:
        parsed = ast.parse(text, mode="eval")
        result = _evaluate_formula_ast(parsed)
    except Exception:
        return None

    if isinstance(result, (list, tuple)) or isinstance(result, bool):
        return None

    try:
        numeric = float(result)
    except (TypeError, ValueError, OverflowError):
        return None

    if not math.isfinite(numeric):
        return None
    return numeric


def _parse_numeric_cell(val: str | None) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "n/a":
        return None
    if ":" in s:
        parts = s.split(":")
        if 2 <= len(parts) <= 3:
            try:
                hh = int(parts[0])
                mm = int(parts[1])
                ss = int(parts[2]) if len(parts) == 3 else 0
                if 0 <= hh <= 48 and 0 <= mm < 60 and 0 <= ss < 60:
                    return float(hh) + float(mm) / 60.0 + float(ss) / 3600.0
            except Exception:
                pass
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _format_numeric_cell(val: Any) -> str:
    if val is None:
        return "n/a"
    try:
        fval = float(val)
        if fval.is_integer():
            return str(int(fval))
        return str(fval)
    except (ValueError, TypeError):
        return str(val)


def _lookup_item_raw_value(item_id: str, data: dict) -> Any:
    raw = data.get(item_id)
    if raw is None and item_id not in data:
        item_id_lower = str(item_id).strip().lower()
        for key, value in data.items():
            if str(key).strip().lower() == item_id_lower:
                raw = value
                break
    return raw


def _get_item_value(
    item_id: str,
    data: dict,
    invert_items: set[str],
    invert_min: Any,
    invert_max: Any,
    item_scales: dict | None = None,
) -> float | None:
    raw = _lookup_item_raw_value(item_id, data)
    v = _parse_numeric_cell(raw)
    if v is None:
        return None
    if item_id in invert_items:
        if item_scales and item_id in item_scales:
            imin = item_scales[item_id].get("min")
            imax = item_scales[item_id].get("max")
        else:
            imin, imax = invert_min, invert_max
        if imin is not None and imax is not None:
            try:
                return float(imax) + float(imin) - float(v)
            except Exception:
                return v
    return v


def _resolve_formula_placeholder(
    item_id: str,
    data: dict,
    invert_items: set[str],
    invert_min: Any,
    invert_max: Any,
    item_scales: dict | None = None,
) -> str | None:
    numeric_value = _get_item_value(
        item_id,
        data,
        invert_items,
        invert_min,
        invert_max,
        item_scales,
    )
    if numeric_value is not None:
        return str(numeric_value)

    raw = _lookup_item_raw_value(item_id, data)
    if raw is None:
        return None

    raw_text = str(raw).strip()
    if not raw_text or raw_text.lower() == "n/a":
        return None

    return json.dumps(raw_text)


def _map_value_to_bucket(val: float, mapping: dict) -> Any:
    for range_str, mapped in mapping.items():
        if "-" in str(range_str):
            try:
                low, high = map(float, str(range_str).split("-"))
                if low <= val <= high:
                    return mapped
            except Exception:
                continue
        else:
            try:
                if float(val) == float(range_str):
                    return mapped
            except Exception:
                continue
    return None


def _calculate_derived_variables(
    derived_cfg: list[dict],
    current_row: dict[str, str],
    invert_items: set[str],
    invert_min: Any,
    invert_max: Any,
    item_scales: dict | None = None,
) -> None:
    for d in derived_cfg:
        d_name = d.get("Name")
        if not d_name:
            continue
        d_method = str(d.get("Method", "max")).strip().lower()
        d_items = [str(i).strip() for i in (d.get("Items") or []) if str(i).strip()]

        d_result = None
        if d_method in {"max", "min", "mean", "avg", "sum"}:
            d_values = []
            for item_id in d_items:
                v = _get_item_value(
                    item_id,
                    current_row,
                    invert_items,
                    invert_min,
                    invert_max,
                    item_scales,
                )
                if v is not None:
                    d_values.append(v)

            if d_values:
                if d_method == "max":
                    d_result = max(d_values)
                elif d_method == "min":
                    d_result = min(d_values)
                elif d_method in ("mean", "avg"):
                    d_result = sum(d_values) / float(len(d_values))
                elif d_method == "sum":
                    d_result = sum(d_values)

        elif d_method == "map":
            mapping = d.get("Mapping") or {}
            source = d.get("Source")
            if not source and d_items:
                source = d_items[0]
            v = (
                _get_item_value(
                    str(source).strip(),
                    current_row,
                    invert_items,
                    invert_min,
                    invert_max,
                    item_scales,
                )
                if source
                else None
            )
            if v is not None and isinstance(mapping, dict) and mapping:
                d_result = _map_value_to_bucket(v, mapping)

        elif d_method == "formula":
            formula = d.get("Formula")
            if formula:
                expr = str(formula)
                any_missing = False
                for item_id in d_items:
                    token = _resolve_formula_placeholder(
                        item_id,
                        current_row,
                        invert_items,
                        invert_min,
                        invert_max,
                        item_scales,
                    )
                    if token is None:
                        any_missing = True
                        break
                    expr = expr.replace(f"{{{item_id}}}", token)
                if not any_missing:
                    d_result = _safe_eval_formula_expression(expr)

        current_row[d_name] = _format_numeric_cell(d_result)


def _calculate_scores(
    scores: list[dict],
    current_row: dict[str, str],
    invert_items: set[str],
    invert_min: Any,
    invert_max: Any,
    item_scales: dict | None = None,
) -> dict[str, str]:
    out: dict[str, str] = {}
    for score in scores:
        name = str(score.get("Name", "")).strip()
        if not name:
            continue
        method = str(score.get("Method", "sum")).strip().lower()
        items = [str(i).strip() for i in (score.get("Items") or []) if str(i).strip()]
        missing = str(score.get("Missing", "ignore")).strip().lower()
        min_valid_raw = score.get("MinValid")
        min_valid: int | None = None
        if isinstance(min_valid_raw, int) and not isinstance(min_valid_raw, bool):
            if min_valid_raw > 0:
                min_valid = min_valid_raw

        values: list[float] = []
        any_missing = False
        for item_id in items:
            v = _get_item_value(
                item_id, current_row, invert_items, invert_min, invert_max, item_scales
            )
            if v is None:
                any_missing = True
            else:
                values.append(v)

        result: float | None = None
        if min_valid is not None and len(values) < min_valid:
            result = None
        elif missing in {"require_all", "all", "strict"} and any_missing:
            result = None
        elif method == "formula":
            formula = score.get("Formula")
            if formula:
                expr = formula
                for item_id in items:
                    token = _resolve_formula_placeholder(
                        item_id,
                        current_row,
                        invert_items,
                        invert_min,
                        invert_max,
                        item_scales,
                    )
                    expr = expr.replace(
                        f"{{{item_id}}}",
                        token if token is not None else "0.0",
                    )
                result = _safe_eval_formula_expression(expr)
        elif method == "map":
            source = score.get("Source")
            mapping = score.get("Mapping")
            if source and mapping:
                val = _get_item_value(
                    source,
                    current_row,
                    invert_items,
                    invert_min,
                    invert_max,
                    item_scales,
                )
                if val is not None:
                    result = _map_value_to_bucket(val, mapping)
        elif method not in {"sum", "mean"}:
            result = None
        elif not values:
            result = None
        else:
            if method == "mean":
                result = sum(values) / float(len(values))
            else:
                result = sum(values)

        formatted_val = _format_numeric_cell(result)
        out[name] = formatted_val
        current_row[name] = formatted_val
    return out