import os
import sys
import tempfile
import unittest
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.subject_id_matching import build_subject_id_matcher, load_existing_participant_ids


class TestBuildSubjectIdMatcher(unittest.TestCase):
    def test_unpadded_id_matches_existing_zero_padded_participant(self):
        match = build_subject_id_matcher({"sub-001", "sub-002", "sub-013"})
        self.assertEqual(match("sub-1"), "sub-001")
        self.assertEqual(match("sub-2"), "sub-002")
        self.assertEqual(match("sub-13"), "sub-013")

    def test_exact_match_returned_as_is(self):
        match = build_subject_id_matcher({"sub-001"})
        self.assertEqual(match("sub-001"), "sub-001")

    def test_zero_padded_incoming_id_matches_existing_unpadded_participant(self):
        match = build_subject_id_matcher({"sub-1", "sub-2"})
        self.assertEqual(match("sub-001"), "sub-1")

    def test_no_match_for_genuinely_new_participant(self):
        match = build_subject_id_matcher({"sub-001", "sub-002"})
        self.assertIsNone(match("sub-999"))

    def test_no_match_for_non_numeric_label(self):
        match = build_subject_id_matcher({"sub-001"})
        self.assertIsNone(match("sub-abc"))

    def test_ambiguous_match_returns_none_not_a_guess(self):
        # If a project somehow already has both sub-1 and sub-001 as
        # independent real entries, an exact hit still resolves directly...
        match = build_subject_id_matcher({"sub-1", "sub-001"})
        self.assertEqual(match("sub-1"), "sub-1")
        self.assertEqual(match("sub-001"), "sub-001")
        # ...but an incoming id that is numerically ambiguous between two
        # distinct existing entries (and isn't an exact hit on either) must
        # not guess which one it means.
        self.assertIsNone(match("sub-01"))

    def test_empty_existing_set_never_matches(self):
        match = build_subject_id_matcher(set())
        self.assertIsNone(match("sub-1"))

    def test_empty_candidate_returns_none(self):
        match = build_subject_id_matcher({"sub-001"})
        self.assertIsNone(match(""))


class TestLoadExistingParticipantIds(unittest.TestCase):
    def test_loads_unpadded_and_padded_ids_from_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            (project_root / "participants.tsv").write_text(
                "participant_id\tage\nsub-001\t30\nsub-002\t31\n",
                encoding="utf-8",
            )
            ids = load_existing_participant_ids(project_root)
            self.assertEqual(ids, {"sub-001", "sub-002"})

    def test_missing_file_returns_empty_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            ids = load_existing_participant_ids(Path(tmp))
            self.assertEqual(ids, set())

    def test_non_participant_id_header_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            (project_root / "participants.tsv").write_text(
                "subject_id\tage\nsub-001\t30\n",
                encoding="utf-8",
            )
            ids = load_existing_participant_ids(project_root)
            self.assertEqual(ids, {"sub-001"})


if __name__ == "__main__":
    unittest.main()
