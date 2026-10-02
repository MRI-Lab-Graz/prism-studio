"""prism_tools publish: thin adapter over src.share_publish."""

from __future__ import annotations

import json
import sys

from src.share_publish import (
    HookExistsError,
    check_for_hook,
    install_hook,
    parse_identity,
    publish_to_server,
)


def _emit(args, payload: dict, code: int) -> None:
    if getattr(args, "json", False):
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(payload.get("message", ""))
        for error in payload.get("errors", []):
            print(f"  - {error}")
    sys.exit(code)


def cmd_publish(args) -> None:
    if args.install_hook:
        try:
            hook = install_hook(args.project, args.sibling)
        except HookExistsError as exc:
            _emit(args, {"success": False, "reason": "hook_exists", "errors": [], "message": str(exc)}, 2)
        _emit(args, {"success": True, "reason": "hook_installed", "errors": [], "message": f"Installed {hook}"}, 0)

    if args.check:
        errors = check_for_hook(args.project, args.sibling)
        message = "Valid." if not errors else f"{len(errors)} validation error(s)."
        _emit(args, {"success": not errors, "reason": "valid" if not errors else "validation_errors", "errors": errors, "message": message}, 1 if errors else 0)

    try:
        identity = parse_identity(args.as_identity) if args.as_identity else None
    except ValueError as exc:
        _emit(args, {"success": False, "reason": "bad_identity", "errors": [], "message": str(exc)}, 2)

    result = publish_to_server(args.project, sibling_name=args.sibling, identity=identity)
    code = 0 if result["success"] else 1 if result["reason"] == "validation_errors" else 2
    _emit(args, result, code)
