import os
import sys
import tempfile
import unittest
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.session_resolution import list_known_sessions, resolve_sessions


class TestListKnownSessions(unittest.TestCase):
    def test_lists_sessions_across_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            (project_root / "sub-001" / "ses-01" / "survey").mkdir(parents=True)
            (project_root / "sub-002" / "ses-02" / "survey").mkdir(parents=True)
            self.assertEqual(
                list_known_sessions(project_root), ["ses-01", "ses-02"]
            )

    def test_lists_sessions_for_one_subject_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            (project_root / "sub-001" / "ses-01" / "survey").mkdir(parents=True)
            (project_root / "sub-002" / "ses-02" / "survey").mkdir(parents=True)
            self.assertEqual(
                list_known_sessions(project_root, subject="sub-001"), ["ses-01"]
            )

    def test_missing_subject_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self.assertEqual(
                list_known_sessions(project_root, subject="sub-999"), []
            )

    def test_no_sessions_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            self.assertEqual(list_known_sessions(project_root), [])


class TestResolveSessions(unittest.TestCase):
    def test_no_known_sessions_matches_everything(self):
        result = resolve_sessions(["ses-01", "ses-02"], [])
        self.assertEqual(result.matched, ["ses-01", "ses-02"])
        self.assertEqual(result.unmatched, [])

    def test_existing_session_matches(self):
        result = resolve_sessions(["ses-01"], ["ses-01", "ses-02"])
        self.assertEqual(result.matched, ["ses-01"])
        self.assertEqual(result.unmatched, [])

    def test_unknown_session_is_unmatched_without_decision(self):
        result = resolve_sessions(["ses-99"], ["ses-01"])
        self.assertEqual(result.matched, [])
        self.assertEqual(result.unmatched, ["ses-99"])

    def test_use_existing_decision_resolves_to_target(self):
        decisions = {"ses99": {"action": "use_existing", "target_session": "ses-01"}}
        result = resolve_sessions(["ses99"], ["ses-01"], decisions)
        self.assertEqual(result.matched, ["ses-01"])
        self.assertEqual(result.unmatched, [])

    def test_add_new_decision_confirms_new_session(self):
        decisions = {"ses-03": {"action": "add_new"}}
        result = resolve_sessions(["ses-03"], ["ses-01"], decisions)
        self.assertEqual(result.matched, ["ses-03"])
        self.assertEqual(result.unmatched, [])

    def test_use_existing_decision_with_unknown_target_stays_unmatched(self):
        decisions = {"ses99": {"action": "use_existing", "target_session": "ses-77"}}
        result = resolve_sessions(["ses99"], ["ses-01"], decisions)
        self.assertEqual(result.matched, [])
        self.assertEqual(result.unmatched, ["ses99"])


if __name__ == "__main__":
    unittest.main()
