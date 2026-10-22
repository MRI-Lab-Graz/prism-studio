"""Term registry commands for prism_tools: list, show and suggest."""

from __future__ import annotations

import json
import sys

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
