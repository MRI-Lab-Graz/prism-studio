"""Per-project mapping from a survey file's column names to a template's item IDs.

Stored in ``code/item_maps/<task>.json`` as ``{item: column}``; only entries where
the column differs from the item are kept.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable, Mapping
from pathlib import Path

from src.converters.survey_core import _NON_ITEM_TOPLEVEL_KEYS

MAP_DIR = Path("code") / "item_maps"
_TASK = re.compile(r"[A-Za-z0-9]+")
_DIGITS = re.compile(r"\d+")


class ItemMapError(ValueError):
    """Anything wrong with an item map or a request to save one."""


def template_items(template: dict) -> list[str]:
    return [
        k
        for k, v in template.items()
        if k not in _NON_ITEM_TOPLEVEL_KEYS and isinstance(v, dict) and "AliasOf" not in v
    ]


def _numbers(name: str) -> tuple[int, ...]:
    return tuple(int(d) for d in _DIGITS.findall(name))


def _stem(name: str) -> str:
    return "".join(c for c in _DIGITS.sub("#", name.lower()) if c == "#" or c.isalpha())


def suggest(
    items: list[str], columns: list[str], saved: Mapping[str, str] | None = None
) -> list[dict]:
    """One row per item: the column that most likely holds it and why."""
    found: dict[str, tuple[str, str]] = {}
    used: set[str] = set()

    def take(item: str, column: str, why: str) -> None:
        found[item] = (column, why)
        used.add(column)

    for item in items:
        col = (saved or {}).get(item)
        if col in columns and col not in used:
            take(item, col, "saved")
    for item in items:
        if item not in found and item in columns and item not in used:
            take(item, item, "same")

    left = [i for i in items if i not in found]
    groups: dict[str, list[str]] = {}
    for col in columns:
        if col not in used and _numbers(col):
            groups.setdefault(_stem(col), []).append(col)
    if left and groups:
        def score(stem: str) -> int:
            return sum(1 for i in left if _numbers(i) in {_numbers(c) for c in groups[stem]})

        # dict order = first column in the file, so max() breaks ties toward the file's start
        best = max(groups, key=score)
        if score(best) == 0:
            best = max(groups, key=lambda s: len(groups[s]))
        pool = groups[best]
        for item in left:
            hit = next((c for c in pool if c not in used and _numbers(c) == _numbers(item)), None)
            if hit:
                take(item, hit, "number")
        rest_items = sorted((i for i in left if i not in found), key=_numbers)
        rest_cols = sorted((c for c in pool if c not in used), key=_numbers)
        for item, col in zip(rest_items, rest_cols):
            take(item, col, "order")

    return [
        {"item": i, "column": found[i][0], "why": found[i][1]}
        if i in found
        else {"item": i, "column": None, "why": "none"}
        for i in items
    ]


def _root(project_path: str | Path) -> Path:
    path = Path(project_path).expanduser()
    return path.parent if path.is_file() else path


def _check_task(task: str) -> str:
    if not isinstance(task, str) or not _TASK.fullmatch(task):
        raise ItemMapError(f"Invalid task name {task!r}: use letters and digits only")
    return task


def map_path(project_path: str | Path, task: str) -> Path:
    return _root(project_path) / MAP_DIR / f"{_check_task(task)}.json"


def _read(path: Path, strict: bool = False) -> dict[str, str]:
    """The map in ``path``; an invalid file is skipped with a warning, or with ``strict`` an ItemMapError."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("not a JSON object")
        if not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in raw.items()):
            raise ValueError("every entry must be a non-empty item ID and column name")
        return raw
    except (OSError, ValueError, RecursionError) as exc:  # RecursionError: deeply nested JSON
        if strict:
            raise ItemMapError(
                f"{(MAP_DIR / path.name).as_posix()} is not a valid item map; fix or delete it"
            ) from exc
        print(f"[PRISM] WARNING item map {path} ignored: {exc}")
        return {}


def load_item_map(project_path: str | Path, task: str, strict: bool = False) -> dict[str, str]:
    """The stored map of ``task``; ``strict`` (the save paths) refuses an invalid file instead of skipping it."""
    path = map_path(project_path, task)
    return _read(path, strict) if path.is_file() else {}


def check_item_map(items: list[str], mapping: Mapping[str, str]) -> dict[str, str]:
    """The cleaned ``{item: column}`` (blanks dropped, item == column dropped); ItemMapError if invalid."""
    clean = {k: v.strip() for k, v in mapping.items() if isinstance(v, str) and v.strip()}
    unknown = [k for k in clean if k not in items]
    if unknown:
        raise ItemMapError(f"Not items of this template: {', '.join(unknown)}")
    columns = list(clean.values())
    twice = sorted({c for c in columns if columns.count(c) > 1})
    if twice:
        raise ItemMapError(f"Column used for more than one item: {', '.join(twice)}")
    return {k: v for k, v in clean.items() if k != v}


def save_item_map(
    project_path: str | Path, task: str, mapping: Mapping[str, str], items: list[str]
) -> Path | None:
    path = map_path(project_path, task)
    clean = check_item_map(items, mapping)
    if not clean:
        path.unlink(missing_ok=True)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def item_alias_map(project_path: str | Path, tasks: Iterable[str] | None = None) -> dict[str, str]:
    """``{column: item}`` over every task's map (only the maps of ``tasks`` when given); a column
    claimed twice is an error."""
    wanted = None if tasks is None else {t.lower() for t in tasks}
    aliases: dict[str, str] = {}
    owner: dict[str, str] = {}
    for path in sorted((_root(project_path) / MAP_DIR).glob("*.json")):
        if wanted is not None and path.stem.lower() not in wanted:
            continue
        for item, column in _read(path).items():
            if column in owner:
                raise ItemMapError(
                    f"Column {column!r} is mapped in both item maps {owner[column]!r} and {path.stem!r}"
                )
            owner[column] = path.stem
            aliases[column] = item
    return aliases


