# pyright: reportMissingImports=false

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

from src.web.blueprints.conversion_utils import read_tabular_dataframe_robust


class TestConversionUtilsTabularReader(unittest.TestCase):
    def test_reads_utf8_sig_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "participants.tsv"
            path.write_text(
                "participant_id\tage\nsub-001\t21\nsub-002\t22\n",
                encoding="utf-8-sig",
            )

            df = read_tabular_dataframe_robust(path, expected_delimiter="\t", dtype=str)

            self.assertEqual(list(df.columns), ["participant_id", "age"])
            self.assertEqual(df.iloc[0]["participant_id"], "sub-001")

    def test_falls_back_when_csv_mislabeled_as_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "participants.tsv"
            path.write_text(
                "participant_id,age\nsub-001,21\nsub-002,22\n",
                encoding="utf-8",
            )

            df = read_tabular_dataframe_robust(path, expected_delimiter="\t", dtype=str)

            self.assertEqual(list(df.columns), ["participant_id", "age"])
            self.assertEqual(df.iloc[1]["participant_id"], "sub-002")

    def test_skips_malformed_rows_as_last_resort(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "participants.csv"
            path.write_text(
                (
                    "participant_id,age,group\n"
                    "sub-001,21,control\n"
                    "sub-002,22,patient,EXTRA\n"
                    "sub-003,23,control\n"
                ),
                encoding="utf-8",
            )

            df = read_tabular_dataframe_robust(path, expected_delimiter=",", dtype=str)

            self.assertEqual(list(df.columns), ["participant_id", "age", "group"])
            self.assertEqual(df.shape[0], 2)
            self.assertIn("sub-001", set(df["participant_id"].tolist()))
            self.assertIn("sub-003", set(df["participant_id"].tolist()))


if __name__ == "__main__":
    unittest.main()
