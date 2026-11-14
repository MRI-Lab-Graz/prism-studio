"""Check the mapping files under mappings/<modality>/<family>.json (stdlib only).

Usage: python scripts/check_mappings.py [--repo DIR] [--mappings DIR]
Prints one line per problem and exits 1 when there is any. The format is in specs/mappings.md.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_terms  # noqa: E402
import survey_ids  # noqa: E402

FIELDS = ("SameAs", "Measures", "ValueRules", "Levels")
LEVEL_FIELDS = ("Measures", "ValueRules")
MEASURES_KEYS = ("URL", "Match", "Higher", "Source", "Checked", "Status")
MATCH = ("exact", "broader", "narrower", "related")
HIGHER = ("more", "less")
STATUS = ("reviewed", "unreviewed")
OPS = ("==", "!=", ">=", ">", "<=", "<", "in")
_SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,62}")
_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_KEY = re.compile(r"prism:([a-z][a-z0-9-]{0,62})(\.[a-z0-9][a-z0-9-]{0,62})*")
MAX_TEXT = 300


def _text(value) -> bool:
    return isinstance(value, str) and 0 < len(value) <= MAX_TEXT and "\n" not in value


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _scalar(value) -> bool:
    return _number(value) or isinstance(value, str)


def load_vocabularies(path: Path) -> tuple[dict[str, re.Pattern], list[str]]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [f"vocabularies.json: cannot read ({exc})"]
    vocabs, problems = {}, []
    if not isinstance(data, dict):
        return {}, ["vocabularies.json: must hold a JSON object"]
    for name, entry in data.items():
        try:
            vocabs[name] = re.compile(entry["pattern"])
        except (TypeError, KeyError, re.error) as exc:
            problems.append(f"vocabularies.json: {name!r} needs a valid pattern ({exc})")
    return vocabs, problems


def _measures(value, where, vocabs) -> list[str]:
    if not isinstance(value, list):
        return [f"{where}: Measures must be a list"]
    out = []
    for i, entry in enumerate(value):
        at = f"{where}: Measures[{i}]"
        if not isinstance(entry, dict):
            out.append(f"{at} must be an object")
            continue
        out += [f"{at}: unknown key {k!r}" for k in entry if k not in MEASURES_KEYS]
        url = entry.get("URL")
        if not isinstance(url, str):
            out.append(f"{at}: URL is required and must be a string")
        elif not any(p.fullmatch(url) for p in vocabs.values()):
            out.append(f"{at}: URL {url!r} matches no known vocabulary")
        for key, allowed in (("Match", MATCH), ("Higher", HIGHER), ("Status", STATUS)):
            if key in entry and entry[key] not in allowed:
                out.append(f"{at}: {key} must be one of {', '.join(allowed)}")
        if "Source" in entry and not _text(entry["Source"]):
            out.append(f"{at}: Source must be a short string")
        if "Checked" in entry:
            try:
                ok = isinstance(entry["Checked"], str) and _DATE.fullmatch(entry["Checked"])
                ok = ok and datetime.date.fromisoformat(entry["Checked"])
            except ValueError:
                ok = False
            if not ok:
                out.append(f"{at}: Checked must be a date YYYY-MM-DD")
    return out


def _value_rules(value, where, _vocabs) -> list[str]:
    if not isinstance(value, list):
        return [f"{where}: ValueRules must be a list"]
    out = []
    for i, rule in enumerate(value):
        at = f"{where}: ValueRules[{i}]"
        if not isinstance(rule, dict):
            out.append(f"{at} must be an object")
            continue
        out += [f"{at}: unknown key {k!r}" for k in rule if k not in ("Name", "Source", "Rules")]
        if not (isinstance(rule.get("Name"), str) and _SLUG.fullmatch(rule["Name"])):
            out.append(f"{at}: Name must be a slug")
        if not _text(rule.get("Source")):
            out.append(f"{at}: Source is required (a short string)")
        rules = rule.get("Rules")
        if not (isinstance(rules, list) and rules):
            out.append(f"{at}: Rules must be a non-empty list")
            continue
        for j, r in enumerate(rules):
            rat = f"{at}: Rules[{j}]"
            when = r.get("When") if isinstance(r, dict) else None
            if not (isinstance(r, dict) and set(r) == {"When", "State"} and isinstance(when, dict)
                    and set(when) == {"Op", "Value"}):
                out.append(f"{rat} must be {{When: {{Op, Value}}, State}}")
                continue
            if when["Op"] not in OPS:
                out.append(f"{rat}: Op must be one of {', '.join(OPS)}")
            elif when["Op"] == "in":
                if not (isinstance(when["Value"], list) and all(_scalar(v) for v in when["Value"])):
                    out.append(f"{rat}: Value of 'in' must be a list of numbers or strings")
            elif not _scalar(when["Value"]):
                out.append(f"{rat}: Value must be a number or a string")
            if not (isinstance(r["State"], str) and _SLUG.fullmatch(r["State"])):
                out.append(f"{rat}: State must be a slug")
    return out


def _same_as(value, where, vocabs) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where}: SameAs must be an object {{vocabulary: URL}}"]
    out = []
    for name, url in value.items():
        if name not in vocabs:
            out.append(f"{where}: SameAs has an unknown vocabulary {name!r} (known: {', '.join(vocabs)})")
        elif not isinstance(url, str) or not vocabs[name].fullmatch(url):
            out.append(f"{where}: SameAs {name} {url!r} must match {vocabs[name].pattern}")
    return out


def _levels(value, where, vocabs, defined) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where}: Levels must be an object"]
    if not defined:
        return [f"{where}: Levels given, but this ID has no Levels in its definition"]
    out = []
    for code, entry in value.items():
        at = f"{where}: Levels {code!r}"
        if code not in defined:
            out.append(f"{at} is not a level of this ID (has: {', '.join(sorted(defined))})")
        if not isinstance(entry, dict):
            out.append(f"{at} must be an object")
            continue
        out += [f"{at}: only {' and '.join(LEVEL_FIELDS)} are allowed, not {k!r}" for k in entry if k not in LEVEL_FIELDS]
        for field, check in (("Measures", _measures), ("ValueRules", _value_rules)):
            if field in entry:
                out += check(entry[field], at, vocabs)
    return out


def entry_problems(entry, where, vocabs, defined) -> list[str]:
    if not isinstance(entry, dict):
        return [f"{where}: must be an object"]
    out = [f"{where}: unknown field {k!r} (allowed: {', '.join(FIELDS)})" for k in entry if k not in FIELDS]
    for field, check in (("SameAs", _same_as), ("Measures", _measures), ("ValueRules", _value_rules)):
        if field in entry:
            out += check(entry[field], where, vocabs)
    if "Levels" in entry:
        out += _levels(entry["Levels"], where, vocabs, defined)
    return out


def _level_codes(levels) -> set[str] | None:
    return {str(k) for k in levels} if isinstance(levels, dict) and levels else None


def survey_definitions(repo: Path) -> tuple[dict[str, set[str] | None], list[str]]:
    """{derived ID: its level codes or None} for the library templates, and the derivation's own problems."""
    library = Path(repo) / "library" / "survey"
    registry, problems = survey_ids.build_survey_registry(library, Path(repo) / "recipes" / "survey")
    problems = [p for p in problems if "no library template" not in p]  # a recipe may wait for its template
    levels: dict[str, set[str] | None] = {t["TermID"]: None for t in registry.values()}
    for path, task, template in survey_ids._templates(library, []):
        for key, item in template.items():
            if key in survey_ids._NOT_ITEMS or not isinstance(item, dict) or "AliasOf" in item:
                continue
            tid = f"prism:{survey_ids.item_local_id(task, key)}"
            if tid in levels:
                codes = set(_level_codes(item.get("Levels")) or ())
                for variant in item.get("VariantScales") or []:
                    codes |= _level_codes(variant.get("Levels") if isinstance(variant, dict) else None) or set()
                levels[tid] = codes or None
    return levels, problems


