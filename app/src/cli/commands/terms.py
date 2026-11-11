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
from src.survey_terms import build_survey_registry, freeze_problems, released_ids, resolve_survey_sidecar, write_released_ids
from src.term_registry import context_value, find_term, load_registry, resolve_column, term_links, term_names


def _emit(args, payload: dict, text: str) -> None:
    print(json.dumps(payload, ensure_ascii=False) if getattr(args, "json", False) else text)


def _registry(modality: str) -> tuple[dict[str, dict], list[str]]:
    """(shipped terms, problems) of a modality; the survey registry is derived from the library and the recipes."""
    return build_survey_registry() if modality == "survey" else (load_registry(modality), [])


def _candidates(registry: dict[str, dict], name: str) -> list[str]:
    """The IDs a name matches by label, alias or equivalent; empty when it is an exact ID or slug (those are not ambiguous)."""
    lowered = name.lower()
    if name in registry or lowered in registry or any(t.get("TermID") == name for t in registry.values()):
        return []
    return sorted(t["TermID"] for key, t in registry.items() if lowered in term_names(key, t))


def cmd_terms_list(args) -> None:
    """List the shipped terms of a modality."""
    registry, problems = _registry(args.modality)
    terms = [registry[key] for key in sorted(registry)]
    lines = [
        f"{t.get('TermID', '?')}\t{t.get('Level', '?')}\t{t.get('Units', t.get('Label', ''))}\t{t.get('Status', '')}"
        for t in terms
    ]
    for problem in problems:
        print(problem, file=sys.stderr)
    _emit(args, {"success": True, "modality": args.modality, "terms": terms, "problems": problems}, "\n".join(lines))


def cmd_terms_freeze(args) -> None:
    """Add the survey IDs that are new to the released list; refuse when a released ID is gone."""
    if args.modality != "survey":
        _emit(args, {"success": False, "error": "only the survey registry is frozen this way"},
              "Error: only the survey registry is frozen this way")
        sys.exit(1)
    registry, problems = build_survey_registry()
    gone = freeze_problems(registry, released_ids())
    if gone:
        _emit(args, {"success": False, "problems": problems + gone}, "\n".join(problems + gone))
        sys.exit(1)
    added = write_released_ids(registry)
    _emit(args, {"success": True, "added": added, "problems": problems},
          "\n".join(problems + [f"added {len(added)} ID(s)"]))


def cmd_terms_resolve(args) -> None:
    """Give each column of a project's survey sidecar its official item ID, or say why it has none."""
    try:
        sidecar = json.loads(Path(args.sidecar).read_text(encoding="utf-8"))
        if not isinstance(sidecar, dict):
            raise ValueError("the sidecar must hold a JSON object")
    except (OSError, ValueError) as exc:
        _emit(args, {"success": False, "error": str(exc)}, f"Error: cannot read {args.sidecar}: {exc}")
        sys.exit(1)
    result = resolve_survey_sidecar(sidecar)
    _emit(args, {"success": True, **result},
          "\n".join(f"{c['column']}\t{c['term'] or '-'}\t{c['reason']}" for c in result["columns"]))


def cmd_terms_show(args) -> None:
    """Show one term by ID, local name, label, alias or equivalent."""
    registry, _problems = _registry(args.modality)
    candidates = _candidates(registry, args.term)
    if len(candidates) > 1:
        message = f"ambiguous term {args.term!r}: " + ", ".join(candidates) + " (use the full ID)"
        _emit(args, {"success": False, "error": message, "candidates": candidates}, f"Error: {message}")
        sys.exit(1)
    found = find_term(registry, args.term)
    if not found:
        _emit(args, {"success": False, "error": f"unknown term: {args.term}"}, f"Error: unknown term: {args.term}")
        sys.exit(1)
    links = term_links(registry, found[1])
    text = json.dumps(found[1], indent=2, ensure_ascii=False)
    if links:
        text += "\nLinks:\n" + "\n".join(f"  {k}: {v['url']} (from {v['from']})" for k, v in links.items())
    _emit(args, {"success": True, "term": found[1], "links": links}, text)


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
    similar = list(resolve_column(registry, args.column, column_def, context_value(sidecar, args.modality)).similar)
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
