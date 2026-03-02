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


if __name__ == "__main__":
    unittest.main()
