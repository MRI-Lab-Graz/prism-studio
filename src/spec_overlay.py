"""A project's own, not yet official specification: terms in `<project>/code/specification/terms/<modality>/`.

Phase 1 of docs/superpowers/specs/2026-10-23-specification-contributions-design.md. A local term file is
exactly a proposal term (no `Status`), so sharing it later is a plain copy into prism-specification. The
validator reads the overlay through `load_specification(project_root=...)`; the official registry always wins.
Project files are data: a bad file is skipped and reported, never trusted and never a crash.
"""

from __future__ import annotations

import importlib.util
import json
import os
from functools import lru_cache
from pathlib import Path

from src.term_proposal import (
    ProposalError,
    as_v2,
    build_proposal,
    check_with_specification,
    issue_url,
    load_inherited_sidecar,
    specification_scripts_dir,
)
from src.term_registry import analyte_columns, load_registry, resolve_column, term_names

OVERLAY_PARTS = ("code", "specification")


class OverlayError(ValueError):
    """The overlay cannot be changed as asked; the message says why."""


@lru_cache(maxsize=None)
def _vendored(name: str):
    """A prism-specification script (scripts/specification/<name>.py): the rules for terms live there once."""
    spec = importlib.util.spec_from_file_location(f"overlay_{name}", specification_scripts_dir() / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scripts():
    """The vendored term rules (check_terms, term_proposal), or OverlayError when this installation lacks them."""
    try:
        return _vendored("check_terms"), _vendored("term_proposal")
    except OSError as exc:
        raise OverlayError(
            f"the specification scripts (scripts/specification) are not installed, so local specification files are not used ({exc})"
        ) from exc


def overlay_root(project_root) -> Path:
    return Path(project_root).joinpath(*OVERLAY_PARTS)


def _terms_folder(project_root, modality: str) -> Path:
    return overlay_root(project_root) / "terms" / modality


def _real_terms_folder(project_root, modality: str) -> Path:
    """The terms folder for writing or removing: no part of its path inside the project may be a symbolic link.

    A shared project could ship `code/specification -> /somewhere/else`; following it would write or delete
    outside the project.
    """
    current = Path(project_root)
    for part in (*OVERLAY_PARTS, "terms", modality):
        current = current / part
        if current.is_symlink():
            raise OverlayError(f"{current} is a symbolic link; the specification folder of a project must be a real folder")
    return current


def _local_part(term_id) -> str | None:
    """The file stem of a `prism:` term ID, or None when it is not a valid local ID."""
    prefix, _, local = term_id.partition(":") if isinstance(term_id, str) else ("", "", "")
    return local if prefix == "prism" and _scripts()[1]._LOCAL.fullmatch(local) else None


def load_local_terms(project_root, modality: str = "biosample") -> tuple[dict[str, dict], list[str]]:
    """The valid local terms (file stem -> term) and one message per file that was skipped."""
    folder = _terms_folder(project_root, modality)
    files = sorted(folder.glob("*.json")) if folder.is_dir() else []
    if not files:
        return {}, []
    try:
        check_terms = _scripts()[0]
    except OverlayError as exc:
        return {}, [str(exc)]
    terms: dict[str, dict] = {}
    problems: list[str] = []
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError) as exc:  # RecursionError: absurdly nested JSON
            problems.append(f"{path.name}: cannot read ({type(exc).__name__})")
            continue
        if not isinstance(data, dict):
            problems.append(f"{path.name}: must be a JSON object")
        elif "Status" in data:
            problems.append(f"{path.name}: a local term has no Status (the maintainers' merge sets it)")
        elif _local_part(data.get("TermID")) != path.stem:
            problems.append(f"{path.name}: TermID {data.get('TermID')!r} must be prism:{path.stem}")
        elif (bad := check_terms.type_problems(data, path.name)):
            problems += bad
        else:
            terms[path.stem] = data
    return terms, problems