def _released_survey_ids(repo: Path) -> set[str]:
    try:
        return {l.strip() for l in (Path(repo) / "ids" / "survey-ids.txt").read_text(encoding="utf-8").splitlines() if l.strip()}
    except OSError:
        return set()


def check(repo: Path, mappings: Path | None = None) -> list[str]:
    repo = Path(repo)
    mappings = Path(mappings) if mappings else repo / "mappings"
    if not mappings.is_dir():
        return []
    vocabs, problems = load_vocabularies(mappings / "vocabularies.json")

    # What exists, per modality: {full ID: level codes or None}
    declared = check_terms.term_modalities(repo)
    known: dict[str, dict[str, set[str] | None]] = {}
    for modality in declared:
        registry, found = check_terms.load_terms(repo / "terms" / modality)
        problems += [f"terms/{modality}/{p}" for p in found]
        known[modality] = {f"prism:{stem}": _level_codes(t.get("Levels")) for stem, t in registry.items()}
    derived, found = survey_definitions(repo)
    released = _released_survey_ids(repo)
    problems += [f"library: {p}" for p in found]
    problems += [f"ids/survey-ids.txt: {tid} (derived from library/ and recipes/) is not in the released list"
                 for tid in sorted(set(derived) - released)]
    known["survey"] = {tid: derived.get(tid) for tid in released}

    owner: dict[str, str] = {}
    for folder in sorted(p for p in mappings.iterdir() if p.is_dir()):
        modality = folder.name
        if modality not in known:
            problems.append(f"mappings/{modality}: unknown modality (known: {', '.join(known)})")
            continue
        for path in sorted(folder.glob("*.json")):
            name = f"mappings/{modality}/{path.name}"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                problems.append(f"{name}: cannot read ({exc})")
                continue
            if not isinstance(data, dict):
                problems.append(f"{name}: must hold a JSON object")
                continue
            for key, entry in data.items():
                where = f"{name}: {key}"
                match = _KEY.fullmatch(key)
                if not match:
                    problems.append(f"{where}: key must be a prism:<id>")
                    continue
                family = match.group(1)
                if family != path.stem:
                    problems.append(f"{where}: the family of this ID is {family!r}, the file is {path.stem!r}")
                ids = known[modality]
                parent = f"prism:{family}"
                if key not in ids and not (modality != "survey" and parent in ids and "." in key):
                    problems.append(f"{where}: not a released {modality} ID")
                if key in owner and owner[key] != name:
                    problems.append(f"{where}: already mapped in {owner[key]} (an ID is in one file)")
                owner.setdefault(key, name)
                problems += entry_problems(entry, where, vocabs, ids.get(key))
    return problems


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", type=Path, default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--mappings", type=Path, help="the mappings folder (default REPO/mappings)")
    args = ap.parse_args(argv)
    problems = check(args.repo, args.mappings)
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
