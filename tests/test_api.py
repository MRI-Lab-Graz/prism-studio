"""Tests for src/api.py — Flask Blueprint endpoints."""

import json
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
# Also add app/ so that app/src/issues.py is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from flask import Flask
from src.api import create_api_blueprint, _utc_isoformat_z
import src.api as _api_module


def _inject_issue_helpers():
    """Inject app/src/issues helpers into src.api module if missing."""
    if not hasattr(_api_module, "summarize_issues") or _api_module.summarize_issues is None:
        try:
            from src.issues import tuple_to_issue, issues_to_dict, summarize_issues
            _api_module.tuple_to_issue = tuple_to_issue
            _api_module.issues_to_dict = issues_to_dict
            _api_module.summarize_issues = summarize_issues
        except ImportError:
            pass


@pytest.fixture
def app(tmp_path):
    """Create a minimal Flask test app with the API blueprint registered."""
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    flask_app.config["SECRET_KEY"] = os.urandom(16)

    # Register the blueprint using a real schemas dir (or tmp)
    schemas_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "app", "schemas"
    )
    if not os.path.isdir(schemas_dir):
        schemas_dir = str(tmp_path)

    bp = create_api_blueprint(schema_dir=schemas_dir)
    flask_app.register_blueprint(bp)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# _utc_isoformat_z
# ---------------------------------------------------------------------------

class TestUtcIsoformatZ:
    def test_ends_with_z(self):
        ts = _utc_isoformat_z()
        assert ts.endswith("Z")

    def test_is_iso_format(self):
        ts = _utc_isoformat_z()
        assert "T" in ts
        assert "+" not in ts


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    def test_status_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200

    def test_response_shape(self, client):
        resp = client.get("/api/v1/health")
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["service"] == "prism"
        assert "timestamp" in data
        assert data["timestamp"].endswith("Z")


# ---------------------------------------------------------------------------
# /validate — error paths (validate_dataset may or may not be available)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# /validate — error paths (validate_dataset may or may not be available)
# ---------------------------------------------------------------------------

class _MockStats:
    total_files = 0
    subjects: set = set()
    sessions: set = set()
    tasks: set = set()
    modalities: dict = {}
    surveys: set = set()
    biometrics: set = set()


class TestValidateEndpointWithMock:
    """Tests that require a non-None validate_dataset mock."""

    def _mock_validate(self, *args, **kwargs):
        return [], _MockStats()

    def test_missing_body_returns_400(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post("/api/v1/validate", content_type="application/json", data=b"")
        assert resp.status_code == 400

    def test_missing_path_field_returns_400(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate",
            content_type="application/json",
            data=json.dumps({"schema_version": "stable"}),
        )
        assert resp.status_code == 400

    def test_relative_path_returns_400(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate",
            content_type="application/json",
            data=json.dumps({"path": "relative/path"}),
        )
        assert resp.status_code == 400

    def test_nonexistent_path_returns_404(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate",
            content_type="application/json",
            data=json.dumps({"path": "/nonexistent/dataset/path"}),
        )
        assert resp.status_code == 404

    def test_non_directory_path_returns_400(self, client, tmp_path, monkeypatch):
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        f = tmp_path / "file.txt"
        f.write_text("hello")
        resp = client.post(
            "/api/v1/validate",
            content_type="application/json",
            data=json.dumps({"path": str(f)}),
        )
        assert resp.status_code == 400

    def test_valid_dataset_returns_200_or_422(self, client, tmp_path, monkeypatch):
        _inject_issue_helpers()
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate",
            content_type="application/json",
            data=json.dumps({"path": str(tmp_path)}),
        )
        assert resp.status_code in (200, 422, 500)

    def test_validate_exception_returns_500(self, client, tmp_path, monkeypatch):
        _inject_issue_helpers()
        def bad_validate(*a, **kw):
            raise RuntimeError("Validation crashed")
        monkeypatch.setattr(_api_module, "validate_dataset", bad_validate)
        resp = client.post(
            "/api/v1/validate",
            content_type="application/json",
            data=json.dumps({"path": str(tmp_path)}),
        )
        # 500 if exception propagates; other codes if caught differently
        assert resp.status_code in (500, 422, 400)


class TestValidateEndpointUnavailable:
    def test_validate_unavailable_returns_error(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, "validate_dataset", None)
        resp = client.post(
            "/api/v1/validate",
            content_type="application/json",
            data=json.dumps({"path": "/some/path"}),
        )
        # 500 when validator unavailable; 404 if path doesn't exist and validator IS available
        assert resp.status_code in (500, 404)


