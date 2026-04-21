"""Tests for src/derivatives/apps_runner_compat.py — profile management and utility helpers."""

import json
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.derivatives.apps_runner_compat import (
    _normalize_profile_name,
    _profiles_file,
    _load_profiles,
    _save_profiles,
    list_remote_profiles,
    get_remote_profile,
    save_remote_profile,
    delete_remote_profile,
    list_apptainer_images,
    _extract_help_options,
    list_docker_tags,
    _encrypt_secret,
    _decrypt_secret,
    _get_fernet,
    resolve_remote_passphrase,
    _parse_subjects,
    _ensure_runner_files,
)


# ---------------------------------------------------------------------------
# _normalize_profile_name
# ---------------------------------------------------------------------------

class TestNormalizeProfileName:
    def test_valid_name(self):
        assert _normalize_profile_name("my-server") == "my-server"

    def test_strips_whitespace(self):
        assert _normalize_profile_name("  server  ") == "server"

    def test_allows_dots_dashes_underscores(self):
        result = _normalize_profile_name("server.01_prod")
        assert result == "server.01_prod"

    def test_removes_special_chars(self):
        result = _normalize_profile_name("server!@#$%")
        assert result == "server"

    def test_empty_name_raises(self):
        with pytest.raises(ValueError, match="required"):
            _normalize_profile_name("")

    def test_only_special_chars_raises(self):
        with pytest.raises(ValueError, match="no valid"):
            _normalize_profile_name("!@#$%")


# ---------------------------------------------------------------------------
# _load_profiles / _save_profiles
# ---------------------------------------------------------------------------

class TestLoadSaveProfiles:
    def test_load_nonexistent_returns_empty(self, tmp_path):
        result = _load_profiles(str(tmp_path))
        assert result == {"profiles": {}}

    def test_load_malformed_json_returns_empty(self, tmp_path):
        profiles_dir = tmp_path / "derivatives" / "apps_runner"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "remote_profiles.json").write_text("NOT JSON")
        result = _load_profiles(str(tmp_path))
        assert result == {"profiles": {}}

    def test_save_and_reload(self, tmp_path):
        data = {"profiles": {"server1": {"host": "192.168.1.1"}}}
        _save_profiles(str(tmp_path), data)
        reloaded = _load_profiles(str(tmp_path))
        assert reloaded == data

    def test_load_non_dict_returns_empty(self, tmp_path):
        profiles_dir = tmp_path / "derivatives" / "apps_runner"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "remote_profiles.json").write_text(json.dumps([1, 2, 3]))
        result = _load_profiles(str(tmp_path))
        assert result == {"profiles": {}}

    def test_load_profiles_key_not_dict_gets_replaced(self, tmp_path):
        # profiles key exists but is a list instead of dict → gets replaced with {}
        profiles_dir = tmp_path / "derivatives" / "apps_runner"
        profiles_dir.mkdir(parents=True)
        (profiles_dir / "remote_profiles.json").write_text(json.dumps({"profiles": ["list", "not", "dict"]}))
        result = _load_profiles(str(tmp_path))
        assert isinstance(result["profiles"], dict)


# ---------------------------------------------------------------------------
# list_remote_profiles
# ---------------------------------------------------------------------------

class TestListRemoteProfiles:
    def test_empty_list(self, tmp_path):
        result = list_remote_profiles(str(tmp_path))
        assert result["count"] == 0
        assert result["profiles"] == []

    def test_lists_existing_profiles(self, tmp_path):
        data = {
            "profiles": {
                "server1": {"host": "10.0.0.1", "project_path": "/data", "runner_repo_path": "/runner"},
            }
        }
        _save_profiles(str(tmp_path), data)
        result = list_remote_profiles(str(tmp_path))
        assert result["count"] == 1
        assert result["profiles"][0]["name"] == "server1"

    def test_strips_passphrase_encrypted(self, tmp_path):
        data = {
            "profiles": {
                "server1": {"host": "10.0.0.1", "passphrase_encrypted": "token123"},
            }
        }
        _save_profiles(str(tmp_path), data)
        result = list_remote_profiles(str(tmp_path))
        profile_cfg = result["profiles"][0]["config"]
        assert "passphrase_encrypted" not in profile_cfg
        assert profile_cfg["has_encrypted_passphrase"] is True

    def test_sorted_alphabetically(self, tmp_path):
        data = {
            "profiles": {
                "zebra": {"host": "z"},
                "alpha": {"host": "a"},
                "middle": {"host": "m"},
            }
        }
        _save_profiles(str(tmp_path), data)
        result = list_remote_profiles(str(tmp_path))
        names = [p["name"] for p in result["profiles"]]
        assert names == sorted(names, key=str.lower)


