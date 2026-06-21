import json
import os
import stat
import sys
import tempfile
import time
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

    def test_create_project_defaults_auto_environment_enrichment_on(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(str(project_path), {"name": "demo_project"})

            self.assertTrue(result.get("success"), result)

            payload = json.loads((project_path / "project.json").read_text(encoding="utf-8"))

        self.assertTrue(payload["app"]["features"]["auto_environment_enrichment"])

    def test_create_project_forwards_auto_environment_enrichment_opt_out(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(
                str(project_path),
                {"name": "demo_project", "auto_environment_enrichment": False},
            )

            self.assertTrue(result.get("success"), result)

            payload = json.loads((project_path / "project.json").read_text(encoding="utf-8"))

        self.assertFalse(payload["app"]["features"]["auto_environment_enrichment"])

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
            gitattributes_content = (project_path / ".gitattributes").read_text(
                encoding="utf-8"
            )

        self.assertTrue(result.get("success"), result)
        self.assertFalse(result.get("datalad", {}).get("requested"))
        self.assertFalse(result.get("datalad", {}).get("initialized"))
        mock_run.assert_not_called()
        self.assertIn("*.json annex.largefiles=nothing", gitattributes_content)
        self.assertIn("*.tsv annex.largefiles=nothing", gitattributes_content)

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which", return_value=None)
    def test_create_project_applies_text_policy_without_datalad_requested(
        self, _mock_which, mock_run
    ):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            result = manager.create_project(
                str(project_path),
                {"name": "demo_project"},
            )
            gitattributes_content = (project_path / ".gitattributes").read_text(
                encoding="utf-8"
            )

        self.assertTrue(result.get("success"), result)
        mock_run.assert_not_called()
        self.assertIn("*.json annex.largefiles=nothing", gitattributes_content)
        self.assertIn("*.tsv annex.largefiles=nothing", gitattributes_content)

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
                    'PRISM: Nested structure conversion (initialize "derivatives")',
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
            self.assertIn("*.json annex.largefiles=nothing", gitattributes_content)
            self.assertIn("*.tsv annex.largefiles=nothing", gitattributes_content)

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
                with patch(
                    "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                    return_value=False,
                ):
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
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(["/usr/bin/datalad", "create", "-d", ".", "--force", "derivatives"], commands)
        self.assertIn(
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'PRISM: Nested structure conversion (initialize "derivatives")',
            ],
            commands,
        )
        self.assertIn(["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-001"], commands)
        self.assertIn(
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'PRISM: Nested structure conversion (initialize "sub-001")',
            ],
            commands,
        )
        self.assertIn(["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-002"], commands)
        self.assertIn(
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'PRISM: Nested structure conversion (initialize "sub-002")',
            ],
            commands,
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
                with patch(
                    "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                    return_value=False,
                ):
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
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-172"], commands)

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which")
    def test_create_datalad_dataset_keeps_existing_datalad_root_idempotent(
        self,
        mock_which,
        mock_run,
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "dataset"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)

            result = manager._create_datalad_dataset(project_path, enabled=False)

        self.assertTrue(result.get("initialized"), result)
        self.assertIn("already tracked by DataLad", result.get("message", ""))
        mock_run.assert_not_called()

    def test_inspect_remote_dataset_source_marks_openneuro_github_as_datalad(self):
        manager = ProjectManager()

        result = manager.inspect_remote_dataset_source(
            "https://github.com/OpenNeuroDatasets/ds003612.git"
        )

        self.assertTrue(result.get("valid"), result)
        self.assertEqual(result.get("remote_kind"), "openneuro")
        self.assertTrue(result.get("requires_datalad"), result)
        self.assertEqual(result.get("clone_method"), "datalad_install")

    def test_inspect_remote_dataset_source_marks_generic_git_as_git_clone(self):
        manager = ProjectManager()

        result = manager.inspect_remote_dataset_source(
            "https://github.com/example/dataset.git"
        )

        self.assertTrue(result.get("valid"), result)
        self.assertEqual(result.get("remote_kind"), "git")
        self.assertFalse(result.get("requires_datalad"), result)
        self.assertEqual(result.get("clone_method"), "git_clone")

    @patch("src.project_manager.ProjectManager._run_datalad_save")
    @patch("src.project_manager.ProjectManager._create_nested_subdatasets")
    @patch("src.project_manager.shutil.which")
    @patch("src.project_manager.subprocess.run")
    def test_init_on_existing_bids_installs_openneuro_remote_with_datalad(
        self,
        mock_run,
        mock_which,
        mock_create_nested,
        mock_run_datalad_save,
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: {
            "datalad": "/usr/bin/datalad",
            "git-annex": "/usr/bin/git-annex",
        }.get(executable)
        mock_create_nested.return_value = {
            "subdatasets_created": [],
            "subdatasets_existing": [],
            "subdataset_failures": [],
            "subdatasets_skipped": [],
            "subdatasets_total_count": 0,
            "subdatasets_registered_count": 0,
            "subdatasets_remaining_count": 0,
            "subject_datasets_created": [],
            "subject_datasets_existing": [],
            "subject_dataset_failures": [],
        }
        mock_run_datalad_save.return_value = {
            "available": True,
            "saved": True,
            "message": 'DataLad saved changes with message "Initialize PRISM on existing BIDS dataset".',
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "ds003612"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if normalized[:3] == ["/usr/bin/datalad", "install", "-s"]:
                    destination_path = Path(normalized[4])
                    destination_path.mkdir(parents=True, exist_ok=True)
                    (destination_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (destination_path / ".git").mkdir(parents=True, exist_ok=True)
                    (destination_path / "dataset_description.json").write_text(
                        "{}\n",
                        encoding="utf-8",
                    )
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized == [
                    "/usr/bin/datalad",
                    "-C",
                    str(project_path),
                    "get",
                    "-n",
                    "-r",
                    ".",
                ]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            mock_run.side_effect = _fake_run

            result = manager.init_on_existing_bids(
                str(project_path),
                {
                    "remote_url": "https://github.com/OpenNeuroDatasets/ds003612.git",
                    "use_datalad": False,
                },
            )

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result.get("source", {}).get("clone_method"), "datalad_install")
        self.assertIn("OpenNeuro", result.get("source", {}).get("message", ""))
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(
            [
                "/usr/bin/datalad",
                "install",
                "-s",
                "https://github.com/OpenNeuroDatasets/ds003612.git",
                str(project_path),
            ],
            commands,
        )
        self.assertIn(
            [
                "/usr/bin/datalad",
                "-C",
                str(project_path),
                "get",
                "-n",
                "-r",
                ".",
            ],
            commands,
        )
        self.assertNotIn(["/usr/bin/datalad", "create", "--force"], commands)

    @patch("src.project_manager.ProjectManager._run_datalad_save")
    @patch("src.project_manager.ProjectManager._create_nested_subdatasets")
    @patch("src.project_manager.shutil.which")
    @patch("src.project_manager.subprocess.run")
    def test_init_on_existing_bids_merges_into_preexisting_bidsignore(
        self,
        mock_run,
        mock_which,
        mock_create_nested,
        mock_run_datalad_save,
    ):
        """An OpenNeuro source that already ships its own .bidsignore (missing
        project.json/.prismrc.json) must have those PRISM rules merged in,
        instead of PRISM skipping the file entirely."""
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: {
            "datalad": "/usr/bin/datalad",
            "git-annex": "/usr/bin/git-annex",
        }.get(executable)
        mock_create_nested.return_value = {
            "subdatasets_created": [],
            "subdatasets_existing": [],
            "subdataset_failures": [],
            "subdatasets_skipped": [],
            "subdatasets_total_count": 0,
            "subdatasets_registered_count": 0,
            "subdatasets_remaining_count": 0,
            "subject_datasets_created": [],
            "subject_datasets_existing": [],
            "subject_dataset_failures": [],
        }
        mock_run_datalad_save.return_value = {
            "available": True,
            "saved": True,
            "message": 'DataLad saved changes with message "Initialize PRISM on existing BIDS dataset".',
        }

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "ds003612"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if normalized[:3] == ["/usr/bin/datalad", "install", "-s"]:
                    destination_path = Path(normalized[4])
                    destination_path.mkdir(parents=True, exist_ok=True)
                    (destination_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (destination_path / ".git").mkdir(parents=True, exist_ok=True)
                    (destination_path / "dataset_description.json").write_text(
                        "{}\n",
                        encoding="utf-8",
                    )
                    # Simulate a real OpenNeuro dataset that ships its own
                    # .bidsignore (without any PRISM-specific rules).
                    (destination_path / ".bidsignore").write_text(
                        "derivatives/\n",
                        encoding="utf-8",
                    )
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized == [
                    "/usr/bin/datalad",
                    "-C",
                    str(project_path),
                    "get",
                    "-n",
                    "-r",
                    ".",
                ]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            mock_run.side_effect = _fake_run

            result = manager.init_on_existing_bids(
                str(project_path),
                {
                    "remote_url": "https://github.com/OpenNeuroDatasets/ds003612.git",
                    "use_datalad": False,
                },
            )

            self.assertTrue(result.get("success"), result)
            bidsignore_content = (project_path / ".bidsignore").read_text(
                encoding="utf-8"
            )
            self.assertIn("derivatives/", bidsignore_content)
            self.assertIn("project.json", bidsignore_content)
            self.assertIn(".prismrc.json", bidsignore_content)

    @patch("src.project_manager.subprocess.run")
    def test_init_on_existing_bids_clones_generic_remote_with_git(self, mock_run):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo-remote"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if normalized[:2] == ["git", "clone"]:
                    destination_path = Path(normalized[3])
                    destination_path.mkdir(parents=True, exist_ok=True)
                    (destination_path / ".git").mkdir(parents=True, exist_ok=True)
                    (destination_path / "dataset_description.json").write_text(
                        "{}\n",
                        encoding="utf-8",
                    )
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            mock_run.side_effect = _fake_run

            result = manager.init_on_existing_bids(
                str(project_path),
                {
                    "remote_url": "https://github.com/example/dataset.git",
                    "use_datalad": False,
                },
            )

            self.assertTrue((project_path / "project.json").exists())

        self.assertTrue(result.get("success"), result)
        self.assertEqual(result.get("source", {}).get("clone_method"), "git_clone")

    @patch("src.project_manager.subprocess.run")
    @patch(
        "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
        return_value=False,
    )
    @patch(
        "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
        return_value=False,
    )
    @patch("src.project_manager.shutil.which")
    def test_create_nested_subdatasets_can_limit_repairs_to_one_per_call(
        self,
        mock_which,
        _mock_parent_tracks,
        _mock_parent_has_staged_deletions,
        mock_run,
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

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_get_datalad_status_openneuro_remote_uses_registered_topology_only(
        self, _mock_which
    ):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-002").mkdir(parents=True, exist_ok=True)

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths",
                return_value={"sub-001"},
            ):
                with patch(
                    "src.project_manager.ProjectManager._is_openneuro_remote_dataset",
                    return_value=True,
                ):
                    result = manager.get_datalad_status(project_path)

        self.assertEqual(result.get("subdatasets_total_count"), 1)
        self.assertEqual(result.get("subdatasets_registered_count"), 1)
        self.assertEqual(result.get("subdatasets_remaining_count"), 0)
        self.assertEqual(result.get("subdatasets_progress_percent"), 100)
        self.assertEqual(result.get("next_missing_subdataset"), "")
        self.assertEqual(result.get("subdatasets_topology_mode"), "openneuro-registered")
        self.assertIn("OpenNeuro nested subdatasets", result.get("message", ""))
        self.assertIn("not the subject count", result.get("message", ""))

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
        self.assertIn("uv tool install datalad git-annex", result.get("message", ""))

    @patch("src.project_manager.shutil.which")
    def test_get_datalad_status_reports_missing_text_policy(self, mock_which):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / ".gitattributes").write_text(
                "*.json annex.largefiles=nothing\n", encoding="utf-8"
            )
            (project_path / "sub-001" / ".datalad").mkdir(parents=True, exist_ok=True)

            with patch.object(
                ProjectManager,
                "_summarize_nested_subdatasets",
                return_value={
                    "subdatasets_total_count": 1,
                    "subdatasets_registered_count": 1,
                    "subdatasets_remaining_count": 0,
                    "subdatasets_progress_percent": 100,
                    "next_missing_subdataset": "",
                    "subdatasets_topology_mode": "local-expected",
                },
            ):
                result = manager.get_datalad_status(project_path)

        self.assertTrue(result.get("enabled"))
        self.assertFalse(result.get("text_policy_complete"))
        self.assertEqual(result.get("text_policy_missing_count"), 2)
        self.assertIn("Text-file Git tracking policy is missing", result.get("message", ""))

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
        self.assertTrue(result.get("datalad", {}).get("gitattributes_policy_updated"))
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(
            ["/usr/bin/datalad", "save", "-r", "-m", "Checkpoint metadata updates"],
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
            gitattributes_content = (project_path / ".gitattributes").read_text(
                encoding="utf-8"
            )

        self.assertTrue(result.get("success"), result)
        self.assertIn("already tracked by DataLad", result.get("message", ""))
        self.assertIn("*.json annex.largefiles=nothing", gitattributes_content)
        self.assertIn("*.tsv annex.largefiles=nothing", gitattributes_content)

    def test_editable_metadata_policy_applies_to_nested_datalad_subdatasets(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001" / ".datalad").mkdir(parents=True, exist_ok=True)

            updated = manager._ensure_datalad_editable_metadata_policy(
                project_path,
            )

            self.assertTrue(updated)
            root_gitattributes = (project_path / ".gitattributes").read_text(
                encoding="utf-8"
            )
            nested_gitattributes = (
                project_path / "sub-001" / ".gitattributes"
            ).read_text(encoding="utf-8")

            self.assertIn("*.json annex.largefiles=nothing", root_gitattributes)
            self.assertIn("*.json annex.largefiles=nothing", nested_gitattributes)
            self.assertIn("*.tsv annex.largefiles=nothing", nested_gitattributes)

            updated_second = manager._ensure_datalad_editable_metadata_policy(
                project_path,
            )
            self.assertFalse(updated_second)

    def test_iter_datalad_dataset_roots_uses_gitmodules_paths(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-001").mkdir(parents=True, exist_ok=True)
            (project_path / "derivatives").mkdir(parents=True, exist_ok=True)
            (project_path / ".gitmodules").write_text(
                """
[submodule \"sub-001\"]
	path = sub-001
	url = ./sub-001
[submodule \"derivatives\"]
	path = derivatives
	url = ./derivatives
""".strip()
                + "\n",
                encoding="utf-8",
            )

            roots = manager._iter_datalad_dataset_roots(project_path)
            rel_roots = [
                "." if root == project_path else root.relative_to(project_path).as_posix()
                for root in roots
            ]

        self.assertIn(".", rel_roots)
        self.assertIn("sub-001", rel_roots)
        self.assertIn("derivatives", rel_roots)

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
                with patch(
                    "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                    return_value=False,
                ):
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
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-172"], commands)
        self.assertIn(
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'PRISM: Nested structure conversion (initialize "sub-172")',
            ],
            commands,
        )
        self.assertIn(["/usr/bin/datalad", "save", "-m", "Enable DataLad for PRISM project"], commands)

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
                with patch(
                    "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                    return_value=False,
                ):
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
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(["/usr/bin/datalad", "create", "-d", ".", "--force", "derivatives"], commands)
        self.assertIn(
            [
                "/usr/bin/datalad",
                "save",
                "-m",
                'PRISM: Nested structure conversion (initialize "derivatives")',
            ],
            commands,
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
                    side_effect=[True, True, False],
                ):
                    with patch(
                        "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                        return_value=False,
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
                'PRISM: Converting data into nested PRISM-structure (prepare parent untracking "derivatives")',
            ],
            commands,
        )
        self.assertIn(
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "derivatives"],
            commands,
        )

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_continues_when_post_save_leaves_staged_parent_deletions(
        self, mock_which, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-020").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-020" / "file.txt").write_text("demo\n", encoding="utf-8")

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                with patch(
                    "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
                    side_effect=[True, True, False, False],
                ):
                    with patch(
                        "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                        side_effect=[False, True, False],
                    ):
                        mock_registered_paths.side_effect = _registered_nested_path_sequence(
                            set(),
                            set(),
                            {"sub-020"},
                            {"sub-020"},
                        )
                        result = manager.enable_datalad_for_project(project_path)

            self.assertTrue((project_path / "sub-020" / "file.txt").exists())
            self.assertFalse((project_path / ".prism-datalad-stage-sub-020").exists())

        self.assertTrue(result.get("success"), result)
        self.assertIn("Added 1 nested subdataset", result.get("message", ""))
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertIn(
            ["git", "rm", "--cached", "-r", "--", "sub-020"],
            commands,
        )
        self.assertIn(
            [
                "/usr/bin/datalad",
                "save",
                "--updated",
                "-m",
                'PRISM: Converting data into nested PRISM-structure (prepare parent untracking "sub-020")',
            ],
            commands,
        )
        self.assertIn(
            [
                "git",
                "commit",
                "-m",
                'PRISM: Converting data into nested PRISM-structure (prepare parent untracking "sub-020")',
                "--",
                "sub-020",
            ],
            commands,
        )
        self.assertIn(
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-020"],
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
                    side_effect=[True, True, False],
                ):
                    with patch(
                        "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                        return_value=False,
                    ):
                        result = manager.enable_datalad_for_project(project_path)

            self.assertTrue((project_path / "derivatives" / "file.txt").exists())
            self.assertFalse((project_path / ".prism-datalad-stage-derivatives").exists())

        self.assertTrue(result.get("success"), result)
        self.assertIn("create nested dataset failed", result.get("message", ""))

    @patch("src.project_manager.subprocess.run")
    @patch("src.project_manager.shutil.which")
    def test_enable_datalad_for_project_resumes_from_staged_parent_deletions(
        self, mock_which, mock_run
    ):
        manager = ProjectManager()
        mock_which.side_effect = lambda executable: f"/usr/bin/{executable}"
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-013").mkdir(parents=True, exist_ok=True)
            (project_path / "sub-013" / "file.txt").write_text("demo\n", encoding="utf-8")

            with patch(
                "src.project_manager.ProjectManager._get_registered_nested_dataset_paths"
            ) as mock_registered_paths:
                with patch(
                    "src.project_manager.ProjectManager._parent_tracks_nested_dataset_path",
                    return_value=False,
                ):
                    with patch(
                        "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                        side_effect=[True, True, False],
                    ):
                        mock_registered_paths.side_effect = _registered_nested_path_sequence(
                            set(),
                            set(),
                            {"sub-013"},
                            {"sub-013"},
                        )
                        result = manager.enable_datalad_for_project(project_path)

        self.assertTrue(result.get("success"), result)
        self.assertIn("Added 1 nested subdataset", result.get("message", ""))
        commands = [call.args[0] for call in mock_run.call_args_list]
        self.assertNotIn(["git", "rm", "--cached", "-r", "--", "sub-013"], commands)
        self.assertNotIn(
            [
                "/usr/bin/datalad",
                "save",
                "--updated",
                "-m",
                'PRISM: Converting data into nested PRISM-structure (prepare parent untracking "sub-013")',
            ],
            commands,
        )
        self.assertIn(
            [
                "git",
                "commit",
                "-m",
                'PRISM: Converting data into nested PRISM-structure (prepare parent untracking "sub-013")',
                "--",
                "sub-013",
            ],
            commands,
        )
        self.assertIn(
            ["/usr/bin/datalad", "create", "-d", ".", "--force", "sub-013"],
            commands,
        )

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
                    side_effect=[True, True, True],
                ):
                    with patch(
                        "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                        return_value=False,
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
                'PRISM: Converting data into nested PRISM-structure (prepare parent untracking "sub-035")',
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
                    side_effect=[True, True, False],
                ):
                    with patch(
                        "src.project_manager.ProjectManager._parent_has_staged_nested_dataset_deletions",
                        return_value=False,
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
            exported_bidsignore = output_path / ".bidsignore"
            self.assertTrue(exported_bidsignore.exists())
            bidsignore_text = exported_bidsignore.read_text(encoding="utf-8")
            self.assertIn("project.json", bidsignore_text)
            self.assertIn("survey/", bidsignore_text)

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_export_project_to_plain_folder_preserves_existing_bidsignore_rules(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
            (project_path / ".bidsignore").write_text("*.log\n", encoding="utf-8")

            subject_dir = project_path / "sub-001" / "survey"
            subject_dir.mkdir(parents=True, exist_ok=True)
            (subject_dir / "sub-001_task-demo_survey.tsv").write_text(
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
            bidsignore_path = output_path / ".bidsignore"
            self.assertTrue(bidsignore_path.exists())

            bidsignore_text = bidsignore_path.read_text(encoding="utf-8")
            self.assertIn("*.log", bidsignore_text)
            self.assertIn("survey/", bidsignore_text)
            self.assertIn("project.json", bidsignore_text)

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

    def test_export_project_to_plain_folder_honors_scope_filters(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
            (project_path / "analysis").mkdir(parents=True, exist_ok=True)
            (project_path / "analysis" / "qc.txt").write_text("qc\n", encoding="utf-8")

            included_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "anat"
                / "sub-001_ses-1_T1w.nii.gz"
            )
            included_file.parent.mkdir(parents=True, exist_ok=True)
            included_file.write_bytes(b"nifti")

            excluded_file = (
                project_path
                / "sub-001"
                / "ses-3"
                / "dwi"
                / "sub-001_ses-3_acq-1k20_dwi.nii.gz"
            )
            excluded_file.parent.mkdir(parents=True, exist_ok=True)

            try:
                excluded_file.symlink_to(project_path / "missing_dwi_payload.nii.gz")
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            export_root = Path(tmp) / "exports"
            result = manager.export_project_to_plain_folder(
                project_path,
                output_root=export_root,
                include_analysis=False,
                exclude_sessions={"ses-3"},
                exclude_modalities={"dwi"},
            )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertTrue(
                (
                    output_path
                    / "sub-001"
                    / "ses-1"
                    / "anat"
                    / "sub-001_ses-1_T1w.nii.gz"
                ).exists()
            )
            self.assertFalse((output_path / "sub-001" / "ses-3").exists())
            self.assertFalse((output_path / "analysis").exists())

    def test_export_project_to_plain_folder_excludes_anat_suffix_labels(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            t1_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "anat"
                / "sub-001_ses-1_T1w.nii.gz"
            )
            t2_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "anat"
                / "sub-001_ses-1_T2w.nii.gz"
            )
            t1_file.parent.mkdir(parents=True, exist_ok=True)
            t1_file.write_bytes(b"t1")
            t2_file.write_bytes(b"t2")

            export_root = Path(tmp) / "exports"
            result = manager.export_project_to_plain_folder(
                project_path,
                output_root=export_root,
                exclude_acq={"anat": {"T1w"}},
            )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertFalse((output_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_T1w.nii.gz").exists())
            self.assertTrue((output_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_T2w.nii.gz").exists())

    def test_export_project_to_plain_folder_excludes_anat_mpm_suffix_with_acq_entities(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            mpm_file = (
                project_path
                / "sub-147"
                / "ses-1"
                / "anat"
                / "sub-147_ses-1_acq-PDw_echo-5_flip-4_mt-off_MPM.nii.gz"
            )
            t1_file = (
                project_path
                / "sub-147"
                / "ses-1"
                / "anat"
                / "sub-147_ses-1_acq-PDw_T1w.nii.gz"
            )
            mpm_file.parent.mkdir(parents=True, exist_ok=True)
            mpm_file.write_bytes(b"mpm")
            t1_file.write_bytes(b"t1")

            export_root = Path(tmp) / "exports"
            result = manager.export_project_to_plain_folder(
                project_path,
                output_root=export_root,
                exclude_acq={"anat": {"PDw-MPM"}},
            )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertFalse(
                (
                    output_path
                    / "sub-147"
                    / "ses-1"
                    / "anat"
                    / "sub-147_ses-1_acq-PDw_echo-5_flip-4_mt-off_MPM.nii.gz"
                ).exists()
            )
            self.assertTrue(
                (
                    output_path
                    / "sub-147"
                    / "ses-1"
                    / "anat"
                    / "sub-147_ses-1_acq-PDw_T1w.nii.gz"
                ).exists()
            )

    def test_export_project_to_plain_folder_excludes_dwi_suffix_labels(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            dwi_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "dwi"
                / "sub-001_ses-1_acq-shell1_dwi.nii.gz"
            )
            sbref_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "dwi"
                / "sub-001_ses-1_sbref.nii.gz"
            )
            dwi_file.parent.mkdir(parents=True, exist_ok=True)
            dwi_file.write_bytes(b"dwi")
            sbref_file.write_bytes(b"sbref")

            export_root = Path(tmp) / "exports"
            result = manager.export_project_to_plain_folder(
                project_path,
                output_root=export_root,
                exclude_acq={"dwi": {"sbref"}},
            )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertTrue((output_path / "sub-001" / "ses-1" / "dwi" / "sub-001_ses-1_acq-shell1_dwi.nii.gz").exists())
            self.assertFalse((output_path / "sub-001" / "ses-1" / "dwi" / "sub-001_ses-1_sbref.nii.gz").exists())

    def test_export_project_to_plain_folder_scrubs_sensitive_mri_json_tags(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            sidecar_path = (
                project_path
                / "sub-003"
                / "ses-1"
                / "anat"
                / "sub-003_ses-1_acq-mprage_T1w.json"
            )
            sidecar_path.parent.mkdir(parents=True, exist_ok=True)
            sidecar_path.write_text(
                json.dumps(
                    {
                        "Manufacturer": "Siemens",
                        "StationName": "AWP175956",
                        "DeviceSerialNumber": "175956",
                        "AcquisitionDateTime": "2023-04-19T09:06:20.070000",
                        "EchoTime": 0.00206,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            export_root = Path(tmp) / "exports"
            result = manager.export_project_to_plain_folder(
                project_path,
                output_root=export_root,
                scrub_mri_json=True,
            )

            self.assertTrue(result.get("success"), result)
            output_sidecar = (
                Path(result["output_path"])
                / "sub-003"
                / "ses-1"
                / "anat"
                / "sub-003_ses-1_acq-mprage_T1w.json"
            )
            self.assertTrue(output_sidecar.exists())
            scrubbed_payload = json.loads(output_sidecar.read_text(encoding="utf-8"))
            self.assertNotIn("Manufacturer", scrubbed_payload)
            self.assertNotIn("StationName", scrubbed_payload)
            self.assertNotIn("DeviceSerialNumber", scrubbed_payload)
            self.assertNotIn("AcquisitionDateTime", scrubbed_payload)
            self.assertEqual(scrubbed_payload.get("EchoTime"), 0.00206)
            self.assertGreaterEqual(int(result.get("scrubbed_mri_json_files") or 0), 1)
            self.assertGreaterEqual(int(result.get("scrubbed_mri_json_fields") or 0), 1)

    def test_export_project_to_plain_folder_skips_missing_annex_content_with_warning(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)

            system_file = project_path / "sub-001" / "ses-1" / ".DS_Store"
            system_file.parent.mkdir(parents=True, exist_ok=True)
            missing_system_target = project_path / "missing_system_payload"

            missing_annex_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "anat"
                / "sub-001_ses-1_acq-T1w_echo-1_mpm.nii.gz"
            )
            missing_annex_file.parent.mkdir(parents=True, exist_ok=True)
            missing_annex_target = (
                project_path
                / ".git"
                / "annex"
                / "objects"
                / "missing_annex_payload.nii.gz"
            )

            kept_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "anat"
                / "sub-001_ses-1_T1w.nii.gz"
            )
            kept_file.write_bytes(b"nifti")

            try:
                system_file.symlink_to(missing_system_target)
                missing_annex_file.symlink_to(missing_annex_target)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            export_root = Path(tmp) / "exports"
            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                result = manager.export_project_to_plain_folder(
                    project_path,
                    output_root=export_root,
                )

            self.assertTrue(result.get("success"), result)
            self.assertTrue(result.get("partial_export"), result)
            self.assertEqual(result.get("missing_files_count"), 1)
            self.assertIn("datalad get -r .", result.get("warning", ""))

            missing_preview = result.get("missing_files_preview") or []
            self.assertEqual(len(missing_preview), 1)
            self.assertIn(
                "sub-001_ses-1_acq-T1w_echo-1_mpm.nii.gz",
                str(missing_preview[0]),
            )
            self.assertFalse(str(missing_preview[0]).startswith("/"))
            self.assertNotIn(".DS_Store", "\n".join(str(value) for value in missing_preview))
            self.assertEqual(
                result.get("missing_files_preview_root"),
                str(project_path),
            )

            output_path = Path(result["output_path"])
            self.assertTrue((output_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_T1w.nii.gz").exists())
            self.assertFalse((output_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_acq-T1w_echo-1_mpm.nii.gz").exists())
            self.assertFalse((output_path / "sub-001" / "ses-1" / ".DS_Store").exists())

    def test_export_project_to_plain_folder_materializes_via_temporary_datalad_clone(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (clone_path / ".git").mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
                    clone_file = clone_path / "sub-001" / "anat" / "sub-001_T1w.nii.gz"
                    clone_file.parent.mkdir(parents=True, exist_ok=True)
                    clone_file.write_bytes(b"nifti")
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[:4] == ["/usr/bin/datalad", "get", "--on-failure", "ignore"]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/git-annex" and normalized[1] == "unlock":
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch(
                    "src.project_manager.tempfile.mkdtemp",
                    return_value=str(materialization_workspace),
                ) as mock_mkdtemp:
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run) as mock_run:
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                        )

            self.assertTrue(result.get("success"), result)
            self.assertTrue(result.get("materialized_export"), result)
            output_path = Path(result["output_path"])
            self.assertTrue((output_path / "dataset_description.json").exists())
            self.assertTrue((output_path / "sub-001" / "anat" / "sub-001_T1w.nii.gz").exists())
            self.assertFalse((output_path / ".git").exists())
            self.assertFalse(materialization_workspace.exists())
            temp_dir = mock_mkdtemp.call_args.kwargs.get("dir")
            self.assertIsNotNone(temp_dir)
            self.assertEqual(Path(str(temp_dir)).resolve(), export_root.resolve())
            self.assertTrue(
                str(mock_mkdtemp.call_args.kwargs.get("prefix", "")).startswith(
                    ".prism-folder-export-"
                )
            )

            commands = [" ".join(str(part) for part in call.args[0]) for call in mock_run.call_args_list]
            self.assertTrue(any(command.startswith("/usr/bin/datalad clone ") for command in commands), commands)
            self.assertTrue(any(command.startswith("/usr/bin/datalad get --on-failure ignore ") for command in commands), commands)
            self.assertTrue(any("sub-001/anat/sub-001_T1w.nii.gz" in command for command in commands if command.startswith("/usr/bin/datalad get ")), commands)
            self.assertTrue(any(command.startswith("/usr/bin/git-annex unlock ") for command in commands), commands)

    def test_export_project_to_plain_folder_deletes_read_only_temporary_workspace(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (clone_path / ".git").mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

                    clone_dir = clone_path / "sub-001" / "anat"
                    clone_dir.mkdir(parents=True, exist_ok=True)
                    clone_file = clone_dir / "sub-001_T1w.nii.gz"
                    clone_file.write_bytes(b"nifti")

                    # Simulate read-only annex payloads that used to survive cleanup.
                    os.chmod(clone_file, stat.S_IRUSR)
                    os.chmod(clone_dir, stat.S_IRUSR | stat.S_IXUSR)
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[:4] == ["/usr/bin/datalad", "get", "--on-failure", "ignore"]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/git-annex" and normalized[1] == "unlock":
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch(
                    "src.project_manager.tempfile.mkdtemp",
                    return_value=str(materialization_workspace),
                ):
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run):
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                        )

            self.assertTrue(result.get("success"), result)
            self.assertFalse(materialization_workspace.exists())

    def test_export_project_to_plain_folder_materialize_recurses_subject_scope_when_clone_has_no_subject_files(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **kwargs):
                normalized = [str(part) for part in command]
                cwd = Path(str(kwargs.get("cwd"))) if kwargs.get("cwd") else None

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (clone_path / ".git").mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
                    # Simulate a clone layout where subject folders exist but files are not yet visible.
                    (clone_path / "sub-001" / "ses-2" / "anat").mkdir(parents=True, exist_ok=True)
                    return subprocess.CompletedProcess(command, 0, "", "")

                if (
                    len(normalized) >= 5
                    and normalized[0] == "/usr/bin/datalad"
                    and normalized[1] == "get"
                    and "-r" in normalized
                    and "--on-failure" in normalized
                    and "ignore" in normalized
                ):
                    if cwd is not None:
                        subject_file = cwd / "sub-001" / "ses-2" / "anat" / "sub-001_ses-2_T1w.nii.gz"
                        subject_file.parent.mkdir(parents=True, exist_ok=True)
                        subject_file.write_bytes(b"nifti")
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[:4] == ["/usr/bin/datalad", "get", "--on-failure", "ignore"]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/git-annex" and normalized[1] == "unlock":
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch(
                    "src.project_manager.tempfile.mkdtemp",
                    return_value=str(materialization_workspace),
                ):
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run) as mock_run:
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                            exclude_sessions={"ses-1", "ses-3"},
                        )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertTrue(
                (output_path / "sub-001" / "ses-2" / "anat" / "sub-001_ses-2_T1w.nii.gz").exists()
            )

            commands = [" ".join(str(part) for part in call.args[0]) for call in mock_run.call_args_list]
            self.assertTrue(
                any(
                    command.startswith("/usr/bin/datalad get -r -n --on-failure ignore ")
                    or command.startswith("/usr/bin/datalad get -r --on-failure ignore ")
                    for command in commands
                ),
                commands,
            )
            self.assertTrue(
                any(
                    command.startswith("/usr/bin/datalad get --on-failure ignore ")
                    and "sub-001/ses-2/anat/sub-001_ses-2_T1w.nii.gz" in command
                    for command in commands
                ),
                commands,
            )

    def test_export_project_to_plain_folder_materialize_fallback_recurses_with_data_when_subject_targets_missing(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **kwargs):
                normalized = [str(part) for part in command]
                cwd = Path(str(kwargs.get("cwd"))) if kwargs.get("cwd") else None

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (clone_path / ".git").mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
                    # Subdataset directories are present, but no subject files are discoverable yet.
                    (clone_path / "sub-001" / "ses-2" / "anat").mkdir(parents=True, exist_ok=True)
                    # Keep at least one top-level file so target collection is not empty.
                    (clone_path / "task-rest_survey.json").write_text("{}\n", encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, "", "")

                if (
                    len(normalized) >= 3
                    and normalized[0] == "/usr/bin/datalad"
                    and normalized[1] == "get"
                    and "-r" in normalized
                    and "-n" in normalized
                ):
                    # Metadata recursion does not expose subject file entries in this scenario.
                    return subprocess.CompletedProcess(command, 0, "", "")

                if (
                    len(normalized) >= 5
                    and normalized[0] == "/usr/bin/datalad"
                    and normalized[1] == "get"
                    and "-r" in normalized
                    and "--on-failure" in normalized
                    and "ignore" in normalized
                    and "-n" not in normalized
                ):
                    # Fallback recursive data get makes subject files available for copy.
                    if cwd is not None:
                        subject_file = cwd / "sub-001" / "ses-2" / "anat" / "sub-001_ses-2_T1w.nii.gz"
                        subject_file.parent.mkdir(parents=True, exist_ok=True)
                        subject_file.write_bytes(b"nifti")
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[:4] == ["/usr/bin/datalad", "get", "--on-failure", "ignore"]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/git-annex" and normalized[1] == "unlock":
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch(
                    "src.project_manager.tempfile.mkdtemp",
                    return_value=str(materialization_workspace),
                ):
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run) as mock_run:
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                            exclude_sessions={"ses-1", "ses-3"},
                        )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertTrue(
                (output_path / "sub-001" / "ses-2" / "anat" / "sub-001_ses-2_T1w.nii.gz").exists()
            )

            commands = [" ".join(str(part) for part in call.args[0]) for call in mock_run.call_args_list]
            self.assertTrue(
                any(
                    command.startswith("/usr/bin/datalad get -r -n --on-failure ignore ")
                    or command.startswith("/usr/bin/datalad get -r --on-failure ignore ")
                    for command in commands
                ),
                commands,
            )
            self.assertTrue(
                any(
                    command.startswith("/usr/bin/datalad get -r --on-failure ignore ")
                    and "sub-001/ses-2/anat" in command
                    for command in commands
                ),
                commands,
            )

    def test_export_project_to_plain_folder_materialize_falls_back_to_source_when_clone_has_no_subject_files(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
            source_subject_file = project_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_T1w.nii.gz"
            source_subject_file.parent.mkdir(parents=True, exist_ok=True)
            source_subject_file.write_bytes(b"nifti")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (clone_path / ".git").mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
                    # Keep subject scope structure but do not expose subject files in clone working tree.
                    (clone_path / "sub-001" / "ses-1" / "anat").mkdir(parents=True, exist_ok=True)
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[0:2] == ["/usr/bin/datalad", "get"]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[0:2] == ["/usr/bin/git-annex", "unlock"]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch(
                    "src.project_manager.tempfile.mkdtemp",
                    return_value=str(materialization_workspace),
                ):
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run):
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                        )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertTrue(
                (output_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_T1w.nii.gz").exists()
            )
            warnings = result.get("materialization_warnings") or []
            self.assertTrue(
                any(
                    "Temporary clone did not expose selected subject files" in warning
                    or "retrying scoped copy directly from source project files" in warning
                    for warning in warnings
                ),
                warnings,
            )

    def test_export_project_to_plain_folder_materialize_gets_only_selected_scope_targets(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (clone_path / ".git").mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
                    (clone_path / "task-ads_survey.json").write_text("{}\n", encoding="utf-8")

                    anat_file = clone_path / "sub-001" / "anat" / "sub-001_T1w.nii.gz"
                    anat_file.parent.mkdir(parents=True, exist_ok=True)
                    anat_file.write_bytes(b"anat")

                    func_file = clone_path / "sub-001" / "func" / "sub-001_task-rest_bold.nii.gz"
                    func_file.parent.mkdir(parents=True, exist_ok=True)
                    func_file.write_bytes(b"func")
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[:4] == ["/usr/bin/datalad", "get", "--on-failure", "ignore"]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/git-annex" and normalized[1] == "unlock":
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch(
                    "src.project_manager.tempfile.mkdtemp",
                    return_value=str(materialization_workspace),
                ):
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run) as mock_run:
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                            exclude_modalities={"anat", "func"},
                        )

            self.assertTrue(result.get("success"), result)
            commands = [" ".join(str(part) for part in call.args[0]) for call in mock_run.call_args_list]
            datalad_get_commands = [
                command for command in commands if command.startswith("/usr/bin/datalad get ")
            ]
            self.assertTrue(datalad_get_commands, commands)
            self.assertTrue(any("task-ads_survey.json" in command for command in datalad_get_commands), datalad_get_commands)
            self.assertFalse(any("sub-001_T1w.nii.gz" in command for command in datalad_get_commands), datalad_get_commands)
            self.assertFalse(any("sub-001_task-rest_bold.nii.gz" in command for command in datalad_get_commands), datalad_get_commands)

    def test_export_project_to_plain_folder_materialize_recovers_missing_clone_files_from_source(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            source_file = project_path / "sub-001" / "anat" / "sub-001_T1w.nii.gz"
            source_file.parent.mkdir(parents=True, exist_ok=True)
            source_file.write_bytes(b"source-nifti")

            symlink_probe = Path(tmp) / "symlink_probe"
            try:
                symlink_probe.symlink_to(Path(tmp) / "missing_symlink_target")
                symlink_probe.unlink(missing_ok=True)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / ".datalad").mkdir(parents=True, exist_ok=True)
                    (clone_path / ".git").mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

                    clone_file = clone_path / "sub-001" / "anat" / "sub-001_T1w.nii.gz"
                    clone_file.parent.mkdir(parents=True, exist_ok=True)
                    clone_file.symlink_to(clone_path / "missing_annex_payload.nii.gz")
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[:4] == ["/usr/bin/datalad", "get", "--on-failure", "ignore"]:
                    return subprocess.CompletedProcess(command, 0, "", "")

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/git-annex" and normalized[1] == "unlock":
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch(
                    "src.project_manager.tempfile.mkdtemp",
                    return_value=str(materialization_workspace),
                ):
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run):
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                        )

            self.assertTrue(result.get("success"), result)
            self.assertTrue(result.get("materialized_export"), result)
            self.assertFalse(result.get("partial_export"), result)
            self.assertIsNone(result.get("missing_files_count"), result)
            warnings = result.get("materialization_warnings") or []
            self.assertTrue(
                any(
                    "Recovered 1 file(s) from the source project" in str(item)
                    or "Temporary clone did not expose selected subject files" in str(item)
                    for item in warnings
                ),
                warnings,
            )

            output_path = Path(result["output_path"])
            exported_file = output_path / "sub-001" / "anat" / "sub-001_T1w.nii.gz"
            self.assertTrue(exported_file.exists())
            self.assertEqual(exported_file.read_bytes(), b"source-nifti")
            self.assertFalse(materialization_workspace.exists())

    def test_preview_plain_folder_export_availability_reports_missing_annex_symlinks(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            missing_annex_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "anat"
                / "sub-001_ses-1_T1w.nii.gz"
            )
            missing_annex_file.parent.mkdir(parents=True, exist_ok=True)
            existing_file = (
                project_path
                / "sub-001"
                / "ses-1"
                / "func"
                / "sub-001_ses-1_task-rest_bold.nii.gz"
            )
            existing_file.parent.mkdir(parents=True, exist_ok=True)
            existing_file.write_bytes(b"nifti")

            try:
                missing_annex_file.symlink_to(project_path / "missing_payload.nii.gz")
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                result = manager.preview_plain_folder_export_availability(
                    project_path,
                    exclude_modalities={"func"},
                )

            self.assertTrue(result.get("success"), result)
            self.assertEqual(result.get("missing_files_count"), 1)
            self.assertEqual(
                result.get("missing_files_preview"),
                ["sub-001/ses-1/anat/sub-001_ses-1_T1w.nii.gz"],
            )
            self.assertEqual(result.get("missing_files_preview_root"), str(project_path))
            self.assertIn("datalad -C", str(result.get("hint_command", "")))

    def test_export_project_to_plain_folder_materialize_requires_datalad_executable(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": None,
                    "annex_executable": None,
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch("src.project_manager.shutil.which", return_value=None):
                    result = manager.export_project_to_plain_folder(
                        project_path,
                        materialize_annex_content=True,
                    )

        self.assertFalse(result.get("success"), result)
        self.assertIn("requires the datalad executable", result.get("error", ""))

    def test_export_project_to_plain_folder_materialize_get_failure_becomes_warning(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[:4] == ["/usr/bin/datalad", "get", "--on-failure", "ignore"]:
                    return subprocess.CompletedProcess(
                        command,
                        1,
                        "[INFO] Ensuring presence ...",
                        "",
                    )

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/git-annex" and normalized[1] == "unlock":
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch("src.project_manager.tempfile.mkdtemp", return_value=str(materialization_workspace)):
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run):
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                        )

            self.assertTrue(result.get("success"), result)
            self.assertTrue(result.get("materialized_export"), result)
            warnings = result.get("materialization_warnings") or []
            self.assertTrue(any("could not retrieve all selected export content" in str(item) for item in warnings), warnings)

    def test_export_project_to_plain_folder_materialize_get_unknown_flag_falls_back(self):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / ".datalad").mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            export_root = Path(tmp) / "exports"
            materialization_workspace = Path(tmp) / "materialized_workspace"

            def _fake_run(command, **_kwargs):
                normalized = [str(part) for part in command]
                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "clone":
                    clone_path = Path(normalized[-1])
                    clone_path.mkdir(parents=True, exist_ok=True)
                    (clone_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
                    return subprocess.CompletedProcess(command, 0, "", "")

                if normalized[:4] == ["/usr/bin/datalad", "get", "--on-failure", "ignore"]:
                    return subprocess.CompletedProcess(
                        command,
                        1,
                        "",
                        "[ERROR] unknown argument: --on-failure",
                    )

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/datalad" and normalized[1] == "get" and "--on-failure" not in normalized:
                    return subprocess.CompletedProcess(command, 0, "", "")

                if len(normalized) >= 2 and normalized[0] == "/usr/bin/git-annex" and normalized[1] == "unlock":
                    return subprocess.CompletedProcess(command, 0, "", "")

                return subprocess.CompletedProcess(command, 1, "", "unexpected command")

            with patch.object(
                manager,
                "get_datalad_status",
                return_value={
                    "enabled": True,
                    "available": True,
                    "executable": "/usr/bin/datalad",
                    "annex_executable": "/usr/bin/git-annex",
                    "message": "Current project is tracked by DataLad.",
                },
            ):
                with patch("src.project_manager.tempfile.mkdtemp", return_value=str(materialization_workspace)):
                    with patch("src.project_manager.subprocess.run", side_effect=_fake_run) as mock_run:
                        result = manager.export_project_to_plain_folder(
                            project_path,
                            output_root=export_root,
                            materialize_annex_content=True,
                        )

            self.assertTrue(result.get("success"), result)
            self.assertTrue(result.get("materialized_export"), result)
            self.assertFalse(result.get("materialization_warnings"), result)

            commands = [" ".join(str(part) for part in call.args[0]) for call in mock_run.call_args_list]
            self.assertTrue(any(command.startswith("/usr/bin/datalad get --on-failure ignore ") for command in commands), commands)
            self.assertTrue(
                any(
                    command.startswith("/usr/bin/datalad get ") and "--on-failure" not in command
                    for command in commands
                ),
                commands,
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

    def test_export_project_to_plain_folder_rejects_case_only_colliding_subject_dirs(self):
        """Regression guard: a source dataset can contain subject
        directories that differ only by case (e.g. created on a
        case-sensitive filesystem, or by an importer that predates the
        case-collision check at conversion time). Copying both onto a
        case-insensitive destination (default macOS/Windows) would
        silently merge one into the other mid-copy with no error — fail
        fast instead, before any copy starts.

        True co-existing case-variant directories can't be staged on this
        host's filesystem (the same reason production code needs this
        check at all), so this test fakes the directory listing rather
        than creating the directories for real."""
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            class _FakeDirEntry:
                def __init__(self, name: str) -> None:
                    self.name = name

                def is_dir(self) -> bool:
                    return True

            real_iterdir = Path.iterdir

            def _fake_iterdir(self):
                if self == project_path:
                    return iter([_FakeDirEntry("sub-Ab"), _FakeDirEntry("sub-ab")])
                return real_iterdir(self)

            with patch.object(Path, "iterdir", _fake_iterdir):
                result = manager.export_project_to_plain_folder(project_path)

            self.assertFalse(result.get("success"))
            self.assertIn("differ only by case", result.get("error", ""))
            self.assertFalse((project_path.parent / "demo_project_folder_export").exists())

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_export_project_to_plain_folder_exclude_subjects_filters_output(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            subj1_file = project_path / "sub-001" / "ses-1" / "anat" / "sub-001_ses-1_T1w.nii.gz"
            subj1_file.parent.mkdir(parents=True, exist_ok=True)
            subj1_file.write_bytes(b"nifti-1")

            subj2_file = project_path / "sub-002" / "ses-1" / "anat" / "sub-002_ses-1_T1w.nii.gz"
            subj2_file.parent.mkdir(parents=True, exist_ok=True)
            subj2_file.write_bytes(b"nifti-2")

            result = manager.export_project_to_plain_folder(
                project_path,
                exclude_subjects={"sub-002"},
            )

            self.assertTrue(result.get("success"), result)
            output_path = Path(result["output_path"])
            self.assertTrue((output_path / "sub-001").exists())
            self.assertFalse((output_path / "sub-002").exists())

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_export_project_to_plain_folder_excludes_sourcedata_by_default(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")
            (project_path / "sourcedata").mkdir(parents=True, exist_ok=True)
            (project_path / "sourcedata" / "raw.csv").write_text("a,b\n1,2\n", encoding="utf-8")

            default_result = manager.export_project_to_plain_folder(project_path)
            self.assertTrue(default_result.get("success"), default_result)
            default_output = Path(default_result["output_path"])
            self.assertFalse((default_output / "sourcedata").exists())

            included_result = manager.export_project_to_plain_folder(
                project_path,
                include_sourcedata=True,
            )
            self.assertTrue(included_result.get("success"), included_result)
            included_output = Path(included_result["output_path"])
            self.assertTrue((included_output / "sourcedata" / "raw.csv").exists())

    @patch("src.project_manager.shutil.which", return_value="/usr/bin/datalad")
    def test_export_project_to_plain_folder_cleans_stale_hidden_workspaces(self, _mock_which):
        manager = ProjectManager()

        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "demo_project"
            project_path.mkdir(parents=True, exist_ok=True)
            (project_path / "dataset_description.json").write_text("{}\n", encoding="utf-8")

            export_root = Path(tmp) / "exports"
            export_root.mkdir(parents=True, exist_ok=True)
            stale_workspace = export_root / ".prism-folder-export-old"
            stale_workspace.mkdir(parents=True, exist_ok=True)
            (stale_workspace / "payload.bin").write_bytes(b"stale")

            old_timestamp = time.time() - (2 * 60 * 60)
            os.utime(stale_workspace, (old_timestamp, old_timestamp))

            result = manager.export_project_to_plain_folder(
                project_path,
                output_root=export_root,
            )

            self.assertTrue(result.get("success"), result)
            self.assertFalse(stale_workspace.exists())


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