def merge_terms(official: dict[str, dict], local: dict[str, dict]) -> tuple[dict, frozenset[str], tuple[str, ...]]:
    """The official registry plus the local terms that add something.

    A local term is ignored when the official registry has its file stem, its TermID or ANY name it answers to
    (label, alias, equivalent), so a project can never shadow an official name. Returns (merged with official
    first, the TermIDs of the local terms in use, the TermIDs of the local terms ignored).
    """
    merged = dict(official)
    official_ids = {term.get("TermID") for term in official.values()}
    official_names = {name for stem, term in official.items() for name in term_names(stem, term)}
    in_use: set[str] = set()
    ignored: list[str] = []
    for stem, term in local.items():
        if stem in official or term["TermID"] in official_ids or official_names & set(term_names(stem, term)):
            ignored.append(term["TermID"])
        else:
            merged[stem] = term
            in_use.add(term["TermID"])
    return merged, frozenset(in_use), tuple(ignored)


def write_local_terms(project_root, modality: str, terms: list[dict]) -> list[Path]:
    """Write one file per term (exactly the proposal term); every ID is checked before anything is written."""
    for term in terms:
        if _local_part(term.get("TermID")) is None:
            raise OverlayError(f"{term.get('TermID')!r} is not a valid local term ID (prism:<slug>[.<specimen>])")
    folder = _real_terms_folder(project_root, modality)
    targets = [folder / f"{_local_part(term['TermID'])}.json" for term in terms]
    for path in targets:  # all of them first: nothing is written when one is in the way, and nothing is overwritten
        if path.exists() or path.is_symlink():
            raise OverlayError(f"{path.name} already exists in the project's specification folder; remove it first")
    folder.mkdir(parents=True, exist_ok=True)
    for term, path in zip(terms, targets):
        path.write_text(json.dumps(term, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return targets


def remove_local_terms(project_root, modality: str, term_id: str) -> list[Path]:
    """Remove a local term and, for a parent, the local children that name it as their Parent."""
    stem = _local_part(term_id)
    if stem is None:
        raise OverlayError(f"{term_id!r} is not a valid local term ID")
    folder = _real_terms_folder(project_root, modality)
    target = folder / f"{stem}.json"
    if target.is_symlink() or not target.is_file():
        raise OverlayError(f"no local term {term_id} in this project")
    doomed = [target]
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            continue
        if isinstance(data, dict) and data.get("Parent") == f"prism:{stem}" and path != target and not path.is_symlink():
            doomed.append(path)
    for path in doomed:
        path.unlink()
    return doomed


# --- operations the CLI and the Contribute page share ------------------------------------------------

_NOT_PROJECT_DATA = {"code", "derivatives", "sourcedata", ".git", ".datalad"}


def merged_registry(project_root, modality: str = "biosample") -> dict[str, dict]:
    """The official registry plus the project's local terms (the official one wins)."""
    return merge_terms(load_registry(modality), load_local_terms(project_root, modality)[0])[0]


def _specimen(sidecar: dict):
    technical = sidecar.get("Technical")
    return technical.get("SpecimenType") if isinstance(technical, dict) else None


def add_local_term(
    project_root, *, column: str, data_file=None, sidecar_file=None, label=None, modality: str = "biosample"
) -> dict:
    """Make a column's metric a local term of this project: build the proposal, check it, write the term files."""
    if bool(data_file) == bool(sidecar_file):
        raise OverlayError("give exactly one of a data file and a sidecar file")
    try:
        if data_file:
            sidecar, _path = load_inherited_sidecar(data_file)
        else:
            sidecar = json.loads(Path(sidecar_file).read_text(encoding="utf-8"))
        registry = merged_registry(project_root, modality)
        proposal = build_proposal(registry, sidecar, column, label, modality)
    except (ProposalError, OSError, ValueError, RecursionError) as exc:
        raise OverlayError(str(exc) or type(exc).__name__) from exc
    # the check wants a Status on every registry entry; a local term has none until the maintainers merge it
    checked_against = {stem: term if "Status" in term else {**term, "Status": "official"} for stem, term in registry.items()}
    problems = check_with_specification(proposal, checked_against)
    if problems:
        raise OverlayError("; ".join(problems))
    return {"proposal": proposal, "written": write_local_terms(project_root, modality, proposal["terms"])}


def list_local_items(project_root, modality: str = "biosample") -> list[dict]:
    """Every file of the overlay: layer, ID, and whether it is local, now official (ignored) or invalid."""
    terms, problems = load_local_terms(project_root, modality)
    official = load_registry(modality)
    official_ids = {term.get("TermID") for term in official.values()}
    folder = _terms_folder(project_root, modality)
    items = []
    for stem, term in terms.items():
        now_official = stem in official or term["TermID"] in official_ids
        items.append({
            "layer": 3, "modality": modality, "id": term["TermID"], "label": term.get("Label") or term["TermID"],
            "path": str(folder / f"{stem}.json"), "status": "now-official" if now_official else "local",
        })
    for problem in problems:
        items.append({
            "layer": 3, "modality": modality, "id": None, "label": None, "problem": problem,
            "path": str(folder / problem.split(":", 1)[0]), "status": "invalid",
        })
    return items


def find_unknown_metrics(project_root, modality: str = "biosample") -> list[dict]:
    """Analyte columns of the project's data files that neither the official registry nor a local term knows."""
    root = Path(project_root)
    registry = merged_registry(root, modality)
    found, seen = [], set()
    data_files = []
    for folder, subfolders, names in os.walk(root):
        subfolders[:] = sorted(name for name in subfolders if name not in _NOT_PROJECT_DATA)  # never descend into them
        data_files += [Path(folder) / name for name in sorted(names) if name.endswith(f"_{modality}.tsv")]
    for data_file in data_files:
        try:
            sidecar, sidecar_path = load_inherited_sidecar(data_file)
        except ProposalError:
            continue
        specimen = _specimen(sidecar)
        for column, definition in analyte_columns(sidecar):
            res = resolve_column(registry, column, definition, specimen)
            if res.kind == "unknown" and (sidecar_path, column) not in seen:
                seen.add((sidecar_path, column))
                found.append({
                    "column": column, "data_file": str(data_file), "specimen": specimen,
                    "units": definition.get("Units"), "similar": list(res.similar),
                })
    return found


def proposal_for_local_terms(project_root, term_ids: list[str] | None = None, modality: str = "biosample") -> dict:
    """The proposal that shares local terms: the named ones (default: every local term).

    A named child brings its local parent and a named parent its local children, so a proposal is never
    incomplete. Local terms the official registry has adopted since are left out and listed in `skipped`.
    Returns {"proposal": {"modality", "terms"}, "document" (format v2), "issue_url", "problems", "skipped"}.
    """
    local, _problems = load_local_terms(project_root, modality)
    official = load_registry(modality)
    _merged, in_use, ignored = merge_terms(official, local)
    usable = {stem: term for stem, term in local.items() if term["TermID"] in in_use}
    if term_ids is None:
        chosen_stems = list(usable)
        skipped = list(ignored)
    else:
        chosen_stems, skipped = [], []
        for term_id in term_ids:
            stem = _local_part(term_id)
            if stem is None or stem not in local:
                raise OverlayError(f"no local term {term_id} in this project")
            if term_id in ignored:
                if term_id not in skipped:
                    skipped.append(term_id)
                continue
            term = usable[stem]
            related = [
                other_stem for other_stem, other in usable.items()
                if other["TermID"] == term.get("Parent") or other.get("Parent") == term["TermID"]
            ]
            chosen_stems += [stem, *related]
    chosen = [usable[stem] for stem in dict.fromkeys(chosen_stems)]
    if not chosen:
        raise OverlayError("nothing to share" + (f" ({', '.join(skipped)} are official now)" if skipped else ""))
    limit = _scripts()[1].MAX_FILES
    if len(chosen) > limit:
        raise OverlayError(f"a proposal carries at most {limit} files, found {len(chosen)}: share some of them first")
    proposal = {"modality": modality, "terms": sorted(chosen, key=lambda t: t["TermID"])}
    document = as_v2(proposal)
    return {
        "proposal": proposal,
        "document": document,
        "issue_url": issue_url(document),
        "problems": check_with_specification(document, official),
        "skipped": skipped,
    }
