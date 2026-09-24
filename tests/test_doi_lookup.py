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
