import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.fernet import Fernet

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

from src.derivatives.apps_runner_compat import (  # noqa: E402
    validate_runner_config,
    inspect_runner_repo,
    build_compatibility_report,
    delete_remote_profile,
    get_remote_profile,
    list_apptainer_images,
    list_docker_tags,
    list_remote_profiles,
    load_app_help,
    pull_docker_image,
    prepare_project_runner_config,
    resolve_remote_passphrase,
    run_runner_with_project,
    save_remote_profile,
)


class TestPrismAppRunnerCompatibility(unittest.TestCase):
    def test_validate_runner_config_valid_minimal(self):
        config = {
            "common": {
                "bids_folder": "/data/bids",
                "output_folder": "/data/derivatives/fmriprep",
                "container_engine": "apptainer",
                "container": "/containers/fmriprep.sif",
            },
            "app": {"analysis_level": "participant"},
        }

        result = validate_runner_config(config)
        self.assertTrue(result["present"])
        self.assertEqual(result["errors"], [])

    def test_validate_runner_config_rejects_invalid_engine(self):
        config = {
            "common": {
                "bids_folder": "/data/bids",
                "output_folder": "/data/derivatives/out",
                "container_engine": "podman",
                "container": "example/image:latest",
            },
            "app": {},
        }

        result = validate_runner_config(config)
        self.assertTrue(
            any("Unsupported common.container_engine" in e for e in result["errors"])
        )

    def test_inspect_runner_repo_reports_missing_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            (repo / "scripts").mkdir(parents=True, exist_ok=True)
            (repo / "scripts" / "prism_runner.py").write_text(
                "# stub", encoding="utf-8"
            )

            result = inspect_runner_repo(str(repo))
            self.assertTrue(result["provided"])
            self.assertTrue(result["exists"])
            self.assertIn("prism_app_runner.py", result["missing_files"])
            self.assertIn("scripts/build_apptainer.sh", result["missing_files"])

    def test_build_report_includes_status_and_recommendations(self):
        config_json = """{
            "common": {
                "bids_folder": "/bids",
                "output_folder": "/tmp/not-derivatives",
                "container_engine": "apptainer",
                "container": "/containers/app.sif"
            },
            "app": {}
        }"""

        report = build_compatibility_report(config_json=config_json)
        self.assertIn(report["status"], {"compatible", "partial", "incompatible"})
        self.assertTrue(isinstance(report.get("recommendations"), list))

    def test_prepare_project_runner_config_uses_rawdata_if_present(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir)
            rawdata = project / "rawdata" / "sub-001"
            rawdata.mkdir(parents=True, exist_ok=True)

            prepared = prepare_project_runner_config(
                project_path=str(project),
                app_name="fmriprep",
                container_engine="apptainer",
                container="/containers/fmriprep.sif",
            )

            self.assertIn("rawdata", prepared["bids_folder"])
            self.assertTrue(prepared["config_path"].endswith(".json"))
            self.assertIn("derivatives", prepared["output_folder"])

    @patch("src.derivatives.apps_runner_compat.subprocess.run")
    def test_run_runner_with_project_builds_command(self, mock_run):
        class _Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        mock_run.return_value = _Result()

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir(parents=True, exist_ok=True)
            (project / "sub-001").mkdir(parents=True, exist_ok=True)

            runner = Path(temp_dir) / "runner"
            (runner / "scripts").mkdir(parents=True, exist_ok=True)
            (runner / "scripts" / "prism_runner.py").write_text(
                "# stub", encoding="utf-8"
            )

            result = run_runner_with_project(
                project_path=str(project),
                runner_repo_path=str(runner),
                app_name="fmriprep",
                container_engine="apptainer",
                container="/containers/fmriprep.sif",
                mode="local",
                dry_run=True,
                subjects="sub-001,sub-002",
            )

            self.assertTrue(result["success"])
            self.assertIn("--local", result["command"])
            self.assertIn("--dry-run", result["command"])
            self.assertIn("--subjects", result["command"])
            self.assertIn("sub-001", result["command"])
            self.assertIn("sub-002", result["command"])

    @patch("src.derivatives.apps_runner_compat.subprocess.run")
    def test_run_runner_with_project_includes_hpc_config(self, mock_run):
        class _Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        mock_run.return_value = _Result()

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir(parents=True, exist_ok=True)

            runner = Path(temp_dir) / "runner"
            (runner / "scripts").mkdir(parents=True, exist_ok=True)
            (runner / "scripts" / "prism_runner.py").write_text(
                "# stub", encoding="utf-8"
            )

            hpc = {
                "partition": "compute",
                "time": "24:00:00",
                "mem": "32G",
                "cpus": 8,
                "modules": ["apptainer/1.2.0"],
                "environment": {"APPTAINER_CACHEDIR": "/tmp/.apptainer"},
            }

            result = run_runner_with_project(
                project_path=str(project),
                runner_repo_path=str(runner),
                app_name="qsiprep",
                container_engine="apptainer",
                container="/containers/qsiprep.sif",
                mode="hpc",
                dry_run=True,
                hpc=hpc,
            )

            self.assertTrue(result["success"])
            self.assertEqual(
                result["prepared"]["config"]["hpc"]["partition"], "compute"
            )
            self.assertEqual(result["prepared"]["config"]["hpc"]["cpus"], 8)
            self.assertIn("--hpc", result["command"])

    @patch("src.derivatives.apps_runner_compat.subprocess.run")
    def test_run_runner_with_project_includes_datalad_config(self, mock_run):
        class _Result:
            returncode = 0
            stdout = "ok"
            stderr = ""

        mock_run.return_value = _Result()

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir(parents=True, exist_ok=True)

            runner = Path(temp_dir) / "runner"
            (runner / "scripts").mkdir(parents=True, exist_ok=True)
            (runner / "scripts" / "prism_runner.py").write_text(
                "# stub", encoding="utf-8"
            )

            datalad = {
                "input_repo": "git@github.com:lab/data.git",
                "output_repos": ["git@github.com:lab/results.git"],
                "branch_prefix": "prism-run",
            }

            result = run_runner_with_project(
                project_path=str(project),
                runner_repo_path=str(runner),
                app_name="mriqc",
                container_engine="apptainer",
                container="/containers/mriqc.sif",
                mode="local",
                dry_run=True,
                datalad=datalad,
            )

            self.assertTrue(result["success"])
            self.assertEqual(
                result["prepared"]["config"]["datalad"]["input_repo"],
                "git@github.com:lab/data.git",
            )
            self.assertEqual(
                result["prepared"]["config"]["datalad"]["output_repos"],
                ["git@github.com:lab/results.git"],
            )

    @patch("src.derivatives.apps_runner_compat.subprocess.run")
    def test_run_runner_with_project_remote_preview(self, mock_run):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir(parents=True, exist_ok=True)

            result = run_runner_with_project(
                project_path=str(project),
                runner_repo_path="",
                app_name="qsiprep",
                container_engine="apptainer",
                container="/containers/qsiprep.sif",
                mode="hpc",
                dry_run=True,
                execution_target="remote_ssh",
                remote={
                    "host": "hpc.example.org",
                    "user": "karl",
                    "project_path": "/data/project_134",
                    "runner_repo_path": "/opt/bids_apps_runner",
                    "python_exec": "python3",
                    "execute": False,
                },
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["execution_target"], "remote_ssh")
            self.assertFalse(result["remote_execute"])
            self.assertIn("ssh", result["ssh_command"][0])
            self.assertIn(
                "/data/project_134/derivatives/apps_runner/configs",
                result["remote_shell"],
            )
            mock_run.assert_not_called()

    @patch("src.derivatives.apps_runner_compat.subprocess.run")
    def test_run_runner_with_project_remote_execute_calls_ssh(self, mock_run):
        class _Result:
            returncode = 0
            stdout = "submitted"
            stderr = ""

        mock_run.return_value = _Result()

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir(parents=True, exist_ok=True)

            result = run_runner_with_project(
                project_path=str(project),
                runner_repo_path="",
                app_name="mriqc",
                container_engine="apptainer",
                container="/containers/mriqc.sif",
                mode="hpc",
                dry_run=False,
                execution_target="remote_ssh",
                remote={
                    "host": "hpc.example.org",
                    "project_path": "/data/project_134",
                    "runner_repo_path": "/opt/bids_apps_runner",
                    "execute": True,
                },
            )

            self.assertTrue(result["success"])
            self.assertTrue(result["remote_execute"])
            mock_run.assert_called_once()

    @patch("src.derivatives.apps_runner_compat.subprocess.run")
    def test_run_runner_with_project_remote_ssh_options(self, mock_run):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir(parents=True, exist_ok=True)

            result = run_runner_with_project(
                project_path=str(project),
                runner_repo_path="",
                app_name="mriqc",
                container_engine="apptainer",
                container="/containers/mriqc.sif",
                mode="hpc",
                dry_run=True,
                execution_target="remote_ssh",
                remote={
                    "host": "hpc.example.org",
                    "user": "karl",
                    "project_path": "/data/project_134",
                    "runner_repo_path": "/opt/bids_apps_runner",
                    "execute": False,
                    "port": 2222,
                    "identity_file": "~/.ssh/id_ed25519",
                    "strict_host_key_checking": "accept-new",
                    "user_known_hosts_file": "~/.ssh/known_hosts",
                    "proxy_jump": "jump.host.org",
                    "connect_timeout": 20,
                },
            )

            ssh_cmd = result["ssh_command"]
            self.assertIn("-p", ssh_cmd)
            self.assertIn("2222", ssh_cmd)
            self.assertIn("-i", ssh_cmd)
            self.assertIn("~/.ssh/id_ed25519", ssh_cmd)
            self.assertIn("-J", ssh_cmd)
            self.assertIn("jump.host.org", ssh_cmd)
            self.assertIn("StrictHostKeyChecking=accept-new", " ".join(ssh_cmd))
            self.assertIn("UserKnownHostsFile=~/.ssh/known_hosts", " ".join(ssh_cmd))
            self.assertIn("ConnectTimeout=20", " ".join(ssh_cmd))
            mock_run.assert_not_called()

    def test_list_apptainer_images_filters_supported_extensions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)
            (folder / "qsiprep_1.1.1.sif").write_text("x", encoding="utf-8")
            (folder / "fmriprep.img").write_text("x", encoding="utf-8")
            (folder / "README.txt").write_text("x", encoding="utf-8")

            result = list_apptainer_images(str(folder))
            self.assertEqual(result["count"], 2)
            self.assertIn("qsiprep_1.1.1.sif", result["images"])
            self.assertIn("fmriprep.img", result["images"])
            self.assertNotIn("README.txt", result["images"])

    @patch("src.derivatives.apps_runner_compat.shutil.which")
    @patch("src.derivatives.apps_runner_compat.subprocess.run")
    def test_load_app_help_apptainer_extracts_options(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/apptainer"

        class _Result:
            returncode = 0
            stdout = (
                "usage: app [--participant-label] [--output-spaces MNI152NLin6Asym]"
            )
            stderr = ""

        mock_run.return_value = _Result()

        with tempfile.TemporaryDirectory() as temp_dir:
            container = Path(temp_dir) / "app.sif"
            container.write_text("stub", encoding="utf-8")

            result = load_app_help(
                container_engine="apptainer",
                container=str(container),
                timeout_seconds=5,
            )

            self.assertEqual(result["engine"], "apptainer")
            self.assertIn("--participant-label", result["options"])
            self.assertIn("--output-spaces", result["options"])

    def test_remote_profile_crud(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir(parents=True, exist_ok=True)

            saved = save_remote_profile(
                str(project),
                "cluster-main",
                {
                    "host": "hpc.example.org",
                    "project_path": "/data/project_134",
                    "runner_repo_path": "/opt/bids_apps_runner",
                    "user": "karl",
                },
            )
            self.assertEqual(saved["name"], "cluster-main")

            listed = list_remote_profiles(str(project))
            self.assertEqual(listed["count"], 1)
            self.assertEqual(listed["profiles"][0]["name"], "cluster-main")

            loaded = get_remote_profile(str(project), "cluster-main")
            self.assertEqual(loaded["config"]["host"], "hpc.example.org")

            deleted = delete_remote_profile(str(project), "cluster-main")
            self.assertEqual(deleted["name"], "cluster-main")

            listed_after = list_remote_profiles(str(project))
            self.assertEqual(listed_after["count"], 0)

    @patch.dict(
        os.environ,
        {"PRISM_REMOTE_PROFILE_ENC_KEY": Fernet.generate_key().decode("utf-8")},
        clear=False,
    )
    def test_remote_profile_encrypted_passphrase_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "project"
            project.mkdir(parents=True, exist_ok=True)

            save_remote_profile(
                str(project),
                "cluster-secure",
                {
                    "host": "hpc.example.org",
                    "project_path": "/data/project_134",
                    "runner_repo_path": "/opt/bids_apps_runner",
                    "passphrase": "topsecret",
                    "store_encrypted_passphrase": True,
                },
            )

            loaded = get_remote_profile(str(project), "cluster-secure")
            self.assertTrue(loaded["config"]["has_encrypted_passphrase"])
            self.assertNotIn("passphrase_encrypted", loaded["config"])

            resolved = resolve_remote_passphrase(
                str(project),
                {
                    "profile_name": "cluster-secure",
                    "use_saved_passphrase": True,
                },
            )
            self.assertEqual(resolved, "topsecret")

    @patch.dict(os.environ, {}, clear=False)
    def test_remote_profile_encrypted_passphrase_requires_key(self):
        existing_key = os.environ.pop("PRISM_REMOTE_PROFILE_ENC_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                project = Path(temp_dir) / "project"
                project.mkdir(parents=True, exist_ok=True)

                with self.assertRaises(ValueError):
                    save_remote_profile(
                        str(project),
                        "cluster-fail",
                        {
                            "host": "hpc.example.org",
                            "project_path": "/data/project_134",
                            "runner_repo_path": "/opt/bids_apps_runner",
                            "passphrase": "secret",
                            "store_encrypted_passphrase": True,
                        },
                    )
        finally:
            if existing_key is not None:
                os.environ["PRISM_REMOTE_PROFILE_ENC_KEY"] = existing_key

    @patch("src.derivatives.apps_runner_compat.requests.get")
    def test_list_docker_tags(self, mock_get):
        class _Response:
            status_code = 200
            content = b"{}"

            @staticmethod
            def json():
                return {
                    "results": [
                        {"name": "latest"},
                        {"name": "24.0.1"},
                        {"name": "stable"},
                    ]
                }

        mock_get.return_value = _Response()

        result = list_docker_tags("nipreps/fmriprep")
        self.assertEqual(result["repository"], "nipreps/fmriprep")
        self.assertIn("latest", result["tags"])
        self.assertIn("stable", result["tags"])

    @patch("src.derivatives.apps_runner_compat.shutil.which")
    @patch("src.derivatives.apps_runner_compat.subprocess.run")
    def test_pull_docker_image(self, mock_run, mock_which):
        mock_which.return_value = "/usr/bin/docker"

        class _Result:
            returncode = 0
            stdout = "Downloaded newer image"
            stderr = ""

        mock_run.return_value = _Result()

        result = pull_docker_image("nipreps/fmriprep:latest")
        self.assertTrue(result["success"])
        self.assertEqual(result["image"], "nipreps/fmriprep:latest")


if __name__ == "__main__":
    unittest.main()
