"""Per-project mapping from a survey file's column names to a template's item IDs.

Stored in ``code/item_maps/<task>.json`` as ``{item: column}``; only entries where
the column differs from the item are kept.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from pathlib import Path

from src.converters.survey_core import _NON_ITEM_TOPLEVEL_KEYS

MAP_DIR = Path("code") / "item_maps"
_TASK = re.compile(r"[A-Za-z0-9_-]+")
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


def map_path(project_path: str | Path, task: str) -> Path:
    if not isinstance(task, str) or not _TASK.fullmatch(task):
        raise ItemMapError(f"Invalid task name {task!r}: use letters, digits, '-' and '_' only")
    return _root(project_path) / MAP_DIR / f"{task}.json"


def _read(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("not a JSON object")
        if not all(isinstance(k, str) and k and isinstance(v, str) and v for k, v in raw.items()):
            raise ValueError("every entry must be a non-empty item ID and column name")
        return raw
    except (OSError, ValueError) as exc:
        print(f"[PRISM] WARNING item map {path} ignored: {exc}")
        return {}


def load_item_map(project_path: str | Path, task: str) -> dict[str, str]:
    path = map_path(project_path, task)
    return _read(path) if path.is_file() else {}


def save_item_map(
    project_path: str | Path, task: str, mapping: Mapping[str, str], items: list[str]
) -> Path | None:
    path = map_path(project_path, task)
    clean = {k: v.strip() for k, v in mapping.items() if isinstance(v, str) and v.strip()}
    unknown = [k for k in clean if k not in items]
    if unknown:
        raise ItemMapError(f"Not items of this template: {', '.join(unknown)}")
    columns = list(clean.values())
    twice = sorted({c for c in columns if columns.count(c) > 1})
    if twice:
        raise ItemMapError(f"Column used for more than one item: {', '.join(twice)}")
    clean = {k: v for k, v in clean.items() if k != v}
    if not clean:
        path.unlink(missing_ok=True)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(clean, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def item_alias_map(project_path: str | Path) -> dict[str, str]:
    """``{column: item}`` over every task's map; a column claimed twice is an error."""
    aliases: dict[str, str] = {}
    owner: dict[str, str] = {}
    for path in sorted((_root(project_path) / MAP_DIR).glob("*.json")):
        for item, column in _read(path).items():
            if column in owner:
                raise ItemMapError(
                    f"Column {column!r} is mapped in both item maps {owner[column]!r} and {path.stem!r}"
                )
            owner[column] = path.stem
            aliases[column] = item
    return aliases
