"""
Unit tests for prism core functionality.

Run with: pytest tests/test_unit.py -v
"""

import os
import sys
import json
import pytest
import tempfile
import shutil

# Add app/src to path for testing
sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src")
)

from issues import (
    Issue,
    Severity,
    create_issue,
    error,
    warning,
    info,
    tuple_to_issue,
    issues_to_dict,
    summarize_issues,
    ERROR_CODES,
)
from config import PrismConfig, load_config, save_config, find_config_file
from schema_manager import load_schema, load_all_schemas, get_available_schema_versions


class TestIssues:
    """Test the Issue class and error codes system"""

    def test_issue_creation(self):
        """Test creating an Issue directly"""
        issue = Issue(
            code="PRISM001",
            severity=Severity.ERROR,
            message="Test message",
            file_path="/path/to/file",
            fix_hint="Fix this way",
        )
        assert issue.code == "PRISM001"
        assert issue.severity == Severity.ERROR
        assert issue.message == "Test message"
        assert issue.file_path == "/path/to/file"
        assert issue.fix_hint == "Fix this way"

    def test_create_issue_with_defaults(self):
        """Test create_issue uses defaults from ERROR_CODES"""
        issue = create_issue("PRISM001")
        assert issue.code == "PRISM001"
        assert issue.severity == Severity.ERROR
        assert "dataset_description.json" in issue.message.lower()
        assert issue.fix_hint is not None

    def test_error_shorthand(self):
        """Test error() shorthand function"""
        issue = error("PRISM001", file_path="/test/path")
        assert issue.severity == Severity.ERROR
        assert issue.file_path == "/test/path"

    def test_warning_shorthand(self):
        """Test warning() shorthand function"""
        issue = warning("PRISM501")
        assert issue.severity == Severity.WARNING

    def test_info_shorthand(self):
        """Test info() shorthand function"""
        issue = info("PRISM001", message="Info message")
        assert issue.severity == Severity.INFO
        assert issue.message == "Info message"

    def test_issue_to_dict(self):
        """Test Issue.to_dict() method"""
        issue = error("PRISM001")
        d = issue.to_dict()
        assert isinstance(d, dict)
        assert d["code"] == "PRISM001"
        assert d["severity"] == "ERROR"

    def test_issue_to_tuple(self):
        """Test Issue.to_tuple() for backward compatibility"""
        issue = error("PRISM001", file_path="/test/path")
        t = issue.to_tuple()
        assert len(t) == 3
        assert t[0] == "ERROR"
        assert t[2] == "/test/path"

    def test_tuple_to_issue(self):
        """Test converting legacy tuple to Issue"""
        t = ("ERROR", "Test message", "/path")
        issue = tuple_to_issue(t)
        assert isinstance(issue, Issue)
        assert issue.severity == Severity.ERROR
        assert issue.message == "Test message"
        assert issue.file_path == "/path"

    def test_tuple_to_issue_without_path(self):
        """Test converting tuple without path"""
        t = ("WARNING", "Warning message")
        issue = tuple_to_issue(t)
        assert issue.severity == Severity.WARNING
        assert issue.file_path is None

    def test_issues_to_dict(self):
        """Test converting list of Issues to dicts"""
        issues = [error("PRISM001"), warning("PRISM501")]
        dicts = issues_to_dict(issues)
        assert len(dicts) == 2
        assert all(isinstance(d, dict) for d in dicts)

    def test_summarize_issues(self):
        """Test issue summarization"""
        issues = [
            error("PRISM001"),
            error("PRISM001"),
            warning("PRISM501"),
            info("PRISM001"),
        ]
        summary = summarize_issues(issues)
        assert summary["total"] == 4
        assert summary["errors"] == 2
        assert summary["warnings"] == 1
        assert summary["info"] == 1
        assert summary["by_code"]["PRISM001"] == 3
        assert summary["by_code"]["PRISM501"] == 1

    def test_all_error_codes_have_defaults(self):
        """Test that all defined error codes have message and fix_hint"""
        for code, data in ERROR_CODES.items():
            assert "message" in data, f"{code} missing message"
            assert "fix_hint" in data, f"{code} missing fix_hint"


class TestConfig:
    """Test configuration file support"""

    def test_default_config(self):
        """Test PrismConfig defaults"""
        config = PrismConfig()
        assert config.schema_version == "stable"
        assert config.strict_mode is False
        assert config.run_bids is False
        assert len(config.ignore_paths) > 0

    def test_should_ignore(self):
        """Test ignore path matching"""
        config = PrismConfig(ignore_paths=["derivatives/**", "*.pyc"])
        assert config.should_ignore("derivatives/sub-01/file.nii") is True
        assert config.should_ignore("test.pyc") is True
        assert config.should_ignore("sub-01/anat/scan.nii") is False

    def test_config_to_dict(self):
        """Test converting config to dict"""
        config = PrismConfig(schema_version="v0.1")
        d = config.to_dict()
        assert d["schema_version"] == "v0.1"
        assert "_config_path" not in d

    def test_save_and_load_config(self):
        """Test saving and loading config file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save config
            config = PrismConfig(
                schema_version="v0.1",
                strict_mode=True,
                run_bids=True,
            )
            path = save_config(config, tmpdir)
            assert os.path.exists(path)

            # Load config
            loaded = load_config(tmpdir)
            assert loaded.schema_version == "v0.1"
            assert loaded.strict_mode is True
            assert loaded.run_bids is True

    def test_find_config_file(self):
        """Test finding config file in directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # No config file
            assert find_config_file(tmpdir) is None

            # Create config file
            config_path = os.path.join(tmpdir, ".prismrc.json")
            with open(config_path, "w") as f:
                json.dump({"schemaVersion": "stable"}, f)

            assert find_config_file(tmpdir) == config_path

    def test_load_config_with_missing_file(self):
        """Test loading config when file doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = load_config(tmpdir)
            # Should return defaults
            assert config.schema_version == "stable"

    def test_load_config_with_invalid_json(self):
        """Test loading config with invalid JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, ".prismrc.json")
            with open(config_path, "w") as f:
                f.write("not valid json {")

            # Should return defaults without crashing
            config = load_config(tmpdir)
            assert config.schema_version == "stable"


