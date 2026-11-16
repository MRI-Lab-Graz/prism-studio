import io
import json
import urllib.error
import urllib.request
from unittest import mock

import pytest

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
    with mock.patch("src.doi_lookup._open", return_value=_resp(msg)):
        r = d.lookup_doi("10.1000/x1")
    assert r["status"] == "ok" and r["citation"] == "A et al., 2020, T, J"


def test_not_found_and_unreachable():
    err404 = urllib.error.HTTPError("u", 404, "nf", {}, None)
    with mock.patch("src.doi_lookup._open", side_effect=err404):
        assert d.lookup_doi("10.1000/x1")["status"] == "not_found"
    with mock.patch("src.doi_lookup._open", side_effect=urllib.error.URLError("off")):
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
    with mock.patch("src.doi_lookup._open", fake):
        r = d.lookup_doi("10.23668/psycharchives.21079")
    assert r == {"status": "ok", "doi": "10.23668/psycharchives.21079", "title": "KSE", "authors": "Stephan & Fäth",
                 "year": 2025, "journal": "PsychArchives", "citation": "Stephan & Fäth, 2025, KSE, PsychArchives"}
    urls = [c[0] for c in fake.calls]
    assert urls == ["https://api.crossref.org/works/10.23668/psycharchives.21079",
                    "https://api.datacite.org/dois/10.23668/psycharchives.21079"]
    assert all(c[1] == "PRISM-Studio (DOI check)" and c[2] for c in fake.calls)


def test_both_404_is_not_found():
    with mock.patch("src.doi_lookup._open", _fake({"api.crossref.org": None, "api.datacite.org": None})):
        assert d.lookup_doi("10.1000/x1")["status"] == "not_found"


def test_crossref_hit_does_not_ask_datacite():
    fake = _fake({"api.crossref.org": {"message": {"title": ["T"]}}})
    with mock.patch("src.doi_lookup._open", fake):
        assert d.lookup_doi("10.1000/x1")["status"] == "ok"
    assert len(fake.calls) == 1


def test_network_error_at_datacite_is_unreachable():
    fake = _fake({"api.crossref.org": None, "api.datacite.org": urllib.error.URLError("off")})
    with mock.patch("src.doi_lookup._open", fake):
        assert d.lookup_doi("10.1000/x1")["status"] == "unreachable"


def test_invalid_makes_no_network_call():
    fake = _fake({})
    with mock.patch("src.doi_lookup._open", fake):
        assert d.lookup_doi("not a doi")["status"] == "invalid"
    assert fake.calls == []


def test_dot_dot_segment_is_invalid_without_network():
    fake = _fake({})
    with mock.patch("src.doi_lookup._open", fake):
        assert d.lookup_doi("10.1000/../x")["status"] == "invalid"
        assert d.lookup_doi("10.1000/a/../b")["status"] == "invalid"
        assert d.lookup_doi("10.1000/./x")["status"] == "invalid"
        assert d.lookup_doi("10.1000/.")["status"] == "invalid"
        assert d.lookup_doi("10.1000/x/")["status"] == "invalid"
    assert fake.calls == []


def test_non_dict_json_is_unreachable():
    with mock.patch("src.doi_lookup._open", _fake({"api.crossref.org": ["x"]})):
        assert d.lookup_doi("10.1000/x1")["status"] == "unreachable"


def test_empty_metadata_is_ok_but_flagged():
    with mock.patch("src.doi_lookup._open", _fake({"api.crossref.org": {"message": {}}})):
        r = d.lookup_doi("10.1000/x1")
    assert r["status"] == "ok" and r["empty"] is True


def test_filled_metadata_has_no_empty_flag():
    with mock.patch("src.doi_lookup._open", _fake({"api.crossref.org": {"message": {"title": ["T"]}}})):
        assert "empty" not in d.lookup_doi("10.1000/x1")


def test_oversized_response_is_unreachable():
    big = io.BytesIO(b'{"message": {"title": ["' + b"a" * (1024 * 1024 + 10) + b'"]}}')
    with mock.patch("src.doi_lookup._open", return_value=big):
        assert d.lookup_doi("10.1000/x1")["status"] == "unreachable"


def test_redirects_are_not_followed():
    req = urllib.request.Request("https://api.crossref.org/works/10.1000/x1")
    with pytest.raises(urllib.error.HTTPError):
        d._NoRedirect().redirect_request(req, None, 302, "Found", {}, "https://evil.example/")
