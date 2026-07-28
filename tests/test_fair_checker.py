"""Tests for app/src/fair_checker.py — FAIR compliance scoring."""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from fair_checker import FAIRComplianceChecker


def _checker():
    return FAIRComplianceChecker()


def _full_dataset_metadata(**overrides):
    """A dataset-level metadata dict that scores well on every FAIR axis."""
    metadata = {
        "BIDSVersion": "1.8.0",
        "DatasetDOI": "10.1234/real-doi",
        "Name": "Demo Study",
        "Description": "A" * 120,
        "Authors": [{"name": "A. Researcher", "orcid": "0000-0000-0000-0001", "ror": "01abcde"}],
        "Keywords": ["psychology", "cognition", "survey"],
        "License": "CC-BY-4.0",
        "GeneratedBy": [{"Name": "prism", "Version": "1.0"}],
        "ResearchDomains": ["psychology"],
        "DataCollection": {
            "start_date": "2026-01-01",
            "end_date": "2026-02-01",
            "location": "Graz",
            "sample_size": 100,
        },
        "DatasetType": "raw",
        "Publications": [{"doi": "10.5555/pub"}],
        "ReferencesAndLinks": ["https://example.org"],
        "Contact": {"email": "pi@example.org"},
        "EthicsApprovals": ["EK-123"],
        "Acknowledgements": "Thanks to everyone who made this possible for their support",
        "Funding": ["Grant 123"],
    }
    metadata.update(overrides)
    return metadata


def _minimal_stimulus_metadata(**overrides):
    """Legacy stimulus-level metadata (no BIDSVersion key)."""
    metadata = {
        "Metadata": {
            "Creator": "researcher@example.org",
            "CreationDate": "2026-01-01",
            "SchemaVersion": "1.0.0",
        },
    }
    metadata.update(overrides)
    return metadata


# ---------------------------------------------------------------------------
# check_findable
# ---------------------------------------------------------------------------

