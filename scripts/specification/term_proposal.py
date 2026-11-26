"""Check and write a proposal for new terms (metrics).

A proposal is one JSON document, sent through the "Propose a metric" issue form or saved
to a file with `prism_tools.py terms propose ... --out proposal.json` in PRISM Studio:

  {"modality": "biosample", "terms": [<parent term>, <child term>]}

The issue body is untrusted text: it is parsed as JSON only, size-capped, and every field
is checked against an allow-list before anything is written. Besides term files a proposal may carry links to
other vocabularies, `mappings/<modality>/<family>.json` (checked with check_mappings.py; the bot merges the new IDs
into the family's file and refuses an ID that is already mapped). File names are derived only
from IDs that passed the slug rule. Stdlib only; reuses scripts/check_terms.py.

Usage:
  term_proposal.py check [--terms DIR --schema FILE] --out DIR [--file proposal.json] [--repo DIR]
      --repo (the bot) needs the checkout's schemas/stable/entities.schema.json; --terms/--schema without --repo
      also work where no schemas/ folder is beside the script (biosample only, as vendored in PRISM Studio)
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
    "MinValue WarnMaxValue Equivalents Levels CFStandardName Group".split()
)
REPO = Path(__file__).resolve().parents[1]
# The term modalities before they were declared in entities.schema.json. PRISM Studio vendors these scripts
# without schemas/ beside them and calls them with explicit --terms/--schema; then this declaration applies.
LEGACY_MODALITIES = {"biosample": {"nonTermColumns": ["sample_id", "collection_time", "fasting"],
                                   "contextField": "Technical.SpecimenType"}}
_LOCAL = re.compile(r"^[a-z][a-z0-9-]{0,62}(\.[a-z][a-z0-9-]{0,62})?$")  # at most 63 characters per segment
_PATCH_PATH = re.compile(r"patches/(?P<modality>[a-z][a-z0-9]*)\.json")
# The repository paths a proposal may add. Later layers (schema patches, new modalities) add theirs here.
_TERM_PATH = re.compile(r"terms/(?P<modality>[a-z][a-z0-9]*)/(?P<stem>[a-z][a-z0-9-]{0,62}(?:\.[a-z][a-z0-9-]{0,62})?)\.json")
_MAPPING_PATH = re.compile(r"mappings/(?P<modality>[a-z][a-z0-9]*)/(?P<stem>[a-z][a-z0-9-]{0,62})\.json")  # a family's links
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


def sample_problems(sample: str) -> list[str]:
    """What is wrong with a pasted sample file (measured without the form's code fence, with \\n line ends)."""
    text = (sample or "").replace("\r\n", "\n").strip()
    opening = _OPENING_FENCE.match(text)
    if opening and text.endswith("```"):
        text = text[opening.end():-3].strip()
    if not text:
        return ["the sample is empty"]
    n = len(text.encode("utf-8"))
    return [f"the sample is {n} bytes, larger than {MAX_BYTES} bytes"] if n > MAX_BYTES else []


def check_new_kind(issue_body: str) -> list[str]:
    """Problems of a 'propose a new kind of data' issue; the closest kind is optional and not checked."""
    sections = _sections((issue_body or "").replace("\r\n", "\n"))
    boxes = _CHECKBOX.findall(sections.get("Agreements", ""))
    problems = []
    if len(boxes) < 2 or any(b == " " for b in boxes):
        problems.append("Both agreements (licence, made-up sample) must be ticked.")
    description = sections.get("Description", "").strip()
    if not description or description == "_No response_":
        problems.append("The description is empty.")
    return problems + sample_problems(sections.get("Sample file", ""))


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


def _mapping_shape(path: str, data, stem: str) -> list[str]:
    """Problems of the shape of one proposed mapping file (the entries themselves are checked with the registry)."""
    if not isinstance(data, dict):
        return [f"{path}: must be a JSON object of ID -> entry"]
    if not data:
        return [f"{path}: has no entries"]
    problems = []
    for key, entry in data.items():
        local = key.partition(":")[2] if isinstance(key, str) and key.startswith("prism:") else ""
        if not _LOCAL.fullmatch(local):
            problems.append(f"{path}: key {key!r} must be prism:<lowercase-slug>[.<specimen>]")
        elif local.split(".")[0] != stem:
            problems.append(f"{path}: the family of {key} is {local.split('.')[0]!r}, the file is {stem!r}")
        if not isinstance(entry, dict):
            problems.append(f"{path}: {key!r}: the entry must be a JSON object")
    return problems


def _declared(modalities: dict | None) -> dict[str, dict]:
    """The term modalities a proposal may name: the given ones, else this repository's declaration (LEGACY_MODALITIES
    when the script runs without schemas/ beside it, as vendored in PRISM Studio)."""
    if modalities is not None:
        return modalities
    if not (REPO / "schemas" / "stable" / "entities.schema.json").is_file():
        return LEGACY_MODALITIES
    return check_terms.term_modalities(REPO)


def _normalize_v1(proposal: dict, modalities=None) -> tuple[list[tuple[str, dict]], list[str]]:
    problems = []
    declared = _declared(modalities)
    if proposal.get("modality") not in declared:
        problems.append(f"modality must be one of {', '.join(declared)}")
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


def _normalize_v2(proposal: dict, modalities=None) -> tuple[list[tuple[str, dict]], list[str]]:
    problems = []
    declared = _declared(modalities)
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
        mapping_match = _MAPPING_PATH.fullmatch(path) if isinstance(path, str) else None
        match = patch_match or mapping_match or (_TERM_PATH.fullmatch(path) if isinstance(path, str) else None)
        if not match or (not patch_match and match["modality"] not in declared):
            kinds = "|".join(declared)
            problems.append(f"path {path!r} is not allowed (terms/<{kinds}>/<id>.json, mappings/<{kinds}>/<family>.json "
                            "or patches/<modality>.json)")
            continue
        if mapping_match:  # its entries are checked with the registry, in check_proposal
            found = _mapping_shape(path, term, mapping_match["stem"])
            problems += found
            if not found:
                pairs.append((path, term))
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
    if len(_kinds(pairs, declared)) > 1:
        problems.append("one kind of data per proposal: the term files and term-modality patches name more than one modality")
    return pairs, problems


def _kinds(pairs: list[tuple[str, dict]], declared: dict) -> list[str]:
    """The term modalities a proposal touches: those of its term files and of its patches of term modalities."""
    kinds = []
    for path, _obj in pairs:
        patch = _PATCH_PATH.fullmatch(path)
        match = patch or _TERM_PATH.fullmatch(path) or _MAPPING_PATH.fullmatch(path)
        if not patch or match["modality"] in declared:
            kinds.append(match["modality"])
    return list(dict.fromkeys(kinds))


def normalize(proposal, modalities=None) -> tuple[list[tuple[str, dict]], list[str]]:
    """The (repository path, term) pairs of a v1 or v2 proposal, and the problems found."""
    if not isinstance(proposal, dict):
        return [], ["the proposal must be a JSON object"]
    v2 = "files" in proposal or "format" in proposal
    pairs, problems = (_normalize_v2 if v2 else _normalize_v1)(proposal, modalities)
    return ([] if problems else pairs), problems


def split(pairs: list[tuple[str, dict]]) -> tuple[list[tuple[str, dict]], list[tuple[str, dict]]]:
    """(term pairs, patch pairs) of the files a proposal adds."""
    return [(p, o) for p, o in pairs if p.startswith("terms/")], [(p, o) for p, o in pairs if p.startswith("patches/")]


def links_of(pairs: list[tuple[str, dict]]) -> list[tuple[str, dict]]:
    """The family files of links among the files a proposal adds (`split` gives the terms and the patches)."""
    return [(p, o) for p, o in pairs if p.startswith("mappings/")]


def _mapped_ids(folder: Path) -> tuple[dict[str, str], list[str]]:
    """(ID -> file name of every ID already mapped in a modality's mappings folder, problems).

    A file that cannot be read stops the check: skipping it would let a proposal re-map an ID that is mapped there.
    """
    mapped, problems = {}, []
    for path in sorted(Path(folder).glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if not isinstance(data, dict):
            problems.append(f"{path.name} in the mappings folder cannot be read as a JSON object; a maintainer must fix it first")
            continue
        mapped.update({key: path.name for key in data})
    return mapped, problems


def _mapping_problems(pairs: list[tuple[str, dict]], registry: dict[str, dict], mappings_dir: Path | None) -> list[str]:
    """Problems of the proposed links: a term that exists or is proposed, not yet mapped, a valid entry."""
    if mappings_dir is None:
        return ["a proposal with links needs the mappings folder to check them (mappings_dir)"]
    check_mappings = _sibling("check_mappings")  # only a proposal with links needs it (and scripts/survey_ids.py beside it)
    vocabs, problems = check_mappings.load_vocabularies(Path(mappings_dir) / "vocabularies.json")
    for path, data in pairs:
        mapped, found = _mapped_ids(Path(mappings_dir) / _MAPPING_PATH.fullmatch(path)["modality"])
        problems += found
        for key, entry in data.items():
            term = registry.get(key.partition(":")[2])
            if term is None:
                problems.append(f"{path}: {key} is not a term of this registry and not proposed with the links")
                continue
            if key in mapped:
                problems.append(f"{path}: {key} is already mapped in {mapped[key]}; changing a link is a maintainer's edit")
            levels = term.get("Levels")
            problems += check_mappings.entry_problems(entry, f"{path}: {key}", vocabs, set(levels) if isinstance(levels, dict) else None)
    return problems


# ponytail: hard-coded Technical.SpecimenType; right while biosample is the only term modality with a contextField
# (one kind of data per proposal makes a patched term modality the terms' own). Read the declared contextField
# when a second contextField modality arrives.
def _specimens_of(schema: dict) -> list[str]:
    return schema.get("properties", {}).get("Technical", {}).get("properties", {}).get("SpecimenType", {}).get("enum", [])


def check_proposal(
    proposal: dict, registry: dict[str, dict], specimens: list[str] | None, schema: dict | None = None,
    *, schemas: dict[str, dict] | None = None, modalities=None, mappings_dir: Path | None = None,
    others: dict[str, dict] | None = None,
) -> tuple[list[dict], list[str]]:
    """Return (the new terms with Status "official", problems); checked together with the registry.

    A proposal may carry a schema patch (`patches/<modality>.json`); then `schema`, the schema it targets, is
    required, and the terms are checked against the specimen types of the PATCHED schema. With `schemas`
    (modality -> schema) each patch is checked against its own modality's schema; the specimen types are
    taken from a patched schema only when it is a term modality with a contextField. Without `schemas`, the
    positional `schema` serves only patches of term modalities; a patch of any other modality needs `schemas`.
    `specimens` None = a one-level registry (no context field). `modalities` = modality -> `terms`
    declaration (default: those of this repository, LEGACY_MODALITIES without schemas/ beside the script).
    One kind of data per proposal: the term files and the patches of term modalities name one modality.
    Links (`mappings/<modality>/<family>.json`) are checked against `mappings_dir` (vocabularies.json and what is
    already mapped): the ID must be a term of the registry or proposed with them, and an ID that is already mapped
    is refused (a changed link is a maintainer's edit). `others` = the other registries (modality -> terms, survey
    included): an ID or, across `termsFrom`, a name that CI would refuse is refused here too.
    """
    declared = _declared(modalities)
    pairs, problems = normalize(proposal, declared)
    if problems:
        return [], problems
    term_pairs, patch_pairs = split(pairs)
    for path, patch in patch_pairs:
        modality = _PATCH_PATH.fullmatch(path)["modality"]
        target = schemas.get(modality) if schemas is not None else (schema if modality in declared else None)
        if target is None:
            hint = "" if modality in declared else f" (pass `schemas` with the {modality} schema)"
            problems.append(f"{path}: the schema the patch targets is needed to check it{hint}")
            continue
        try:
            patched, _notes = schema_patch.apply_patch(target, patch)
        except ValueError as exc:  # PatchError; scripts load each other by path, so the class is not shared
            problems.append(f"{path}: {exc}")
            continue
        if declared.get(modality, {}).get("contextField"):
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
    kind = next(iter(_kinds(pairs, declared)), None)
    problems = check_terms.check_registry(merged, specimens, declared.get(kind, {}).get("unitsOptional", False))
    if not problems and kind and others:
        registries = {**others, kind: merged}
        concerned = {n: d for n, d in declared.items()
                     if n in registries and (n == kind or kind in d.get("termsFrom", []))}
        problems = [p for p in check_terms.cross_registry_problems(registries) if p.partition(":")[0] in merged]
        problems += check_terms.terms_from_problems(concerned, registries)
    if not problems and (links := links_of(pairs)):
        problems = _mapping_problems(links, merged, mappings_dir)
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


def write_links(links: list[tuple[str, dict]], out_dir: Path, mappings_dir: Path) -> list[Path]:
    """Write each proposed family file under out_dir/<repository path>: the file as it is in mappings_dir, then the new IDs.

    The IDs were checked as not yet mapped, so merging never changes an existing entry.
    """
    written = []
    for path, entries in links:
        match = _MAPPING_PATH.fullmatch(path)
        existing_file = Path(mappings_dir) / match["modality"] / f"{match['stem']}.json"
        existing = json.loads(existing_file.read_text(encoding="utf-8")) if existing_file.is_file() else {}
        target = Path(out_dir) / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({**existing, **entries}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(target)
    return written


SCHEMA_RELEASE_NOTE = """
This proposal changes a modality schema. The bot prepared the release steps: the previous schema is archived
unchanged, the patch version and `$id` of the stable schema are bumped, and the field tables of the spec page
are regenerated. The stable schema file is edited in place, so its diff shows only the new version, the new
`$id` and the added values or properties; review those, the version bump and the archive copy.
"""


LINKS_CHECK = (
    "- [ ] The links (`mappings/`) are real entries of the named vocabulary, and the diff of each mapping file only adds "
    "lines (an existing link is never changed by a proposal)\n"
)


def pr_body(issue_number: int, schema_release: bool = False, links: bool = False) -> str:
    return f"""Generated by the metric proposal bot from #{issue_number}. Closes #{issue_number} when merged. This is a **draft**.

Contents: the proposed files (terms under `terms/`{", links under `mappings/`" if links else ""}{", schema release under `schemas/` and `specs/`" if schema_release else ""}). The automatic check passed (a failing proposal never gets a pull request).
{SCHEMA_RELEASE_NOTE if schema_release else ""}
Maintainer checklist:
- [ ] The ID is sensible and final (IDs are frozen once released); change it before merging if not
- [ ] The contributor's own column name is in `Aliases`
- [ ] Units are UCUM; ranges are cited or left out (none were invented)
{LINKS_CHECK if links else ""}- [ ] CI is green (the bot commit does not start it; push or approve the run)
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


def _capped(problems: list[str]) -> list[str]:
    """At most MAX_PROBLEMS lines of at most MAX_LINE characters (a GitHub comment holds 65,536 characters)."""
    shown = [p if len(p) <= MAX_LINE else p[: MAX_LINE - 3] + "..." for p in problems[:MAX_PROBLEMS]]
    if len(problems) > len(shown):
        shown.append(f"... and {len(problems) - len(shown)} more problems")
    return shown


def _run_check(args) -> int:
    """Always writes a bundle (status, log, files/<repository path>); a bad proposal is a failed bundle, not a crash."""
    problems: list[str] = []
    registry: dict[str, dict] = {}
    terms: list[dict] = []
    term_modalities: list[str] = []
    patches: list[tuple[str, dict]] = []
    links: list[tuple[str, dict]] = []
    repo = args.repo or REPO
    try:
        proposal = _read_proposal(args.file)
        # --repo (the bot) reads the checkout's declaration and fails without it; explicit --terms/--schema
        # without --repo (PRISM Studio's vendored copy) falls back to LEGACY_MODALITIES
        modalities = check_terms.term_modalities(args.repo) if args.repo is not None else _declared(None)
        pairs = normalize(proposal, modalities)[0]
        term_pairs, patch_pairs = split(pairs)
        kind = next(iter(_kinds(pairs, modalities)), None)  # more than one is refused by normalize
        if args.terms is not None:  # explicit registry and schema (biosample, as before)
            schema_file, terms_dir = args.schema, args.terms
        else:
            schema_file = Path(repo) / "schemas" / "stable" / f"{kind}.schema.json"
            terms_dir = Path(repo) / "terms" / str(kind)
        registry, problems = check_terms.load_terms(terms_dir) if kind or args.terms else ({}, [])
        # a schema that should be there but is not is an error bundle; a table (participants) has none
        has_schema = bool(args.schema or (kind and kind not in check_terms.table_names(repo)))
        schema = json.loads(Path(schema_file).read_text(encoding="utf-8")) if has_schema else None
        context = modalities.get(kind, {}).get("contextField") if kind else "Technical.SpecimenType"
        specimens = check_terms.context_values(schema_file, context) if has_schema else ([] if context else None)
        schemas, missing = {}, []
        for path, _patch in patch_pairs:
            modality = _PATCH_PATH.fullmatch(path)["modality"]
            file = Path(repo) / "schemas" / "stable" / f"{modality}.schema.json"
            if file.is_file():
                schemas[modality] = json.loads(file.read_text(encoding="utf-8"))
            else:
                missing.append(f"{path}: no modality {modality} in schemas/stable")
        mappings_dir = args.mappings or Path(repo) / "mappings"
        others = {}
        if args.terms is None and kind:  # a complete checkout; PRISM Studio's explicit registry has no neighbours
            others = {m: check_terms.load_terms(Path(repo) / "terms" / m)[0] for m in modalities if m != kind}
            if (Path(repo) / "ids" / "survey-ids.txt").is_file():
                others["survey"] = check_terms.survey_registry(Path(repo))[0]
        terms, found = check_proposal(proposal, registry, specimens, schema, schemas=schemas, modalities=modalities,
                                      mappings_dir=mappings_dir, others=others)
        found = missing or found
        problems += found
        if not found:
            patches = patch_pairs
            links = links_of(pairs)
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
            write_links(links, files, args.mappings or Path(repo) / "mappings")
            for path, patch in patches:
                release_patch.release(repo, files, _PATCH_PATH.fullmatch(path)["modality"], patch)
        except ValueError as exc:  # PatchError / ReleaseError: the proposal cannot be released, and the message says why
            problems.append(str(exc))
            shutil.rmtree(files, ignore_errors=True)
        except Exception as exc:  # noqa: BLE001 - writing must never leave a half bundle that says ok
            problems.append(f"internal error while writing the files ({type(exc).__name__}); a maintainer will look at it")
            shutil.rmtree(files, ignore_errors=True)
    (out / "status").write_text("failed\n" if problems else "ok\n", encoding="utf-8")
    # a GitHub comment is limited to 65,536 characters: at most MAX_PROBLEMS lines of at most MAX_LINE characters
    log = "".join(f"ERROR: {p}\n" for p in _capped(problems))
    (out / "log").write_text(log, encoding="utf-8")
    print(log or "ok")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("--terms", type=Path, help="the registry folder (default: terms/<modality> of --repo)")
    check.add_argument("--schema", type=Path, help="the modality schema (default: schemas/stable/<modality>.schema.json of --repo)")
    check.add_argument("--out", required=True, type=Path)
    check.add_argument("--file", type=Path)
    check.add_argument("--mappings", type=Path, help="the mappings folder links are checked against (default: mappings/ of --repo)")
    check.add_argument("--repo", type=Path, help="a complete checkout (the bot passes it): its schemas/stable/entities.schema.json, "
                       "terms and schemas are read and a schema release is prepared from it; without --repo, "
                       "--terms and --schema are required (biosample only)")
    sub.add_parser("pr-body")
    sub.add_parser("check-new-kind")
    args = ap.parse_args(argv)
    if args.command == "pr-body":
        print(pr_body(int(os.environ["ISSUE_NUMBER"]), schema_release=os.environ.get("SCHEMA_RELEASE") == "1",
                      links=os.environ.get("HAS_LINKS") == "1"))
        return 0
    if args.command == "check-new-kind":
        problems = _capped(check_new_kind(os.environ.get("ISSUE_BODY", "")))
        print("\n".join(problems), end="\n" if problems else "")
        return 1 if problems else 0
    return _run_check(args)


if __name__ == "__main__":
    sys.exit(main())
