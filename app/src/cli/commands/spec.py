"""Specification commands for prism_tools: the project's own, not yet official terms, and sharing them."""

from __future__ import annotations

import json
import sys

from src.spec_overlay import (
    OverlayError,
    add_local_term,
    list_local_items,
    proposal_for_local_term,
    remove_local_terms,
)
from src.term_proposal import deliver_proposal


def _emit(args, payload: dict, text: str) -> None:
    print(json.dumps(payload, ensure_ascii=False) if getattr(args, "json", False) else text)


def _fail(args, message: str, **extra) -> None:
    _emit(args, {"success": False, "error": message, **extra}, f"Error: {message}")
    sys.exit(1)


def cmd_spec_local_list(args) -> None:
    """List the project's local specification items."""
    items = list_local_items(args.project, args.modality)
    lines = [f"{i['status']}\t{i['id'] or i['path']}\t{i.get('label') or i.get('problem', '')}" for i in items]
    _emit(args, {"success": True, "items": items}, "\n".join(lines) or "no local specification items")


def cmd_spec_local_add_term(args) -> None:
    """Make the metric of a column a local term of this project, so it validates now."""
    try:
        result = add_local_term(
            args.project, column=args.column, data_file=args.data, sidecar_file=args.sidecar,
            label=args.label, modality=args.modality,
        )
    except OverlayError as exc:
        _fail(args, str(exc))
    ids = [term["TermID"] for term in result["proposal"]["terms"]]
    written = [str(path) for path in result["written"]]
    _emit(
        args,
        {"success": True, "proposal": result["proposal"], "written": written},
        f"Added to this project: {', '.join(ids)}\n  " + "\n  ".join(written)
        + f'\nThe validator uses it from now on. To share it with the PRISM community: '
        f'python prism_tools.py spec propose --project "{args.project}" --term {ids[0]}',
    )


def cmd_spec_local_remove(args) -> None:
    """Remove a local term (and, for a parent, its local children)."""
    try:
        removed = remove_local_terms(args.project, args.modality, args.term)
    except OverlayError as exc:
        _fail(args, str(exc))
    paths = [str(path) for path in removed]
    _emit(args, {"success": True, "removed": paths}, "Removed:\n  " + "\n  ".join(paths))


def cmd_spec_propose(args) -> None:
    """Share a local term: build its proposal and (with --open) open the prefilled form. Sends nothing itself."""
    try:
        result = proposal_for_local_term(args.project, args.term, args.modality)
    except OverlayError as exc:
        _fail(args, str(exc))
    if result["problems"]:
        _fail(
            args, "the proposal does not pass the specification checks: " + "; ".join(result["problems"]),
            proposal=result["proposal"], problems=result["problems"],
        )
    delivered = deliver_proposal(result["proposal"], out=args.out, open_browser=args.open)
    _emit(
        args,
        {
            "success": True, "proposal": result["proposal"], "issue_url": delivered["issue_url"],
            "opened": delivered["opened"], "saved": str(delivered["saved"]) if delivered["saved"] else None,
            "problems": [],
        },
        delivered["text"],
    )
