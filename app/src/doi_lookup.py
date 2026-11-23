"""Resolve a DOI to a short citation string via the Crossref REST API (DataCite as fallback)."""

import json
import re
import urllib.error
import urllib.parse
import urllib.request

DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$", re.IGNORECASE)
_MAX_BYTES = 1024 * 1024  # a metadata record is a few KB; refuse to read more


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Only the fixed hosts below are asked: a redirect (to anywhere) is an error, never followed."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirect)


def _open(req, timeout):
    return _OPENER.open(req, timeout=timeout)  # nosec B310 - fixed https hosts only


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
    # '//' inside a DOI is real (10.1026//0012-...); only '.', '..' and a trailing '/' are refused
    if not DOI_RE.match(doi) or doi.endswith("/") or any(seg in (".", "..") for seg in doi.split("/")):
        return {"status": "invalid", "doi": doi}
    for base, fmt in _AGENCIES:
        req = urllib.request.Request(  # noqa: S310 - fixed https hosts only, DOI is percent-quoted
            base + urllib.parse.quote(doi, safe="/"), headers={"User-Agent": "PRISM-Studio (DOI check)"}
        )
        try:
            with _open(req, timeout) as resp:
                raw = resp.read(_MAX_BYTES + 1)
            if len(raw) > _MAX_BYTES:
                return {"status": "unreachable", "doi": doi}
            body = json.loads(raw)
            if not isinstance(body, dict):
                return {"status": "unreachable", "doi": doi}
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                continue
            return {"status": "unreachable", "doi": doi}
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            return {"status": "unreachable", "doi": doi}
        work = fmt(body)
        # registered but the agency returned no metadata: ok, flagged so the UI can say so
        return {"status": "ok", "doi": doi, **work, **({} if work["title"] or work["authors"] else {"empty": True})}
    return {"status": "not_found", "doi": doi}
