"""Check and write a proposal for new terms (metrics).

A proposal is one JSON document, sent through the "Propose a metric" issue form or saved
to a file with `prism_tools.py terms propose ... --out proposal.json` in PRISM Studio:

  {"modality": "biosample", "terms": [<parent term>, <child term>]}

The issue body is untrusted text: it is parsed as JSON only, size-capped, and every field
is checked against an allow-list before anything is written. File names are derived only
from IDs that passed the slug rule. Stdlib only; reuses scripts/check_terms.py.

Usage:
  term_proposal.py check --terms DIR --schema FILE --out DIR [--file proposal.json]
      reads $ISSUE_BODY unless --file; writes DIR/status, DIR/log and, if ok, DIR/terms/...
  term_proposal.py pr-body        (env ISSUE_NUMBER, LOG_FILE)

Spec: docs/superpowers/specs/2026-10-23-metric-proposal-design.md in prism-studio
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

MAX_BYTES = 20_000
MAX_TERMS = 2
ALLOWED_FIELDS = frozenset(
    "TermID Level Label Aliases Description Parent SpecimenType Units AlternativeUnits "
    "MinValue WarnMaxValue LOINC Equivalents".split()
)
MODALITIES = ("biosample",)
_LOCAL = re.compile(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)?$")
_SECTION = re.compile(r"^### (.+?)\s*$", re.M)
_OPENING_FENCE = re.compile(r"```[A-Za-z]*\n")
_CHECKBOX = re.compile(r"^- \[([ xX])\]", re.M)


class ProposalError(ValueError):
    """The issue does not hold a usable proposal."""


def _sibling(name: str):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).resolve().parent / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_terms = _sibling("check_terms")


def _sections(body: str) -> dict[str, str]:
    parts = _SECTION.split(body)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def extract_proposal(issue_body: str) -> dict:
    """Read the proposal out of an issue-form body; ProposalError says what is wrong."""
    sections = _sections((issue_body or "").replace("\r\n", "\n"))
    boxes = _CHECKBOX.findall(sections.get("Agreements", ""))
    if len(boxes) < 2 or any(b == " " for b in boxes):
        raise ProposalError("Both agreements (licence, no personal data) must be ticked.")
    text = sections.get("Proposal", "").strip()
    opening = _OPENING_FENCE.match(text)
    if opening:  # the form wraps the value in one fence; backticks inside JSON strings are fine
        text = text[opening.end():]
        if not text.rstrip().endswith("```"):
            raise ProposalError("The proposal field must hold exactly one JSON document.")
        text = text.rstrip()[:-3].strip()
    if not text:
        raise ProposalError("The proposal field is empty.")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ProposalError(f"The proposal is larger than {MAX_BYTES} bytes.")
    try:
        proposal = json.loads(text)
    except ValueError as exc:
        raise ProposalError(f"The proposal is not valid JSON: {exc}") from exc
    if not isinstance(proposal, dict):
        raise ProposalError("The proposal must be a JSON object.")
    return proposal


_STRINGS = ("Level", "Label", "Description", "Parent", "SpecimenType", "Units", "LOINC")
_STRING_LISTS = ("Aliases", "AlternativeUnits", "Equivalents")
_NUMBERS = ("MinValue", "WarnMaxValue")


def _type_problems(term: dict, where: str) -> list[str]:
    """Value types: the checks downstream assume them, and a wrong type must be a message, not a crash."""
    problems = []
    for key in _STRINGS:
        if key in term and not isinstance(term[key], str):
            problems.append(f"{where}: {key} must be a string")
    for key in _STRING_LISTS:
        if key in term and not (isinstance(term[key], list) and all(isinstance(v, str) for v in term[key])):
            problems.append(f"{where}: {key} must be a list of strings")
    for key in _NUMBERS:
        if key in term and (isinstance(term[key], bool) or not isinstance(term[key], (int, float))):
            problems.append(f"{where}: {key} must be a number")
    return problems


def _shape_problems(proposal) -> list[str]:
    if not isinstance(proposal, dict):
        return ["the proposal must be a JSON object"]
    problems = []
    if proposal.get("modality") not in MODALITIES:
        problems.append(f"modality must be one of {', '.join(MODALITIES)}")
    terms = proposal.get("terms")
    if not isinstance(terms, list) or not terms:
        return problems + ["terms must be a non-empty list"]
    if len(terms) > MAX_TERMS:
        problems.append(f"a proposal has at most {MAX_TERMS} terms, found {len(terms)}")
    for i, term in enumerate(terms, 1):
        where = f"term {i}"
        if not isinstance(term, dict):
            problems.append(f"{where}: must be a JSON object")
            continue
        for key in sorted(set(term) - ALLOWED_FIELDS):
            hint = " (set by the maintainer's merge)" if key in ("Status", "ReplacedBy") else ""
            problems.append(f"{where}: field {key!r} is not allowed in a proposal{hint}")
        problems += _type_problems(term, where)
        tid = term.get("TermID")
        prefix, _, local = tid.partition(":") if isinstance(tid, str) else ("", "", "")
        if prefix != "prism" or not _LOCAL.fullmatch(local):
            problems.append(f"{where}: TermID {tid!r} must be prism:<lowercase-slug>[.<specimen>]")
    return problems


def check_proposal(proposal: dict, registry: dict[str, dict], specimens: list[str]) -> tuple[list[dict], list[str]]:
    """Return (the new terms with Status "official", problems); checked together with the registry."""
    problems = _shape_problems(proposal)
    if problems:
        return [], problems
    terms = [{**t, "Status": "official"} for t in proposal["terms"]]
    merged = dict(registry)
    for term in terms:
        local = term["TermID"].partition(":")[2]
        if local in merged:
            problems.append(f"{term['TermID']} is already an official term")
        merged[local] = term
    if problems:
        return [], problems
    problems = check_terms.check_registry(merged, specimens)
    return ([] if problems else terms), problems


def write_terms(terms: list[dict], out_dir: Path, modality: str) -> list[Path]:
    """Write one <local>.json per term under out_dir/<modality>/; the local part is re-checked."""
    for term in terms:
        if not _LOCAL.fullmatch(term["TermID"].partition(":")[2]):
            raise ProposalError(f"cannot derive a file name from {term['TermID']!r}")
    folder = Path(out_dir) / modality
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for term in terms:
        path = folder / f"{term['TermID'].partition(':')[2]}.json"
        path.write_text(json.dumps(term, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


def pr_body(issue_number: int, log: str) -> str:
    warnings = [line for line in log.splitlines() if line.startswith("WARNING:")]
    # inline code span: @mentions and links in contributor-controlled text stay inert
    warning_text = "\n".join(f"- `{w.replace(chr(96), chr(39))}`" for w in warnings) or "- none"
    return f"""Generated by the metric proposal bot from #{issue_number}. Closes #{issue_number} when merged. This is a **draft**.

