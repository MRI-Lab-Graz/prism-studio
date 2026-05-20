import json
import os
import sys
import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")

if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.project_manager import ProjectManager


def _registered_nested_path_sequence(*path_sets):
    remaining = [set(paths) for paths in path_sets]
    last_paths = set()

    def _side_effect(*_args, **_kwargs):
        nonlocal last_paths
        if remaining:
            last_paths = set(remaining.pop(0))
        return set(last_paths)

    return _side_effect


class TestProjectManager(unittest.TestCase):
    def test_create_project_sets_default_author(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(str(project_path), {"name": "demo_project"})

            self.assertTrue(result.get("success"), result)

            desc_path = project_path / "dataset_description.json"
            self.assertTrue(desc_path.exists())

            payload = json.loads(desc_path.read_text(encoding="utf-8"))
            self.assertNotIn("Authors", payload)

            citation_content = (project_path / "CITATION.cff").read_text(
                encoding="utf-8"
            )
            self.assertIn('family-names: "prism-studio"', citation_content)
            self.assertIn('given-names: "dataset"', citation_content)

    def test_create_project_does_not_seed_sessions_metadata(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(str(project_path), {"name": "demo_project"})

            self.assertTrue(result.get("success"), result)

            payload = json.loads((project_path / "project.json").read_text(encoding="utf-8"))

        self.assertNotIn("Sessions", payload)

    def test_create_project_normalizes_invalid_dataset_type(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(
                str(project_path),
                {"name": "demo_project", "dataset_type": "study"},
            )

            self.assertTrue(result.get("success"), result)

            desc_path = project_path / "dataset_description.json"
            payload = json.loads(desc_path.read_text(encoding="utf-8"))
            self.assertEqual(payload.get("DatasetType"), "raw")

    def test_create_project_bidsignore_covers_prism_only_paths(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(str(project_path), {"name": "demo_project"})

            self.assertTrue(result.get("success"), result)

            bidsignore_path = project_path / ".bidsignore"
            self.assertTrue(bidsignore_path.exists())

            content = bidsignore_path.read_text(encoding="utf-8")
            self.assertIn("code/", content)
            self.assertIn("code/library/", content)
            self.assertIn("code/recipes/", content)
            self.assertIn("derivatives/", content)
            self.assertIn("recipes/", content)
            self.assertNotIn("CITATION.cff", content)

    def test_create_project_ignores_system_files_in_existing_target(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "Desktop.ini").write_text("", encoding="utf-8")
            (project_path / "Thumbs.db").write_text("", encoding="utf-8")

            result = manager.create_project(str(project_path), {"name": "demo_project"})

            self.assertTrue(result.get("success"), result)

    @patch("src.project_manager.shutil.which", return_value=None)
    def test_create_project_datalad_is_opt_in_when_missing(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(str(project_path), {"name": "demo_project"})

        self.assertTrue(result.get("success"), result)
        self.assertFalse(result.get("datalad", {}).get("requested"))
        self.assertFalse(result.get("datalad", {}).get("available"))
        self.assertIn("skipped by user choice", result.get("datalad", {}).get("message", ""))

    @patch("src.project_manager.shutil.which")
    def test_create_project_continues_without_datalad_when_git_annex_missing(self, mock_which):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: (
            "/usr/bin/datalad" if executable == "datalad" else None
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(
                str(project_path),
                {"name": "demo_project", "use_datalad": True},
            )

        self.assertTrue(result.get("success"), result)
        self.assertTrue(result.get("datalad", {}).get("requested"))
        self.assertFalse(result.get("datalad", {}).get("initialized"))
        self.assertFalse(result.get("datalad", {}).get("annex_available"))
        self.assertIn("git-annex", result.get("datalad", {}).get("message", ""))

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_create_project_allows_opting_out_of_datalad(
        self, _mock_which, mock_run
    ):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(
                str(project_path),
                {"name": "demo_project", "use_datalad": False},
            )

        self.assertTrue(result.get("success"), result)
        self.assertFalse(result.get("datalad", {}).get("requested"))
        self.assertFalse(result.get("datalad", {}).get("initialized"))
        mock_run.assert_not_called()

    @patch(
        "src.project_manager.subprocess.run",
        return_value=Mock(returncode=0, stdout="", stderr=""),
    )
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_create_project_initializes_and_saves_datalad_dataset(
        self, _mock_which, _mock_parent_tracks, mock_run
    ):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                mock_registered_paths.side_effect = _registered_nested_path_sequence(
                    set(),
                    set(),
                    {"derivatives"},
                )
                result = manager.create_project(
                    str(project_path),
                    {"name": "demo_project", "use_datalad": True},
                )

            self.assertTrue(result.get("success"), result)
            self.assertTrue(result.get("datalad", {}).get("initialized"))
            self.assertTrue(result.get("datalad", {}).get("saved"))
            commands = [call.args[0] for call in mock_run.call_args_list]
            self.assertIn(["/usr/bin/datalad", "create", "--force"], commands)
            self.assertIn(
                ["/usr/bin/datalad", "create", "-d", ".", "--force", "derivatives"],
                commands,
            )
            self.assertIn(
                [
                    "/usr/bin/datalad",
                    "save",
                    "-m",
                    'Initialize DataLad nested dataset "derivatives"',
                ],
                commands,
            )
            self.assertIn(
                ["/usr/bin/datalad", "save", "-m", "Initialize PRISM dataset structure"],
                commands,
            )
            gitattributes_content = (project_path / ".gitattributes").read_text(
                encoding="utf-8"
            )
            self.assertIn(
                "dataset_description.json annex.largefiles=nothing",
                gitattributes_content,
            )
            self.assertIn(
                "CITATION.cff annex.largefiles=nothing", gitattributes_content
            )

    @patch("src.project_manager.subprocess.run")
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which")
    def test_create_datalad_dataset_initializes_derivatives_and_subject_subdatasets(
        self, mock_which, _mock_parent_tracks, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "dataset"
            (project_path / "derivatives").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-002").mkdir(parents=True, exist_ok=True)
            (project_path / "README").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001" / "data.tsv").write_text("value\n1\n", encoding="utf-8")
            (project_path / "sub-002" / "data.tsv").write_text("value\n2\n", encoding="utf-8")

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                mock_registered_paths.side_effect = _registered_nested_path_sequence(
                    set(),
                    {"derivatives"},
                    {"derivatives"},
                    {"derivatives", "sub-001"},
                    {"derivatives", "sub-001"},
                    {"derivatives", "sub-001", "sub-002"},
                    {"derivatives", "sub-001", "sub-002"},
                )
                result = manager._create_datalad_dataset(project_path, enabled=True)

        self.assertTrue(result.get("initialized"), result)
        self.assertEqual(
            result.get("subdatasets_created"),
            ["derivatives", "sub-001", "sub-002"],
        )
        self.assertEqual(result.get("subdatasets_existing"), [])
        self.assertEqual(result.get("subdataset_failures"), [])
        self.assertEqual(
            mock_run.call_args_list[0].args[0],
            ["/usr/bin/datalad", "create", "--force"],
        )
        self.assertEqual(
            mock_run.call_args_list[1].args[0],
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "derivatives"],
        )
        self.assertEqual(
            mock_run.call_args_list[2].args[0],
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'Initialize DataLad nested dataset "derivatives"',
            ],
        )
        self.assertEqual(
            mock_run.call_args_list[3].args[0],
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-001"],
        )
        self.assertEqual(
            mock_run.call_args_list[3].kwargs.get("cwd"),
            str(project_path),
        )
        self.assertEqual(
            mock_run.call_args_list[4].args[0],
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'Initialize DataLad nested dataset "sub-001"',
            ],
        )
        self.assertEqual(
            mock_run.call_args_list[4].kwargs.get("cwd"),
            str(project_path / "sub-001"),
        )
        self.assertEqual(
            mock_run.call_args_list[5].args[0],
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-002"],
        )
        self.assertEqual(
            mock_run.call_args_list[6].args[0],
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'Initialize DataLad nested dataset "sub-002"',
            ],
        )

    @patch("src.project_manager.subprocess.run")
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which")
    def test_create_datalad_dataset_skips_subjects_that_are_already_datasets(
        self, mock_which, _mock_parent_tracks, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "rawdata"
            subject_existing = project_path / "sub-171"
            subject_missing = project_path / "sub-172"
            subject_existing.mkdir(parents=True, exist_ok=True)
            subject_missing.mkdir(parents=True, exist_ok=True)
            (subject_existing / ".datalad").mkdir(parents=True, exist_ok=True)
            (subject_missing / "data.tsv").write_text("value\n1\n", encoding="utf-8")

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                mock_registered_paths.side_effect = _registered_nested_path_sequence(
                    {"sub-171"},
                    {"sub-171", "sub-172"},
                )
                result = manager._create_datalad_dataset(project_path, enabled=True)

        self.assertTrue(result.get("initialized"), result)
        self.assertEqual(result.get("subdatasets_created"), ["sub-172"])
        self.assertEqual(result.get("subdatasets_existing"), ["sub-171"])
        self.assertEqual(result.get("subdataset_failures"), [])
        self.assertEqual(result.get("subdatasets_remaining_count"), 0)
        self.assertEqual(
            mock_run.call_args_list[1].args[0],
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-172"],
        )

    @patch("src.project_manager.subprocess.run")
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which")
    def test_create_nested_subdatasets_can_limit_repairs_to_one_per_call(
        self, mock_which, _mock_parent_tracks, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "rawdata"
            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-002").mkdir(parents=True, exist_ok=True)

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                mock_registered_paths.side_effect = _registered_nested_path_sequence(
                    set(),
                    {"sub-001"},
                )
                result = manager._create_nested_subdatasets(
                    project_path,
                    "/usr/bin/datalad",
                    max_to_create=1,
                )

        self.assertEqual(result.get("subdatasets_created"), ["sub-001"])
        self.assertEqual(result.get("subdatasets_skipped"), ["sub-002"])
        self.assertEqual(result.get("subdatasets_remaining_count"), 1)
        self.assertEqual(
            mock_run.call_args_list[0].args[0],
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-001"],
        )
        self.assertEqual(len(mock_run.call_args_list), 2)

    @patch("src.project_manager.subprocess.run")
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which")
    def test_create_nested_subdatasets_stages_existing_untracked_content_before_create(
        self, mock_which, _mock_parent_tracks, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "rawdata"
            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001" / "file.txt").write_text("demo\n", encoding="utf-8")

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                mock_registered_paths.side_effect = _registered_nested_path_sequence(
                    set(),
                    {"sub-001"},
                )
                result = manager._create_nested_subdatasets(
                    project_path,
                    "/usr/bin/datalad",
                    max_to_create=1,
                )

            self.assertTrue((project_path / "sub-001" / "file.txt").exists())
            self.assertFalse((project_path / ".prism-datalad-stage-sub-001").exists())

        self.assertEqual(result.get("subdatasets_created"), ["sub-001"])
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-001"],
            commands,
        )

    def test_iter_nested_dataset_paths_includes_rawdata_subjects_for_parent_project(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "project"
            (project_path / "derivatives").mkdir(parents=True, exist_ok=True)
            (project_path / "rawdata" / "sub-001").mkdir(parents=True, exist_ok=True)
            (project_path / "rawdata" / "sub-002").mkdir(parents=True, exist_ok=True)

            result = manager._iter_nested_dataset_paths(project_path)

        self.assertEqual(
            [path.relative_to(project_path).as_posix() for path in result],
            ["derivatives", "rawdata/sub-001", "rawdata/sub-002"],
        )

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_get_datalad_status_detects_project_dataset(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001" / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-002").mkdir(parents=True, exist_ok=True)

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value={"sub-001"},
            ):
                result = manager.get_datalad_status(project_path)

        self.assertTrue(result.get("enabled"))
        self.assertTrue(result.get("available"))
        self.assertTrue(result.get("annex_available"))
        self.assertTrue(result.get("can_save"))
        self.assertEqual(result.get("subdatasets_total_count"), 2)
        self.assertEqual(result.get("subdatasets_registered_count"), 1)
        self.assertEqual(result.get("subdatasets_remaining_count"), 1)
        self.assertEqual(result.get("subdatasets_progress_percent"), 50)
        self.assertEqual(result.get("next_missing_subdataset"), "sub-002")

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_get_datalad_status_does_not_count_unregistered_local_dataset_metadata(
        self, _mock_which
    ):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001" / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-002").mkdir(parents=True, exist_ok=True)

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value=set(),
            ):
                result = manager.get_datalad_status(project_path)

        self.assertEqual(result.get("subdatasets_registered_count"), 0)
        self.assertEqual(result.get("subdatasets_remaining_count"), 2)
        self.assertEqual(result.get("next_missing_subdataset"), "sub-001")

    @patch("src.project_manager.shutil.which")
    def test_get_datalad_status_reports_missing_git_annex(self, mock_which):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: (
            "/usr/bin/datalad" if executable == "datalad" else None
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)

            result = manager.get_datalad_status(project_path)

        self.assertFalse(result.get("enabled"))
        self.assertTrue(result.get("available"))
        self.assertFalse(result.get("annex_available"))
        self.assertFalse(result.get("can_enable"))
        self.assertIn("git-annex", result.get("message", ""))

    @patch(
        "src.project_manager.subprocess.run",
        return_value=Mock(returncode=0, stdout="", stderr=""),
    )
    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_save_datalad_snapshot_runs_save_for_existing_dataset(
        self, _mock_which, mock_run
    ):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value=set(),
            ):
                result = manager.save_datalad_snapshot(
                    project_path,
                    message="Checkpoint metadata updates",
                )

        self.assertTrue(result.get("success"), result)
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(
            ["/usr/bin/datalad", "save", "-m", "Checkpoint metadata updates"],
            commands,
        )

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_save_datalad_snapshot_rejects_non_datalad_project(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            result = manager.save_datalad_snapshot(
                project_path,
                message="Checkpoint metadata updates",
            )

        self.assertFalse(result.get("success"))
        self.assertIn("not a DataLad dataset", result.get("error", ""))

    @patch(
        "src.project_manager.subprocess.run",
        return_value=Mock(returncode=0, stdout="", stderr=""),
    )
    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_autosave_datalad_snapshot_uses_lifecycle_message_for_project_switch(
        self, _mock_which, mock_run
    ):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value=set(),
            ):
                result = manager.autosave_datalad_snapshot(
                    project_path,
                    reason="project_switch next_project=/tmp/other",
                )

        self.assertTrue(result.get("success"), result)
        self.assertTrue(result.get("attempted"), result)
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(
            ["/usr/bin/datalad", "save", "-m", "PRISM auto-save before project switch"],
            commands,
        )

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_autosave_datalad_snapshot_skips_non_datalad_project(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            result = manager.autosave_datalad_snapshot(
                project_path,
                reason="prism_closed",
            )

        self.assertTrue(result.get("success"), result)
        self.assertTrue(result.get("skipped"), result)
        self.assertFalse(result.get("attempted"), result)

    @patch(
        "src.project_manager.subprocess.run",
        return_value=Mock(returncode=0, stdout="", stderr=""),
    )
    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_enable_datalad_for_project_initializes_and_saves_dataset(
        self, _mock_which, mock_run
    ):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value=set(),
            ):
                result = manager.enable_datalad_for_project(
                    project_path,
                    message="Enable DataLad for PRISM project",
                )

        self.assertTrue(result.get("success"), result)
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(["/usr/bin/datalad", "create", "--force"], commands)
        self.assertIn(
            ["/usr/bin/datalad", "save", "-m", "Enable DataLad for PRISM project"],
            commands,
        )

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_enable_datalad_for_project_is_idempotent_for_existing_dataset(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            result = manager.enable_datalad_for_project(project_path)

        self.assertTrue(result.get("success"), result)
        self.assertIn("already tracked by DataLad", result.get("message", ""))

    @patch("src.project_manager.subprocess.run")
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_backfills_missing_subject_subdatasets(
        self, mock_which, _mock_parent_tracks, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "rawdata"
            subject_existing = project_path / "sub-171"
            subject_missing = project_path / "sub-172"
            subject_remaining = project_path / "sub-173"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            subject_existing.mkdir(parents=True, exist_ok=True)
            subject_missing.mkdir(parents=True, exist_ok=True)
            subject_remaining.mkdir(parents=True, exist_ok=True)
            (subject_existing / ".datalad").mkdir(parents=True, exist_ok=True)
            (subject_missing / "data.tsv").write_text("value\n1\n", encoding="utf-8")
            (subject_remaining / "data.tsv").write_text("value\n2\n", encoding="utf-8")

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                mock_registered_paths.side_effect = _registered_nested_path_sequence(
                    {"sub-171"},
                    {"sub-171"},
                    {"sub-171", "sub-172"},
                    {"sub-171", "sub-172"},
                )
                result = manager.enable_datalad_for_project(project_path)

        self.assertTrue(result.get("success"), result)
        self.assertIn("Added 1 nested subdataset", result.get("message", ""))
        self.assertIn("run repair again to continue", result.get("message", ""))
        self.assertEqual(
            result.get("datalad", {}).get("subdatasets_created"),
            ["sub-172"],
        )
        self.assertEqual(
            result.get("datalad", {}).get("subdatasets_existing"),
            ["sub-171"],
        )
        self.assertEqual(
            result.get("datalad", {}).get("subdatasets_skipped"),
            ["sub-173"],
        )
        self.assertEqual(
            result.get("datalad", {}).get("subdatasets_remaining_count"),
            1,
        )
        self.assertEqual(
            mock_run.call_args_list[0].args[0],
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-172"],
        )
        self.assertEqual(
            mock_run.call_args_list[0].kwargs.get("cwd"),
            str(project_path),
        )
        self.assertEqual(
            mock_run.call_args_list[1].args[0],
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'Initialize DataLad nested dataset "sub-172"',
            ],
        )
        self.assertEqual(
            mock_run.call_args_list[1].kwargs.get("cwd"),
            str(subject_missing),
        )
        self.assertEqual(
            mock_run.call_args_list[2].args[0],
            ["/usr/bin/datalad", "save", "-m", "Enable DataLad for PRISM project"],
        )

    @patch("src.project_manager.subprocess.run")
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_backfills_derivatives_subdataset(
        self, mock_which, _mock_parent_tracks, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "derivatives").mkdir(parents=True, exist_ok=True)

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                mock_registered_paths.side_effect = _registered_nested_path_sequence(
                    set(),
                    set(),
                    {"derivatives"},
                    {"derivatives"},
                )
                result = manager.enable_datalad_for_project(project_path)

        self.assertTrue(result.get("success"), result)
        self.assertIn("Added 1 nested subdataset", result.get("message", ""))
        self.assertEqual(
            result.get("datalad", {}).get("subdatasets_remaining_count"),
            0,
        )
        self.assertEqual(
            result.get("datalad", {}).get("subdatasets_created"),
            ["derivatives"],
        )
        self.assertEqual(
            mock_run.call_args_list[0].args[0],
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "derivatives"],
        )
        self.assertEqual(
            mock_run.call_args_list[1].args[0],
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'Initialize DataLad nested dataset "derivatives"',
            ],
        )

    @patch("src.project_manager.subprocess.run")
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_reports_failure_when_next_repair_fails(
        self, mock_which, _mock_parent_tracks, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="boom")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "rawdata"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-172").mkdir(parents=True, exist_ok=True)

            result = manager.enable_datalad_for_project(project_path)

        self.assertTrue(result.get("success"), result)
        self.assertIn("could not register the next missing nested dataset", result.get("message", ""))
        self.assertEqual(
            result.get("datalad", {}).get("subdataset_failures"),
            ["sub-172 (create nested dataset failed: boom)"],
        )

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_migrates_parent_tracked_derivatives(
        self, mock_which, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "derivatives").mkdir(parents=True, exist_ok=True)
            (project_path / "derivatives" / "file.txt").write_text("demo\n", encoding="utf-8")

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                with patch(
                    "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
                    side_effect=[True, False],
                ):
                    mock_registered_paths.side_effect = _registered_nested_path_sequence(
                        set(),
                        set(),
                        {"derivatives"},
                        {"derivatives"},
                    )
                    result = manager.enable_datalad_for_project(project_path)

            self.assertTrue((project_path / "derivatives" / "file.txt").exists())
            self.assertFalse((project_path / ".prism-datalad-stage-derivatives").exists())

        self.assertTrue(result.get("success"), result)
        self.assertIn("Added 1 nested subdataset", result.get("message", ""))
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(
            ["git", "rm", "--cached", "-r", "--", "derivatives"],
            commands,
        )
        self.assertIn(
            [
                "/usr/bin/datalad",
                "save",
                "--updated",
                "-m",
                'Stage parent untracking for nested DataLad dataset "derivatives"',
            ],
            commands,
        )
        self.assertIn(
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "derivatives"],
            commands,
        )

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_restores_staged_content_when_create_fails(
        self, mock_which, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"

        def _run_side_effect(command, **_kwargs):
            if command[:4] == ["git", "rm", "--cached", "-r"]:
                return Mock(returncode=0, stdout="", stderr="")
            if command[:3] == ["/usr/bin/datalad", "save", "--updated"]:
                return Mock(returncode=0, stdout="", stderr="")
            if command[:2] == ["/usr/bin/datalad", "create"]:
                return Mock(returncode=1, stdout="", stderr="collision")
            return Mock(returncode=0, stdout="", stderr="")

        mock_run.side_effect = _run_side_effect

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "derivatives").mkdir(parents=True, exist_ok=True)
            (project_path / "derivatives" / "file.txt").write_text("demo\n", encoding="utf-8")

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value=set(),
            ):
                with patch(
                    "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
                    side_effect=[True, False],
                ):
                    result = manager.enable_datalad_for_project(project_path)

            self.assertTrue((project_path / "derivatives" / "file.txt").exists())
            self.assertFalse((project_path / ".prism-datalad-stage-derivatives").exists())

        self.assertTrue(result.get("success"), result)
        self.assertIn("create nested dataset failed", result.get("message", ""))

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_fails_before_create_when_parent_still_tracks_after_staging_save(
        self, mock_which, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-035").mkdir(parents=True, exist_ok=True)

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value=set(),
            ):
                with patch(
                    "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
                    side_effect=[True, True],
                ):
                    result = manager.enable_datalad_for_project(project_path)

        self.assertTrue(result.get("success"), result)
        self.assertIn(
            "could not register the next missing nested dataset",
            result.get("message", ""),
        )
        failures = result.get("datalad", {}).get("subdataset_failures") or []
        self.assertEqual(len(failures), 1)
        self.assertIn("verify parent untracking failed", failures[0])
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(
            [
                "/usr/bin/datalad",
                "save",
                "--updated",
                "-m",
                'Stage parent untracking for nested DataLad dataset "sub-035"',
            ],
            commands,
        )
        self.assertNotIn(
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-035"],
            commands,
        )

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_requires_registration_confirmation_before_progress(
        self, mock_which, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "derivatives").mkdir(parents=True, exist_ok=True)

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value=set(),
            ):
                with patch(
                    "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
                    side_effect=[True, False],
                ):
                    result = manager.enable_datalad_for_project(project_path)

        self.assertTrue(result.get("success"), result)
        self.assertIn(
            "could not register the next missing nested dataset",
            result.get("message", ""),
        )
        failures = result.get("datalad", {}).get("subdataset_failures") or []
        self.assertEqual(len(failures), 1)
        self.assertIn("verify nested dataset registration failed", failures[0])

    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=True,
    )
    @patch("src.project_manager.shutil.which")
    @patch("src.project_manager.subprocess.run")
    def test_enable_datalad_for_project_reports_timeout_for_parent_untrack_step(
        self, mock_run, mock_which, _mock_parent_tracks
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["git", "rm", "--cached", "-r", "--", "derivatives"],
            timeout=120,
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "derivatives").mkdir(parents=True, exist_ok=True)

            result = manager.enable_datalad_for_project(project_path)

        self.assertTrue(result.get("success"), result)
        failures = result.get("datalad", {}).get("subdataset_failures") or []
        self.assertEqual(len(failures), 1)
        self.assertIn("timed out after 120 seconds", failures[0])

    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_fails_without_git_annex(self, mock_which):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: (
            "/usr/bin/datalad" if executable == "datalad" else None
        )

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            result = manager.enable_datalad_for_project(project_path)

        self.assertFalse(result.get("success"))
        self.assertIn("git-annex", result.get("error", ""))

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_export_project_to_plain_folder_strips_repository_metadata(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / ".git").mkdir(parents=True, exist_ok=True)
            (project_path / ".gitattributes").write_text("* annex.largefiles=anything\n", encoding="utf-8")
            (project_path / "CHANGES").write_text("history\n", encoding="utf-8")
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
            subject_dir = project_path / "sub-001" / "beh"
            subject_dir.mkdir(parents=True, exist_ok=True)
            (subject_dir / "sub-001_task-demo_events.tsv").write_text(
                "participant_id\tvalue\nsub-001\t1\n",
                encoding="utf-8",
            )

            export_root = Path(tmp) / "exports"
            result = manager.export_project_to_plain_folder(
                project_path,
                output_root=export_root,
            )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertTrue(output_path.exists())
            self.assertEqual(
                result.get("excluded_repository_metadata"),
                [".datalad", ".git", ".gitattributes", ".gitignore", ".gitmodules", "CHANGES"],
            )
            self.assertTrue((output_path / "dataset_description.json").exists())
            self.assertTrue((output_path / "sub-001" / "beh" / "sub-001_task-demo_events.tsv").exists())
            self.assertFalse((output_path / ".git").exists())
            self.assertFalse((output_path / ".datalad").exists())
            self.assertFalse((output_path / ".gitattributes").exists())
            self.assertFalse((output_path / "CHANGES").exists())

    def test_export_project_to_plain_folder_materializes_symlinked_files(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            annex_target = project_path / ".git" / "annex" / "objects" / "payload.tsv"
            annex_target.parent.mkdir(parents=True, exist_ok=True)
            annex_target.write_text("participant_id\tvalue\nsub-001\t1\n", encoding="utf-8")

            linked_file = project_path / "sub-001" / "beh" / "sub-001_task-demo_events.tsv"
            linked_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                linked_file.symlink_to(annex_target)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            export_root = Path(tmp) / "exports"
            result = manager.export_project_to_plain_folder(
                project_path,
                output_root=export_root,
            )

            self.assertTrue(result.get("success"), result)
            output_file = (
                Path(result["output_path"])
                / "sub-001"
                / "beh"
                / "sub-001_task-demo_events.tsv"
            )
            self.assertTrue(output_file.exists())
            self.assertFalse(output_file.is_symlink())
            self.assertEqual(
                output_file.read_text(encoding="utf-8"),
                "participant_id\tvalue\nsub-001\t1\n",
            )

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_export_project_to_plain_folder_accepts_nontracked_project(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            result = manager.export_project_to_plain_folder(project_path)

            self.assertTrue(result.get("success"), result)
            self.assertTrue(Path(result["output_path"]).exists())


    def test_create_project_reports_existing_nonempty_target_actionably(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "notes.txt").write_text("existing", encoding="utf-8")

            result = manager.create_project(str(project_path), {"name": "demo_project"})

            self.assertFalse(result.get("success"))
            self.assertIn("parent folder", result.get("error", ""))
            self.assertIn("Open Existing Project", result.get("error", ""))

    def test_create_bidsignore_excludes_eyetracking_passthrough(self):
        manager = ProjectManager()

        content = manager._create_bidsignore(["survey", "eyetracking"])

        self.assertIn("survey/", content)
        self.assertNotIn("eyetracking/", content)

    def test_create_citation_cff_includes_demo_author_fields_when_empty(self):
        manager = ProjectManager()

        content = manager._create_citation_cff("demo_project", {"name": "demo_project"})

        self.assertIn("given-names", content)
        self.assertIn("family-names", content)
        self.assertIn("type: dataset", content)

    def test_create_citation_cff_supports_rich_author_dict(self):
        manager = ProjectManager()

        rich_author = {
            "given-names": "Alex",
            "family-names": "Example",
            "website": "https://example.org",
            "orcid": "https://orcid.org/0000-0000-0000-0001",
            "affiliation": "Example Institute",
            "email": "alex@example.org",
        }

        content = manager._create_citation_cff(
            "demo_project",
            {"name": "demo_project", "authors": [rich_author]},
        )

        self.assertIn('family-names: "Example"', content)
        self.assertIn('given-names: "Alex"', content)
        self.assertIn('website: "https://example.org"', content)
        self.assertIn('orcid: "https://orcid.org/0000-0000-0000-0001"', content)
        self.assertIn('affiliation: "Example Institute"', content)
        self.assertIn('email: "alex@example.org"', content)

    def test_create_citation_cff_preserves_unicode_text(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "Depressivitäts-Studie",
                "authors": [
                    {
                        "family-names": "Müller",
                        "given-names": "Jörg",
                    }
                ],
                "abstract": "Strukturelle Veränderungen werden באמצעות MRT erfasst.",
            },
        )

        self.assertIn('title: "Depressivitäts-Studie"', content)
        self.assertIn('family-names: "Müller"', content)
        self.assertIn('given-names: "Jörg"', content)
        self.assertIn('abstract: "Strukturelle Veränderungen werden באמצעות MRT erfasst."', content)
        self.assertNotIn('\\u00', content)
        self.assertNotIn('\\u05', content)

    def test_update_citation_cff_prefers_richer_project_contact_metadata(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "project.json").write_text(
                json.dumps(
                    {
                        "name": "demo_project",
                        "governance": {
                            "contacts": [
                                {
                                    "name": "Koschutnig, Karl",
                                    "email": "karl.koschutnig@uni-graz.at",
                                    "orcid": "https://orcid.org/0000-0001-6234-0498",
                                    "corresponding": True,
                                    "roles": ["Data curation"],
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            manager.update_citation_cff(
                project_path,
                {
                    "Name": "Demo",
                    "BIDSVersion": "1.10.1",
                    "DatasetType": "raw",
                    "Authors": ["Koschutnig, Karl"],
                },
            )

            citation_content = (project_path / "CITATION.cff").read_text(
                encoding="utf-8"
            )
            self.assertIn('family-names: "Koschutnig"', citation_content)
            self.assertIn('given-names: "Karl"', citation_content)
            self.assertIn(
                'orcid: "https://orcid.org/0000-0001-6234-0498"',
                citation_content,
            )
            self.assertIn(
                'email: "karl.koschutnig@uni-graz.at"',
                citation_content,
            )
            self.assertIn("contact:", citation_content)

    def test_create_citation_cff_deduplicates_duplicate_author_entries(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "demo_project",
                "authors": [
                    "Ada Lovelace",
                    {
                        "family-names": "Lovelace",
                        "given-names": "Ada",
                        "email": "ada@example.org",
                    },
                    {
                        "family-names": "Lovelace",
                        "given-names": "Ada",
                    },
                ],
            },
        )

        self.assertEqual(content.count('family-names: "Lovelace"'), 1)
        self.assertEqual(content.count('given-names: "Ada"'), 1)
        self.assertIn('email: "ada@example.org"', content)

    def test_create_citation_cff_parses_family_given_author_strings(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "demo_project",
                "authors": ["Lovelace, Ada"],
            },
        )

        self.assertIn('family-names: "Lovelace"', content)
        self.assertIn('given-names: "Ada"', content)

    def test_create_citation_cff_includes_extended_dataset_fields(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "Limb assignment task B006b",
                "authors": ["Jane Doe"],
                "doi": "10.60817/9fzf-v802",
                "license": "CC-BY-4.0",
                "license_url": "https://example.org/license",
                "keywords": ["tactile", "remapping"],
                "abstract": "Dataset abstract",
                "url": "https://example.org/dataset",
                "repository_code": "https://github.com/example/repo",
                "references": [
                    "https://osf.io/zh5rg/",
                    "10.17605/OSF.IO/ZH5RG",
                    "Heed et al. manuscript",
                ],
            },
        )

        self.assertIn("type: dataset", content)
        self.assertIn('doi: "10.60817/9fzf-v802"', content)
        self.assertIn("message: >-", content)
        self.assertIn(
            "If you use this dataset, please cite it using the metadata from this file.",
            content,
        )
        self.assertNotIn("preferred-citation:", content)
        self.assertIn('license: "CC-BY-4.0"', content)
        self.assertIn('license-url: "https://example.org/license"', content)
        self.assertIn('url: "https://example.org/dataset"', content)
        self.assertIn('repository-code: "https://github.com/example/repo"', content)
        self.assertIn("keywords:", content)
        self.assertIn('  - "tactile"', content)
        self.assertIn('abstract: "Dataset abstract"', content)
        self.assertIn("references:", content)
        self.assertIn('type: "generic"', content)
        self.assertIn("authors:", content)
        self.assertIn('name: "Jane Doe"', content)
        self.assertIn('url: "https://osf.io/zh5rg/"', content)
        self.assertIn('doi: "10.17605/OSF.IO/ZH5RG"', content)
        self.assertIn('title: "Heed et al. manuscript"', content)

    def test_create_citation_cff_splits_semicolon_delimited_keywords(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "demo_project",
                "keywords": [
                    "Hippocampus",
                    "email-lists; social-media",
                    "Running, longitudinal",
                ],
            },
        )

        self.assertIn('  - "Hippocampus"', content)
        self.assertIn('  - "email-lists"', content)
        self.assertIn('  - "social-media"', content)
        self.assertIn('  - "Running"', content)
        self.assertIn('  - "longitudinal"', content)
        self.assertNotIn('  - "email-lists; social-media"', content)

    def test_create_citation_cff_builds_preferred_citation_from_url_acknowledgement(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "demo_project",
                "how_to_acknowledge": "https://doi.org/10.1007/s00429-024-02885-2",
            },
        )

        self.assertIn("message: >-", content)
        self.assertIn(
            "If you use this dataset, please cite both the preferred-citation and the dataset itself.",
            content,
        )
        self.assertIn("preferred-citation:", content)
        self.assertIn('title: "Preferred citation"', content)
        self.assertIn('doi: "10.1007/s00429-024-02885-2"', content)
        self.assertNotIn('message: "https://doi.org/10.1007/s00429-024-02885-2"', content)

    def test_create_citation_cff_uses_matching_reference_as_preferred_citation(self):
        manager = ProjectManager()

        content = manager._create_citation_cff(
            "demo_project",
            {
                "name": "demo_project",
                "authors": ["Jane Doe"],
                "how_to_acknowledge": "10.1000/preferred",
                "references": [
                    {
                        "type": "article",
                        "title": "Dataset paper",
                        "doi": "10.1000/preferred",
                        "journal": "Journal of Datasets",
                        "year": 2026,
                        "authors": [{"family-names": "Doe", "given-names": "Jane"}],
                    },
                    {
                        "type": "article",
                        "title": "Background paper",
                        "doi": "10.1000/background",
                    },
                ],
            },
        )

        self.assertIn("preferred-citation:", content)
        self.assertIn('type: "article"', content)
        self.assertIn('title: "Dataset paper"', content)
        self.assertIn('journal: "Journal of Datasets"', content)
        self.assertIn('year: "2026"', content)
        self.assertEqual(content.count('doi: "10.1000/preferred"'), 1)
        self.assertIn('doi: "10.1000/background"', content)

    def test_build_citation_config_uses_project_json_fallbacks(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            project_payload = {
                "name": "workshop",
                "Basics": {
                    "DatasetName": "Workshop Test Dataset",
                    "Keywords": ["psychology", "survey"],
                },
                "Overview": {
                    "Main": "Test study overview.",
                },
                "StudyDesign": {
                    "Type": "longitudinal",
                    "TypeDescription": "Randomized intervention over 4 weeks.",
                },
                "Recruitment": {
                    "Method": "snowball",
                },
                "DataCollection": {
                    "Description": "Daily app-based questionnaires.",
                },
                "Procedure": {
                    "Overview": "Baseline, intervention, and post assessment.",
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
                    "study": [
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
            (project_path / "project.json").write_text(
                json.dumps(project_payload), encoding="utf-8"
            )

            config = manager._build_citation_config(
                "workshop", {"Name": "", "Authors": []}, project_path
            )
            content = manager._create_citation_cff("workshop", config)

        self.assertEqual(config.get("name"), "Workshop Test Dataset")
        self.assertIn('family-names: "ff"', content)
        self.assertIn('given-names: "prism-studio"', content)
        self.assertIn('email: "team@example.org"', content)
        self.assertIn(
            'abstract: "Test study overview. Randomized intervention over 4 weeks. Daily app-based questionnaires. Baseline, intervention, and post assessment."',
            content,
        )
        self.assertIn('  - "psychology"', content)
        self.assertIn('  - "longitudinal"', content)
        self.assertIn('  - "wellbeing"', content)
        self.assertIn('  - "survey"', content)
        self.assertNotIn('  - "snowball"', content)
        self.assertIn('doi: "10.1000/xyz123"', content)
        self.assertEqual(config.get("url"), "")

    def test_build_citation_config_separates_dataset_url_and_code_repository(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            project_payload = {
                "name": "demo",
                "References": {
                    "resources": [
                        {
                            "title": "Archive",
                            "url": "https://osf.io/abcd1/",
                        }
                    ]
                },
                "governance": {
                    "funding": [{"agency": "Grant Agency", "grant_number": "1234"}],
                    "ethics_approvals": [{"committee": "IRB", "approval_number": "1"}],
                },
            }
            (project_path / "project.json").write_text(
                json.dumps(project_payload), encoding="utf-8"
            )

            description = {
                "Name": "demo",
                "Authors": ["Jane Doe"],
                "DatasetLinks": {"landing": "https://example.org/dataset"},
                "ReferencesAndLinks": [
                    "[object Object]",
                    {
                        "title": "Code",
                        "url": "https://github.com/example/repo",
                    },
                ],
            }

            config = manager._build_citation_config("demo", description, project_path)
            reference_titles = [
                str(item.get("title") or "") for item in config.get("references", [])
            ]

        self.assertEqual(config.get("url"), "https://example.org/dataset")
        self.assertEqual(
            config.get("repository_code"),
            "https://github.com/example/repo",
        )
        self.assertEqual(config.get("repository"), "https://osf.io/abcd1/")
        self.assertFalse(
            any(title.lower() == "[object object]" for title in reference_titles)
        )
        self.assertFalse(any("Grant Agency" in title for title in reference_titles))

    def test_build_citation_config_avoids_url_repository_code_duplication(self):
        manager = ProjectManager()

        config = manager._build_citation_config(
            "demo",
            {
                "Name": "demo",
                "Authors": ["Jane Doe"],
                "ReferencesAndLinks": ["https://github.com/example/repo"],
            },
        )

        self.assertEqual(config.get("repository_code"), "https://github.com/example/repo")
        self.assertEqual(config.get("url"), "")

    def test_citation_status_reports_missing_file(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            status = manager.get_citation_cff_status(Path(tmp))

        self.assertFalse(status.get("exists"))
        self.assertFalse(status.get("valid"))
        self.assertTrue(status.get("issues"))

    def test_citation_status_reports_valid_generated_file(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            citation_path = project_path / "CITATION.cff"
            citation_path.write_text(
                manager._create_citation_cff(
                    "demo_project",
                    {
                        "name": "demo_project",
                        "authors": ["Jane Doe"],
                        "references": ["https://example.org/ref"],
                    },
                ),
                encoding="utf-8",
            )

            status = manager.get_citation_cff_status(project_path)

        self.assertTrue(status.get("exists"))
        self.assertTrue(status.get("valid"))
        self.assertEqual(status.get("issues"), [])
        self.assertTrue(status.get("consistent"))
        self.assertEqual(status.get("consistency_issues"), [])

    def test_citation_status_reports_manual_cff_drift(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path),
                {
                    "name": "demo_project",
                    "authors": ["Jane Doe"],
                    "license": "CC-BY-4.0",
                    "doi": "10.1000/demo",
                },
            )
            self.assertTrue(created.get("success"), created)

            citation_path = project_path / "CITATION.cff"
            content = citation_path.read_text(encoding="utf-8")
            citation_path.write_text(
                content.replace('title: "demo_project"', 'title: "manual edit"', 1),
                encoding="utf-8",
            )

            status = manager.get_citation_cff_status(project_path)

        self.assertTrue(status.get("exists"))
        self.assertTrue(status.get("valid"))
        self.assertEqual(status.get("issues"), [])
        self.assertFalse(status.get("consistent"))
        self.assertTrue(status.get("consistency_issues"))

    def test_sync_dataset_metadata_to_project_json_updates_basics_and_name(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "project.json").write_text(
                json.dumps(
                    {"name": "old-name", "Basics": {"DatasetName": "old-name"}}
                ),
                encoding="utf-8",
            )

            manager.sync_dataset_metadata_to_project_json(
                project_path,
                {
                    "Name": "new-name",
                    "BIDSVersion": "1.10.1",
                    "DatasetType": "raw",
                    "DatasetDOI": "10.1000/demo",
                    "License": "CC-BY-4.0",
                    "HowToAcknowledge": "Please cite this dataset.",
                    "Description": "Dataset summary",
                    "Keywords": ["memory", "attention"],
                    "DatasetLinks": {"landing": "https://example.org/dataset"},
                    "ReferencesAndLinks": ["https://example.org/paper"],
                    "Funding": ["FWF P12345"],
                    "EthicsApprovals": ["EK-2026-001"],
                    "Authors": ["Jane Doe"],
                },
            )

            payload = json.loads(
                (project_path / "project.json").read_text(encoding="utf-8")
            )

        self.assertEqual(payload.get("name"), "new-name")
        basics = payload.get("Basics") or {}
        self.assertEqual(basics.get("DatasetName"), "new-name")
        self.assertEqual(basics.get("DatasetDOI"), "10.1000/demo")
        self.assertEqual(basics.get("License"), "CC-BY-4.0")
        self.assertEqual(
            basics.get("HowToAcknowledge"), "Please cite this dataset."
        )
        self.assertEqual(basics.get("Keywords"), ["memory", "attention"])
        self.assertEqual(
            basics.get("DatasetLinks"),
            {"landing": "https://example.org/dataset"},
        )
        self.assertEqual(
            basics.get("ReferencesAndLinks"), ["https://example.org/paper"]
        )
        self.assertEqual(basics.get("Funding"), ["FWF P12345"])
        self.assertEqual(basics.get("EthicsApprovals"), ["EK-2026-001"])
        self.assertEqual(basics.get("Authors"), ["Jane Doe"])

    def test_build_citation_config_prefers_project_json_dataset_links(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "project.json").write_text(
                json.dumps(
                    {
                        "name": "demo",
                        "Basics": {
                            "DatasetLinks": {
                                "landing": "https://example.org/dataset",
                                "docs": "https://example.org/docs",
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            config = manager._build_citation_config(
                "demo",
                {
                    "Name": "demo",
                    "Authors": ["Jane Doe"],
                    "DatasetLinks": {"landing": "https://stale.example.org/dataset"},
                    "ReferencesAndLinks": [
                        {"title": "Code", "url": "https://github.com/example/repo"}
                    ],
                },
                project_path,
            )

        self.assertEqual(config.get("url"), "https://example.org/dataset")
        self.assertEqual(
            config.get("identifiers"),
            [
                {
                    "type": "url",
                    "value": "https://example.org/docs",
                    "description": "Dataset link: docs",
                }
            ],
        )

    def test_metadata_sync_status_reports_project_and_dataset_mismatch(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp)
            (project_path / "project.json").write_text(
                json.dumps(
                    {
                        "name": "project-name",
                        "Basics": {
                            "DatasetName": "project-name",
                            "DatasetDOI": "10.1000/project",
                            "Keywords": ["memory"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            (project_path / "dataset_description.json").write_text(
                json.dumps(
                    {
                        "Name": "dataset-name",
                        "BIDSVersion": "1.10.1",
                        "DatasetType": "raw",
                        "DatasetDOI": "10.1000/dataset",
                        "Keywords": ["attention"],
                    }
                ),
                encoding="utf-8",
            )

            status = manager.get_metadata_sync_status(project_path)

        self.assertTrue(status.get("project_json_exists"))
        self.assertTrue(status.get("dataset_description_exists"))
        self.assertFalse(status.get("consistent"))
        self.assertTrue(status.get("issues"))

    def test_metadata_sync_status_ignores_citation_only_drift(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path),
                {
                    "name": "demo_project",
                    "authors": ["Jane Doe"],
                    "license": "CC-BY-4.0",
                    "doi": "10.1000/demo",
                },
            )
            self.assertTrue(created.get("success"), created)

            citation_path = project_path / "CITATION.cff"
            content = citation_path.read_text(encoding="utf-8")
            citation_path.write_text(
                content.replace('title: "demo_project"', 'title: "manual edit"', 1),
                encoding="utf-8",
            )

            status = manager.get_metadata_sync_status(project_path)

        self.assertTrue(status.get("project_json_exists"))
        self.assertTrue(status.get("dataset_description_exists"))
        self.assertTrue(status.get("citation_exists"))
        self.assertTrue(status.get("consistent"))
        self.assertEqual(status.get("issues"), [])

    def test_citation_status_uses_rich_project_contact_metadata(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)

            (project_path / "dataset_description.json").write_text(
                json.dumps(
                    {
                        "Name": "Demo",
                        "BIDSVersion": "1.10.1",
                        "DatasetType": "raw",
                    }
                ),
                encoding="utf-8",
            )
            (project_path / "project.json").write_text(
                json.dumps(
                    {
                        "name": "demo_project",
                        "Basics": {
                            "DatasetName": "Demo",
                            "License": "CC-BY-4.0",
                        },
                        "governance": {
                            "contacts": [
                                {
                                    "name": "Fink, Andreas",
                                    "given-names": "Andreas",
                                    "family-names": "Fink",
                                    "website": "https://example.org/andreas",
                                    "affiliation": "University of Graz",
                                    "orcid": "https://orcid.org/0000-0001-7316-3140",
                                    "email": "andreas@example.org",
                                    "roles": ["Methodology"],
                                    "corresponding": True,
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            manager.regenerate_citation_cff(project_path)
            citation_text = (project_path / "CITATION.cff").read_text(encoding="utf-8")
            status = manager.get_citation_cff_status(project_path)

        self.assertIn('website: "https://example.org/andreas"', citation_text)
        self.assertIn('affiliation: "University of Graz"', citation_text)
        self.assertIn('email: "andreas@example.org"', citation_text)
        self.assertTrue(status.get("consistent"))
        self.assertEqual(status.get("consistency_issues"), [])

    def test_validate_structure_does_not_require_participants_for_empty_project(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertNotIn("PRISM004", issue_codes)
        self.assertTrue(result.get("stats", {}).get("has_participants_tsv"))
        self.assertFalse(result.get("stats", {}).get("participants_tsv_required"))

    def test_validate_structure_requires_participants_when_subjects_exist(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertIn("PRISM004", issue_codes)
        self.assertFalse(result.get("stats", {}).get("has_participants_tsv"))
        self.assertTrue(result.get("stats", {}).get("participants_tsv_required"))

    def test_validate_structure_counts_bids_modalities_in_stats(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            (project_path / "sub-001" / "func").mkdir(parents=True, exist_ok=True)
            result = manager.validate_structure(str(project_path))

        modalities = result.get("stats", {}).get("modalities", [])
        self.assertIn("func", modalities)

    def test_validate_structure_reports_invalid_dataset_description_content(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            # Force schema violations while keeping valid JSON syntax.
            (project_path / "dataset_description.json").write_text(
                "{}",
                encoding="utf-8",
            )

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertIn("PRISM301", issue_codes)

    def test_validate_structure_does_not_modify_bidsignore(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            bidsignore_path = project_path / ".bidsignore"
            original_content = "# Existing rules\ncustom-rule/\n"
            bidsignore_path.write_text(original_content, encoding="utf-8")

            result = manager.validate_structure(str(project_path))

            self.assertTrue(result.get("valid"), result)
            self.assertEqual(
                bidsignore_path.read_text(encoding="utf-8"),
                original_content,
            )

    def test_validate_structure_surfaces_runner_warnings_separately(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            (project_path / "derivatives" / "demo-derivative").mkdir(
                parents=True, exist_ok=True
            )

            result = manager.validate_structure(str(project_path))

        warning_messages = [
            (warning.get("message") or "").lower()
            for warning in result.get("runner_warnings", [])
        ]
        self.assertTrue(
            any(
                "derivatives dataset" in msg
                and "missing dataset_description.json" in msg
                for msg in warning_messages
            )
        )

        issue_messages = [
            (issue.get("message") or "").lower() for issue in result.get("issues", [])
        ]
        self.assertFalse(any("derivatives dataset" in msg for msg in issue_messages))

    def test_validate_structure_maps_participants_mismatch_to_actionable_issue(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            runner_issues = [
                (
                    "ERROR",
                    "participants.tsv mismatch with dataset subject folders. "
                    "Subjects present as sub-* folders but missing in participants.tsv: sub-002",
                    str(project_path / "participants.tsv"),
                )
            ]

            with patch(
                "src.core.validation.validate_dataset",
                return_value=(runner_issues, None),
            ):
                result = manager.validate_structure(str(project_path))

        issues_by_code = {
            issue.get("code"): issue for issue in result.get("issues", [])
        }
        mismatch_issue = issues_by_code.get("PRISM707")
        self.assertIsNotNone(mismatch_issue)
        self.assertIn(
            "Open Sociodemographics",
            mismatch_issue.get("fix_hint", ""),
        )

    def test_validate_structure_does_not_flag_missing_sidecar_for_beh(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            beh_dir = project_path / "sub-001" / "ses-01" / "beh"
            beh_dir.mkdir(parents=True, exist_ok=True)
            (beh_dir / "sub-001_ses-01_task-demo_beh.tsv").write_text(
                "onset\tduration\tresponse_time\n0\t1\t0.5\n",
                encoding="utf-8",
            )

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertNotIn("PRISM201", issue_codes)

    def test_validate_structure_keeps_missing_sidecar_warning_for_survey(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            survey_dir = project_path / "sub-001" / "ses-01" / "survey"
            survey_dir.mkdir(parents=True, exist_ok=True)
            (survey_dir / "sub-001_ses-01_task-demo_survey.tsv").write_text(
                "item1\n1\n",
                encoding="utf-8",
            )

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertIn("PRISM201", issue_codes)

    def test_validate_structure_does_not_flag_missing_sidecar_for_scans_table(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            session_dir = project_path / "sub-001" / "ses-01"
            session_dir.mkdir(parents=True, exist_ok=True)
            (session_dir / "sub-001_ses-01_scans.tsv").write_text(
                "filename\tacq_time\nfunc/sub-001_ses-01_task-rest_bold.nii.gz\t2026-04-22T10:00:00\n",
                encoding="utf-8",
            )

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertNotIn("PRISM201", issue_codes)

    def test_validate_structure_respects_inherited_physio_sidecar_with_entities(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            created = manager.create_project(
                str(project_path), {"name": "demo_project"}
            )
            self.assertTrue(created.get("success"), created)

            physio_dir = project_path / "sub-001" / "ses-01" / "physio"
            physio_dir.mkdir(parents=True, exist_ok=True)
            (physio_dir / "sub-001_ses-01_task-rest_recording-ecg_physio.tsv").write_text(
                "time\tcardiac\n0\t72\n",
                encoding="utf-8",
            )

            (project_path / "task-rest_recording-ecg_physio.json").write_text(
                '{"SamplingFrequency": 1000}',
                encoding="utf-8",
            )

            result = manager.validate_structure(str(project_path))

        issue_codes = {issue.get("code") for issue in result.get("issues", [])}
        self.assertNotIn("PRISM201", issue_codes)


if __name__ == "__main__":
    unittest.main()
