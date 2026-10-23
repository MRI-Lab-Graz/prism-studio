"""Check and write a proposal for new terms (metrics).

A proposal is one JSON document, sent through the "Propose a metric" issue form or saved
to a file with `prism_tools.py terms propose ... --out proposal.json` in PRISM Studio:

  {"modality": "biosample", "terms": [<parent term>, <child term>]}

The issue body is untrusted text: it is parsed as JSON only, size-capped, and every field
is checked against an allow-list before anything is written. File names are derived only
from IDs that passed the slug rule. Stdlib only; reuses scripts/check_terms.py.

Usage:
  term_proposal.py check --terms DIR --schema FILE --out DIR [--file proposal.json] [--repo DIR]
      reads $ISSUE_BODY unless --file; writes DIR/status, DIR/log and, if ok, DIR/files/<repository path>
      for every file the proposal adds or changes (terms; for a schema patch the archive, the stable
      schema and the spec page of the release)
  term_proposal.py pr-body        (env ISSUE_NUMBER, SCHEMA_RELEASE=1 for a schema release)

Spec: docs/superpowers/specs/2026-10-23-metric-proposal-design.md in prism-studio
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

FORMAT_V2 = "prism-proposal/2"
MAX_BYTES = 50_000  # a GitHub issue-form text field holds 65,536 characters
MAX_FILES = 40  # format v2
V1_MAX_TERMS = 2  # format v1
MAX_PROBLEMS = 50
MAX_LINE = 300  # characters per problem line in the log
ALLOWED_FIELDS = frozenset(
    "TermID Level Label Aliases Description Parent SpecimenType Units AlternativeUnits "
    "MinValue WarnMaxValue LOINC Equivalents".split()
)
MODALITIES = ("biosample",)
_LOCAL = re.compile(r"^[a-z][a-z0-9-]{0,62}(\.[a-z][a-z0-9-]{0,62})?$")  # at most 63 characters per segment
_PATCH_PATH = re.compile(r"patches/(?P<modality>[a-z][a-z0-9]*)\.json")
# The repository paths a proposal may add. Later layers (schema patches, new modalities) add theirs here.
_TERM_PATH = re.compile(r"terms/(?P<modality>[a-z][a-z0-9]*)/(?P<stem>[a-z][a-z0-9-]{0,62}(?:\.[a-z][a-z0-9-]{0,62})?)\.json")
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
schema_patch = _sibling("schema_patch")
release_patch = _sibling("release_patch")


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


def _term_problems(term, where: str) -> list[str]:
    """Problems of one proposed term (allowed fields, value types, the TermID rule)."""
    if not isinstance(term, dict):
        return [f"{where}: must be a JSON object"]
    problems = []
    for key in sorted(set(term) - ALLOWED_FIELDS):
        hint = " (set by the maintainer's merge)" if key in ("Status", "ReplacedBy") else ""
        problems.append(f"{where}: field {key!r} is not allowed in a proposal{hint}")
    problems += check_terms.type_problems(term, where)
    tid = term.get("TermID")
    prefix, _, local = tid.partition(":") if isinstance(tid, str) else ("", "", "")
    if prefix != "prism" or not _LOCAL.fullmatch(local):
        problems.append(f"{where}: TermID {tid!r} must be prism:<lowercase-slug>[.<specimen>]")
    return problems


def _normalize_v1(proposal: dict) -> tuple[list[tuple[str, dict]], list[str]]:
    problems = []
    if proposal.get("modality") not in MODALITIES:
        problems.append(f"modality must be one of {', '.join(MODALITIES)}")
    terms = proposal.get("terms")
    if not isinstance(terms, list) or not terms:
        return [], problems + ["terms must be a non-empty list"]
    if len(terms) > V1_MAX_TERMS:
        problems.append(f"a proposal has at most {V1_MAX_TERMS} terms, found {len(terms)}")
    pairs = []
    for i, term in enumerate(terms, 1):
        found = _term_problems(term, f"term {i}")
        problems += found
        if not found and not problems:
            pairs.append((f"terms/{proposal['modality']}/{term['TermID'].partition(':')[2]}.json", term))
    return pairs, problems


def _normalize_v2(proposal: dict) -> tuple[list[tuple[str, dict]], list[str]]:
    problems = []
    if proposal.get("format") != FORMAT_V2:
        problems.append(f"format must be {FORMAT_V2!r}")
    for key in sorted(set(proposal) - {"format", "files"}):
        problems.append(f"field {key!r} is not allowed in a proposal")
    files = proposal.get("files")
    if not isinstance(files, dict) or not files:
        return [], problems + ["files must be a non-empty object of repository path -> term"]
    if len(files) > MAX_FILES:
        problems.append(f"a proposal has at most {MAX_FILES} files, found {len(files)}")
    pairs = []
    for path, term in files.items():
        patch_match = _PATCH_PATH.fullmatch(path) if isinstance(path, str) else None
        match = patch_match or (_TERM_PATH.fullmatch(path) if isinstance(path, str) else None)
        if not match or match["modality"] not in MODALITIES:
            problems.append(f"path {path!r} is not allowed (terms/<{'|'.join(MODALITIES)}>/<id>.json or patches/<{'|'.join(MODALITIES)}>.json)")
            continue
        if patch_match:  # the patch is validated against the schema it targets, in check_proposal
            if isinstance(term, dict):
                pairs.append((path, term))
            else:
                problems.append(f"{path}: must be a JSON object")
            continue
        found = _term_problems(term, path)
        problems += found
        if not found:
            local = term["TermID"].partition(":")[2]
            if local != match["stem"]:
                problems.append(f"{path}: the file name {match['stem']!r} must equal the TermID local part {local!r}")
            else:
                pairs.append((path, term))
    return pairs, problems


def normalize(proposal) -> tuple[list[tuple[str, dict]], list[str]]:
    """The (repository path, term) pairs of a v1 or v2 proposal, and the problems found."""
    if not isinstance(proposal, dict):
        return [], ["the proposal must be a JSON object"]
    pairs, problems = _normalize_v2(proposal) if "files" in proposal or "format" in proposal else _normalize_v1(proposal)
    return ([] if problems else pairs), problems


def split(pairs: list[tuple[str, dict]]) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    """(term pairs, patch pairs) of the files a proposal adds."""
    return [(p, o) for p, o in pairs if p.startswith("terms/")], [(p, o) for p, o in pairs if p.startswith("patches/")]


def _specimens_of(schema: dict) -> list[str]:
    return schema["properties"]["Technical"]["properties"]["SpecimenType"]["enum"]


def check_proposal(
    proposal: dict, registry: dict[str, dict], specimens: list[str], schema: dict | None = None
) -> tuple[list[dict], list[str]]:
    """Return (the new terms with Status "official", problems); checked together with the registry.

    A proposal may carry a schema patch (`patches/<modality>.json`); then `schema`, the schema it targets, is
    required, and the terms are checked against the specimen types of the PATCHED schema.
    """
    pairs, problems = normalize(proposal)
    if problems:
        return [], problems
    term_pairs, patch_pairs = split(pairs)
    for path, patch in patch_pairs:
        if schema is None:
            problems.append(f"{path}: the schema the patch targets is needed to check it")
            continue
        try:
            patched, _notes = schema_patch.apply_patch(schema, patch)
        except ValueError as exc:  # PatchError; scripts load each other by path, so the class is not shared
            problems.append(f"{path}: {exc}")
            continue
        specimens = _specimens_of(patched)
    if problems:
        return [], problems
    terms = [{**term, "Status": "official"} for _path, term in term_pairs]
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


SCHEMA_RELEASE_NOTE = """
This proposal changes a modality schema. The bot prepared the release steps: the previous schema is archived
unchanged, the minor version and `$id` of the stable schema are bumped, and the field tables of the spec page
are regenerated. The stable schema file is edited in place, so its diff shows only the new version, the new
`$id` and the added values or properties; review those, the version bump and the archive copy.
"""


def pr_body(issue_number: int, schema_release: bool = False) -> str:
    return f"""Generated by the metric proposal bot from #{issue_number}. Closes #{issue_number} when merged. This is a **draft**.

