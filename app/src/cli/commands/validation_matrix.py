"""CLI handler for `prism_tools dataset validation-matrix` (thin adapter over src.validation_matrix)."""

from __future__ import annotations

import contextlib
import json
import sys
from pathlib import Path

from src.validation_matrix import build_clean_project, format_matrix, matrix_problems, run_matrix


def cmd_dataset_validation_matrix(args) -> None:
    """Build a clean control project, inject known defects one at a time and show what the validator reported."""
    output = Path(args.output).resolve()
    if output.exists() and any(output.iterdir()):
        print(f"Error: output folder is not empty: {output}")
        sys.exit(2)
    # the converters print progress; keep stdout clean for --json
    with contextlib.redirect_stdout(sys.stderr if getattr(args, "json", False) else sys.stdout):
        build_clean_project(output)
        result = run_matrix(output)
    problems = matrix_problems(result)
    if getattr(args, "json", False):
        print(json.dumps({**result, "problems": problems}, indent=2, ensure_ascii=False))
    else:
        print(format_matrix(result))
        print(f"\nClean control project kept at: {output}")
        for problem in problems:
            print(f"  ! {problem}")
    if problems:
        sys.exit(1)
