"""Match an imported questionnaire against the template library by question wording.

Read-only: the global and project libraries are only ever loaded, never written.
"""

from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

from src.converters import survey_templates as st

PAIR_THRESHOLD = 0.85
EXACT_THRESHOLD = 0.97
LEVEL_LABEL_THRESHOLD = 0.9
MEDIUM_SHARE = 0.7
_RANK = {"medium": 1, "high": 2, "exact": 3}
_TAG_RE = re.compile(r"<[^>]+>")
_NON_WORD_RE = re.compile(r"[\W_]+")


def normalize_wording(text) -> str:
    """Lowercase letters and digits only, single spaces; HTML and punctuation dropped."""
    text = html.unescape(_TAG_RE.sub(" ", str(text or "")))
    return _NON_WORD_RE.sub(" ", unicodedata.normalize("NFKC", text).lower()).strip()


def similarity(a: str, b: str) -> float:
    """Text similarity in [0, 1]. Below PAIR_THRESHOLD the value is only an upper bound."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    bound = 2 * min(len(a), len(b)) / (len(a) + len(b))
    if bound < PAIR_THRESHOLD:
        return bound
    matcher = SequenceMatcher(None, a, b, autojunk=False)
    upper = matcher.quick_ratio()
    return upper if upper < PAIR_THRESHOLD else matcher.ratio()


def _text(value, language: str) -> str:
    if isinstance(value, dict):
        value = st._pick_language_value(value, language) if value else ""
    return normalize_wording(value)


def _items(template: dict) -> list[tuple[str, dict]]:
    """Ordered (code, item) pairs of real items; metadata and alias-only entries skipped."""
    return [
        (key, value)
        for key, value in template.items()
        if key not in st._NON_ITEM_TOPLEVEL_KEYS
        and not st._METADATA_CODE_RE.match(key)
        and isinstance(value, dict)
        and "Description" in value
    ]


def _pair(imp_items, lib_items, language):
    """One-to-one pairing {imported index: (library index, similarity)}, best pairs first."""
    n, m = len(imp_items), len(lib_items)
    imp_texts = [_text(item.get("Description"), language) for _code, item in imp_items]
    lib_texts = [_text(item.get("Description"), language) for _code, item in lib_items]
    candidates = []
    for i, a in enumerate(imp_texts):
        for j, b in enumerate(lib_texts):
            score = similarity(a, b)
            if score >= PAIR_THRESHOLD:
                candidates.append((-score, abs(i / n - j / m), i, j))
    candidates.sort()
    used_lib, pairs = set(), {}
    for negative, _position, i, j in candidates:
        if i in pairs or j in used_lib:
            continue
        pairs[i] = (j, -negative)
        used_lib.add(j)
    return pairs


def _levels_ok(imp_item: dict, lib_item: dict, language: str):
    """True/False when both items have Levels, None when not comparable."""
    imp, lib = imp_item.get("Levels"), lib_item.get("Levels")
    if not isinstance(imp, dict) or not isinstance(lib, dict) or not imp or not lib:
        return None
    if set(imp) != set(lib):
        return False
    for key in imp:
        a, b = _text(imp[key], language), _text(lib[key], language)
        if (a or b) and similarity(a, b) < LEVEL_LABEL_THRESHOLD:
            return False
    return True


def _code_owners(template: dict) -> dict[str, str]:
    """code -> library item key that owns it: item keys, existing Aliases, alias-only entries."""
    owners = {}
    for key, value in template.items():
        if key in st._NON_ITEM_TOPLEVEL_KEYS or st._METADATA_CODE_RE.match(key) or not isinstance(value, dict):
            continue
        if "Description" in value:
            owners[key] = key
            aliases = value.get("Aliases")
            for alias in aliases if isinstance(aliases, list) else []:
                owners.setdefault(str(alias), key)
        elif isinstance(value.get("AliasOf"), str):
            owners.setdefault(key, value["AliasOf"])
    return owners


def _match_one(imp_items, lib_template: dict, language: str) -> dict | None:
    lib_items = _items(lib_template)
    n, m = len(imp_items), len(lib_items)
    if not n or not m or max(n, m) > 2 * min(n, m):
        return None
    pairs = _pair(imp_items, lib_items, language)
    paired = len(pairs)
    if paired == 0 or paired < MEDIUM_SHARE * n:
        return None

    id_map = {imp_items[i][0]: lib_items[j][0] for i, (j, _score) in pairs.items()}
    owners = _code_owners(lib_template)
    ids_conflict = any(owners.get(imp, lib) != lib for imp, lib in id_map.items())
    levels = [_levels_ok(imp_items[i][1], lib_items[j][1], language) for i, (j, _s) in pairs.items()]
    levels_ok = all(result is not False for result in levels)
    scores = [score for _j, score in pairs.values()]
    min_score = min(scores)

    if paired == n == m and min_score >= EXACT_THRESHOLD and levels_ok:
        confidence = "exact"
    elif paired == n and levels_ok:
        confidence = "high"
    else:
        confidence = "medium"
    if ids_conflict and confidence != "medium":
        confidence = "medium"

    paired_lib = {j for j, _s in pairs.values()}
    return {
        "confidence": confidence,
        "paired": paired,
        "imported_items": n,
        "library_items": m,
        "ids_identical": all(imp == lib for imp, lib in id_map.items()),
        "ids_conflict": ids_conflict,
        "adoptable": confidence in ("exact", "high"),
        "levels_ok": levels_ok,
        "mean_similarity": round(sum(scores) / paired, 4),
        "id_map": id_map,
        "reworded": [
            {"imported": imp_items[i][0], "library": lib_items[j][0], "similarity": round(score, 4)}
            for i, (j, score) in sorted(pairs.items())
            if score < EXACT_THRESHOLD
        ],
        "unpaired_imported": [code for i, (code, _item) in enumerate(imp_items) if i not in pairs],
        "unpaired_library": [code for j, (code, _item) in enumerate(lib_items) if j not in paired_lib],
    }


def best_library_match(template: dict, project_path=None) -> dict | None:
    """Best global/project library template for an imported questionnaire, or None."""
    imp_items = _items(template)
    if not imp_items:
        return None
    language = st._default_language_from_template(template)
    candidates = []
    if project_path:
        candidates += [(key, "project", t) for key, t in st._load_project_templates(project_path).items()]
    candidates += [(key, "global", t) for key, t in st._load_global_templates().items()]

    best, best_rank = None, None
    for key, source, tdata in candidates:
        found = _match_one(imp_items, tdata["json"], language)
        if not found:
            continue
        found.update(
            template_key=key,
            source=source,
            template_path=str(tdata["path"]),
            template_file=Path(tdata["path"]).name,
        )
        rank = (_RANK[found["confidence"]], found["mean_similarity"], source == "project")
        if best is None or rank > best_rank:
            best, best_rank = found, rank
    return best


def public_library_match(match: dict | None) -> dict | None:
    """The match as sent to the browser: everything but the local file path."""
    if match is None:
        return None
    return {key: value for key, value in match.items() if key != "template_path"}


def apply_library_template(match: dict | None) -> dict:
    """The matched library template (a copy) with the survey's codes added as ``Aliases``.

    Library IDs stay authoritative. Reads the library file; never writes it.
    """
    if not match or not match.get("adoptable"):
        raise ValueError(
            "The library template does not match every item one-to-one; import the questionnaire as new"
        )
    template = st._read_json(Path(match["template_path"]))
    for imported_code, library_code in match["id_map"].items():
        item = template.get(library_code)
        if imported_code == library_code or not isinstance(item, dict):
            continue
        aliases = item.setdefault("Aliases", [])
        if imported_code not in aliases:
            aliases.append(imported_code)
    return template