# ---------------------------------------------------------------------------
# get_remote_profile
# ---------------------------------------------------------------------------

class TestGetRemoteProfile:
    def test_returns_existing_profile(self, tmp_path):
        data = {"profiles": {"server1": {"host": "10.0.0.1"}}}
        _save_profiles(str(tmp_path), data)
        result = get_remote_profile(str(tmp_path), "server1")
        assert result["name"] == "server1"
        assert result["config"]["host"] == "10.0.0.1"

    def test_raises_for_missing_profile(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            get_remote_profile(str(tmp_path), "nonexistent")

    def test_masks_passphrase_encrypted(self, tmp_path):
        data = {
            "profiles": {"server1": {"host": "10.0.0.1", "passphrase_encrypted": "tok"}}
        }
        _save_profiles(str(tmp_path), data)
        result = get_remote_profile(str(tmp_path), "server1")
        assert "passphrase_encrypted" not in result["config"]
        assert result["config"]["has_encrypted_passphrase"] is True


# ---------------------------------------------------------------------------
# save_remote_profile
# ---------------------------------------------------------------------------

class TestSaveRemoteProfile:
    def _base_config(self):
        return {
            "host": "10.0.0.1",
            "project_path": "/remote/data",
            "runner_repo_path": "/remote/runner",
        }

    def test_saves_profile(self, tmp_path):
        result = save_remote_profile(str(tmp_path), "server1", self._base_config())
        assert result["name"] == "server1"
        assert result["config"]["host"] == "10.0.0.1"

    def test_requires_host(self, tmp_path):
        cfg = {"project_path": "/data", "runner_repo_path": "/runner"}
        with pytest.raises(ValueError, match="host is required"):
            save_remote_profile(str(tmp_path), "server1", cfg)

    def test_requires_project_path(self, tmp_path):
        cfg = {"host": "10.0.0.1", "runner_repo_path": "/runner"}
        with pytest.raises(ValueError, match="project_path is required"):
            save_remote_profile(str(tmp_path), "server1", cfg)

    def test_requires_runner_repo_path(self, tmp_path):
        cfg = {"host": "10.0.0.1", "project_path": "/data"}
        with pytest.raises(ValueError, match="runner_repo_path is required"):
            save_remote_profile(str(tmp_path), "server1", cfg)

    def test_non_dict_config_raises(self, tmp_path):
        with pytest.raises(ValueError, match="must be an object"):
            save_remote_profile(str(tmp_path), "server1", "not a dict")

    def test_ignores_unknown_keys(self, tmp_path):
        cfg = {**self._base_config(), "evil_key": "ignored"}
        result = save_remote_profile(str(tmp_path), "server1", cfg)
        assert "evil_key" not in result["config"]

    def test_strips_empty_strings(self, tmp_path):
        cfg = {**self._base_config(), "user": "   "}
        result = save_remote_profile(str(tmp_path), "server1", cfg)
        assert "user" not in result["config"]

    def test_none_values_excluded(self, tmp_path):
        cfg = {**self._base_config(), "identity_file": None}
        result = save_remote_profile(str(tmp_path), "server1", cfg)
        assert "identity_file" not in result["config"]



# ---------------------------------------------------------------------------
# delete_remote_profile
# ---------------------------------------------------------------------------

class TestDeleteRemoteProfile:
    def test_deletes_existing(self, tmp_path):
        data = {"profiles": {"server1": {"host": "10.0.0.1"}}}
        _save_profiles(str(tmp_path), data)
        result = delete_remote_profile(str(tmp_path), "server1")
        assert "deleted" in result or result.get("name") == "server1"
        # Verify it's gone
        with pytest.raises(ValueError):
            get_remote_profile(str(tmp_path), "server1")

    def test_raises_for_missing(self, tmp_path):
        with pytest.raises(ValueError, match="not found"):
            delete_remote_profile(str(tmp_path), "nonexistent")


# ---------------------------------------------------------------------------
# list_apptainer_images
# ---------------------------------------------------------------------------

class TestListApptainerImages:
    def test_lists_sif_files(self, tmp_path):
        (tmp_path / "image.sif").write_text("")
        (tmp_path / "other.img").write_text("")
        result = list_apptainer_images(str(tmp_path))
        assert "image.sif" in result["images"]
        assert "other.img" in result["images"]
        assert result["count"] == 2

    def test_empty_folder(self, tmp_path):
        result = list_apptainer_images(str(tmp_path))
        assert result["images"] == []
        assert result["count"] == 0

    def test_invalid_folder_raises(self, tmp_path):
        with pytest.raises(ValueError, match="invalid"):
            list_apptainer_images(str(tmp_path / "nonexistent"))

    def test_sorted_output(self, tmp_path):
        for name in ["zebra.sif", "alpha.sif", "middle.sif"]:
            (tmp_path / name).write_text("")
        result = list_apptainer_images(str(tmp_path))
        assert result["images"] == sorted(result["images"], key=str.lower)


# ---------------------------------------------------------------------------
# _extract_help_options
# ---------------------------------------------------------------------------

class TestExtractHelpOptions:
    def test_extracts_options(self):
        help_text = "  --input path   --output dir\n  --verbose"
        opts = _extract_help_options(help_text)
        assert "--input" in opts
        assert "--output" in opts
        assert "--verbose" in opts

    def test_deduplicates(self):
        help_text = "  --input path\n  --input more"
        opts = _extract_help_options(help_text)
        assert opts.count("--input") == 1

    def test_empty_returns_empty(self):
        assert _extract_help_options("") == []
        assert _extract_help_options(None) == []

    def test_sorted_output(self):
        help_text = "  --zebra  --alpha  --middle"
        opts = _extract_help_options(help_text)
        assert opts == sorted(opts, key=str.lower)


# ---------------------------------------------------------------------------
# list_docker_tags (mocked HTTP)
# ---------------------------------------------------------------------------

class TestListDockerTags:
    def test_empty_repository_raises(self):
        with pytest.raises(ValueError, match="required"):
            list_docker_tags("")

    def test_404_raises(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.content = b""
        with patch("requests.get", return_value=mock_resp):
            with pytest.raises(ValueError, match="not found"):
                list_docker_tags("nonexistent/repo")

    def test_returns_tags_from_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b'{"results": [{"name": "latest"}, {"name": "v1.0"}]}'
        mock_resp.json.return_value = {"results": [{"name": "latest"}, {"name": "v1.0"}]}
        with patch("requests.get", return_value=mock_resp):
            result = list_docker_tags("myrepo/image")
        assert "latest" in result["tags"]
        assert "v1.0" in result["tags"]
        assert result["count"] == 2

    def test_request_exception_raises(self):
        import requests
        with patch("requests.get", side_effect=requests.RequestException("timeout")):
            with pytest.raises(ValueError, match="Could not fetch"):
                list_docker_tags("myrepo/image")


# ---------------------------------------------------------------------------
# prepare_project_runner_config
# ---------------------------------------------------------------------------

from src.derivatives.apps_runner_compat import prepare_project_runner_config


class TestPrepareProjectRunnerConfig:
    def test_creates_config_file(self, tmp_path):
        # Setup a minimal project root
        (tmp_path / "rawdata").mkdir()
        result = prepare_project_runner_config(
            project_path=str(tmp_path),
            app_name="fmriprep",
            container_engine="docker",
            container="nipreps/fmriprep:latest",
        )
        assert "config_path" in result
        import json as _json
        config = _json.loads(open(result["config_path"]).read())
        assert config["app"]["name"] == "fmriprep"
        assert config["common"]["container_engine"] == "docker"

    def test_raises_for_invalid_project_path(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid PRISM project path"):
            prepare_project_runner_config(
                project_path=str(tmp_path / "nonexistent"),
                app_name="fmriprep",
                container_engine="docker",
                container="image:latest",
            )

    def test_raises_for_invalid_engine(self, tmp_path):
        with pytest.raises(ValueError, match="container_engine must be one of"):
            prepare_project_runner_config(
                project_path=str(tmp_path),
                app_name="fmriprep",
                container_engine="invalid_engine",
                container="image:latest",
            )

    def test_raises_for_empty_app_name(self, tmp_path):
        with pytest.raises(ValueError, match="App name is required"):
            prepare_project_runner_config(
                project_path=str(tmp_path),
                app_name="   ",
                container_engine="docker",
                container="image:latest",
            )

    def test_raises_for_empty_container(self, tmp_path):
        with pytest.raises(ValueError, match="Container image"):
            prepare_project_runner_config(
                project_path=str(tmp_path),
                app_name="fmriprep",
                container_engine="docker",
                container="  ",
            )

    def test_custom_output_folder(self, tmp_path):
        custom_out = str(tmp_path / "custom_out")
        result = prepare_project_runner_config(
            project_path=str(tmp_path),
            app_name="fmriprep",
            container_engine="docker",
            container="nipreps/fmriprep:latest",
            output_folder=custom_out,
        )
        assert result["output_folder"] == custom_out

    def test_jobs_clamped_to_one(self, tmp_path):
        result = prepare_project_runner_config(
            project_path=str(tmp_path),
            app_name="fmriprep",
            container_engine="docker",
            container="nipreps/fmriprep:latest",
            jobs=0,
        )
        import json as _json
        config = _json.loads(open(result["config_path"]).read())
        assert config["common"]["jobs"] == 1


# ---------------------------------------------------------------------------
# _get_fernet / _encrypt_secret / _decrypt_secret
# ---------------------------------------------------------------------------

import os

class TestFernetHelpers:
    def test_get_fernet_none_when_no_key(self, monkeypatch):
        monkeypatch.delenv("PRISM_REMOTE_PROFILE_ENC_KEY", raising=False)
        assert _get_fernet() is None

    def test_encrypt_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("PRISM_REMOTE_PROFILE_ENC_KEY", raising=False)
        import pytest
        with pytest.raises(ValueError, match="PRISM_REMOTE_PROFILE_ENC_KEY"):
            _encrypt_secret("mysecret")

    def test_decrypt_without_key_raises(self, monkeypatch):
        monkeypatch.delenv("PRISM_REMOTE_PROFILE_ENC_KEY", raising=False)
        import pytest
        with pytest.raises(ValueError, match="PRISM_REMOTE_PROFILE_ENC_KEY"):
            _decrypt_secret("sometoken")

    def test_encrypt_decrypt_roundtrip(self, monkeypatch):
        try:
            from cryptography.fernet import Fernet
        except ImportError:
            import pytest
            pytest.skip("cryptography not available")
        key = Fernet.generate_key().decode("utf-8")
        monkeypatch.setenv("PRISM_REMOTE_PROFILE_ENC_KEY", key)
        token = _encrypt_secret("my_passphrase")
        assert token != "my_passphrase"
        result = _decrypt_secret(token)
        assert result == "my_passphrase"

    def test_invalid_fernet_key_raises(self, monkeypatch):
        monkeypatch.setenv("PRISM_REMOTE_PROFILE_ENC_KEY", "notavalidkey")
        import pytest
        with pytest.raises(ValueError, match="invalid"):
            _get_fernet()


# ---------------------------------------------------------------------------
# _resolve_passphrase
# ---------------------------------------------------------------------------

class TestResolvePassphrase:
    def test_returns_direct_passphrase(self, tmp_path):
        result = resolve_remote_passphrase(str(tmp_path), {"passphrase": "mypass"})
        assert result == "mypass"

    def test_returns_none_when_no_passphrase(self, tmp_path):
        result = resolve_remote_passphrase(str(tmp_path), {})
        assert result is None

    def test_returns_none_when_no_profile(self, tmp_path):
        result = resolve_remote_passphrase(str(tmp_path), {"profile_name": "missing", "use_saved_passphrase": True})
        assert result is None

    def test_returns_none_when_no_token(self, tmp_path):
        # Save profile without passphrase_encrypted
        save_remote_profile(str(tmp_path), "server1", {
            "host": "10.0.0.1",
            "project_path": "/data",
            "runner_repo_path": "/runner",
        })
        result = resolve_remote_passphrase(str(tmp_path), {"profile_name": "server1", "use_saved_passphrase": True})
        assert result is None


# ---------------------------------------------------------------------------
# _parse_subjects
# ---------------------------------------------------------------------------

class TestParseSubjects:
    def test_none_returns_empty(self):
        assert _parse_subjects(None) == []

    def test_list_of_strings(self):
        assert _parse_subjects(["sub-01", "sub-02"]) == ["sub-01", "sub-02"]

    def test_comma_separated_string(self):
        assert _parse_subjects("sub-01, sub-02") == ["sub-01", "sub-02"]

    def test_empty_string_returns_empty(self):
        assert _parse_subjects("") == []


# ---------------------------------------------------------------------------
# _ensure_runner_files
# ---------------------------------------------------------------------------

class TestEnsureRunnerFiles:
    def test_raises_for_nonexistent_dir(self, tmp_path):
        with pytest.raises(ValueError, match="invalid"):
            _ensure_runner_files(str(tmp_path / "nonexistent"))

    def test_raises_when_runner_script_missing(self, tmp_path):
        with pytest.raises(ValueError, match="Runner script"):
            _ensure_runner_files(str(tmp_path))


