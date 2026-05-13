import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.orcid_lookup import (
    OrcidLookupError,
    _build_candidate,
    _build_search_query,
    _candidate_rank,
    _extract_orcid_path,
    _extract_primary_affiliation_from_payload,
    _fetch_json,
    _fetch_person_name,
    _fetch_person_profile,
    _fetch_primary_affiliation,
    _format_affiliation_label,
    _lucene_phrase,
    _normalize_orcid_id,
    _normalize_for_match,
    _normalize_name_token,
    search_orcid_candidates,
)


class TestOrcidLookup(unittest.TestCase):
    def test_normalizers_and_query_helpers(self):
        self.assertEqual(_normalize_name_token("  Ada   Lovelace "), "Ada Lovelace")
        self.assertEqual(_normalize_for_match("Ada-Lovelace!"), "ada lovelace")
        self.assertEqual(_normalize_for_match(""), "")
        self.assertEqual(_lucene_phrase('Ada "A"'), '"Ada \\"A\\""')
        self.assertEqual(
            _normalize_orcid_id("https://orcid.org/0000-0001-7316-3140"),
            "0000-0001-7316-3140",
        )
        self.assertEqual(
            _normalize_orcid_id("0009-0001-0825-932x"),
            "0009-0001-0825-932X",
        )
        self.assertEqual(_normalize_orcid_id("bad-id"), "")

        self.assertEqual(
            _build_search_query("Ada", "Lovelace"),
            'given-names:"Ada" AND family-name:"Lovelace"',
        )
        self.assertEqual(_build_search_query("Ada", ""), 'given-names:"Ada"')
        self.assertEqual(_build_search_query("", "Lovelace"), 'family-name:"Lovelace"')

        with self.assertRaises(ValueError):
            _build_search_query("", "")

    def test_fetch_json_success_and_error_paths(self):
        class _FakeResponse:
            def __init__(self, payload: bytes):
                self._payload = payload

            def read(self):
                return self._payload

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch(
            "src.orcid_lookup.urlopen",
            return_value=_FakeResponse(b'{"ok": true}'),
        ):
            self.assertEqual(_fetch_json("https://example.com"), {"ok": True})

        with patch(
            "src.orcid_lookup.urlopen",
            side_effect=HTTPError("https://example.com", 503, "down", None, None),
        ):
            with self.assertRaises(OrcidLookupError):
                _fetch_json("https://example.com")

        with patch("src.orcid_lookup.urlopen", side_effect=URLError("offline")):
            with self.assertRaises(OrcidLookupError):
                _fetch_json("https://example.com")

        with patch(
            "src.orcid_lookup.urlopen",
            return_value=_FakeResponse(b"not-json"),
        ):
            with self.assertRaises(OrcidLookupError):
                _fetch_json("https://example.com")

        with patch(
            "src.orcid_lookup.urlopen",
            return_value=_FakeResponse(b"[]"),
        ):
            with self.assertRaises(OrcidLookupError):
                _fetch_json("https://example.com")

    def test_extract_orcid_path(self):
        self.assertEqual(_extract_orcid_path({"path": "0000-0001"}), "0000-0001")
        self.assertEqual(
            _extract_orcid_path({"uri": "https://orcid.org/0000-0002"}),
            "0000-0002",
        )
        self.assertEqual(_extract_orcid_path({}), "")

    def test_person_and_affiliation_helpers(self):
        with patch(
            "src.orcid_lookup._fetch_json",
            return_value={
                "name": {
                    "given-names": {"value": "Ada"},
                    "family-name": {"value": "Lovelace"},
                }
            },
        ):
            self.assertEqual(
                _fetch_person_name("0000-0000", timeout_seconds=1.0),
                ("Ada", "Lovelace"),
            )
            self.assertEqual(
                _fetch_person_profile("0000-0000", timeout_seconds=1.0),
                ("Ada", "Lovelace", False),
            )

        with patch("src.orcid_lookup._fetch_json", return_value={"name": []}):
            self.assertEqual(
                _fetch_person_name("0000-0000", timeout_seconds=1.0),
                ("", ""),
            )

        self.assertEqual(_format_affiliation_label({"name": "Uni"}), "Uni")
        self.assertEqual(
            _format_affiliation_label(
                {
                    "name": "Uni",
                    "address": {"city": "Graz", "country": "AT"},
                }
            ),
            "Uni (Graz, AT)",
        )
        self.assertEqual(_format_affiliation_label({"address": {"city": "Graz"}}), "")

        payload = {
            "affiliation-group": [
                {
                    "summaries": [
                        {
                            "employment-summary": {
                                "organization": {
                                    "name": "University of Graz",
                                    "address": {"country": "AT"},
                                }
                            }
                        }
                    ]
                }
            ]
        }
        self.assertEqual(
            _extract_primary_affiliation_from_payload(payload, "employment-summary"),
            "University of Graz (AT)",
        )
        self.assertEqual(
            _extract_primary_affiliation_from_payload({}, "employment-summary"),
            "",
        )

    def test_fetch_primary_affiliation_uses_fallback_sources(self):
        def fake_fetch(url: str, timeout_seconds: float = 6.0):
            if url.endswith("/employments"):
                return {"affiliation-group": []}
            if url.endswith("/educations"):
                return {
                    "affiliation-group": [
                        {
                            "summaries": [
                                {
                                    "education-summary": {
                                        "organization": {"name": "Uni", "address": {"country": "DE"}}
                                    }
                                }
                            ]
                        }
                    ]
                }
            return {}

        with patch("src.orcid_lookup._fetch_json", side_effect=fake_fetch):
            self.assertEqual(_fetch_primary_affiliation("0000", 1.0), "Uni (DE)")

        with patch("src.orcid_lookup._fetch_json", side_effect=OrcidLookupError("x")):
            self.assertEqual(_fetch_primary_affiliation("0000", 1.0), "")

    def test_candidate_rank_branches(self):
        candidate = {"given_names": "Ada", "family_name": "Lovelace", "orcid_id": "x"}
        self.assertEqual(_candidate_rank(candidate, "ada", "lovelace"), (0, "x"))
        self.assertEqual(_candidate_rank(candidate, "nope", "lovelace"), (1, "x"))
        self.assertEqual(_candidate_rank(candidate, "ada", "nope"), (2, "x"))
        self.assertEqual(_candidate_rank(candidate, "nope", "nope"), (3, "x"))
        self.assertEqual(_candidate_rank(candidate, "", "lovelace"), (0, "x"))
        self.assertEqual(_candidate_rank(candidate, "ada", ""), (0, "x"))
        self.assertEqual(_candidate_rank(candidate, "", ""), (1, "x"))

    def test_search_orcid_candidates_handles_non_list_results(self):
        with patch("src.orcid_lookup._fetch_json", return_value={"result": "invalid"}):
            self.assertEqual(search_orcid_candidates("Ada", "Lovelace"), [])

    def test_search_orcid_candidates_skips_bad_rows_dedupes_and_respects_limit(self):
        with patch(
            "src.orcid_lookup._fetch_json",
            return_value={
                "result": [
                    "bad-row",
                    {"orcid-identifier": "bad"},
                    {"orcid-identifier": {"path": "0000-0001"}},
                    {"orcid-identifier": {"path": "0000-0001"}},
                    {"orcid-identifier": {"path": "0000-0002"}},
                ]
            },
        ), patch(
            "src.orcid_lookup._fetch_person_name",
            side_effect=[("Ada", "Lovelace"), ("Bea", "Other")],
        ), patch(
            "src.orcid_lookup._fetch_primary_affiliation",
            return_value="",
        ):
            candidates = search_orcid_candidates("Ada", "Lovelace", limit=1)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["orcid_id"], "0000-0001")

    def test_search_orcid_candidates_survives_person_and_affiliation_lookup_failures(self):
        with patch(
            "src.orcid_lookup._fetch_json",
            return_value={
                "result": [{"orcid-identifier": {"path": "0000-0009"}}]
            },
        ), patch(
            "src.orcid_lookup._fetch_person_name",
            side_effect=OrcidLookupError("person failed"),
        ), patch(
            "src.orcid_lookup._fetch_primary_affiliation",
            side_effect=OrcidLookupError("affiliation failed"),
        ):
            candidates = search_orcid_candidates("Ada", "Lovelace")

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["display_name"], "ORCID 0000-0009")
        self.assertEqual(candidates[0]["affiliation"], "")

    def test_search_orcid_candidates_includes_employment_affiliation(self):
        def fake_fetch(url: str, timeout_seconds: float = 6.0):
            if "/search?" in url:
                return {
                    "result": [
                        {
                            "orcid-identifier": {
                                "path": "0000-0001-6234-0498",
                            }
                        }
                    ]
                }
            if url.endswith("/person"):
                return {
                    "name": {
                        "given-names": {"value": "Karl"},
                        "family-name": {"value": "Koschutnig"},
                    }
                }
            if url.endswith("/employments"):
                return {
                    "affiliation-group": [
                        {
                            "summaries": [
                                {
                                    "employment-summary": {
                                        "organization": {
                                            "name": "University of Graz",
                                            "address": {
                                                "city": "Graz",
                                                "country": "AT",
                                            },
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            if url.endswith("/educations"):
                return {"affiliation-group": []}
            raise AssertionError(f"Unexpected ORCID URL: {url}")

        with patch("src.orcid_lookup._fetch_json", side_effect=fake_fetch):
            candidates = search_orcid_candidates("Karl", "Koschutnig", limit=5)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["orcid_id"], "0000-0001-6234-0498")
        self.assertEqual(candidates[0]["affiliation"], "University of Graz (Graz, AT)")
        self.assertTrue(candidates[0]["public_data_available"])
        self.assertEqual(
            candidates[0]["public_data_status"],
            "Public profile data available",
        )

    def test_search_orcid_candidates_falls_back_to_education_affiliation(self):
        def fake_fetch(url: str, timeout_seconds: float = 6.0):
            if "/search?" in url:
                return {
                    "result": [
                        {
                            "orcid-identifier": {
                                "path": "0000-0002-0000-0001",
                            }
                        }
                    ]
                }
            if url.endswith("/person"):
                return {
                    "name": {
                        "given-names": {"value": "Anna"},
                        "family-name": {"value": "Example"},
                    }
                }
            if url.endswith("/employments"):
                return {"affiliation-group": []}
            if url.endswith("/educations"):
                return {
                    "affiliation-group": [
                        {
                            "summaries": [
                                {
                                    "education-summary": {
                                        "organization": {
                                            "name": "Example University",
                                            "address": {"country": "DE"},
                                        }
                                    }
                                }
                            ]
                        }
                    ]
                }
            raise AssertionError(f"Unexpected ORCID URL: {url}")

        with patch("src.orcid_lookup._fetch_json", side_effect=fake_fetch):
            candidates = search_orcid_candidates("Anna", "Example", limit=5)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["affiliation"], "Example University (DE)")

    def test_search_orcid_candidates_seeds_preferred_orcid_when_missing(self):
        preferred = "0000-0001-7316-3140"

        with patch(
            "src.orcid_lookup._fetch_json",
            return_value={
                "result": [
                    {"orcid-identifier": {"path": "0000-0002-3237-1450"}},
                ]
            },
        ), patch(
            "src.orcid_lookup._build_candidate",
            side_effect=lambda orcid_id, _timeout: {
                "orcid_id": orcid_id,
                "orcid": f"https://orcid.org/{orcid_id}",
                "given_names": "Andreas",
                "family_name": "Fink",
                "display_name": "Andreas Fink",
                "affiliation": "",
                "public_data_available": False,
                "public_data_status": "Limited public profile data",
            },
        ):
            candidates = search_orcid_candidates(
                "Andreas",
                "Fink",
                limit=2,
                preferred_orcid=preferred,
            )

        self.assertEqual(len(candidates), 2)
        self.assertEqual(candidates[0]["orcid_id"], preferred)
        self.assertEqual(candidates[1]["orcid_id"], "0000-0002-3237-1450")

    def test_build_candidate_marks_limited_public_data(self):
        with patch(
            "src.orcid_lookup._fetch_person_profile",
            return_value=("Andreas", "Fink", False),
        ), patch(
            "src.orcid_lookup._fetch_primary_affiliation",
            return_value="",
        ):
            candidate = _build_candidate("0000-0002-3622-2487", timeout_seconds=1.0)

        self.assertFalse(candidate["public_data_available"])
        self.assertEqual(
            candidate["public_data_status"],
            "Limited public profile data",
        )