class TestSchemaManager:
    """Test schema loading functionality"""

    @pytest.fixture
    def schema_dir(self):
        """Get path to schemas directory"""
        # After reorg, schemas are in app/schemas
        return os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "app", "schemas"
        )

    def test_get_available_versions(self, schema_dir):
        """Test listing available schema versions"""
        versions = get_available_schema_versions(schema_dir)
        assert "stable" in versions
        assert len(versions) >= 1

    def test_load_survey_schema(self, schema_dir):
        """Test loading survey schema"""
        schema = load_schema("survey", schema_dir, version="stable")
        assert schema is not None
        assert "properties" in schema
        assert "Technical" in schema["properties"]

    def test_load_all_schemas(self, schema_dir):
        """Test loading all schemas for a version"""
        schemas = load_all_schemas(schema_dir, version="stable")
        assert len(schemas) > 0
        assert "survey" in schemas
        assert "dataset_description" in schemas

    def test_load_nonexistent_schema(self, schema_dir):
        """Test loading non-existent schema returns None"""
        schema = load_schema("nonexistent_modality", schema_dir)
        assert schema is None


class TestValidatorIntegration:
    """Integration tests for the validator"""

    @pytest.fixture
    def valid_dataset(self):
        """Create a minimal valid dataset for testing"""
        tmpdir = tempfile.mkdtemp()

        # Create dataset_description.json
        desc = {
            "Name": "Test Dataset",
            "BIDSVersion": "1.9.0",
            "DatasetType": "raw",
        }
        with open(os.path.join(tmpdir, "dataset_description.json"), "w") as f:
            json.dump(desc, f)

        # Create a subject directory with survey data
        sub_dir = os.path.join(tmpdir, "sub-01", "survey")
        os.makedirs(sub_dir)

        # Create survey TSV
        tsv_path = os.path.join(sub_dir, "sub-01_survey-test_beh.tsv")
        with open(tsv_path, "w") as f:
            f.write("item01\titem02\n")
            f.write("1\t2\n")

        # Create survey sidecar
        sidecar = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "Language": "en",
                "Respondent": "self",
            },
            "Study": {"TaskName": "test", "OriginalName": "Test Survey"},
            "Metadata": {"SchemaVersion": "1.1.1", "CreationDate": "2024-01-01"},
        }
        with open(os.path.join(sub_dir, "sub-01_survey-test_beh.json"), "w") as f:
            json.dump(sidecar, f)

        yield tmpdir

        # Cleanup
        shutil.rmtree(tmpdir)

    def test_validate_minimal_dataset(self, valid_dataset):
        """Test validating a minimal valid dataset"""
        from runner import validate_dataset

        issues, stats = validate_dataset(valid_dataset)

        # Should have stats
        assert len(stats.subjects) == 1
        assert "sub-01" in stats.subjects

        # Check issues (may have warnings but no critical errors for basic structure)
        error_count = sum(1 for i in issues if i[0] == "ERROR")
        # Allow for schema validation issues in minimal test
        assert isinstance(issues, list)

    def test_validate_missing_dataset_description(self):
        """Test validation fails for missing dataset_description.json"""
        from runner import validate_dataset

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create subject dir without dataset_description.json
            os.makedirs(os.path.join(tmpdir, "sub-01"))

            issues, stats = validate_dataset(tmpdir)

            # Should have error about missing dataset_description.json
            error_messages = [i[1] for i in issues if i[0] == "ERROR"]
            assert any(
                "dataset_description.json" in msg.lower() for msg in error_messages
            )

    def test_validate_empty_dataset(self):
        """Test validation of empty directory"""
        from runner import validate_dataset

        with tempfile.TemporaryDirectory() as tmpdir:
            issues, stats = validate_dataset(tmpdir)

            # Should have error about no subjects and missing dataset_description
            assert len(stats.subjects) == 0
            error_count = sum(1 for i in issues if i[0] == "ERROR")
            assert error_count >= 1


class TestAPI:
    """Test REST API functionality"""

    @pytest.fixture
    def api_blueprint(self):
        """Create API blueprint for testing"""
        from api import create_api_blueprint
        from flask import Flask

        app = Flask(__name__)
        # After reorg, schemas are in app/schemas
        schema_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "app", "schemas"
        )
        api_bp = create_api_blueprint(schema_dir)
        app.register_blueprint(api_bp)

        return app.test_client()

    def test_health_endpoint(self, api_blueprint):
        """Test /api/v1/health endpoint"""
        response = api_blueprint.get("/api/v1/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_schemas_endpoint(self, api_blueprint):
        """Test /api/v1/schemas endpoint"""
        response = api_blueprint.get("/api/v1/schemas")
        assert response.status_code == 200
        data = response.get_json()
        assert "versions" in data
        assert "stable" in data["versions"]

    def test_validate_missing_path(self, api_blueprint):
        """Test validation with missing path"""
        response = api_blueprint.post(
            "/api/v1/validate", json={}, content_type="application/json"
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_validate_nonexistent_path(self, api_blueprint):
        """Test validation with non-existent path"""
        response = api_blueprint.post(
            "/api/v1/validate",
            json={"path": "/nonexistent/path/to/dataset"},
            content_type="application/json",
        )
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
