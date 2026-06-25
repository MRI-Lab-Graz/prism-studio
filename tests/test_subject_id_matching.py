import os
import sys
import tempfile
import unittest
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.subject_id_matching import (
    apply_id_resolution_decisions,
    build_subject_id_matcher,
    load_existing_participant_ids,
    load_id_aliases,
    resolve_participant_ids,
    save_id_alias,
)


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


class TestIdAliases(unittest.TestCase):
    def test_save_then_load_round_trips(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            save_id_alias(project_root, "P-12", "sub-012")
            self.assertEqual(load_id_aliases(project_root), {"P-12": "sub-012"})

    def test_load_missing_file_returns_empty_dict(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(load_id_aliases(Path(tmp)), {})

    def test_save_merges_with_existing_aliases(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            save_id_alias(project_root, "P-12", "sub-012")
            save_id_alias(project_root, "P-13", "sub-013")
            self.assertEqual(
                load_id_aliases(project_root),
                {"P-12": "sub-012", "P-13": "sub-013"},
            )


class TestResolveParticipantIds(unittest.TestCase):
    def _write_participants(self, project_root: Path, ids: list[str]) -> None:
        rows = "\n".join(f"{pid}\t30" for pid in ids)
        (project_root / "participants.tsv").write_text(
            f"participant_id\tage\n{rows}\n", encoding="utf-8"
        )

    def test_no_ground_truth_matches_everything_as_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            result = resolve_participant_ids(["sub-1", "sub-2"], project_root)
            self.assertFalse(result.has_ground_truth)
            self.assertEqual(result.matched, {"sub-1": "sub-1", "sub-2": "sub-2"})
            self.assertEqual(result.unmatched, [])

    def test_unambiguous_numeric_match_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_participants(project_root, ["sub-001", "sub-002"])
            result = resolve_participant_ids(["sub-1"], project_root)
            self.assertTrue(result.has_ground_truth)
            self.assertEqual(result.matched, {"sub-1": "sub-001"})
            self.assertEqual(result.unmatched, [])

    def test_genuinely_unmatched_id_is_blocked_with_no_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_participants(project_root, ["sub-001", "sub-002"])
            result = resolve_participant_ids(["sub-999"], project_root)
            self.assertEqual(result.unmatched, ["sub-999"])
            self.assertEqual(result.suggested_matches, {})

    def test_ambiguous_id_is_unmatched_but_suggests_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_participants(project_root, ["sub-1", "sub-001"])
            result = resolve_participant_ids(["sub-01"], project_root)
            self.assertEqual(result.unmatched, ["sub-01"])
            self.assertEqual(
                sorted(result.suggested_matches["sub-01"]), ["sub-001", "sub-1"]
            )

    def test_saved_alias_resolves_otherwise_unmatched_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self._write_participants(project_root, ["sub-001"])
            save_id_alias(project_root, "P-weird", "sub-001")
            result = resolve_participant_ids(["P-weird"], project_root)
            self.assertEqual(result.matched, {"P-weird": "sub-001"})
            self.assertEqual(result.unmatched, [])


class TestApplyIdResolutionDecisions(unittest.TestCase):
    def test_map_action_resolves_and_persists_alias_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            decisions = {"P-weird": {"action": "map", "target_participant_id": "sub-001"}}
            resolved = apply_id_resolution_decisions(["P-weird"], decisions, project_root)
            self.assertEqual(resolved, {"P-weird": "sub-001"})
            self.assertEqual(load_id_aliases(project_root), {"P-weird": "sub-001"})

    def test_map_action_with_remember_false_does_not_persist(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            decisions = {
                "P-weird": {
                    "action": "map",
                    "target_participant_id": "sub-001",
                    "remember": False,
                }
            }
            resolved = apply_id_resolution_decisions(["P-weird"], decisions, project_root)
            self.assertEqual(resolved, {"P-weird": "sub-001"})
            self.assertEqual(load_id_aliases(project_root), {})

    def test_create_new_action_resolves_to_itself(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            decisions = {"sub-999": {"action": "create_new"}}
            resolved = apply_id_resolution_decisions(["sub-999"], decisions, project_root)
            self.assertEqual(resolved, {"sub-999": "sub-999"})

    def test_id_without_decision_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            resolved = apply_id_resolution_decisions(["sub-999"], {}, project_root)
            self.assertEqual(resolved, {})


if __name__ == "__main__":
    unittest.main()
