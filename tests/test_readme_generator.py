import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.readme_generator import ReadmeGenerator


class TestReadmeGenerator(unittest.TestCase):
    def test_generate_handles_null_data_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "project.json").write_text(
                json.dumps(
                    {
                        "name": "demo_project",
                        "Overview": {"Main": "Demo dataset"},
                        "DataCollection": None,
                        "Recruitment": None,
                        "Eligibility": None,
                        "Procedure": None,
                        "MissingData": None,
                    }
                ),
                encoding="utf-8",
            )
            (project_path / "dataset_description.json").write_text(
                json.dumps(
                    {
                        "Name": "Demo Dataset",
                        "BIDSVersion": "1.9.0",
                        "License": "CC-BY-4.0",
                    }
                ),
                encoding="utf-8",
            )

            generator = ReadmeGenerator(project_path)
            content = generator.generate()

            self.assertIn("Demo Dataset", content)
            self.assertIn("### Apparatus", content)
            self.assertIn("Not specified", content)

    def test_generate_formats_overview_lists_as_bullets(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "project.json").write_text(
                json.dumps(
                    {
                        "name": "demo_project",
                        "Overview": {
                            "Main": "Demo dataset",
                            "IndependentVariables": [
                                "ballet intervention",
                                "contemporary dance intervention",
                            ],
                            "QualityAssessment": [
                                "manual QC",
                                "double-check scoring",
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (project_path / "dataset_description.json").write_text(
                json.dumps(
                    {
                        "Name": "Demo Dataset",
                        "BIDSVersion": "1.9.0",
                        "License": "CC-BY-4.0",
                    }
                ),
                encoding="utf-8",
            )

            generator = ReadmeGenerator(project_path)
            content = generator.generate()

            self.assertIn("- ballet intervention", content)
            self.assertIn("- contemporary dance intervention", content)
            self.assertIn("- manual QC", content)

    def test_generate_formats_missing_files_as_five_column_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "project.json").write_text(
                json.dumps(
                    {
                        "name": "demo_project",
                        "Overview": {"Main": "Demo dataset"},
                        "MissingData": {
                            "MissingFiles": (
                                "sub-01 | ses-01 | func | motion_artifact | "
                                "excessive movement during scan"
                            ),
                        },
                    }
                ),
                encoding="utf-8",
            )
            (project_path / "dataset_description.json").write_text(
                json.dumps(
                    {
                        "Name": "Demo Dataset",
                        "BIDSVersion": "1.9.0",
                        "License": "CC-BY-4.0",
                    }
                ),
                encoding="utf-8",
            )

            generator = ReadmeGenerator(project_path)
            content = generator.generate()

            self.assertIn(
                "| sub-01 | ses-01 | func | motion_artifact | "
                "excessive movement during scan |",
                content,
            )

    def test_generate_pads_legacy_two_column_missing_files_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "project.json").write_text(
                json.dumps(
                    {
                        "name": "demo_project",
                        "Overview": {"Main": "Demo dataset"},
                        "MissingData": {
                            "MissingFiles": "sub-002, ses-2 | T1w missing",
                        },
                    }
                ),
                encoding="utf-8",
            )
            (project_path / "dataset_description.json").write_text(
                json.dumps(
                    {
                        "Name": "Demo Dataset",
                        "BIDSVersion": "1.9.0",
                        "License": "CC-BY-4.0",
                    }
                ),
                encoding="utf-8",
            )

            generator = ReadmeGenerator(project_path)
            content = generator.generate()

            self.assertIn("| sub-002, ses-2 | T1w missing |  |  |  |", content)


if __name__ == "__main__":
    unittest.main()
