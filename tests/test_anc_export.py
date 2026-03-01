import json
import tempfile
from pathlib import Path

from src.converters.anc_export import ANCExporter


class TestANCExporterCitation:
    def test_extract_metadata_reads_project_json_for_cff_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset_path = Path(tmp) / "dataset"
            output_path = Path(tmp) / "export"
            dataset_path.mkdir(parents=True, exist_ok=True)
            output_path.mkdir(parents=True, exist_ok=True)

            (dataset_path / "dataset_description.json").write_text(
                json.dumps(
                    {
                        "BIDSVersion": "1.10.1",
                        "License": "CC0-1.0",
                    }
                ),
                encoding="utf-8",
            )

            (dataset_path / "project.json").write_text(
                json.dumps(
                    {
                        "Basics": {
                            "DatasetName": "Workshop Test Dataset",
                            "Keywords": ["psychology", "survey"],
                        },
                        "Overview": {
                            "Main": "This is a test study investigating daily mood.",
                        },
                        "StudyDesign": {
                            "Type": "longitudinal",
                            "TypeDescription": "Randomized intervention over 4 weeks.",
                        },
                        "Recruitment": {
                            "Method": "snowball",
                        },
                        "DataCollection": {
                            "Description": "Daily surveys in a smartphone app.",
                        },
                        "Procedure": {
                            "Overview": "Baseline and post-intervention assessments.",
                        },
                        "governance": {
                            "contacts": [
                                {
                                    "given": "prism-studio",
                                    "family": "ff",
                                    "email": "team@example.org",
                                }
                            ],
                            "preregistration": "https://osf.io/abcd1/",
                            "data_access": "https://example.org/access",
                        },
                        "References": {
                            "primary": [
                                {
                                    "title": "Primary study reference",
                                    "doi": "10.1000/xyz123",
                                }
                            ]
                        },
                        "TaskDefinitions": {
                            "wellbeing": {
                                "modality": "survey",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            exporter = ANCExporter(dataset_path=dataset_path, output_path=output_path)
            metadata = exporter._extract_metadata()

            assert metadata["CFF_TITLE"] == "Workshop Test Dataset"
            assert metadata["CFF_AUTHORS"][0]["family-names"] == "ff"
            assert metadata["CFF_AUTHORS"][0]["given-names"] == "prism-studio"
            assert metadata["CFF_AUTHORS"][0]["email"] == "team@example.org"
            assert "longitudinal" in metadata["CFF_KEYWORDS"]
            assert "wellbeing" in metadata["CFF_KEYWORDS"]
            assert any(
                isinstance(ref, dict) and ref.get("doi") == "10.1000/xyz123"
                for ref in metadata["CFF_REFERENCES"]
            )
            assert any(
                str(ref).strip() == "https://osf.io/abcd1/"
                for ref in metadata["CFF_REFERENCES"]
            )

    def test_generate_citation_includes_project_driven_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            dataset_path = Path(tmp) / "dataset"
            output_path = Path(tmp) / "export"
            dataset_path.mkdir(parents=True, exist_ok=True)
            output_path.mkdir(parents=True, exist_ok=True)

            (dataset_path / "dataset_description.json").write_text(
                json.dumps(
                    {
                        "BIDSVersion": "1.10.1",
                    }
                ),
                encoding="utf-8",
            )

            (dataset_path / "project.json").write_text(
                json.dumps(
                    {
                        "Basics": {
                            "DatasetName": "Workshop Test Dataset",
                        },
                        "Overview": {
                            "Main": "Project overview abstract.",
                        },
                        "governance": {
                            "contacts": [
                                {
                                    "given": "prism-studio",
                                    "family": "ff",
                                    "email": "team@example.org",
                                }
                            ],
                            "preregistration": "https://osf.io/abcd1/",
                        },
                        "References": [
                            {
                                "title": "Primary study reference",
                                "doi": "10.1000/xyz123",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            exporter = ANCExporter(dataset_path=dataset_path, output_path=output_path)
            metadata = exporter._extract_metadata()
            exporter._generate_citation(metadata)

            citation_text = (output_path / "CITATION.cff").read_text(encoding="utf-8")

            assert 'title: "Workshop Test Dataset"' in citation_text
            assert 'family-names: "ff"' in citation_text
            assert 'given-names: "prism-studio"' in citation_text
            assert 'email: "team@example.org"' in citation_text
            assert 'abstract: "Project overview abstract."' in citation_text
            assert 'doi: "10.1000/xyz123"' in citation_text
            assert 'url: "https://osf.io/abcd1/"' in citation_text
            assert "references:" in citation_text