def read_survey_columns(path: str | Path) -> list[str]:
    """Column names of a survey file as the converter sees them (an .lsa gets its renamed columns)."""
    from src.converters.survey import _read_table_as_dataframe

    path = Path(path).expanduser().resolve()
    kind = {".xlsx": "xlsx", ".csv": "csv", ".tsv": "tsv", ".lsa": "lsa"}.get(path.suffix.lower())
    if kind is None:
        raise ItemMapError("Supported formats: .xlsx, .csv, .tsv, .lsa")
    try:
        df = _read_table_as_dataframe(input_path=path, kind=kind)
    except (OSError, ValueError):
        raise
    except Exception as exc:  # e.g. zipfile.BadZipFile for a corrupt .xlsx/.lsa
        raise ItemMapError(f"Cannot read {path.name}: {exc}") from exc
    if isinstance(df, tuple):  # .lsa: (dataframe, questions_map)
        df = df[0]
    return [str(c) for c in df.columns]


def _project_template(project_path: str | Path, task: str) -> dict:
    path = _root(project_path) / "code" / "library" / "survey" / f"survey-{_check_task(task)}.json"
    try:
        template = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise ItemMapError(f"No template for task {task!r} in the project library: {exc}") from exc
    if not isinstance(template, dict):
        raise ItemMapError(f"No template for task {task!r} in the project library: not a JSON object")
    return template


def _library(project_path: str | Path) -> dict[str, dict]:
    """``{task: template}`` of the project library's survey templates, sorted; unreadable ones skipped."""
    templates = {}
    for path in sorted((_root(project_path) / "code" / "library" / "survey").glob("survey-*.json")):
        try:
            templates[path.stem[len("survey-"):]] = _project_template(project_path, path.stem[len("survey-"):])
        except ItemMapError:
            continue
    return templates


def _claims(project_path: str | Path) -> tuple[dict[str, str], dict[str, str]]:
    """Which task owns a column name: ``({item or item alias: task}, {mapped column: task})`` over
    the project library's templates and their stored maps."""
    items: dict[str, str] = {}
    mapped: dict[str, str] = {}
    for task, template in _library(project_path).items():
        for key, value in template.items():
            if key in _NON_ITEM_TOPLEVEL_KEYS or not isinstance(value, dict):
                continue
            items.setdefault(key, task)
            for alias in value.get("Aliases") or []:
                if isinstance(alias, str):
                    items.setdefault(alias, task)
        for column in load_item_map(project_path, task).values():
            mapped.setdefault(column, task)
    return items, mapped


def free_columns(columns: Iterable[str], task: str, *owners: Mapping[str, str]) -> list[str]:
    """The columns ``task`` may take: none that another task owns in ``owners`` (each ``{column: task}``)."""
    return [c for c in columns if all(o.get(c, task).lower() == task.lower() for o in owners)]


def check_project_map(
    project_path: str | Path, task: str, items: list[str], mapping: Mapping[str, str]
) -> dict[str, str]:
    """``check_item_map`` plus: no column is another task's item or stored map (every save path)."""
    clean = check_item_map(items, mapping)
    items_of, mapped = _claims(project_path)
    for column in clean.values():
        for owners, what in ((mapped, "already the item map of task"), (items_of, "an item of template")):
            if not free_columns([column], task, owners):
                raise ItemMapError(
                    f"column {column!r} is {what} {owners[column]!r}; "
                    "one column name can stand for one item per project"
                )
    return clean


def tasks_needing_map(project_path: str | Path, columns: list[str]) -> list[str]:
    """Project-library tasks with a missing item that a free column of the file could hold."""
    claims = _claims(project_path)
    return [
        task
        for task, template in _library(project_path).items()
        if any(
            r["why"] in ("number", "order")
            for r in suggest(template_items(template), free_columns(columns, task, *claims),
                             load_item_map(project_path, task))
        )
    ]


def suggest_for_project(project_path: str | Path, task: str, columns: list[str]) -> dict:
    """The guess for ``task``; ``columns`` in the answer are the file's columns ``task`` may take."""
    items = template_items(_project_template(project_path, task))
    free = free_columns(columns, task, *_claims(project_path))
    rows = suggest(items, free, load_item_map(project_path, task))
    for r in rows:
        print(f"[PRISM]   {r['item']} <- {r['column'] or '(none)'}  ({r['why']})")
    return {"task": task, "rows": rows, "columns": free}


def apply_choices(
    project_path: str | Path,
    task: str,
    columns: list[str],
    choices: Mapping[str, str] | None,
    accept: bool,
) -> Path | None:
    """Save the map: the suggestion (with ``accept``) overridden by ``choices``; '' clears a row."""
    if not accept and not choices:
        raise ItemMapError("nothing to save: pass accept or at least one choice")
    items = template_items(_project_template(project_path, task))
    saved = load_item_map(project_path, task, strict=True)
    free = free_columns(columns, task, *_claims(project_path))
    chosen = {r["item"]: r["column"] for r in suggest(items, free, saved) if r["column"]} if accept else {}
    chosen.update(choices or {})
    if not all(isinstance(v, str) for v in chosen.values()):
        raise ItemMapError("choices values must be column names (text)")
    missing = sorted({c for c in chosen.values() if c and c not in columns})
    if missing:
        raise ItemMapError(f"Not columns of the survey file: {', '.join(missing)}")
    check_project_map(project_path, task, items, chosen)
    return save_item_map(project_path, task, chosen, items)
