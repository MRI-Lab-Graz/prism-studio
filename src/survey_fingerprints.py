"""Fingerprints of a survey item's wording and scale: hashes only, never the item text."""

import hashlib
import json
import unicodedata

from src.survey_terms import _NOT_ITEMS, _collapse, _slug, _texts

VERSION = 1


def _hash(obj) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _num(value):
    return int(value) if isinstance(value, float) and value.is_integer() else value


def scale_hash(item: dict) -> str:
    levels = item.get("Levels")
    codes = sorted(str(_num(k)) for k in levels) if isinstance(levels, dict) else None
    return _hash({"Levels": codes or None, "MinValue": _num(item.get("MinValue")), "MaxValue": _num(item.get("MaxValue"))})


def wording_hashes(description, language: str) -> dict[str, str]:
    return {lang: _hash(unicodedata.normalize("NFC", text)) for lang, text in _texts(description, language).items()}


def fingerprint_sidecar(sidecar: dict, language: str | None = None) -> dict:
    study = sidecar.get("Study")
    task = _slug(str(study.get("TaskName") or "").strip()) if isinstance(study, dict) else ""
    technical = sidecar.get("Technical")
    default = str((technical.get("Language") if isinstance(technical, dict) else None) or "en")
    items = {}
    for key, item in sidecar.items():
        if key in _NOT_ITEMS or not isinstance(item, dict) or "AliasOf" in item:
            continue
        scales = [scale_hash(item)]
        for variant in item.get("VariantScales") or []:
            if isinstance(variant, dict) and scale_hash(variant) not in scales:
                scales.append(scale_hash(variant))
        items[key] = {"Wording": wording_hashes(item.get("Description"), default), "Scales": scales}
    if language is not None:
        if not any(language in entry["Wording"] for entry in items.values()):
            raise ValueError(f"language {language!r} is not carried by this sidecar")
        for entry in items.values():
            entry["Wording"] = {k: v for k, v in entry["Wording"].items() if k == language}
    return {"Version": VERSION, "Task": task, "Items": items}


def item_matches(entry: dict, column: dict, language: str) -> str:
    """Why a column is not the fingerprinted item ("" when it is)."""
    if "AliasOf" in column:
        return "alias"
    if scale_hash(column) not in entry.get("Scales", []):
        return "changed scale"
    ours = wording_hashes(column.get("Description"), language)  # no Description: scale alone
    theirs = entry.get("Wording", {})
    if ours and not ours.keys() & theirs.keys():
        return "language not registered"
    if any(ours[lang] != theirs[lang] for lang in ours.keys() & theirs.keys()):
        return "changed wording"
    return ""
