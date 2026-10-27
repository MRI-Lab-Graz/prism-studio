"""Specification commands for prism_tools: the project's own, not yet official terms, and sharing them."""

from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

from src.spec_overlay import (
    OverlayError,
    add_local_term,
    add_local_values,
    check_modality,
    list_local_items,
    load_local_patches,
    proposal_for_local_terms,
    remove_local_terms,
    remove_local_values,
)
from src.spec_contribute import check_new_kind_name, example_entries, proposal_for_new_kind, proposal_for_new_metric, proposal_for_values, spec_catalog
from src.term_proposal import deliver_proposal, vendored_term_proposal


def _emit(args, payload: dict, text: str) -> None:
    print(json.dumps(payload, ensure_ascii=False) if getattr(args, "json", False) else text)


def _fail(args, message: str, **extra) -> None:
    _emit(args, {"success": False, "error": message, **extra}, f"Error: {message}")
    sys.exit(1)


def cmd_spec_catalog(args) -> None:
    """Print what can be proposed (kinds of data, lists, known measurements); needs no project."""
    catalog = spec_catalog()
    lines = []
    for m in catalog["modalities"]:
        lines.append(m["label"])
        lines += [f"  {x['label']} ({x['field']}): {', '.join(x['values'])}" for x in m["lists"]]
        if m["metrics"]:
            lines.append("  Known measurements: " + ", ".join(t["label"] for t in m["metrics"]))
    _emit(args, {"success": True, **catalog}, "\n".join(lines))


def cmd_spec_example(args) -> None:
    """Print each field of a kind of data with the example value of a library template; needs no project."""
    try:
        result = example_entries(args.modality, args.template)
    except OverlayError as exc:
        _fail(args, str(exc))
    lines = [f"{e['field']}\t{e['example'] if e['example'] is not None else ''}" for e in result["entries"]]
    _emit(args, {"success": True, **result}, "\n".join(lines) or "no fields")


def cmd_spec_local_list(args) -> None:
    """List the project's local specification items."""
    try:
        items = list_local_items(args.project, args.modality)
    except OverlayError as exc:
        _fail(args, str(exc))
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
        f'python prism_tools.py spec propose --project "{args.project}" --term {ids[0]} --modality {args.modality}',
    )


def cmd_spec_local_remove(args) -> None:
    """Remove a local term (and, for a parent, its local children)."""
    try:
        removed = remove_local_terms(args.project, args.modality, args.term)
    except OverlayError as exc:
        _fail(args, str(exc))
    paths = [str(path) for path in removed]
    _emit(args, {"success": True, "removed": paths}, "Removed:\n  " + "\n  ".join(paths))


def cmd_spec_local_add_values(args) -> None:
    """Allow new values of a sidecar field (for example a new SpecimenType) in this project, so it validates now."""
    try:
        result = add_local_values(args.project, args.field, args.value, args.modality)
    except OverlayError as exc:
        _fail(args, str(exc))
    written = str(result["written"]) if result["written"] else None
    skipped = f"\nAlready official, left out: {', '.join(result['skipped'])}" if result["skipped"] else ""
    _emit(
        args,
        {"success": True, "written": written, "skipped": result["skipped"], "patch": result["patch"]},
        (f"Added to this project: {args.field} = {', '.join(v for v in args.value if v not in result['skipped'])}\n  {written}"
         f'\nThe validator uses it from now on. To share it with the PRISM community: '
         f'python prism_tools.py spec propose --project "{args.project}" --patch --modality {args.modality}' if written
         else "Nothing to add: every value is already official.")
        + skipped,
    )


def cmd_spec_local_remove_values(args) -> None:
    """Remove values added with add-values."""
    try:
        result = remove_local_values(args.project, args.field, args.value, args.modality)
    except OverlayError as exc:
        _fail(args, str(exc))
    written = str(result["written"]) if result["written"] else None
    _emit(
        args,
        {"success": True, "removed": result["removed"], "written": written},
        f"Removed from this project: {args.field} = {', '.join(result['removed'])}"
        + ("" if written else " (no additions left: the patch file was removed)"),
    )


def cmd_spec_propose(args) -> None:
    """Share local terms (--term, repeatable, or --all) and schema additions (--patch) in one proposal; --open opens the prefilled form. Sends nothing itself."""
    if not (args.all or args.term or args.patch):
        _fail(args, "say what to share: --term <id> (repeatable), --patch or --all")
    try:
        check_modality(args.modality)
        if args.patch and not load_local_patches(args.project, args.modality)[0]:
            raise OverlayError("this project has no schema additions to share (see: spec local add-values)")
        result = proposal_for_local_terms(
            args.project, None if args.all else args.term or [], args.modality, include_patch=args.patch or args.all
        )
    except OverlayError as exc:
        _fail(args, str(exc))
    _deliver_result(args, result)