Contents: the proposed term files under `terms/`.

Warnings from the automatic check:
{warning_text}

Maintainer checklist:
- [ ] The ID is sensible and final (IDs are frozen once released); change it before merging if not
- [ ] The contributor's own column name is in `Aliases`
- [ ] Units are UCUM; ranges and LOINC codes are cited or left out (none were invented)
- [ ] CI is green (the bot commit does not start it; push or approve the run)
"""


def _read_proposal(file: Path | None) -> dict:
    if file is None:
        return extract_proposal(os.environ.get("ISSUE_BODY", ""))
    text = file.read_text(encoding="utf-8")
    if len(text.encode("utf-8")) > MAX_BYTES:
        raise ProposalError(f"The proposal is larger than {MAX_BYTES} bytes.")
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ProposalError(f"The proposal is not valid JSON: {exc}") from exc


def _run_check(args) -> int:
    """Always writes a bundle (status, log, terms); a bad proposal is a failed bundle, not a crash."""
    registry, problems = check_terms.load_terms(args.terms)
    terms: list[dict] = []
    modality = "biosample"
    try:
        proposal = _read_proposal(args.file)
        terms, found = check_proposal(proposal, registry, check_terms.specimen_types(args.schema))
        problems += found
        modality = proposal.get("modality", modality) if isinstance(proposal, dict) else modality
    except ProposalError as exc:
        problems.append(str(exc))
    except Exception as exc:  # noqa: BLE001 - the bot must always leave a bundle, or the contributor hears nothing
        problems.append(f"internal error while checking the proposal ({type(exc).__name__}); a maintainer will look at it")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "status").write_text("failed\n" if problems else "ok\n", encoding="utf-8")
    log = "".join(f"ERROR: {p}\n" for p in problems)
    (out / "log").write_text(log, encoding="utf-8")
    if not problems:
        write_terms(terms, out / "terms", modality)
    print(log or "ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--terms", required=True, type=Path)
    check.add_argument("--schema", required=True, type=Path)
    check.add_argument("--out", required=True, type=Path)
    check.add_argument("--file", type=Path)
    sub.add_parser("pr-body")
    args = ap.parse_args(argv)
    if args.command == "pr-body":
        log = Path(os.environ.get("LOG_FILE", "log")).read_text(encoding="utf-8")
        print(pr_body(int(os.environ["ISSUE_NUMBER"]), log))
        return 0
    return _run_check(args)


if __name__ == "__main__":
    sys.exit(main())
