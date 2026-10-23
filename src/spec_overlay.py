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


def _vendored_or_error(name: str):
    """A vendored script, or OverlayError when this installation lacks it."""
    try:
        return _vendored(name)
    except OSError as exc:
        raise OverlayError(
            f"the specification scripts (scripts/specification) are not installed, so local specification files are not used ({exc})"
        ) from exc


def _scripts():
    """The vendored term rules (check_terms, term_proposal), or OverlayError when this installation lacks them."""
    return _vendored_or_error("check_terms"), _vendored_or_error("term_proposal")


def overlay_root(project_root) -> Path:
    return Path(project_root).joinpath(*OVERLAY_PARTS)


def _terms_folder(project_root, modality: str) -> Path:
    return overlay_root(project_root) / "terms" / modality


def _real_overlay_folder(project_root, *parts: str) -> Path:
    """A folder under code/specification for writing or removing: no part of its path inside the project may be a symbolic link.

    A shared project could ship `code/specification -> /somewhere/else`; following it would write or delete
    outside the project.
    """
    current = Path(project_root)
    for part in (*OVERLAY_PARTS, *parts):
        current = current / part
        if current.is_symlink():
            raise OverlayError(f"{current} is a symbolic link; the specification folder of a project must be a real folder")
    return current


def _real_terms_folder(project_root, modality: str) -> Path:
    return _real_overlay_folder(project_root, "terms", modality)


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


def _patch_file(project_root, modality: str) -> Path:
    return overlay_root(project_root) / "patches" / f"{modality}.json"


def load_local_patches(project_root, modality: str = "biosample") -> tuple[dict | None, list[str]]:
    """The project's schema patch for `modality` (operations the official schema already has are dropped) and messages.

    Invalid, unreadable or symlinked files are a message, never an exception; None when nothing is left to add.
    """
    path = _patch_file(project_root, modality)
    if not path.is_file():
        return None, []
    try:
        _real_overlay_folder(project_root, "patches")
    except OverlayError as exc:
        return None, [f"{path.name}: {exc}"]
    if path.is_symlink():
        return None, [f"{path.name}: is a symbolic link, not used"]
    try:
        schema_patch = _vendored("schema_patch")
        from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema  # lazy: specification imports this module

        data = json.loads(path.read_text(encoding="utf-8"))
        adds, notes = schema_patch.additions(load_schema(modality, DEFAULT_SCHEMA_DIR, "stable"), data)
    except OSError as exc:
        return None, [f"{path.name}: cannot be used ({type(exc).__name__}; the specification scripts may not be installed)"]
    except (ValueError, RecursionError) as exc:  # PatchError is a ValueError (but a different class per loaded copy)
        return None, [f"{path.name}: {exc}" if isinstance(exc, ValueError) else f"{path.name}: cannot read ({type(exc).__name__})"]
    operations = [
        {"op": "add_enum_values", "path": a["path"], "values": a["values"]} if a["kind"] == "enum"
        else {"op": "add_optional_properties", "path": a["path"], "properties": a["properties"]}
        for a in adds
    ]
    return {"operations": operations}, [f"{path.name}: {note}" for note in notes]


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


def _project_specimens(project_root, modality: str) -> list[str] | None:
    """The SpecimenType values of the official schema plus the project's patch; None when there is no patch."""
    patch, _ = load_local_patches(project_root, modality)
    if patch is None:
        return None
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema

    schema = _vendored("schema_patch").apply_patch(load_schema(modality, DEFAULT_SCHEMA_DIR, "stable"), patch)[0]
    return schema["properties"]["Technical"]["properties"]["SpecimenType"]["enum"]


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
    new_stems = {term["TermID"].partition(":")[2] for term in proposal["terms"]}
    other_stems = set(load_local_terms(project_root, modality)[0]) - new_stems  # existing local terms
    # another, already broken local term must not stop an unrelated metric: drop only the problems that name one
    # (the registry check prefixes its messages with the file stem); everything else blocks, the safe default
    problems = [
        p for p in check_with_specification(proposal, checked_against, _project_specimens(project_root, modality))
        if not any(p.startswith(f"{stem}:") for stem in other_stems)
    ]
    if problems:
        raise OverlayError("; ".join(problems))
    return {"proposal": proposal, "written": write_local_terms(project_root, modality, proposal["terms"])}


