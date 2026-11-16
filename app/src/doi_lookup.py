"""Resolve a DOI to a short citation string via the Crossref REST API (DataCite as fallback)."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)


def normalize_doi(value: str) -> str:
    doi = str(value or "").strip()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.IGNORECASE)
    doi = re.sub(r"^doi:\s*", "", doi, flags=re.IGNORECASE)
    return doi.strip()


def format_crossref_work(msg: dict) -> dict:
    """Reduce a Crossref ``message`` to {title, authors, year, journal, citation}."""
    title = (msg.get("title") or [""])[0].strip()
    family = [a.get("family") or a.get("name") or "" for a in msg.get("author") or []]
    parts = (msg.get("issued") or {}).get("date-parts") or [[None]]
    year = parts[0][0] if parts and parts[0] else None
    journal = (msg.get("container-title") or [""])[0].strip()
    return _short(family, year, title, journal)


def format_datacite_work(attrs: dict) -> dict:
    """Reduce DataCite ``data.attributes`` to the same shape as format_crossref_work."""
    title = ((attrs.get("titles") or [{}])[0].get("title") or "").strip()
    creators = attrs.get("creators") or []
    family = [c.get("familyName") or c.get("name") or "" for c in creators]
    year = attrs.get("publicationYear")
    pub = attrs.get("publisher")
    journal = ((pub.get("name") if isinstance(pub, dict) else pub) or "").strip()
    return _short(family, year, title, journal)


def _short(family: list, year, title: str, journal: str) -> dict:
    family = [f for f in family if f]
    authors = (
        family[0] if len(family) == 1
        else f"{family[0]} et al." if len(family) > 2
        else " & ".join(family)
    ) if family else ""
    citation = ", ".join(str(p) for p in (authors, year, title, journal) if p)
    return {"title": title, "authors": authors, "year": year, "journal": journal, "citation": citation}


# Crossref first, DataCite when Crossref does not know the DOI (e.g. 10.23668, the Open Test Archive).
# Fixed https hosts only; the DOI is the sole user input and is percent-quoted.
_AGENCIES = (
    ("https://api.crossref.org/works/", lambda body: format_crossref_work(body.get("message") or {})),
    ("https://api.datacite.org/dois/", lambda body: format_datacite_work((body.get("data") or {}).get("attributes") or {})),
)


def lookup_doi(value: str, timeout: float = 8.0) -> dict:
    """Return {status: 'ok'|'invalid'|'not_found'|'unreachable', doi, ...}.

    'unreachable' (offline, timeout, 5xx) means the DOI could not be checked,
    not that it is wrong. 'not_found' only when every agency answered 404.
    """
    doi = normalize_doi(value)
    if not DOI_RE.match(doi):
        return {"status": "invalid", "doi": doi}
    for base, fmt in _AGENCIES:
        req = urllib.request.Request(
            base + urllib.parse.quote(doi, safe="/"), headers={"User-Agent": "PRISM-Studio (DOI check)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310 - hardcoded https URL
                body = json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            return {"status": "unreachable", "doi": doi}
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return {"status": "unreachable", "doi": doi}
        return {"status": "ok", "doi": doi, **fmt(body)}
    return {"status": "not_found", "doi": doi}
