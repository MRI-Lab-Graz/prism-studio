import json
import re
from pathlib import Path

_DEFAULT_CITATION_MESSAGE = "If you use this dataset, please cite it."


def _parse_cff_value(raw: str) -> str:
    value = raw.strip()
    if not value:
        return ""
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        try:
            return json.loads(value)
        except Exception:
            return value.strip("\"'")
    return value


def _split_recruitment_locations(raw_locations) -> list[str]:
    if raw_locations is None:
        return []
    if isinstance(raw_locations, str):
        values = raw_locations.split(";")
    elif isinstance(raw_locations, list):
        values = raw_locations
    else:
        return []
    return [str(item).strip() for item in values if str(item).strip()]


def _is_online_only_location(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
    return normalized in {"online", "online only", "online-only"}


def _validate_recruitment_payload(recruitment: dict | None) -> str | None:
    if not isinstance(recruitment, dict):
        return None

    locations = _split_recruitment_locations(recruitment.get("Location"))
    for location in locations:
        if _is_online_only_location(location):
            continue
        country = (
            location.rsplit(",", 1)[-1].strip() if "," in location else location.strip()
        )
        if not country:
            return "Recruitment location must include a country, or be set to 'Online'."

    period = recruitment.get("Period")
    if not isinstance(period, dict):
        return None

    start = str(period.get("Start") or "").strip()
    end = str(period.get("End") or "").strip()
    if not start or not end:
        return None

    date_pattern = re.compile(r"^\d{4}(-\d{2}){0,2}$")
    if (
        date_pattern.fullmatch(start)
        and date_pattern.fullmatch(end)
        and len(start) == len(end)
    ):
        if start > end:
            return "Recruitment period start must be before or equal to period end."

    return None


def _read_citation_cff_fields(citation_path: Path) -> dict:
    if not citation_path.exists():
        return {}

    authors = []
    references = []
    current_reference = None
    fields = {}
    current_author = None
    in_authors = False
    in_references = False

    try:
        with open(citation_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return {}

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("authors:"):
            in_authors = True
            in_references = False
            continue

        if stripped.startswith("references:"):
            in_references = True
            in_authors = False
            continue

        if stripped.startswith("title:"):
            fields["Title"] = _parse_cff_value(stripped.split(":", 1)[1])
            continue

        if stripped.startswith("doi:"):
            fields["DatasetDOI"] = _parse_cff_value(stripped.split(":", 1)[1])
            continue

        if stripped.startswith("license:"):
            fields["License"] = _parse_cff_value(stripped.split(":", 1)[1])
            continue

        if stripped.startswith("message:"):
            fields["HowToAcknowledge"] = _parse_cff_value(stripped.split(":", 1)[1])
            continue

        if in_authors:
            if stripped.startswith("- family-names:"):
                if current_author:
                    authors.append(current_author)
                current_author = {
                    "family": _parse_cff_value(stripped.split(":", 1)[1]),
                    "given": "",
                }
                continue
            if stripped.startswith("given-names:") and current_author is not None:
                current_author["given"] = _parse_cff_value(stripped.split(":", 1)[1])
                continue

        if in_references:
            if indent == 2 and stripped == "-":
                if current_reference:
                    references.append(current_reference)
                current_reference = {}
                continue

            if indent == 2 and stripped.startswith("-"):
                if current_reference:
                    references.append(current_reference)
                    current_reference = None

                raw = stripped[1:].strip()
                if ":" in raw:
                    key, value = raw.split(":", 1)
                    current_reference = {
                        key.strip(): _parse_cff_value(value)
                    }
                elif raw:
                    references.append(_parse_cff_value(raw))
                continue

            if current_reference is not None and indent >= 4 and ":" in stripped and not stripped.startswith("-"):
                key, value = stripped.split(":", 1)
                current_reference[key.strip()] = _parse_cff_value(value)
                continue

    if current_reference:
        references.append(current_reference)

    if current_author:
        authors.append(current_author)

    if authors:
        formatted = []
        for author in authors:
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            if given and family:
                formatted.append(f"{given} {family}")
            elif family:
                formatted.append(family)
            elif given:
                formatted.append(given)
        fields["Authors"] = formatted

    if references:
        normalized_references = []
        for reference in references:
            if isinstance(reference, dict):
                ref_url = str(reference.get("url") or "").strip()
                ref_doi = str(reference.get("doi") or "").strip()
                ref_title = str(reference.get("title") or "").strip()
                if ref_url:
                    normalized_references.append(ref_url)
                elif ref_doi:
                    normalized_references.append(ref_doi)
                elif ref_title:
                    normalized_references.append(ref_title)
            else:
                text = str(reference or "").strip()
                if text:
                    normalized_references.append(text)

        if normalized_references:
            fields["ReferencesAndLinks"] = normalized_references

    if fields.get("HowToAcknowledge") == _DEFAULT_CITATION_MESSAGE:
        fields.pop("HowToAcknowledge", None)

    return fields


def _merge_citation_fields(target: dict, citation_fields: dict) -> dict:
    if not citation_fields:
        return dict(target)

    merged = dict(target)
    for key in ("Authors", "License", "HowToAcknowledge", "ReferencesAndLinks"):
        if not merged.get(key) and citation_fields.get(key):
            merged[key] = citation_fields[key]
    return merged