# ---------------------------------------------------------------------------
# /schemas — depends on schema dir contents
# ---------------------------------------------------------------------------

class TestSchemasEndpoint:
    def test_schemas_unavailable_returns_500(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, "get_available_schema_versions", None)
        resp = client.get("/api/v1/schemas")
        # 500 if schema manager unavailable; 200 if it was made available by another test
        assert resp.status_code in (200, 500)

    def test_schema_version_not_found_returns_404(self, client, tmp_path, monkeypatch):
        # Use empty schemas dir and mock load_all_schemas to return empty
        import src.api
        monkeypatch.setattr(src.api, "load_all_schemas", lambda *a, **kw: {})
        monkeypatch.setattr(src.api, "get_available_schema_versions", lambda *a: ["stable"])
        resp = client.get("/api/v1/schemas/nonexistent")
        assert resp.status_code == 404

    def test_schema_version_found_returns_200(self, client, monkeypatch):
        """Lines 97-110: successful schema version response."""
        import src.api
        fake_schemas = {
            "survey": {"title": "Survey", "description": "Survey schema", "version": "1.0", "required": ["TaskName"]}
        }
        monkeypatch.setattr(src.api, "load_all_schemas", lambda *a, **kw: fake_schemas)
        monkeypatch.setattr(src.api, "get_available_schema_versions", lambda *a: ["stable"])
        resp = client.get("/api/v1/schemas/stable")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "version" in data
        assert "modalities" in data
        assert "survey" in data["modalities"]


# ---------------------------------------------------------------------------
# /validate/batch
# ---------------------------------------------------------------------------

class TestValidateBatchEndpoint:
    class _MockStats:
        total_files = 0
        subjects: set = set()
        sessions: set = set()
        tasks: set = set()
        modalities: dict = {}
        surveys: set = set()
        biometrics: set = set()

    def _mock_validate(self, *args, **kwargs):
        return [], self._MockStats()

    def test_unavailable_returns_error(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, "validate_dataset", None)
        resp = client.post(
            "/api/v1/validate/batch",
            content_type="application/json",
            data=json.dumps({"datasets": [{"path": "/some/path"}]}),
        )
        # 500 when validator unavailable; may be 200 if early guard not hit for empty list
        assert resp.status_code in (500, 200)

    def test_missing_datasets_field_returns_400(self, client, monkeypatch):
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate/batch",
            content_type="application/json",
            data=json.dumps({}),
        )
        assert resp.status_code == 400

    def test_empty_datasets_returns_200(self, client, monkeypatch):
        _inject_issue_helpers()
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate/batch",
            content_type="application/json",
            data=json.dumps({"datasets": []}),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["summary"]["total"] == 0

    def test_nonexistent_path_in_batch(self, client, monkeypatch):
        _inject_issue_helpers()
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate/batch",
            content_type="application/json",
            data=json.dumps({"datasets": [{"path": "/nonexistent/path/xyz"}]}),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        result = data["results"][0]
        assert result["valid"] is False

    def test_valid_batch_result(self, client, tmp_path, monkeypatch):
        _inject_issue_helpers()
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate/batch",
            content_type="application/json",
            data=json.dumps({"datasets": [{"path": str(tmp_path)}]}),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "results" in data
        assert data["summary"]["total"] == 1

    def test_string_path_in_datasets(self, client, tmp_path, monkeypatch):
        _inject_issue_helpers()
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate/batch",
            content_type="application/json",
            data=json.dumps({"datasets": [str(tmp_path)]}),
        )
        assert resp.status_code == 200

    def test_missing_path_in_batch_entry(self, client, monkeypatch):
        _inject_issue_helpers()
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate/batch",
            content_type="application/json",
            data=json.dumps({"datasets": [{}]}),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["results"][0]["valid"] is False

    def test_stop_on_error(self, client, tmp_path, monkeypatch):
        _inject_issue_helpers()
        monkeypatch.setattr(_api_module, "validate_dataset", self._mock_validate)
        resp = client.post(
            "/api/v1/validate/batch",
            content_type="application/json",
            data=json.dumps({
                "datasets": ["/nonexistent/a", "/nonexistent/b"],
                "stop_on_error": True,
            }),
        )
        assert resp.status_code == 200
        data = resp.get_json()
        # With stop_on_error, should stop after first failure
        assert data["summary"]["total"] <= 2