def list_local_items(project_root, modality: str = "biosample") -> list[dict]:
    """Every file of the overlay: layer, ID, and whether it is local, now official (ignored) or invalid."""
    terms, problems = load_local_terms(project_root, modality)
    _merged, _in_use, ignored = merge_terms(load_registry(modality), terms)  # the validator's decision, not a second one
    folder = _terms_folder(project_root, modality)
    items = []
    for stem, term in terms.items():
        now_official = term["TermID"] in ignored
        items.append({
            "layer": 3, "modality": modality, "id": term["TermID"], "label": term.get("Label") or term["TermID"],
            "path": str(folder / f"{stem}.json"), "status": "now-official" if now_official else "local",
        })
    for problem in problems:
        items.append({
            "layer": 3, "modality": modality, "id": None, "label": None, "problem": problem,
            "path": str(folder / problem.split(":", 1)[0]), "status": "invalid",
        })
    items += _patch_items(project_root, modality)
    return items


def _patch_items(project_root, modality: str) -> list[dict]:
    """Layer 2 items of the overlay: one per added value or property, with the status the validator would give it."""
    patch, messages = load_local_patches(project_root, modality)
    path = str(_patch_file(project_root, modality))
    items = []
    for op in (patch or {}).get("operations", []):
        for name in op.get("values") or op["properties"]:
            ident = f"{op['path']}: {name}"
            items.append({
                "layer": 2, "modality": modality, "id": ident, "label": ident, "path": path, "status": "local",
                **({"field": op["path"], "value": name} if op["op"] == "add_enum_values" else {}),
            })
    for message in messages:
        official = message.endswith(" is already official")
        items.append({
            "layer": 2, "modality": modality, "id": message.partition(": ")[2].removesuffix(" is already official") if official else None,
            "label": None, "path": path, "status": "now-official" if official else "invalid",
            **({} if official else {"problem": message}),
        })
    return items


def _official_schema(modality: str) -> dict:
    from src.schema_manager import DEFAULT_SCHEMA_DIR, load_schema  # lazy: specification imports this module

    return load_schema(modality, DEFAULT_SCHEMA_DIR, "stable")


