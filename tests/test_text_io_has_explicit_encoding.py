"""Windows text I/O defaults to cp1252 (and CRLF): every text-mode read/write must name its encoding."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED = [*ROOT.joinpath("src").rglob("*.py"), *ROOT.joinpath("app").rglob("*.py"),
           *ROOT.joinpath("scripts").rglob("*.py"), *ROOT.glob("*.py")]


def _text_mode_open(call: ast.Call) -> bool:
    mode = "r"
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        mode = call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    return isinstance(mode, str) and "b" not in mode


def _offenders():
    for path in SCANNED:
        if {"node_modules", "__pycache__", ".venv"} & set(path.parts):
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            keywords = {kw.arg for kw in node.keywords}
            if "encoding" in keywords or None in keywords:  # **kwargs may carry it
                continue
            if isinstance(func, ast.Attribute) and func.attr in {"read_text", "write_text"}:
                if isinstance(func.value, ast.Name) and func.value.id == "CrossPlatformFile":
                    continue
                yield f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
            elif isinstance(func, ast.Name) and func.id == "open" and _text_mode_open(node):
                yield f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"


def test_every_text_file_access_names_its_encoding():
    assert sorted(_offenders()) == []
