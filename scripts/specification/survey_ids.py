"""Survey IDs derived from library/survey/ and recipes/survey/ (stdlib only).

`prism:<task>` (instrument), `prism:<task>.<item-key>` (item), `prism:<task>.score-<name>` (score).
A copy of the derivation in PRISM Studio's src/survey_terms.py (item_local_id, score_local_id and the
template/recipe walk); tests/test_check_mappings.py proves both give the same registry on the shipped templates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# The keys of a template that are no items (Studio: TEMPLATE_SECTIONS plus the alias bookkeeping).
_NOT_ITEMS = {"Technical", "Study", "Metadata", "I18n", "LimeSurvey", "Scoring", "Normative",
              "@context", "_aliases", "_reverse_aliases"}
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
        value = value.get("en") or next((v for v in value.values() if isinstance(v, str) and v), "")
    return value if isinstance(value, str) else ""


def _set_text(term: dict, key: str, value) -> None:
    """Set term[key] to the label text of value; a missing, empty or non-text value leaves the key out."""
    if text := _text(value):
        term[key] = text


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
    repo = Path(__file__).resolve().parent.parent
    library_dir = Path(library_dir or repo / "library" / "survey")
    recipe_dir = Path(recipe_dir or repo / "recipes" / "survey")
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
        _set_text(registry[task], "RecallPeriod", study.get("RecallPeriod"))
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
            _set_text(registry[local], "RecallPeriod", item.get("RecallPeriod"))

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
                for key in ("HigherMeans", "LowerMeans"):
                    _set_text(registry[local], key, score.get(key))
    return registry, problems
