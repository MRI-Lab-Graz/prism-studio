import io
import json
import urllib.error
from unittest import mock

from src import doi_lookup as d


def _resp(payload):
    return io.BytesIO(json.dumps(payload).encode())


def test_normalize_and_invalid():
    assert d.normalize_doi(" https://doi.org/10.1000/x1 ") == "10.1000/x1"
    assert d.normalize_doi("doi: 10.1000/x1") == "10.1000/x1"
    assert d.lookup_doi("not a doi")["status"] == "invalid"


def test_ok_formats_citation():
    msg = {"message": {"title": ["T"], "author": [{"family": "A"}, {"family": "B"}, {"family": "C"}],
                       "issued": {"date-parts": [[2020]]}, "container-title": ["J"]}}
    with mock.patch("urllib.request.urlopen", return_value=_resp(msg)):
        r = d.lookup_doi("10.1000/x1")
    assert r["status"] == "ok" and r["citation"] == "A et al., 2020, T, J"


def test_not_found_and_unreachable():
    err404 = urllib.error.HTTPError("u", 404, "nf", {}, None)
    with mock.patch("urllib.request.urlopen", side_effect=err404):
        assert d.lookup_doi("10.1000/x1")["status"] == "not_found"
    with mock.patch("urllib.request.urlopen", side_effect=urllib.error.URLError("off")):
        assert d.lookup_doi("10.1000/x1")["status"] == "unreachable"


DATACITE = {"data": {"attributes": {
    "titles": [{"title": "KSE"}],
    "creators": [{"name": "Stephan, E.", "familyName": "Stephan"}, {"name": "Fäth, M.", "familyName": "Fäth"}],
    "publicationYear": 2025, "publisher": "PsychArchives",
}}}


def _fake(routes):
    """urlopen stand-in: routes maps a host to a payload dict, an exception, or None for 404."""
    calls = []

    def urlopen(req, timeout=None):
        url = req.full_url
        calls.append((url, req.get_header("User-agent"), timeout))
        host = url.split("/")[2]
        r = routes[host]
        if isinstance(r, Exception):
            raise r
        if r is None:
            raise urllib.error.HTTPError(url, 404, "nf", {}, None)
        return _resp(r)

    urlopen.calls = calls
    return urlopen


def test_crossref_404_falls_back_to_datacite():
    fake = _fake({"api.crossref.org": None, "api.datacite.org": DATACITE})
    with mock.patch("urllib.request.urlopen", fake):
        r = d.lookup_doi("10.23668/psycharchives.21079")
    assert r == {"status": "ok", "doi": "10.23668/psycharchives.21079", "title": "KSE", "authors": "Stephan & Fäth",
                 "year": 2025, "journal": "PsychArchives", "citation": "Stephan & Fäth, 2025, KSE, PsychArchives"}
    urls = [c[0] for c in fake.calls]
    assert urls == ["https://api.crossref.org/works/10.23668/psycharchives.21079",
                    "https://api.datacite.org/dois/10.23668/psycharchives.21079"]
    assert all(c[1] == "PRISM-Studio (DOI check)" and c[2] for c in fake.calls)


def test_both_404_is_not_found():
    with mock.patch("urllib.request.urlopen", _fake({"api.crossref.org": None, "api.datacite.org": None})):
        assert d.lookup_doi("10.1000/x1")["status"] == "not_found"


def test_crossref_hit_does_not_ask_datacite():
    fake = _fake({"api.crossref.org": {"message": {"title": ["T"]}}})
    with mock.patch("urllib.request.urlopen", fake):
        assert d.lookup_doi("10.1000/x1")["status"] == "ok"
    assert len(fake.calls) == 1


def test_network_error_at_datacite_is_unreachable():
    fake = _fake({"api.crossref.org": None, "api.datacite.org": urllib.error.URLError("off")})
    with mock.patch("urllib.request.urlopen", fake):
        assert d.lookup_doi("10.1000/x1")["status"] == "unreachable"


def test_invalid_makes_no_network_call():
    fake = _fake({})
    with mock.patch("urllib.request.urlopen", fake):
        assert d.lookup_doi("not a doi")["status"] == "invalid"
    assert fake.calls == []