def _existing_patch(project_root, modality: str) -> tuple[Path, dict]:
    """The patch file for changing (symlinks refused) and its raw content; a broken file is an error, never overwritten."""
    path = _real_overlay_folder(project_root, "patches") / f"{modality}.json"
    if path.is_symlink():
        raise OverlayError(f"{path} is a symbolic link; the specification folder of a project must be a real folder")
    if not path.exists():
        return path, {"operations": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise OverlayError(f"{path.name} cannot be read ({type(exc).__name__}); fix or remove it first") from exc
    if not (isinstance(data, dict) and isinstance(data.get("operations"), list)):
        raise OverlayError(f"{path.name} is not a schema patch; fix or remove it first")
    return path, data


def _write_patch(path: Path, patch: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(patch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _enum_op(patch: dict, field: str) -> dict | None:
    return next((op for op in patch["operations"] if isinstance(op, dict) and op.get("op") == "add_enum_values" and op.get("path") == field), None)


def add_local_values(project_root, field: str, values: list[str], modality: str = "biosample") -> dict:
    """Add enum values (for example a new SpecimenType) to this project's patch: {"patch", "written", "skipped"}.

    Values the official schema has are skipped; when nothing is left nothing is written. The patch is checked by
    the vendored schema_patch.py (which also decides which fields may be extended) before anything is written.
    """
    sp = _vendored_or_error("schema_patch")
    schema = _official_schema(modality)
    path, patch = _existing_patch(project_root, modality)
    values = list(values) if isinstance(values, (list, tuple)) else values
    try:
        adds, _ = sp.additions(schema, {"operations": [{"op": "add_enum_values", "path": field, "values": values}]})
    except ValueError as exc:  # PatchError, a different class per loaded copy of the script
        if str(exc).startswith("nothing to add"):
            return {"patch": patch if patch["operations"] else None, "written": None, "skipped": list(values)}
        raise OverlayError(str(exc)) from exc
    new = adds[0]["values"]
    op = _enum_op(patch, field)
    if op is None:
        patch["operations"].append({"op": "add_enum_values", "path": field, "values": new})
    else:
        op["values"] = [*op["values"], *(v for v in new if v not in op["values"])]
    problems = sp.validate_patch(patch, schema)
    if problems:
        raise OverlayError("; ".join(problems))
    _write_patch(path, patch)
    return {"patch": patch, "written": path, "skipped": [v for v in values if v not in new]}


def remove_local_values(project_root, field: str, values: list[str], modality: str = "biosample") -> dict:
    """Remove enum values from this project's patch; the last one removes the file: {"removed", "written"}."""
    path, patch = _existing_patch(project_root, modality)
    op = _enum_op(patch, field)
    missing = [v for v in values if op is None or v not in op["values"]]
    if missing:
        raise OverlayError(f"{', '.join(map(str, missing))}: not in this project's additions to {field}")
    op["values"] = [v for v in op["values"] if v not in values]
    patch["operations"] = [o for o in patch["operations"] if o is not op or op["values"]]
    if patch["operations"]:
        _write_patch(path, patch)
        return {"removed": list(values), "written": path}
    path.unlink()
    return {"removed": list(values), "written": None}


def _enum_of(schema: dict, field: str):
    node = schema
    for part in field.split("."):
        node = (node.get("properties") or {}).get(part, {}) if isinstance(node, dict) else {}
    return node.get("enum") if isinstance(node, dict) else None


def _value_at(data, field: str):
    for part in field.split("."):
        data = data.get(part) if isinstance(data, dict) else None
    return data


def find_unknown_values(project_root, modality: str = "biosample") -> list[dict]:
    """Sidecar values outside the (patched) enums that could be added: {"field", "value", "sidecar"}, once per sidecar and value."""
    from src.specification import load_specification  # lazy: specification imports this module

    root = Path(project_root)
    spec = load_specification(project_root=root)
    schema = spec.schemas.get(modality) or {}
    sp = _vendored_or_error("schema_patch")
    found = []
    for folder, subfolders, names in os.walk(root):
        subfolders[:] = sorted(name for name in subfolders if name not in _NOT_PROJECT_DATA)
        for name in sorted(n for n in names if n.endswith(f"_{modality}.json")):
            path = Path(folder) / name
            try:
                sidecar = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, RecursionError):
                continue
            for field in spec.patchable_fields(modality):
                value = _value_at(sidecar, field)
                op = {"operations": [{"op": "add_enum_values", "path": field, "values": [value]}]}
                if isinstance(value, str) and value not in _enum_of(schema, field) and not sp.validate_patch(op, schema):
                    found.append({"field": field, "value": value, "sidecar": str(path)})
    return found


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


def proposal_for_local_terms(
    project_root, term_ids: list[str] | None = None, modality: str = "biosample", include_patch: bool = False
) -> dict:
    """The proposal that shares local terms: the named ones (default: every local term).

    `include_patch` adds the project's schema additions (patches/<modality>.json); a chosen term on a specimen
    that only the patch adds brings the patch along, so a proposal is never incomplete.

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
    patch, patch_messages = load_local_patches(project_root, modality)
    added = {v for op in (patch or {}).get("operations", []) if op.get("path") == "Technical.SpecimenType" for v in op.get("values", [])}
    if patch and (include_patch or any(t.get("SpecimenType") in added for t in chosen)):
        skipped += [m.partition(": ")[2] for m in patch_messages if m.endswith(" is already official")]
    else:
        patch = None
    if not chosen and not patch:
        raise OverlayError("nothing to share" + (f" (covered by official terms: {', '.join(skipped)})" if skipped else ""))
    proposal = {"modality": modality, "terms": sorted(chosen, key=lambda t: t["TermID"]), **({"patch": patch} if patch else {})}
    document = as_v2(proposal)
    return {
        "proposal": proposal,
        "document": document,
        "issue_url": issue_url(document),
        "problems": check_with_specification(document, official),
        "skipped": skipped,
    }