class TestCheckFindable:
    def test_full_dataset_scores_high(self):
        checker = _checker()
        score = checker.check_findable(_full_dataset_metadata())
        assert score == 30  # 7 + 8 + 5 + 3 + 5 + 2

    def test_missing_doi(self):
        checker = _checker()
        metadata = _full_dataset_metadata()
        del metadata["DatasetDOI"]
        checker.check_findable(metadata)
        assert any("Add DOI" in r for r in checker.recommendations)

    def test_placeholder_doi_partial_credit(self):
        checker = _checker()
        metadata = _full_dataset_metadata(DatasetDOI="10.PLACEHOLDER/dataset-doi")
        score = checker.check_findable(metadata)
        assert score < 30
        assert any("placeholder" in r.lower() for r in checker.recommendations)

    def test_missing_dataset_metadata_fields(self):
        checker = _checker()
        metadata = _full_dataset_metadata(Name=None, Description=None)
        checker.check_findable(metadata)
        assert any("Missing dataset metadata" in r for r in checker.recommendations)

    def test_few_keywords_flagged(self):
        checker = _checker()
        metadata = _full_dataset_metadata(Keywords=["one"])
        checker.check_findable(metadata)
        assert any("at least 3 keywords" in r for r in checker.recommendations)

    def test_short_description_flagged(self):
        checker = _checker()
        metadata = _full_dataset_metadata(Description="short")
        checker.check_findable(metadata)
        assert any("comprehensive description" in r for r in checker.recommendations)

    def test_no_orcid_flagged(self):
        checker = _checker()
        metadata = _full_dataset_metadata(Authors=[{"name": "No Orcid"}])
        checker.check_findable(metadata)
        assert any("Add ORCID" in r for r in checker.recommendations)

    def test_no_ror_flagged(self):
        checker = _checker()
        metadata = _full_dataset_metadata(
            Authors=[{"name": "No Ror", "orcid": "0000-0000-0000-0001"}]
        )
        checker.check_findable(metadata)
        assert any("Add ROR" in r for r in checker.recommendations)

    def test_stimulus_metadata_full(self):
        checker = _checker()
        score = checker.check_findable(_minimal_stimulus_metadata())
        assert score == 5  # F2 complete required fields only

    def test_stimulus_missing_required_metadata(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata()
        del metadata["Metadata"]["Creator"]
        checker.check_findable(metadata)
        assert any("Missing required metadata" in r for r in checker.recommendations)

    def test_stimulus_orcid_present(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Metadata={
                "Creator": "x@example.org",
                "CreationDate": "2026-01-01",
                "SchemaVersion": "1.0.0",
                "CreatorORCID": "0000-0000-0000-0001",
            }
        )
        score = checker.check_findable(metadata)
        assert score == 10  # 5 (required fields) + 5 (ORCID)

    def test_stimulus_institution_ror(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Metadata={
                "Creator": "x@example.org",
                "CreationDate": "2026-01-01",
                "SchemaVersion": "1.0.0",
                "InstitutionROR": "01abcde",
            }
        )
        score = checker.check_findable(metadata)
        assert score == 10  # 5 (required fields) + 5 (institution ROR)


# ---------------------------------------------------------------------------
# check_accessible
# ---------------------------------------------------------------------------

class TestCheckAccessible:
    def test_full_dataset_scores_high(self, tmp_path):
        checker = _checker()
        f = tmp_path / "dataset_description.json"
        f.write_text("{}")
        (tmp_path / "README.md").write_text("readme")
        score = checker.check_accessible(_full_dataset_metadata(), str(f))
        assert score >= 20

    def test_no_license(self, tmp_path):
        checker = _checker()
        f = tmp_path / "dataset_description.json"
        f.write_text("{}")
        metadata = _full_dataset_metadata(License="All rights reserved")
        checker.check_accessible(metadata, str(f))
        assert any("Specify clear usage license" in r for r in checker.recommendations)

    def test_non_cc_license_still_scored(self, tmp_path):
        checker = _checker()
        f = tmp_path / "dataset_description.json"
        f.write_text("{}")
        metadata = _full_dataset_metadata(License="MIT")
        score = checker.check_accessible(metadata, str(f))
        assert any("License specified: MIT" in r for r in checker.recommendations)
        assert score > 0

    def test_missing_bids_version(self, tmp_path):
        checker = _checker()
        f = tmp_path / "dataset_description.json"
        f.write_text("{}")
        # Keep the "BIDSVersion" key present (so is_dataset detection still
        # takes the dataset branch) but falsy, unlike test_stimulus_* which
        # omits the key entirely to switch metadata "flavor".
        metadata = _full_dataset_metadata(BIDSVersion="")
        checker.check_accessible(metadata, str(f))
        assert any("Use BIDS-compliant data structure" in r for r in checker.recommendations)

    def test_file_not_found(self):
        checker = _checker()
        checker.check_accessible(_full_dataset_metadata(), "/nonexistent/path.json")
        assert any("not found or not accessible" in r for r in checker.recommendations)

    def test_missing_readme(self, tmp_path):
        checker = _checker()
        f = tmp_path / "dataset_description.json"
        f.write_text("{}")
        checker.check_accessible(_full_dataset_metadata(), str(f))
        assert any("Add README.md" in r for r in checker.recommendations)

    def test_no_contact_no_author_email(self, tmp_path):
        checker = _checker()
        f = tmp_path / "dataset_description.json"
        f.write_text("{}")
        metadata = _full_dataset_metadata(Contact={}, Authors=[{"name": "No Email"}])
        checker.check_accessible(metadata, str(f))
        assert any("Add contact email" in r for r in checker.recommendations)

    def test_author_email_fallback(self, tmp_path):
        checker = _checker()
        f = tmp_path / "dataset_description.json"
        f.write_text("{}")
        metadata = _full_dataset_metadata(
            Contact={}, Authors=[{"name": "Has Email", "email": "a@b.com"}]
        )
        score = checker.check_accessible(metadata, str(f))
        assert any("Author contact information" in r for r in checker.recommendations)
        assert score > 0

    def test_no_ethics_approvals(self, tmp_path):
        checker = _checker()
        f = tmp_path / "dataset_description.json"
        f.write_text("{}")
        metadata = _full_dataset_metadata(EthicsApprovals=[])
        checker.check_accessible(metadata, str(f))
        assert any("Document ethics" in r for r in checker.recommendations)

    def test_stimulus_metadata_standard_format(self, tmp_path):
        checker = _checker()
        f = tmp_path / "stim.json"
        f.write_text("{}")
        metadata = _minimal_stimulus_metadata(
            Technical={"FileFormat": "json"},
        )
        metadata["Metadata"]["Description"] = "x" * 60
        metadata["Metadata"]["Creator"] = "a@b.com"
        score = checker.check_accessible(metadata, str(f))
        assert score > 0
        assert any("standard format: json" in r for r in checker.recommendations)

    def test_stimulus_nonstandard_format(self, tmp_path):
        checker = _checker()
        f = tmp_path / "stim.json"
        f.write_text("{}")
        metadata = _minimal_stimulus_metadata(Technical={"FileFormat": "xyz"})
        checker.check_accessible(metadata, str(f))
        assert any("more standard file formats" in r for r in checker.recommendations)


# ---------------------------------------------------------------------------
# check_interoperable
# ---------------------------------------------------------------------------

class TestCheckInteroperable:
    def test_full_dataset_scores_high(self):
        checker = _checker()
        score = checker.check_interoperable(_full_dataset_metadata())
        assert score > 15

    def test_invalid_bids_version_format(self):
        checker = _checker()
        metadata = _full_dataset_metadata(BIDSVersion="not-a-version")
        checker.check_interoperable(metadata)
        assert any("valid BIDS version format" in r for r in checker.recommendations)

    def test_no_generated_by_version(self):
        checker = _checker()
        metadata = _full_dataset_metadata(GeneratedBy=[{"Name": "tool"}])
        checker.check_interoperable(metadata)
        assert any("Document software versions" in r for r in checker.recommendations)

    def test_no_research_domains(self):
        checker = _checker()
        metadata = _full_dataset_metadata(ResearchDomains=[])
        checker.check_interoperable(metadata)
        assert any("Specify ResearchDomains" in r for r in checker.recommendations)

    def test_no_data_collection_start_date(self):
        checker = _checker()
        metadata = _full_dataset_metadata(DataCollection={})
        checker.check_interoperable(metadata)
        assert any("structured DataCollection" in r for r in checker.recommendations)

    def test_nonstandard_dataset_type(self):
        checker = _checker()
        metadata = _full_dataset_metadata(DatasetType="weird")
        checker.check_interoperable(metadata)
        assert any("standard DatasetType" in r for r in checker.recommendations)

    def test_no_publications_or_references(self):
        # "Add valid DOIs" only fires when Publications is non-empty but
        # lacks a valid DOI (see test_publications_without_valid_doi) -- an
        # empty Publications list just skips that check silently.
        checker = _checker()
        metadata = _full_dataset_metadata(Publications=[], ReferencesAndLinks=[])
        checker.check_interoperable(metadata)
        assert any("Add ReferencesAndLinks" in r for r in checker.recommendations)

    def test_publications_without_valid_doi(self):
        checker = _checker()
        metadata = _full_dataset_metadata(Publications=[{"doi": "not-a-doi"}])
        checker.check_interoperable(metadata)
        assert any("Add valid DOIs" in r for r in checker.recommendations)

    def test_stimulus_schema_version(self):
        checker = _checker()
        score = checker.check_interoperable(_minimal_stimulus_metadata())
        assert score > 0

    def test_stimulus_invalid_schema_version(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Metadata={
                "Creator": "x",
                "CreationDate": "2026-01-01",
                "SchemaVersion": "bad",
            }
        )
        checker.check_interoperable(metadata)
        assert any("semantic versioning" in r for r in checker.recommendations)

    def test_stimulus_categories_controlled_vocab(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Categories={"StudyDomain": "psych", "DataQuality": "high"}
        )
        score = checker.check_interoperable(metadata)
        assert any("controlled vocabulary" in r for r in checker.recommendations)
        assert score > 0

    def test_stimulus_bids_naming_compliance(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Study={"Subject": "sub-01", "Session": "ses-1", "Task": "rest"}
        )
        score = checker.check_interoperable(metadata)
        assert any("Good BIDS compliance" in r for r in checker.recommendations)
        assert score > 0

    def test_stimulus_related_publications(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Metadata={
                "Creator": "x",
                "CreationDate": "2026-01-01",
                "SchemaVersion": "1.0.0",
                "RelatedPublications": ["10.1234/pub"],
            }
        )
        score = checker.check_interoperable(metadata)
        assert any("Linked to publications" in r for r in checker.recommendations)
        assert score > 0


# ---------------------------------------------------------------------------
# check_reusable
# ---------------------------------------------------------------------------

class TestCheckReusable:
    def test_full_dataset_scores_high(self):
        checker = _checker()
        score = checker.check_reusable(_full_dataset_metadata())
        assert score > 15

    def test_missing_data_collection_fields(self):
        checker = _checker()
        metadata = _full_dataset_metadata(DataCollection={})
        checker.check_reusable(metadata)
        assert any("start_date and end_date" in r for r in checker.recommendations)
        assert any("Specify DataCollection location" in r for r in checker.recommendations)
        assert any("Add sample_size" in r for r in checker.recommendations)

    def test_non_by_cc_license(self):
        checker = _checker()
        metadata = _full_dataset_metadata(License="CC0")
        score = checker.check_reusable(metadata)
        assert any("Open license specified" in r for r in checker.recommendations)
        assert score > 0

    def test_permissive_license(self):
        checker = _checker()
        metadata = _full_dataset_metadata(License="MIT")
        score = checker.check_reusable(metadata)
        assert any("Permissive license" in r for r in checker.recommendations)
        assert score > 0

    def test_no_license(self):
        checker = _checker()
        metadata = _full_dataset_metadata(License="")
        checker.check_reusable(metadata)
        assert any("clear open license" in r for r in checker.recommendations)

    def test_short_acknowledgements(self):
        checker = _checker()
        metadata = _full_dataset_metadata(Acknowledgements="short")
        checker.check_reusable(metadata)
        assert any("detailed Acknowledgements" in r for r in checker.recommendations)

    def test_no_research_domains_reusable(self):
        checker = _checker()
        metadata = _full_dataset_metadata(ResearchDomains=[])
        checker.check_reusable(metadata)
        assert any("Add ResearchDomains" in r for r in checker.recommendations)

    def test_no_funding(self):
        checker = _checker()
        metadata = _full_dataset_metadata(Funding=[])
        checker.check_reusable(metadata)
        assert any("Document Funding" in r for r in checker.recommendations)

    def test_no_ethics_or_publications(self):
        checker = _checker()
        metadata = _full_dataset_metadata(EthicsApprovals=[], Publications=[])
        checker.check_reusable(metadata)
        assert any("Document ethics approvals" in r for r in checker.recommendations)
        assert any("Link to related Publications" in r for r in checker.recommendations)

    def test_invalid_date_formats(self):
        checker = _checker()
        metadata = _full_dataset_metadata(
            DataCollection={
                "start_date": "01/01/2026",
                "end_date": "not-a-date",
                "location": "Graz",
                "sample_size": 10,
            }
        )
        checker.check_reusable(metadata)
        assert any("start_date" in r and "ISO" in r for r in checker.recommendations)
        assert any("end_date" in r and "ISO" in r for r in checker.recommendations)

    def test_stimulus_technical_specifications(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Technical={"StimulusType": "image", "FileFormat": "png"}
        )
        score = checker.check_reusable(metadata)
        assert any("Complete technical specifications" in r for r in checker.recommendations)
        assert score > 0

    def test_stimulus_missing_technical_fields(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(Technical={"StimulusType": "image"})
        checker.check_reusable(metadata)
        assert any("Missing technical fields" in r for r in checker.recommendations)

    def test_stimulus_open_license(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Metadata={
                "Creator": "x",
                "CreationDate": "2026-01-01",
                "SchemaVersion": "1.0.0",
                "License": "CC-BY-4.0",
            }
        )
        score = checker.check_reusable(metadata)
        assert any("Open license promotes reuse" in r for r in checker.recommendations)
        assert score > 0

    def test_stimulus_data_quality_and_domain(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Categories={"StudyDomain": "psych", "DataQuality": "high"}
        )
        score = checker.check_reusable(metadata)
        assert any("Clear domain classification" in r for r in checker.recommendations)
        assert any("Data quality assessed" in r for r in checker.recommendations)
        assert score > 0

    def test_stimulus_creation_date_iso(self):
        checker = _checker()
        score = checker.check_reusable(_minimal_stimulus_metadata())
        assert any("Clear temporal information" in r for r in checker.recommendations)
        assert score > 0

    def test_stimulus_creation_date_invalid(self):
        checker = _checker()
        metadata = _minimal_stimulus_metadata(
            Metadata={
                "Creator": "x",
                "CreationDate": "not-a-date",
                "SchemaVersion": "1.0.0",
            }
        )
        checker.check_reusable(metadata)
        assert any("Use ISO date format" in r for r in checker.recommendations)


# ---------------------------------------------------------------------------
# evaluate_dataset / get_grade
# ---------------------------------------------------------------------------

class TestEvaluateDataset:
    def test_full_evaluation(self, tmp_path):
        metadata = _full_dataset_metadata()
        f = tmp_path / "dataset_description.json"
        f.write_text(json.dumps(metadata))
        (tmp_path / "README.md").write_text("readme")

        checker = _checker()
        result = checker.evaluate_dataset(str(f))

        assert "error" not in result
        assert set(result["scores"].keys()) == {
            "findable",
            "accessible",
            "interoperable",
            "reusable",
        }
        # Per-category raw scores aren't clamped to their max_scores entry, so
        # a metadata dict that scores well on every sub-criterion can push a
        # category (and thus the overall percentage) above 100 -- this is
        # existing behavior, not something this test asserts against.
        assert result["total_percentage"] > 0
        assert "grade" in result
        assert result["recommendations"]

    def test_missing_file_returns_error(self):
        checker = _checker()
        result = checker.evaluate_dataset("/nonexistent/dataset_description.json")
        assert "error" in result

    def test_invalid_json_returns_error(self, tmp_path):
        f = tmp_path / "dataset_description.json"
        f.write_text("{not valid json")
        checker = _checker()
        result = checker.evaluate_dataset(str(f))
        assert "error" in result


class TestGetGrade:
    def test_excellent(self):
        assert "A" in _checker().get_grade(95)

    def test_good(self):
        assert "B" in _checker().get_grade(85)

    def test_acceptable(self):
        assert "C" in _checker().get_grade(75)

    def test_poor(self):
        assert "D" in _checker().get_grade(65)

    def test_inadequate(self):
        assert "F" in _checker().get_grade(10)

    def test_boundary_90_is_excellent(self):
        assert "A" in _checker().get_grade(90)

    def test_boundary_80_is_good(self):
        assert "B" in _checker().get_grade(80)

    def test_boundary_70_is_acceptable(self):
        assert "C" in _checker().get_grade(70)

    def test_boundary_60_is_poor(self):
        assert "D" in _checker().get_grade(60)
