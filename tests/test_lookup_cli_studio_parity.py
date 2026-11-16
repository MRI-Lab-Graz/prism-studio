"""The DOI and ORCID checks of Studio are `prism_tools doi lookup` / `orcid search`: same function, same JSON."""

import argparse
import io
import json
import os
import sys
import urllib.error
from pathlib import Path
from unittest import mock

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from src.cli.commands.lookup import cmd_doi_lookup, cmd_orcid_search  # noqa: E402
from src.orcid_lookup import OrcidLookupError  # noqa: E402
from src.cli.parser import build_prism_tools_parsers  # noqa: E402


def _client():
    from src.web.blueprints.projects import projects_bp

    app = Flask(__name__, root_path=str(ROOT / "app"))
    app.secret_key = os.urandom(32)
    app.register_blueprint(projects_bp)
    return app.test_client()


def _cli_json(fn, capsys, **kw):
    capsys.readouterr()
    try:
        fn(argparse.Namespace(json=True, **kw))
    except SystemExit:
        pass
    return json.loads(capsys.readouterr().out)


def _urlopen(routes):
    def urlopen(req, timeout=None):
        r = routes[req.full_url.split("/")[2]]
        if isinstance(r, Exception):
            raise r
        if r is None:
            raise urllib.error.HTTPError(req.full_url, 404, "nf", {}, None)
        return io.BytesIO(json.dumps(r).encode())

    return urlopen


DATACITE = {"data": {"attributes": {"titles": [{"title": "KSE"}], "creators": [{"familyName": "Stephan"}],
                                    "publicationYear": 2025, "publisher": "PsychArchives"}}}


@pytest.mark.parametrize("doi,routes", [
    ("10.23668/psycharchives.21079", {"api.crossref.org": None, "api.datacite.org": DATACITE}),
    ("10.1000/x1", {"api.crossref.org": None, "api.datacite.org": None}),
    ("10.1000/x1", {"api.crossref.org": urllib.error.URLError("off")}),
    ("not a doi", {}),
])
def test_doi_cli_prints_what_the_route_returns(doi, routes, capsys):
    with mock.patch("urllib.request.urlopen", _urlopen(routes)):
        via_route = _client().get("/api/projects/lookup-doi", query_string={"doi": doi}).get_json()
        via_cli = _cli_json(cmd_doi_lookup, capsys, doi=doi)
    assert via_cli == via_route


def test_doi_lookup_is_a_cli_command():
    _root, parsers = build_prism_tools_parsers(ROOT / "app")
    assert "doi" in parsers


CANDIDATE = {"orcid_id": "0000-0001-6234-0498", "orcid": "https://orcid.org/0000-0001-6234-0498", "given_names": "Karl",
             "family_name": "Koschutnig", "display_name": "Karl Koschutnig", "affiliation": "University of Graz"}


def _fake_search(given, family, limit=5, preferred_orcid=""):
    assert (given, family) == ("Karl", "Koschutnig")
    return [CANDIDATE][:limit]


def _failing_search(*a, **k):
    raise OrcidLookupError("down")


@pytest.mark.parametrize("params,search", [
    ({"given_names": "Karl", "family_name": "Koschutnig", "limit": "3"}, _fake_search),
    ({"given_names": "Karl", "family_name": "Koschutnig"}, _failing_search),
    ({}, _fake_search),
])
def test_orcid_cli_prints_what_the_route_returns(params, search, capsys):
    with mock.patch("src.orcid_lookup.search_orcid_candidates", search):
        via_route = _client().get("/api/projects/orcid/search", query_string=params).get_json()
        via_cli = _cli_json(
            cmd_orcid_search, capsys, given_names=params.get("given_names", ""),
            family_name=params.get("family_name", ""), limit=params.get("limit", ""), current_orcid="",
        )
    assert via_cli == via_route


def test_orcid_search_is_a_cli_command():
    _root, parsers = build_prism_tools_parsers(ROOT / "app")
    assert "orcid" in parsers
