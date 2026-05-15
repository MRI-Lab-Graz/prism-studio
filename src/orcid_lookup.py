"""Utilities for looking up ORCID identifiers using the public ORCID API."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

_ORCID_PUBLIC_API_BASE = "https://pub.orcid.org/v3.0"
_ORCID_PUBLIC_API_HOST = "pub.orcid.org"
_JSON_ACCEPT_HEADER = "application/json"
_DEFAULT_TIMEOUT_SECONDS = 6.0
_DEFAULT_LIMIT = 5
_MAX_LIMIT = 10
_MAX_RESULT_ROWS = 50
_ORCID_ID_PATTERN = re.compile(r"^(?:https?://orcid\.org/)?(\d{4}-\d{4}-\d{4}-\d{3}[\dX])/?$", re.IGNORECASE)


class OrcidLookupError(RuntimeError):
    """Raised when ORCID lookup fails due to transport or response issues."""


def _normalize_name_token(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _normalize_for_match(value: str) -> str:
    lowered = _normalize_name_token(value).lower()
    if not lowered:
        return ""
    stripped = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", stripped).strip()


def _lucene_phrase(value: str) -> str:
    token = _normalize_name_token(value)
    escaped = token.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _build_search_query(given_names: str, family_name: str) -> str:
    given = _normalize_name_token(given_names)
    family = _normalize_name_token(family_name)
    clauses: list[str] = []
    if given:
        clauses.append(f"given-names:{_lucene_phrase(given)}")
    if family:
        clauses.append(f"family-name:{_lucene_phrase(family)}")
    if not clauses:
        raise ValueError("At least one name component is required")
    return " AND ".join(clauses)


def _validate_orcid_api_url(url: str) -> str:
    normalized_url = str(url or "").strip()
    parsed = urlsplit(normalized_url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != _ORCID_PUBLIC_API_HOST
        or parsed.port not in (None, 443)
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/v3.0")
    ):
        raise OrcidLookupError(
            "ORCID request URL must target the public HTTPS ORCID API"
        )
    return normalized_url


def _fetch_json(url: str, timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
    validated_url = _validate_orcid_api_url(url)
    request = Request(
        validated_url,
        headers={
            "Accept": _JSON_ACCEPT_HEADER,
            "User-Agent": "prism-studio-orcid-lookup",
        },
        method="GET",
    )
    try:
        # URL is restricted to the validated public ORCID HTTPS API.
        with urlopen(
            request, timeout=timeout_seconds
        ) as response:  # nosec B310
            payload = response.read().decode("utf-8")
    except HTTPError as exc:
        raise OrcidLookupError(f"ORCID request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise OrcidLookupError("ORCID request failed") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise OrcidLookupError("ORCID returned malformed JSON") from exc

    if not isinstance(data, dict):
        raise OrcidLookupError("ORCID returned unexpected payload")
    return data


def _extract_orcid_path(identifier_payload: dict[str, Any]) -> str:
    path = str(identifier_payload.get("path") or "").strip()
    if path:
        return path
    uri = str(identifier_payload.get("uri") or "").strip()
    if not uri:
        return ""
    return uri.rstrip("/").split("/")[-1].strip()


def _normalize_orcid_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    match = _ORCID_ID_PATTERN.match(raw)
    if not match:
        return ""
    return str(match.group(1)).upper()


def _has_public_person_details(person: dict[str, Any]) -> bool:
    details = {
        "biography": person.get("biography"),
        "researcher_urls": person.get("researcher-urls"),
        "keywords": person.get("keywords"),
        "external_identifiers": person.get("external-identifiers"),
        "addresses": person.get("addresses"),
    }
    serialized = json.dumps(details, ensure_ascii=False)
    return any(token in serialized for token in ('"value":', '"url":', '"city":', '"country":'))


def _fetch_person_profile(
    orcid_path: str, timeout_seconds: float
) -> tuple[str, str, bool]:
    person_url = f"{_ORCID_PUBLIC_API_BASE}/{quote(orcid_path)}/person"
    person = _fetch_json(person_url, timeout_seconds=timeout_seconds)
    name = person.get("name")
    if not isinstance(name, dict):
        return "", "", _has_public_person_details(person)

    given_value = name.get("given-names")
    family_value = name.get("family-name")

    given = ""
    family = ""
    if isinstance(given_value, dict):
        given = _normalize_name_token(str(given_value.get("value") or ""))
    if isinstance(family_value, dict):
        family = _normalize_name_token(str(family_value.get("value") or ""))
    return given, family, _has_public_person_details(person)


def _fetch_person_name(orcid_path: str, timeout_seconds: float) -> tuple[str, str]:
    given, family, _has_public_details = _fetch_person_profile(
        orcid_path,
        timeout_seconds,
    )
    return given, family


def _format_affiliation_label(organization: dict[str, Any]) -> str:
    name = _normalize_name_token(str(organization.get("name") or ""))
    if not name:
        return ""

    address = organization.get("address")
    if not isinstance(address, dict):
        return name

    city = _normalize_name_token(str(address.get("city") or ""))
    country = _normalize_name_token(str(address.get("country") or ""))
    location_parts = [part for part in (city, country) if part]
    if not location_parts:
        return name
    return f"{name} ({', '.join(location_parts)})"


def _extract_primary_affiliation_from_payload(
    payload: dict[str, Any],
    summary_key: str,
) -> str:
    groups = payload.get("affiliation-group")
    if not isinstance(groups, list):
        return ""

    for group in groups:
        if not isinstance(group, dict):
            continue
        summaries = group.get("summaries")
        if not isinstance(summaries, list):
            continue
        for summary_entry in summaries:
            if not isinstance(summary_entry, dict):
                continue
            summary = summary_entry.get(summary_key)
            if not isinstance(summary, dict):
                continue
            organization = summary.get("organization")
            if not isinstance(organization, dict):
                continue
            label = _format_affiliation_label(organization)
            if label:
                return label
    return ""


def _fetch_primary_affiliation(orcid_path: str, timeout_seconds: float) -> str:
    sources = (
        ("employments", "employment-summary"),
        ("educations", "education-summary"),
    )
    for endpoint, summary_key in sources:
        url = f"{_ORCID_PUBLIC_API_BASE}/{quote(orcid_path)}/{endpoint}"
        try:
            payload = _fetch_json(url, timeout_seconds=timeout_seconds)
        except OrcidLookupError:
            continue
        affiliation = _extract_primary_affiliation_from_payload(payload, summary_key)
        if affiliation:
            return affiliation
    return ""


def _candidate_rank(candidate: dict[str, Any], query_given: str, query_family: str) -> tuple[int, str]:
    given = _normalize_for_match(candidate.get("given_names", ""))
    family = _normalize_for_match(candidate.get("family_name", ""))

    given_matches = bool(query_given and given == query_given)
    family_matches = bool(query_family and family == query_family)

    if query_given and query_family:
        if given_matches and family_matches:
            return (0, candidate.get("orcid_id", ""))
        if family_matches:
            return (1, candidate.get("orcid_id", ""))
        if given_matches:
            return (2, candidate.get("orcid_id", ""))
        return (3, candidate.get("orcid_id", ""))

    if query_family:
        return ((0 if family_matches else 1), candidate.get("orcid_id", ""))
    if query_given:
        return ((0 if given_matches else 1), candidate.get("orcid_id", ""))
    return (1, candidate.get("orcid_id", ""))


def _build_candidate(orcid_path: str, timeout_seconds: float) -> dict[str, Any]:
    given, family = "", ""
    has_public_person_details = False
    affiliation = ""

    try:
        given, family, has_public_person_details = _fetch_person_profile(
            orcid_path,
            timeout_seconds,
        )
    except OrcidLookupError:
        # Keep the ID candidate even when profile metadata cannot be loaded.
        pass

    try:
        affiliation = _fetch_primary_affiliation(orcid_path, timeout_seconds)
    except OrcidLookupError:
        # Keep basic identity fields when affiliation metadata cannot be loaded.
        pass

    display_name = " ".join(part for part in (given, family) if part).strip()
    if not display_name:
        display_name = f"ORCID {orcid_path}"

    public_data_available = bool(affiliation or has_public_person_details)

    return {
        "orcid_id": orcid_path,
        "orcid": f"https://orcid.org/{orcid_path}",
        "given_names": given,
        "family_name": family,
        "display_name": display_name,
        "affiliation": affiliation,
        "public_data_available": public_data_available,
        "public_data_status": (
            "Public profile data available"
            if public_data_available
            else "Limited public profile data"
        ),
    }


def search_orcid_candidates(
    given_names: str,
    family_name: str,
    limit: int = _DEFAULT_LIMIT,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    preferred_orcid: str = "",
) -> list[dict[str, Any]]:
    """Search ORCID by person name and return ranked candidate identifiers."""
    normalized_limit = max(1, min(int(limit), _MAX_LIMIT))
    normalized_preferred_orcid = _normalize_orcid_id(preferred_orcid)
    query = _build_search_query(given_names=given_names, family_name=family_name)
    search_url = (
        f"{_ORCID_PUBLIC_API_BASE}/search?q={quote(query)}"
        f"&rows={_MAX_RESULT_ROWS}"
    )

    payload = _fetch_json(search_url, timeout_seconds=timeout_seconds)
    raw_results = payload.get("result")
    if not isinstance(raw_results, list):
        return []

    candidates: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw_item in raw_results:
        if not isinstance(raw_item, dict):
            continue
        identifier_payload = raw_item.get("orcid-identifier")
        if not isinstance(identifier_payload, dict):
            continue

        orcid_path = _extract_orcid_path(identifier_payload)
        if not orcid_path or orcid_path in seen_ids:
            continue

        seen_ids.add(orcid_path)
        candidates.append(_build_candidate(orcid_path, timeout_seconds))

    if normalized_preferred_orcid and normalized_preferred_orcid not in seen_ids:
        candidates.append(_build_candidate(normalized_preferred_orcid, timeout_seconds))
        seen_ids.add(normalized_preferred_orcid)

    query_given = _normalize_for_match(given_names)
    query_family = _normalize_for_match(family_name)
    def _sort_key(candidate: dict[str, Any]) -> tuple[int, int, str]:
        rank_weight, rank_id = _candidate_rank(
            candidate,
            query_given=query_given,
            query_family=query_family,
        )
        preferred_weight = (
            0
            if normalized_preferred_orcid
            and str(candidate.get("orcid_id") or "") == normalized_preferred_orcid
            else 1
        )
        return preferred_weight, rank_weight, rank_id

    candidates.sort(key=_sort_key)
    return candidates[:normalized_limit]