Contents: the proposed files (terms under `terms/`{", schema release under `schemas/` and `specs/`" if schema_release else ""}). The automatic check passed (a failing proposal never gets a pull request).
{SCHEMA_RELEASE_NOTE if schema_release else ""}
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
    """Always writes a bundle (status, log, files/<repository path>); a bad proposal is a failed bundle, not a crash."""
    registry, problems = check_terms.load_terms(args.terms)
    terms: list[dict] = []
    term_modalities: list[str] = []
    patches: list[tuple[str, dict]] = []
    try:
        proposal = _read_proposal(args.file)
        schema = json.loads(Path(args.schema).read_text(encoding="utf-8"))
        terms, found = check_proposal(proposal, registry, check_terms.specimen_types(args.schema), schema)
        problems += found
        if not found:
            term_pairs, patches = split(normalize(proposal)[0])
            term_modalities = [_TERM_PATH.fullmatch(path)["modality"] for path, _term in term_pairs]
    except ProposalError as exc:
        problems.append(str(exc))
    except Exception as exc:  # noqa: BLE001 - the bot must always leave a bundle, or the contributor hears nothing
        problems.append(f"internal error while checking the proposal ({type(exc).__name__}); a maintainer will look at it")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    files = out / "files"
    if not problems:
        try:
            for modality in dict.fromkeys(term_modalities):
                write_terms([t for t, m in zip(terms, term_modalities) if m == modality], files / "terms", modality)
            for path, patch in patches:
                release_patch.release(args.repo, files, _PATCH_PATH.fullmatch(path)["modality"], patch)
        except ValueError as exc:  # PatchError / ReleaseError: the proposal cannot be released, and the message says why
            problems.append(str(exc))
            shutil.rmtree(files, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001 - writing must never leave a half bundle that says ok
            problems.append(f"internal error while writing the files ({type(exc).__name__}); a maintainer will look at it")
            shutil.rmtree(files, ignore_errors=True)
    (out / "status").write_text("failed\n" if problems else "ok\n", encoding="utf-8")
    # a GitHub comment is limited to 65,536 characters: at most MAX_PROBLEMS lines of at most MAX_LINE characters
    shown = [p if len(p) <= MAX_LINE else p[: MAX_LINE - 3] + "..." for p in problems[:MAX_PROBLEMS]]
    log = "".join(f"ERROR: {p}\n" for p in shown)
    if len(problems) > len(shown):
        log += f"ERROR: ... and {len(problems) - len(shown)} more problems\n"
    (out / "log").write_text(log, encoding="utf-8")
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
    check.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1],
                       help="the checkout a schema release is prepared from (default: the repository of this script)")
    sub.add_parser("pr-body")
    args = ap.parse_args(argv)
    if args.command == "pr-body":
        print(pr_body(int(os.environ["ISSUE_NUMBER"]), schema_release=os.environ.get("SCHEMA_RELEASE") == "1"))
        return 0
    return _run_check(args)


if __name__ == "__main__":
    sys.exit(main())
