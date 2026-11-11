"""IDs for survey instruments, items and scores, derived from the official library and the recipes.

`prism:<task>` (instrument), `prism:<task>.<item-key>` (item), `prism:<task>.score-<name>` (score). Nothing is stored
per item: the library templates and the recipes stay the only place an item or a score is defined, and the registry
returned here has the shape `src.term_registry.load_registry` returns, so `find_term` and `term_links` work on it.
Spec: docs/superpowers/specs/2026-11-11-term-ids-all-modalities-design.md
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from src.term_registry import terms_root

_LOCAL = re.compile(r"[a-z][a-z0-9-]{0,62}")  # one segment of a local ID
_NOT_ITEMS = ("Technical", "Metadata", "I18n", "Study", "Normative")


def _slug(text: str) -> str:
    return text.lower().replace("_", "-")


def item_local_id(task: str, key: str) -> str:
    """`tipi`, `TIPI02` -> `tipi.tipi02`."""
    return f"{task}.{_slug(key)}"


def score_local_id(task: str, name: str) -> str:
    """`tipi`, `tipi_extraversion` -> `tipi.score-extraversion` (a leading `<task>-` of the name is dropped)."""
    slug = _slug(name)
    return f"{task}.score-{slug[len(task) + 1:] if slug.startswith(task + '-') else slug}"


def _text(value) -> str:
    """A label: English if there is one, else the first language, else a plain string."""
    if isinstance(value, dict):
        return str(value.get("en") or next(iter(value.values()), "") or "")
    return value if isinstance(value, str) else ""


def _read_object(path: Path, problems: list[str]) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        problems.append(f"{path.name}: cannot read ({exc})")
        return None
    if not isinstance(data, dict):
        problems.append(f"{path.name}: must hold a JSON object")
        return None
    return data


def _valid(segment: str) -> bool:
    return bool(_LOCAL.fullmatch(segment))


def build_survey_registry(library_dir: Path | None = None, recipe_dir: Path | None = None) -> tuple[dict[str, dict], list[str]]:
    """(local ID -> term, problems) for every instrument, item and score; bad files and names are reported, never raised."""
    library_dir = Path(library_dir or terms_root().parent / "survey")
    recipe_dir = Path(recipe_dir or terms_root().parents[1] / "recipe" / "survey")
    registry: dict[str, dict] = {}
    problems: list[str] = []
    tasks: dict[str, str] = {}  # task or file stem -> task

    for path in sorted(library_dir.glob("survey-*.json")):
        if "participant" in path.stem.lower():
            continue
        template = _read_object(path, problems)
        if template is None:
            continue
        study = template.get("Study") if isinstance(template.get("Study"), dict) else {}
        stem = path.stem[len("survey-"):]
        task = _slug(str(study.get("TaskName") or "").strip() or stem)
        if not _valid(task):
            problems.append(f"{path.name}: task name {task!r} is not a valid ID segment")
            continue
        if task in registry:
            problems.append(f"{path.name}: task {task!r} is already used by another template; ignored")
            continue
        tasks[task] = tasks[stem] = task
        registry[task] = {"TermID": f"prism:{task}", "Level": "instrument", "Label": str(study.get("ShortName") or task),
                          "Description": _text(study.get("OriginalName")), "Status": "official"}
        for key, item in template.items():
            if key in _NOT_ITEMS or not isinstance(item, dict) or "AliasOf" in item:
                continue
            local = item_local_id(task, key)
            if key.lower().startswith("score-") or not _valid(local.partition(".")[2]):
                problems.append(f"{path.name}: item key {key!r} gives no valid ID")
                continue
            registry[local] = {"TermID": f"prism:{local}", "Level": "item", "Parent": f"prism:{task}", "Label": key,
                               "Description": _text(item.get("Description")), "Status": "official"}

    for path in sorted(recipe_dir.glob("recipe-*.json")):
        stem = path.stem[len("recipe-"):]
        recipe = _read_object(path, problems)
        if recipe is None:
            continue
        task = tasks.get(stem)
        if task is None:
            problems.append(f"{path.name}: no library template for task {stem!r}; no score IDs")
            continue
        for score in recipe.get("Scores") if isinstance(recipe.get("Scores"), list) else []:
            name = score.get("Name") if isinstance(score, dict) else None
            if not isinstance(name, str) or not name:
                problems.append(f"{path.name}: a score without a Name is skipped")
                continue
            local = score_local_id(task, name)
            if not _valid(local.partition(".")[2]):
                problems.append(f"{path.name}: score name {name!r} gives no valid ID")
            elif local in registry:
                problems.append(f"{path.name}: score name {name!r} gives {local!r}, which already exists")
            else:
                registry[local] = {"TermID": f"prism:{local}", "Level": "score", "Parent": f"prism:{task}",
                                   "Label": f"{registry[task]['Label']} {name}", "Description": _text(score.get("Description")),
                                   "Status": "official"}
    return registry, problems
