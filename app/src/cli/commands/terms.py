"""Term registry commands for prism_tools: list, show, suggest and propose."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from src.term_proposal import (
    ProposalError,
    build_proposal,
    check_with_specification,
    deliver_proposal,
    load_inherited_sidecar,
)
from src.term_registry import find_term, load_registry, resolve_column


def _emit(args, payload: dict, text: str) -> None:
    print(json.dumps(payload, ensure_ascii=False) if getattr(args, "json", False) else text)


def cmd_terms_list(args) -> None:
    """List the shipped terms of a modality."""
    registry = load_registry(args.modality)
    terms = [registry[key] for key in sorted(registry)]
    lines = [
        f"{t.get('TermID', '?')}\t{t.get('Level', '?')}\t{t.get('Units', t.get('Label', ''))}\t{t.get('Status', '')}"
        for t in terms
    ]
    _emit(args, {"success": True, "modality": args.modality, "terms": terms}, "\n".join(lines))


def cmd_terms_show(args) -> None:
    """Show one term by ID, local name, label, alias or equivalent."""
    found = find_term(load_registry(args.modality), args.term)
    if not found:
        _emit(args, {"success": False, "error": f"unknown term: {args.term}"}, f"Error: unknown term: {args.term}")
        sys.exit(1)
    _emit(args, {"success": True, "term": found[1]}, json.dumps(found[1], indent=2, ensure_ascii=False))


def cmd_terms_suggest(args) -> None:
    """Relate a column name to the registry, as the validator does."""
    res = resolve_column(load_registry(args.modality), args.column, {}, args.specimen)
    similar = ", ".join(res.similar) or "none"
    _emit(
        args,
        {
            "success": True,
            "column": args.column,
            "specimen": args.specimen,
            "kind": res.kind,
            "term": res.term.get("TermID") if res.term else None,
            "similar": list(res.similar),
            "message": res.message,
        },
        f"{args.column}: {res.kind}; similar official terms: {similar}",
    )


def _fail(args, message: str, **extra) -> None:
    _emit(args, {"success": False, "error": message, **extra}, f"Error: {message}")
    sys.exit(1)


def cmd_terms_propose(args) -> None:
    """Build a proposal for a new metric from a sidecar column; send nothing unless --open."""
    if getattr(args, "data", None):
        try:
            sidecar, _path = load_inherited_sidecar(args.data)
        except ProposalError as exc:
            _fail(args, str(exc))
    else:
        try:
            sidecar = json.loads(Path(args.sidecar).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            _fail(args, f"cannot read the sidecar {args.sidecar}: {exc}")
        if not isinstance(sidecar, dict):
            _fail(args, f"the sidecar {args.sidecar} is not a JSON object")
    registry = load_registry(args.modality)
    try:
        proposal = build_proposal(registry, sidecar, args.column, args.label, args.modality)
    except ProposalError as exc:
        _fail(args, str(exc))
    problems = check_with_specification(proposal, registry)
    if problems:
        _fail(args, "the proposal does not pass the specification checks: " + "; ".join(problems), proposal=proposal, problems=problems)
    column_def = sidecar[args.column]
    similar = list(resolve_column(registry, args.column, column_def, sidecar["Technical"]["SpecimenType"]).similar)
    delivered = deliver_proposal(
        proposal, out=getattr(args, "out", None), open_browser=args.open, similar=similar, alias=args.column
    )
    saved = delivered["saved"]
    url, opened, text = delivered["issue_url"], delivered["opened"], delivered["text"]
    _emit(
        args,
        {"success": True, "proposal": proposal, "issue_url": url, "opened": opened, "saved": str(saved) if saved else None,
         "similar": similar, "problems": []},
        text,
    )
