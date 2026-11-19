"""Check mapping files (links from PRISM IDs to external vocabularies) with the specification's own checker.

`scripts/specification/check_mappings.py` reads a repository-shaped folder (terms/, library/survey/, ids/, mappings/).
Studio keeps the same files under official/, so a small temporary view of them is built and the checker runs on that:
one implementation, no copy of its rules.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from src.schema_manager import DEFAULT_SCHEMA_DIR
from src.spec_overlay import OVERLAY_PARTS, OverlayError, _local_part, _vendored_or_error, load_local_terms
from src.term_registry import mappings_root, terms_root


def _official_view(view: Path) -> None:
    library = terms_root().parent
    (view / "schemas" / "stable").mkdir(parents=True)
    shutil.copy(Path(DEFAULT_SCHEMA_DIR) / "stable" / "entities.schema.json", view / "schemas" / "stable")
    shutil.copytree(terms_root(), view / "terms")
    shutil.copytree(library / "survey", view / "library" / "survey", ignore=shutil.ignore_patterns("term-ids.txt"))
    (view / "ids").mkdir()
    shutil.copy(library / "survey" / "term-ids.txt", view / "ids" / "survey-ids.txt")
    recipes = library.parent / "recipe" / "survey"
    if recipes.is_dir():
        shutil.copytree(recipes, view / "recipes" / "survey")


def _prism_form(data):
    """A project's `local:` IDs in the form the checker knows (`prism:`)."""
    return {f"prism:{_local_part(key) or key.partition(':')[2]}" if key.startswith("local:") else key: value
            for key, value in data.items()} if isinstance(data, dict) else data


def check_links(mappings: Path | None = None, *, project=None) -> list[str]:
    """Problems of the mapping files in `mappings` (`<modality>/<family>.json`), or of a project's local links.

    A project's links (`code/specification/mappings`) are checked against the official IDs and its own local terms."""
    if project is not None:
        mappings = Path(project).joinpath(*OVERLAY_PARTS, "mappings")
    if mappings is None:
        raise OverlayError("give a mappings folder or a project")
    mappings = Path(mappings)
    if not mappings.is_dir():
        raise OverlayError(f"{mappings} is not a folder")
    with tempfile.TemporaryDirectory() as tmp:
        view = Path(tmp)
        _official_view(view)
        (view / "mappings").mkdir()
        shutil.copy(mappings_root() / "vocabularies.json", view / "mappings")  # the lab's files are the ones to check
        for folder in sorted(p for p in mappings.iterdir() if p.is_dir()):
            for path in sorted(folder.glob("*.json")):
                target = view / "mappings" / folder.name / path.name
                target.parent.mkdir(parents=True, exist_ok=True)
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError, RecursionError):
                    target.write_bytes(path.read_bytes())  # the checker reports it
                    continue
                target.write_text(json.dumps(_prism_form(data) if project is not None else data), encoding="utf-8")
            if project is not None:
                terms, _ = load_local_terms(project, folder.name)
                for stem, term in terms.items():
                    out = view / "terms" / folder.name / f"{stem}.json"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_text(json.dumps({**term, "TermID": f"prism:{stem}", "Status": "official",
                                               **({"Parent": f"prism:{term['Parent'].partition(':')[2]}"} if term.get("Parent") else {})}),
                                   encoding="utf-8")
        return _vendored_or_error("check_mappings").check(view)