def _deliver_result(args, result: dict) -> None:
    """Fail on problems, else save/open/print a proposal result (--out, --open, --json)."""
    if result["problems"]:
        _fail(
            args, "the proposal does not pass the specification checks: " + "; ".join(result["problems"]),
            proposal=result["proposal"], problems=result["problems"],
        )
    delivered = deliver_proposal(result["proposal"], out=args.out, open_browser=args.open, context=result.get("context"))
    _emit(
        args,
        {
            "success": True, "proposal": result["proposal"], "document": delivered["document"],
            "skipped": result["skipped"], "context": result.get("context"), "issue_url": delivered["issue_url"],
            "opened": delivered["opened"], "saved": str(delivered["saved"]) if delivered["saved"] else None,
            "problems": [],
        },
        delivered["text"]
        + (f"\nLeft out, they are covered by official terms: {', '.join(result['skipped'])}" if result["skipped"] else ""),
    )


def _cli_entries(args) -> dict[str, str]:
    """`--entry FIELD=VALUE` (repeatable) as an ordered dict; split on the first `=`."""
    entries = {}
    for item in args.entry or []:
        field, sep, value = item.partition("=")
        if not sep or not field:
            _fail(args, f"--entry {item!r}: use FIELD=VALUE")
        if field in entries:
            _fail(args, f"--entry {field!r} is given twice")
        entries[field] = value
    return entries


def cmd_spec_propose_values(args) -> None:
    """Propose missing choices in a list (for example a new SpecimenType); needs no project. Sends nothing itself."""
    try:
        result = proposal_for_values(
            args.modality, args.field, args.value, entries=_cli_entries(args), not_sure=args.not_sure, closest=args.closest
        )
    except OverlayError as exc:
        _fail(args, str(exc))
    _deliver_result(args, result)


def cmd_spec_propose_metric(args) -> None:
    """Propose a missing measurement (analyte plus its sample-type term); needs no project (--project adds its own sample types). Sends nothing itself."""
    levels = {}
    for item in args.level or []:
        code, sep, label = item.partition("=")
        if not sep or not code:
            _fail(args, f"--level {item!r}: use CODE=LABEL")
        levels[code] = label
    try:
        result = proposal_for_new_metric(
            args.name, args.description, args.units, args.specimen, args.alias, args.modality,
            project_root=args.project,
            entries=_cli_entries(args), not_sure=args.not_sure, closest=args.closest,
            levels=levels or None, cf_standard_name=args.cf_standard_name, group=args.group,
        )
    except OverlayError as exc:
        _fail(args, str(exc))
    _deliver_result(args, result)


def cmd_spec_check_kind_name(args) -> None:
    """Say whether a suggested name for a new kind of data is free (BIDS and PRISM names are not)."""
    try:
        check_new_kind_name(args.name)
    except OverlayError as exc:
        _fail(args, str(exc))
    _emit(args, {"success": True}, f"{args.name}: free to suggest")


def cmd_spec_propose_new_kind(args) -> None:
    """Propose a whole new kind of data from a description and a sample file; needs no project. Sends nothing itself."""
    limit = vendored_term_proposal().MAX_BYTES
    try:
        with open(args.sample, "rb") as handle:
            raw = handle.read(limit + 1)  # an oversize file is refused without reading all of it
    except OSError as exc:
        _fail(args, f"cannot read the sample file: {exc}")
    try:
        # over the limit the read was cut, maybe inside a character: decode loosely, the size check refuses it anyway
        sample = raw.decode("utf-8", errors="replace" if len(raw) > limit else "strict")
    except UnicodeDecodeError:
        _fail(args, f"the sample file {args.sample} is not UTF-8 text")
    try:
        parts = {key: getattr(args, key) for key in ("measured", "device", "holds", "row")}
        result = proposal_for_new_kind(args.description, sample, args.closest, args.name, parts if any(parts.values()) else None)
    except OverlayError as exc:
        _fail(args, str(exc))
    problems, url = result["problems"], result["issue_url"]
    if args.out:
        Path(args.out).write_text(result["text"], encoding="utf-8")
    opened = bool(args.open and not problems and url and webbrowser.open(url))
    how = (
        f"Opened the prefilled form in your browser; paste the sample file into its field:\n{url}" if opened
        else f"To send it, run this again with --open (it opens the prefilled form; paste the sample file into its field):\n{url}" if url and not problems
        else result["note"] or ""
    )
    _emit(
        args,
        {"success": not problems, "problems": problems, "issue_url": url, "text": result["text"], "note": result["note"], "opened": opened},
        "\n".join(["Problems:", *(f"- {p}" for p in problems)]) if problems else f"{result['text']}\n{how}",
    )
    if problems:
        sys.exit(1)
