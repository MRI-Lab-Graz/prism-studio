"""A project's own, not yet official specification: terms in `<project>/code/specification/terms/<modality>/`.

Phase 1 of docs/superpowers/specs/2026-10-23-specification-contributions-design.md. A local term file is
exactly a proposal term (no `Status`), so sharing it later is a plain copy into prism-specification. The
validator reads the overlay through `load_specification(project_root=...)`; the official registry always wins.
Project files are data: a bad file is skipped and reported, never trusted and never a crash.
"""

from __future__ import annotations

import importlib.util
import json
from functools import lru_cache
from pathlib import Path

from src.term_proposal import specification_scripts_dir

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


def overlay_root(project_root) -> Path:
    return Path(project_root).joinpath(*OVERLAY_PARTS)


def _terms_folder(project_root, modality: str) -> Path:
    return overlay_root(project_root) / "terms" / modality


def _local_part(term_id) -> str | None:
    """The file stem of a `prism:` term ID, or None when it is not a valid local ID."""
    prefix, _, local = term_id.partition(":") if isinstance(term_id, str) else ("", "", "")
    return local if prefix == "prism" and _vendored("term_proposal")._LOCAL.fullmatch(local) else None


def load_local_terms(project_root, modality: str = "biosample") -> tuple[dict[str, dict], list[str]]:
    """The valid local terms (file stem -> term) and one message per file that was skipped."""
    folder = _terms_folder(project_root, modality)
    terms: dict[str, dict] = {}
    problems: list[str] = []
    for path in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            problems.append(f"{path.name}: cannot read ({exc})")
            continue
        if not isinstance(data, dict):
            problems.append(f"{path.name}: must be a JSON object")
        elif _local_part(data.get("TermID")) != path.stem:
            problems.append(f"{path.name}: TermID {data.get('TermID')!r} must be prism:{path.stem}")
        elif (bad := _vendored("check_terms").type_problems(data, path.name)):
            problems += bad
        else:
            terms[path.stem] = data
    return terms, problems


def write_local_terms(project_root, modality: str, terms: list[dict]) -> list[Path]:
    """Write one file per term (exactly the proposal term); every ID is checked before anything is written."""
    for term in terms:
        if _local_part(term.get("TermID")) is None:
            raise OverlayError(f"{term.get('TermID')!r} is not a valid local term ID (prism:<slug>[.<specimen>])")
    folder = _terms_folder(project_root, modality)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for term in terms:
        path = folder / f"{_local_part(term['TermID'])}.json"
        path.write_text(json.dumps(term, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


def remove_local_terms(project_root, modality: str, term_id: str) -> list[Path]:
    """Remove a local term and, for a parent, the local children that name it as their Parent."""
    stem = _local_part(term_id)
    if stem is None:
        raise OverlayError(f"{term_id!r} is not a valid local term ID")
    folder = _terms_folder(project_root, modality)
    target = folder / f"{stem}.json"
    if not target.is_file():
        raise OverlayError(f"no local term {term_id} in this project")
    doomed = [target]
    for path in sorted(folder.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(data, dict) and data.get("Parent") == f"prism:{stem}" and path != target:
            doomed.append(path)
    for path in doomed:
        path.unlink()
    return doomed
