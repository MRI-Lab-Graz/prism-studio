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

from src.template_languages import NOT_ITEMS as _NOT_ITEMS  # the one list of keys that are no items
from src.term_registry import terms_root

_LOCAL = re.compile(r"[a-z][a-z0-9-]{0,62}")  # one segment of a local ID


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


def _templates(library_dir: Path, problems: list[str]) -> list[tuple[Path, str, dict]]:
    """(file, task, template) of every readable survey template whose task name is a valid ID segment."""
    found = []
    for path in sorted(Path(library_dir).glob("survey-*.json")):
        if "participant" in path.stem.lower():
            continue
        template = _read_object(path, problems)
        if template is None:
            continue
        study = template.get("Study") if isinstance(template.get("Study"), dict) else {}
        task = _slug(str(study.get("TaskName") or "").strip() or path.stem[len("survey-"):])
        if _valid(task):
            found.append((path, task, template))
        else:
            problems.append(f"{path.name}: task name {task!r} is not a valid ID segment")
    return found


def build_survey_registry(library_dir: Path | None = None, recipe_dir: Path | None = None) -> tuple[dict[str, dict], list[str]]:
    """(local ID -> term, problems) for every instrument, item and score; bad files and names are reported, never raised."""
    library_dir = Path(library_dir or terms_root().parent / "survey")
    recipe_dir = Path(recipe_dir or terms_root().parents[1] / "recipe" / "survey")
    registry: dict[str, dict] = {}
    problems: list[str] = []
    tasks: dict[str, str] = {}  # task or file stem -> task

    for path, task, template in _templates(library_dir, problems):
        study = template.get("Study") if isinstance(template.get("Study"), dict) else {}
        stem = path.stem[len("survey-"):]
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
            if local in registry:
                problems.append(f"{path.name}: item key {key!r} gives {local!r}, which already exists; ignored")
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


def _released_path(path: Path | None) -> Path:
    return Path(path or terms_root().parent / "survey" / "term-ids.txt")


def released_ids(path: Path | None = None) -> set[str]:
    """Every survey ID that was ever released (one per line; a missing file is an empty set)."""
    try:
        return {line.strip() for line in _released_path(path).read_text(encoding="utf-8").splitlines() if line.strip()}
    except OSError:
        return set()


def freeze_problems(registry: dict[str, dict], released: set[str]) -> list[str]:
    """One line per released ID the registry no longer has: an ID is frozen once released."""
    now = {t.get("TermID") for t in registry.values()}
    return [f"{tid}: released ID is gone (an ID is frozen; restore the item, score or task name)" for tid in sorted(released - now)]


def write_released_ids(registry: dict[str, dict], path: Path | None = None) -> list[str]:
    """Add the registry's IDs to the released list (never removes a line); returns the IDs that were added."""
    target = _released_path(path)
    old = released_ids(target)
    added = sorted({t["TermID"] for t in registry.values()} - old)
    if added:
        target.write_text("".join(f"{tid}\n" for tid in sorted(old | set(added))), encoding="utf-8")
    return added


# --- a project's sidecar: which columns are an official item, unchanged --------------

def _collapse(text) -> str:
    return " ".join(str(text).split())


def _texts(description, language: str) -> dict[str, str]:
    """{language: text} of a Description given as a language object or as a plain string in `language`."""
    if isinstance(description, dict):
        return {k: _collapse(v) for k, v in description.items() if isinstance(v, str)}
    return {language: _collapse(description)} if isinstance(description, str) else {}


def _scale_matches(column: dict, scale: dict) -> bool:
    levels, lib_levels = column.get("Levels"), scale.get("Levels")
    if isinstance(levels, dict) and isinstance(lib_levels, dict) and {str(k) for k in levels} != {str(k) for k in lib_levels}:
        return False
    for bound in ("MinValue", "MaxValue"):
        if column.get(bound) is not None and scale.get(bound) is not None and column[bound] != scale[bound]:
            return False
    return True


def _item_reason(column: dict, item: dict, column_language: str, library_language: str) -> str:
    """Why a project column is not the library item ("" when it is): alias, changed scale, changed wording."""
    if "AliasOf" in column:
        return "alias"
    variants = [v for v in item.get("VariantScales") or [] if isinstance(v, dict)]
    if not any(_scale_matches(column, scale) for scale in [item, *variants]):
        return "changed scale"
    ours, theirs = _texts(column.get("Description"), column_language), _texts(item.get("Description"), library_language)
    if any(ours[lang] != theirs[lang] for lang in ours.keys() & theirs.keys()):
        return "changed wording"
    return ""


def resolve_survey_sidecar(sidecar: dict, library_dir: Path | None = None, recipe_dir: Path | None = None) -> dict:
    """Give each column of a project's survey sidecar its official item ID, or the reason it has none.

    {"instrument": TermID | None, "columns": [{"column", "term", "reason"}]}; reason is "" with a term, else one of
    unknown instrument, unknown item, alias, changed scale, changed wording. An edited item loses its official ID.
    Nothing is written anywhere.
    """
    library_dir = Path(library_dir or terms_root().parent / "survey")
    study = sidecar.get("Study") if isinstance(sidecar.get("Study"), dict) else {}
    technical = sidecar.get("Technical") if isinstance(sidecar.get("Technical"), dict) else {}
    task = _slug(str(study.get("TaskName") or "").strip())
    template = next((t for _, name, t in _templates(library_dir, []) if name == task), None) if task else None
    columns = []
    for key, column in sidecar.items():
        if key in _NOT_ITEMS:
            continue
        item = template.get(key) if template else None
        if template is None:
            term, reason = None, "unknown instrument"
        elif key in _NOT_ITEMS or not isinstance(item, dict) or "AliasOf" in item or not isinstance(column, dict):
            term, reason = None, "unknown item"
        else:
            library_language = (template.get("Technical") or {}).get("Language") or "en"
            reason = _item_reason(column, item, str(technical.get("Language") or "en"), str(library_language))
            term = None if reason else f"prism:{item_local_id(task, key)}"
        columns.append({"column": key, "term": term, "reason": reason})
    return {"instrument": f"prism:{task}" if template else None, "columns": columns}
