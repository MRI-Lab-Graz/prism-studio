"""Term registry commands for prism_tools: list, show, suggest and propose."""

from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

from src.term_proposal import (
    ISSUE_REPO,
    ISSUE_TEMPLATE,
    ProposalError,
    build_proposal,
    check_with_specification,
    issue_url,
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
    saved = None
    if getattr(args, "out", None):
        saved = Path(args.out)
        saved.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    url = issue_url(proposal)
    opened = bool(args.open and url and webbrowser.open(url))
    form = f"https://github.com/{ISSUE_REPO}/issues/new?template={ISSUE_TEMPLATE}"
    if opened:
        how = f"Opened the prefilled form in your browser:\n{url}"
    elif args.open and url:
        how = f"Could not open a browser; open this address yourself:\n{url}"
    elif url:
        how = f"To send it, run this again with --open (it opens the prefilled form):\n{url}"
    else:
        how = f"The proposal is too long for a link: open {form} and paste the proposal above into the field."
    text = (
        "Proposal (nothing has been sent unless it says 'Opened' below):\n"
        + json.dumps(proposal, indent=2, ensure_ascii=False)
        + f"\n\nSimilar official terms: {', '.join(similar) or 'none'} (check that none of them is what you mean)."
        + f"\nThe maintainers may choose a different ID or name; \"{args.column}\" is kept as an alias, so your files keep working."
        + (f"\nSaved to {saved} (send this file to a maintainer if you do not use GitHub)." if saved else "")
        + f"\n{how}"
    )
    _emit(
        args,
        {"success": True, "proposal": proposal, "issue_url": url, "opened": opened, "saved": str(saved) if saved else None,
         "similar": similar, "problems": []},
        text,
    )
