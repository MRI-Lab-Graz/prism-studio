"""Per-modality schema version commands for prism_tools."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.modality_versions import (
    ModalityVersionError,
    available_versions,
    current_version,
    freeze_modality,
    modality_names,
    pending_updates,
    pin_modalities,
    pin_present_modalities,
    read_pins,
    update_modality,
)


def _emit(args, payload: dict, text: str) -> None:
    print(json.dumps(payload, ensure_ascii=False) if getattr(args, "json", False) else text)


def _fail(args, message: str) -> None:
    _emit(args, {"success": False, "error": message}, f"Error: {message}")
    sys.exit(1)


def _require_project(args) -> None:
    try:
        ok = isinstance(json.loads(Path(args.project, "project.json").read_text(encoding="utf-8")), dict)
    except (OSError, ValueError):
        ok = False
    if not ok:
        _fail(args, f"{args.project} is not a PRISM project (no readable project.json)")


def cmd_modality_version_status(args) -> None:
    _require_project(args)
    pins, _ = read_pins(args.project)
    pending = pending_updates(args.project)
    lines = [f"{n}: pinned {v}" for n, v in sorted(pins.items())] or ["No modality versions pinned."]
    lines += [f"{n}: {latest} is available (pinned {pinned})" for n, pinned, latest in pending]
    _emit(
        args,
        {"success": True, "pins": pins, "pending": [
            {"modality": n, "pinned": p, "latest": latest} for n, p, latest in pending]},
        "\n".join(lines),
    )


def cmd_modality_version_list(args) -> None:
    try:
        names = [args.name] if args.name else modality_names()
        versions = {n: available_versions(n) for n in names}
    except (ModalityVersionError, OSError) as exc:
        _fail(args, str(exc))
        return
    _emit(args, {"success": True, "versions": versions},
          "\n".join(f"{n}: {', '.join(v)} (latest {current_version(n)})" for n, v in versions.items()))


def cmd_modality_version_pin(args) -> None:
    _require_project(args)
    try:
        new = pin_modalities(args.project, args.names) if args.names else pin_present_modalities(args.project)
    except (ModalityVersionError, OSError) as exc:
        _fail(args, str(exc))
        return
    _emit(args, {"success": True, "pinned": new},
          "\n".join(f"Pinned {n} {v}" for n, v in new.items()) or "Nothing to pin.")


def _change(args, fn, verb: str) -> None:
    _require_project(args)
    try:
        version = fn(args.project, args.name)
    except (ModalityVersionError, OSError) as exc:
        _fail(args, str(exc))
        return
    _emit(args, {"success": True, "modality": args.name, "version": version},
          f"{verb} {args.name}: now {version}")


def cmd_modality_version_update(args) -> None:
    _change(args, update_modality, "Updated")


def cmd_modality_version_freeze(args) -> None:
    _change(args, freeze_modality, "Kept")
