"""Resolve a DOI to a short citation string via the Crossref REST API."""

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
    family = [f for f in family if f]
    authors = (
        family[0] if len(family) == 1
        else f"{family[0]} et al." if len(family) > 2
        else " & ".join(family)
    ) if family else ""
    parts = (msg.get("issued") or {}).get("date-parts") or [[None]]
    year = parts[0][0] if parts and parts[0] else None
    journal = (msg.get("container-title") or [""])[0].strip()
    citation = ", ".join(str(p) for p in (authors, year, title, journal) if p)
    return {
        "title": title, "authors": authors, "year": year,
        "journal": journal, "citation": citation,
    }


def lookup_doi(value: str, timeout: float = 8.0) -> dict:
    """Return {status: 'ok'|'invalid'|'not_found'|'unreachable', doi, ...}.

    'unreachable' (offline, timeout, 5xx) means the DOI could not be checked,
    not that it is wrong.
    """
    doi = normalize_doi(value)
    if not DOI_RE.match(doi):
        return {"status": "invalid", "doi": doi}
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")
    req = urllib.request.Request(url, headers={"User-Agent": "PRISM-Studio (DOI check)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310  # nosec B310 - hardcoded https URL
            msg = json.load(resp).get("message") or {}
    except urllib.error.HTTPError as exc:
        return {"status": "not_found" if exc.code == 404 else "unreachable", "doi": doi}
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return {"status": "unreachable", "doi": doi}
    return {"status": "ok", "doi": doi, **format_crossref_work(msg)}
