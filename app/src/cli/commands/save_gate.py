"""prism_tools save-gate: thin adapter over src.save_gate (the git pre-commit hook calls --check)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.save_gate import (
    SAVE_GATE_MARKER,
    audit_save,
    check_save,
    has_save_hook,
    install_save_hooks,
)
from src.share_publish import _dataset_roots

_MAX_LISTED = 20


def _emit(args, payload: dict, text: str, code: int) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False) if args.json else text)
    sys.exit(code)


def _fail(args, message: str) -> None:
    _emit(args, {"errors": [message]}, message, 2)


def cmd_save_gate(args) -> None:
    root = Path(args.project)
    if args.check:
        check = check_save(root)
        audit_save(root, check)
        text = ""
        if not check.allowed:
            lines = [f"{SAVE_GATE_MARKER}: {len(check.errors)} validation error(s). Fix them, then save."]
            lines += [f"  - {e}" for e in check.errors[:_MAX_LISTED]]
            text = "\n".join(lines)
        # 1 = refused for validation errors; 2 = anything else (git_error, validator_crash)
        code = 0 if check.allowed else 1 if check.reason == "validation_errors" else 2
        _emit(args, {"allowed": check.allowed, "reason": check.reason, "errors": check.errors}, text, code)
    if args.install_hooks:
        try:
            result = install_save_hooks(root)
        except Exception as exc:
            _fail(args, f"{root}: {exc}")
        result.setdefault("errors", [])
        problems = result["foreign"] or result["errors"]
        text = f"Installed in {len(result['installed'])} dataset(s)." + (
            f" Left alone (foreign hook or error): {', '.join([*result['foreign'], *result['errors']])}" if problems else ""
        )
        _emit(args, result, text, 2 if problems else 0)
    if args.status:
        try:
            roots = _dataset_roots(root)
        except Exception as exc:
            _fail(args, f"{root}: {exc}")
        # a dataset is a git working tree; a missing or plain folder is an error, not "NO HOOK"
        errors = [f"{r}: not a git repository" for r in roots if not (r / ".git").exists()]
        if errors:
            _emit(args, {"datasets": {}, "errors": errors}, "\n".join(errors), 2)
        datasets = {str(r): has_save_hook(r) for r in roots}
        text = "\n".join(f"{'hook' if ok else 'NO HOOK'}  {path}" for path, ok in datasets.items())
        _emit(args, {"datasets": datasets, "errors": []}, text, 0)
    _fail(args, "Choose one of --check, --install-hooks, --status.")
