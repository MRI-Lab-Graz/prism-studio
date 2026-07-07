import os
import sys
import importlib
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
app_path = os.path.join(project_root, "app")
if app_path not in sys.path:
    sys.path.insert(0, app_path)

projects_export_module = importlib.import_module(
    "src.web.blueprints.projects_export_blueprint"
)
projects_export_bp = projects_export_module.projects_export_bp


def _build_app():
    app = Flask(__name__)
    app.register_blueprint(projects_export_bp)
    return app


def test_projects_export_uses_fixed_internal_anonymization_settings(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    called = {}

    def fake_export_project(**kwargs):
        called.update(kwargs)
        output_zip = kwargs["output_zip"]
        Path(output_zip).write_bytes(b"PK\x03\x04")
        return {"files_processed": 0, "files_anonymized": 0, "participant_count": 0}

    with patch(
        "src.web.export_project.export_project", side_effect=fake_export_project
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export",
                json={
                    "project_path": str(project_dir),
                    "anonymize": True,
                    "mask_questions": False,
                    "scrub_mri_json": True,
                    "scrub_mri_json_groups": ["scanner_site", "timestamps"],
                    "include_derivatives": True,
                    "include_code": False,
                    "include_analysis": False,
                },
            )

    assert response.status_code == 200
    assert called["anonymize"] is True
    assert called["mask_questions"] is False
    assert called["scrub_mri_json"] is True
    assert called["scrub_mri_json_groups"] == {"scanner_site", "timestamps"}
    assert called["clean_nifti_gzip_headers"] is True
    assert called["id_length"] == 8
    assert called["deterministic"] is True
    assert called["include_sourcedata"] is False


def test_projects_export_start_uses_fixed_internal_anonymization_settings(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    with patch(
        "src.web.blueprints.projects_export_blueprint.threading.Thread",
        side_effect=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/start",
                json={
                    "project_path": str(project_dir),
                    "anonymize": True,
                    "mask_questions": False,
                    "scrub_mri_json": True,
                    "scrub_mri_json_groups": ["scanner_site", "timestamps"],
                    "include_derivatives": True,
                    "include_code": False,
                    "include_analysis": False,
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("job_id")
    assert captured.get("started") is True
    assert captured.get("target") is projects_export_module._run_export_job

    args = captured.get("args")
    assert isinstance(args, tuple)
    assert len(args) == 4
    export_kwargs = args[1]
    assert isinstance(export_kwargs, dict)
    assert export_kwargs["anonymize"] is True
    assert export_kwargs["mask_questions"] is False
    assert export_kwargs["scrub_mri_json"] is True
    assert export_kwargs["scrub_mri_json_groups"] == {"scanner_site", "timestamps"}
    assert export_kwargs["clean_nifti_gzip_headers"] is True
    assert export_kwargs["id_length"] == 8
    assert export_kwargs["deterministic"] is True
    assert export_kwargs["include_sourcedata"] is False
    assert args[2] == "study_anonymized_export.zip"


def test_projects_export_start_uses_non_anonymized_filename_when_disabled(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    with patch(
        "src.web.blueprints.projects_export_blueprint.threading.Thread",
        side_effect=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/start",
                json={
                    "project_path": str(project_dir),
                    "anonymize": False,
                    "mask_questions": False,
                    "include_derivatives": True,
                    "include_code": False,
                    "include_analysis": False,
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("job_id")

    args = captured.get("args")
    assert isinstance(args, tuple)
    assert len(args) == 4
    export_kwargs = args[1]
    assert isinstance(export_kwargs, dict)
    assert export_kwargs["anonymize"] is False
    assert export_kwargs["include_sourcedata"] is False
    assert args[2] == "study_export.zip"


def test_projects_export_deface_route_returns_backend_summary(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    copy_target = tmp_path / "study_defacing_export"

    with patch(
        "src.mri_json_scrubber.prepare_defacing_export_copy",
        return_value={
            "success": True,
            "target_path": str(copy_target),
            "copied_nifti_files": 1,
            "copied_sidecars": 1,
        },
    ), patch(
        "src.mri_json_scrubber.deface_anatomical_scans",
        return_value={
            "success": True,
            "message": "Defacing completed successfully.",
            "counts": {"total": 1, "defaced": 1, "already_defaced": 0, "failed": 0, "skipped": 0},
            "items": [{"file": "sub-01/anat/sub-01_T1w.nii.gz", "status": "defaced", "message": "ok"}],
        },
    ), patch(
        "src.mri_json_scrubber.build_defacing_report",
        return_value=[
            {
                "file": "sub-01/anat/sub-01_T1w.json",
                "status": "defaced",
                "reason": "JSON metadata indicates defacing/skull-stripping",
            }
        ],
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/deface",
                json={"project_path": str(project_dir)},
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("defacing", {}).get("counts", {}).get("defaced") == 1
    assert payload.get("report_counts", {}).get("defaced") == 1
    assert payload.get("target_mode") == "export_copy"
    assert payload.get("target_path") == str(copy_target.resolve(strict=False))


def test_projects_export_defacing_report_route_forwards_selected_variants(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    with patch(
        "src.mri_json_scrubber.build_defacing_report",
        return_value=[],
    ) as mock_report:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/defacing-report",
                json={
                    "project_path": str(project_dir),
                    "selected_variants": ["acq:mprage|suffix:t1w"],
                    "exclude_subjects": ["sub-002", ""],
                    "exclude_sessions": ["ses-2", ""],
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True

    args, kwargs = mock_report.call_args
    assert args[0] == project_dir.resolve(strict=False)
    assert kwargs.get("selected_variants") == {"acq:mprage|suffix:t1w"}
    assert kwargs.get("excluded_subjects") == {"sub-002"}
    assert kwargs.get("excluded_sessions") == {"ses-2"}


def test_projects_export_deface_route_forwards_selected_variants(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    copy_target = tmp_path / "study_defacing_export"

    with patch(
        "src.mri_json_scrubber.prepare_defacing_export_copy",
        return_value={
            "success": True,
            "target_path": str(copy_target),
            "copied_nifti_files": 1,
            "copied_sidecars": 0,
        },
    ) as mock_prepare, patch(
        "src.mri_json_scrubber.deface_anatomical_scans",
        return_value={
            "success": True,
            "message": "Defacing completed successfully.",
            "counts": {"total": 0, "defaced": 0, "already_defaced": 0, "failed": 0, "skipped": 0},
            "items": [],
        },
    ) as mock_deface, patch(
        "src.mri_json_scrubber.build_defacing_report",
        return_value=[],
    ) as mock_report:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/deface",
                json={
                    "project_path": str(project_dir),
                    "selected_variants": ["acq:mprage|suffix:t1w"],
                    "exclude_subjects": ["sub-002", ""],
                    "exclude_sessions": ["ses-2", ""],
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True

    deface_args, deface_kwargs = mock_deface.call_args
    assert deface_args[0] == copy_target.resolve(strict=False)
    assert deface_kwargs.get("selected_variants") == {"acq:mprage|suffix:t1w"}
    assert deface_kwargs.get("excluded_subjects") == {"sub-002"}
    assert deface_kwargs.get("excluded_sessions") == {"ses-2"}

    report_args, report_kwargs = mock_report.call_args
    assert report_args[0] == copy_target.resolve(strict=False)
    assert report_kwargs.get("selected_variants") == {"acq:mprage|suffix:t1w"}
    assert report_kwargs.get("excluded_subjects") == {"sub-002"}
    assert report_kwargs.get("excluded_sessions") == {"ses-2"}

    prepare_args, prepare_kwargs = mock_prepare.call_args
    assert prepare_args[0] == project_dir.resolve(strict=False)
    assert prepare_kwargs.get("selected_variants") == {"acq:mprage|suffix:t1w"}
    assert prepare_kwargs.get("excluded_subjects") == {"sub-002"}
    assert prepare_kwargs.get("excluded_sessions") == {"ses-2"}
    assert prepare_kwargs.get("preserve_datalad_metadata") is False


def test_projects_export_deface_route_uses_export_copy_for_datalad_free_mode(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "exports"
    copy_target = output_dir / "study_defacing_export"

    with patch(
        "src.project_manager.ProjectManager.get_datalad_status",
        return_value={"enabled": True, "available": True},
    ), patch(
        "src.mri_json_scrubber.prepare_defacing_export_copy",
        return_value={
            "success": True,
            "target_path": str(copy_target),
            "copied_nifti_files": 1,
            "copied_sidecars": 1,
        },
    ) as mock_prepare, patch(
        "src.mri_json_scrubber.deface_anatomical_scans",
        return_value={
            "success": True,
            "message": "Defacing completed successfully.",
            "counts": {"total": 1, "defaced": 1, "already_defaced": 0, "failed": 0, "skipped": 0},
            "items": [],
        },
    ) as mock_deface, patch(
        "src.mri_json_scrubber.build_defacing_report",
        return_value=[],
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/deface",
                json={
                    "project_path": str(project_dir),
                    "repository_mode": "datalad_free",
                    "output_folder": str(output_dir),
                    "selected_variants": ["acq:mprage|suffix:t1w"],
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("target_mode") == "export_copy"
    assert payload.get("source_project_path") == str(project_dir.resolve(strict=False))
    assert payload.get("target_path") == str(copy_target.resolve(strict=False))

    prepare_args, prepare_kwargs = mock_prepare.call_args
    assert prepare_args[0] == project_dir.resolve(strict=False)
    assert prepare_args[1] == output_dir.resolve(strict=False)
    assert prepare_kwargs.get("selected_variants") == {"acq:mprage|suffix:t1w"}
    assert prepare_kwargs.get("preserve_datalad_metadata") is False

    deface_args, deface_kwargs = mock_deface.call_args
    assert deface_args[0] == copy_target.resolve(strict=False)
    assert deface_kwargs.get("selected_variants") == {"acq:mprage|suffix:t1w"}


def test_projects_export_deface_route_uses_export_copy_when_datalad_not_enabled(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    copy_target = tmp_path / "study_defacing_export"

    with patch(
        "src.project_manager.ProjectManager.get_datalad_status",
        return_value={"enabled": False, "available": True},
    ), patch(
        "src.mri_json_scrubber.prepare_defacing_export_copy",
        return_value={
            "success": True,
            "target_path": str(copy_target),
            "copied_nifti_files": 1,
            "copied_sidecars": 0,
        },
    ) as mock_prepare, patch(
        "src.mri_json_scrubber.deface_anatomical_scans",
        return_value={
            "success": True,
            "message": "Defacing completed successfully.",
            "counts": {"total": 1, "defaced": 1, "already_defaced": 0, "failed": 0, "skipped": 0},
            "items": [],
        },
    ) as mock_deface, patch(
        "src.mri_json_scrubber.build_defacing_report",
        return_value=[],
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/deface",
                json={
                    "project_path": str(project_dir),
                    "repository_mode": "datalad_preserving",
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("target_mode") == "export_copy"
    assert payload.get("target_path") == str(copy_target.resolve(strict=False))
    assert mock_prepare.called

    prepare_args, prepare_kwargs = mock_prepare.call_args
    assert prepare_args[0] == project_dir.resolve(strict=False)
    assert prepare_kwargs.get("preserve_datalad_metadata") is False

    deface_args, _deface_kwargs = mock_deface.call_args
    assert deface_args[0] == copy_target.resolve(strict=False)


def test_projects_export_deface_route_uses_datalad_preserving_copy_when_enabled(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")
    output_dir = tmp_path / "exports"
    copy_target = output_dir / "study_defacing_export"

    with patch(
        "src.project_manager.ProjectManager.get_datalad_status",
        return_value={"enabled": True, "available": True, "executable": "/usr/bin/datalad"},
    ), patch(
        "src.mri_json_scrubber.prepare_defacing_export_copy",
        return_value={
            "success": True,
            "target_path": str(copy_target),
            "copied_nifti_files": 1,
            "copied_sidecars": 1,
        },
    ) as mock_prepare, patch(
        "src.mri_json_scrubber.deface_anatomical_scans",
        return_value={
            "success": True,
            "message": "Defacing completed successfully.",
            "counts": {"total": 1, "defaced": 1, "already_defaced": 0, "failed": 0, "skipped": 0},
            "items": [],
        },
    ), patch(
        "src.mri_json_scrubber.build_defacing_report",
        return_value=[],
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/deface",
                json={
                    "project_path": str(project_dir),
                    "repository_mode": "datalad_preserving",
                    "output_folder": str(output_dir),
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("target_mode") == "export_copy"
    assert payload.get("target_path") == str(copy_target.resolve(strict=False))

    prepare_args, prepare_kwargs = mock_prepare.call_args
    assert prepare_args[0] == project_dir.resolve(strict=False)
    assert prepare_args[1] == output_dir.resolve(strict=False)
    assert prepare_kwargs.get("preserve_datalad_metadata") is True
    assert prepare_kwargs.get("datalad_executable") == "/usr/bin/datalad"


def test_projects_export_defacing_preflight_route_returns_status(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    with patch(
        "src.mri_json_scrubber.get_defacing_preflight",
        return_value={
            "has_anatomical_data": True,
            "pydeface_available": False,
            "fsl_available": True,
            "can_run_defacing": False,
            "missing_requirements": ["pydeface"],
            "message": "pydeface is not available in this environment.",
        },
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/defacing-preflight",
                json={"project_path": str(project_dir)},
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("has_anatomical_data") is True
    assert payload.get("can_run_defacing") is False
    assert "pydeface" in payload.get("missing_requirements", [])


def test_projects_export_start_upload_ready_preset_forces_safe_export_defaults(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    with patch(
        "src.web.blueprints.projects_export_blueprint.threading.Thread",
        side_effect=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/start",
                json={
                    "project_path": str(project_dir),
                    "anonymize": True,
                    "include_derivatives": True,
                    "include_code": True,
                    "include_analysis": True,
                    "export_preset": "upload_ready",
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("job_id")

    args = captured.get("args")
    assert isinstance(args, tuple)
    export_kwargs = args[1]
    assert isinstance(export_kwargs, dict)
    assert export_kwargs["include_derivatives"] is False
    assert export_kwargs["include_sourcedata"] is False
    assert export_kwargs["include_code"] is False
    assert export_kwargs["include_analysis"] is False
    assert export_kwargs["exclude_version_control_metadata"] is True
    assert args[2] == "study_anonymized_upload_ready_export.zip"


def test_projects_export_start_derives_exclude_metadata_from_repository_mode(tmp_path):
    """repository_mode is authoritative: only datalad_preserving keeps VC metadata."""
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    cases = {
        "datalad_free": True,
        "git_lfs": True,
        "datalad_preserving": False,
    }

    for repository_mode, expected_exclude in cases.items():
        captured: dict[str, object] = {}

        class _FakeThread:
            def __init__(self, target=None, args=(), daemon=None):
                captured["args"] = args

            def start(self):
                captured["started"] = True

        with patch(
            "src.web.blueprints.projects_export_blueprint.threading.Thread",
            side_effect=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
        ):
            with app.test_client() as client:
                response = client.post(
                    "/api/projects/export/start",
                    json={
                        "project_path": str(project_dir),
                        "repository_mode": repository_mode,
                    },
                )

        assert response.status_code == 200
        export_kwargs = captured["args"][1]
        assert export_kwargs["exclude_version_control_metadata"] is expected_exclude, (
            f"repository_mode={repository_mode!r}"
        )


def test_projects_export_start_falls_back_to_legacy_exclude_flag_without_repository_mode(
    tmp_path,
):
    """Callers that don't send repository_mode keep working via the legacy flag."""
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            captured["args"] = args

        def start(self):
            captured["started"] = True

    with patch(
        "src.web.blueprints.projects_export_blueprint.threading.Thread",
        side_effect=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/start",
                json={
                    "project_path": str(project_dir),
                    "exclude_version_control_metadata": True,
                },
            )

    assert response.status_code == 200
    export_kwargs = captured["args"][1]
    assert export_kwargs["exclude_version_control_metadata"] is True


def test_projects_export_sync_route_derives_exclude_metadata_from_repository_mode(
    tmp_path,
):
    """The synchronous /api/projects/export ZIP route applies the same rule."""
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    called: dict[str, object] = {}

    def fake_export_project(**kwargs):
        called.update(kwargs)
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 0, "files_anonymized": 0, "participant_count": 0}

    with patch(
        "src.web.export_project.export_project", side_effect=fake_export_project
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export",
                json={
                    "project_path": str(project_dir),
                    "repository_mode": "git_lfs",
                },
            )

    assert response.status_code == 200
    assert called["exclude_version_control_metadata"] is True


def test_projects_export_start_passes_survey_task_filters_to_export_job(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    with patch(
        "src.web.blueprints.projects_export_blueprint.threading.Thread",
        side_effect=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/start",
                json={
                    "project_path": str(project_dir),
                    "anonymize": False,
                    "exclude_tasks": {"survey": ["ads"]},
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("job_id")

    args = captured.get("args")
    assert isinstance(args, tuple)
    export_kwargs = args[1]
    assert isinstance(export_kwargs, dict)
    assert export_kwargs["exclude_tasks"] == {"survey": {"ads"}}


def test_projects_export_start_forwards_subject_scope_filters_to_export_job(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    class _FakeThread:
        def __init__(self, target=None, args=(), daemon=None):
            captured["target"] = target
            captured["args"] = args
            captured["daemon"] = daemon

        def start(self):
            captured["started"] = True

    with patch(
        "src.web.blueprints.projects_export_blueprint.threading.Thread",
        side_effect=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/start",
                json={
                    "project_path": str(project_dir),
                    "anonymize": False,
                    "exclude_subjects": ["sub-002", ""],
                    "exclude_sessions": ["ses-2", ""],
                    "exclude_modalities": ["dwi", ""],
                    "exclude_acq": {"anat": ["T1w", ""]},
                    "exclude_tasks": {"survey": ["ads", ""]},
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("job_id")

    args = captured.get("args")
    assert isinstance(args, tuple)
    export_kwargs = args[1]
    assert isinstance(export_kwargs, dict)
    assert export_kwargs["exclude_subjects"] == {"sub-002"}
    assert export_kwargs["exclude_sessions"] == {"ses-2"}
    assert export_kwargs["exclude_modalities"] == {"dwi"}
    assert export_kwargs["exclude_acq"] == {"anat": {"T1w"}}
    assert export_kwargs["exclude_tasks"] == {"survey": {"ads"}}


def test_projects_export_sync_route_forwards_scope_filters(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    called: dict[str, object] = {}

    def fake_export_project(**kwargs):
        called.update(kwargs)
        output_zip = kwargs["output_zip"]
        Path(output_zip).write_bytes(b"PK\x03\x04")
        return {"files_processed": 0, "files_anonymized": 0, "participant_count": 0}

    with patch(
        "src.web.export_project.export_project", side_effect=fake_export_project
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export",
                json={
                    "project_path": str(project_dir),
                    "anonymize": False,
                    "exclude_subjects": ["sub-003", ""],
                    "exclude_sessions": ["ses-2", ""],
                    "exclude_modalities": ["dwi", ""],
                    "exclude_acq": {"anat": ["T1w", ""]},
                    "exclude_tasks": {"survey": ["ads", ""]},
                },
            )

    assert response.status_code == 200
    assert called["exclude_subjects"] == {"sub-003"}
    assert called["exclude_sessions"] == {"ses-2"}
    assert called["exclude_modalities"] == {"dwi"}
    assert called["exclude_acq"] == {"anat": {"T1w"}}
    assert called["exclude_tasks"] == {"survey": {"ads"}}


def test_projects_export_start_status_includes_defacing_warning_metadata(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    class _FakeThread:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            pass

    with patch(
        "src.web.blueprints.projects_export_blueprint.threading.Thread",
        side_effect=lambda *args, **kwargs: _FakeThread(*args, **kwargs),
    ):
        with patch(
            "src.mri_json_scrubber.build_defacing_report",
            return_value=[
                {"status": "defaced", "file": "sub-001/anat/sub-001_T1w.json"},
                {"status": "not_defaced", "file": "sub-002/anat/sub-002_T1w.json"},
                {"status": "unknown", "file": "sub-003/anat/sub-003_T1w.json"},
            ],
        ):
            with app.test_client() as client:
                start_resp = client.post(
                    "/api/projects/export/start",
                    json={
                        "project_path": str(project_dir),
                        "anonymize": False,
                        "mask_questions": False,
                        "scrub_mri_json": True,
                        "include_derivatives": False,
                        "include_code": False,
                        "include_analysis": False,
                    },
                )

                assert start_resp.status_code == 200
                payload = start_resp.get_json() or {}
                job_id = payload.get("job_id")
                assert job_id

                status_resp = client.get(
                    f"/api/projects/export/{job_id}/status"
                )

    assert status_resp.status_code == 200
    status_payload = status_resp.get_json() or {}
    warning = status_payload.get("defacing_warning") or {}

    assert warning.get("risk_count") == 2
    assert warning.get("counts", {}).get("defaced") == 1
    assert warning.get("counts", {}).get("not_defaced") == 1
    assert warning.get("counts", {}).get("unknown") == 1
    assert "warning-only" in str(warning.get("message", ""))


def test_export_status_payload_does_not_expose_mapping_metadata(tmp_path):
    app = _build_app()

    zip_path = tmp_path / "saved-export.zip"
    zip_path.write_bytes(b"PK\x03\x04")
    job_id = "job-status"

    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
        now = time.monotonic()
        projects_export_module._export_jobs[job_id] = {
            "status": "complete",
            "percent": 100,
            "message": "Export complete",
            "zip_path": str(zip_path),
            "filename": "saved-export.zip",
            "mapping_file": str(tmp_path / "code" / "anonymization_map.json"),
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": now,
            "updated_at": now,
            "done_at": now,
        }

    with app.test_client() as client:
        response = client.get(f"/api/projects/export/{job_id}/status")

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("status") == "complete"
    assert payload.get("zip_path") == str(zip_path)
    assert "mapping_file" not in payload


def test_projects_export_sync_response_cleans_temp_zip_after_close(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    temp_zip = tmp_path / "response-export.zip"
    captured = {}

    def fake_mkstemp(suffix=".zip"):
        fd = os.open(temp_zip, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o600)
        return fd, str(temp_zip)

    def fake_export_project(**kwargs):
        captured["output_zip"] = kwargs["output_zip"]
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 0, "files_anonymized": 0, "participant_count": 0}

    with patch(
        "src.web.blueprints.projects_export_blueprint.tempfile.mkstemp",
        side_effect=fake_mkstemp,
    ):
        with patch(
            "src.web.export_project.export_project", side_effect=fake_export_project
        ):
            with app.test_client() as client:
                response = client.post(
                    "/api/projects/export",
                    json={
                        "project_path": str(project_dir),
                        "anonymize": False,
                        "mask_questions": False,
                    },
                )

    assert response.status_code == 200
    assert Path(captured["output_zip"]) == temp_zip
    assert temp_zip.exists()

    _ = response.get_data()

    assert not temp_zip.exists()


def test_export_download_keeps_saved_zip_and_cleans_job_after_close(tmp_path):
    app = _build_app()

    zip_path = tmp_path / "saved-export.zip"
    zip_path.write_bytes(b"PK\x03\x04")
    job_id = "job-download"

    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
        now = time.monotonic()
        projects_export_module._export_jobs[job_id] = {
            "status": "complete",
            "percent": 100,
            "message": "Export complete",
            "zip_path": str(zip_path),
            "filename": "saved-export.zip",
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": now,
            "updated_at": now,
            "done_at": now,
        }

    with app.test_client() as client:
        response = client.get(f"/api/projects/export/{job_id}/download")

    assert response.status_code == 200
    assert zip_path.exists()

    _ = response.get_data()

    assert zip_path.exists()
    with projects_export_module._export_lock:
        assert job_id not in projects_export_module._export_jobs


def test_export_job_store_prunes_done_jobs_after_ttl(monkeypatch):
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
        projects_export_module._last_export_prune_at = 0.0
        projects_export_module._export_jobs["expired"] = {
            "status": "complete",
            "percent": 100,
            "message": "old",
            "zip_path": "/tmp/old.zip",
            "filename": "old.zip",
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": 0.0,
            "updated_at": 0.0,
            "done_at": 10.0,
        }
        projects_export_module._export_jobs["active"] = {
            "status": "running",
            "percent": 25,
            "message": "running",
            "zip_path": None,
            "filename": None,
            "error": None,
            "cancel_event": threading.Event(),
            "created_at": 100.0,
            "updated_at": 100.0,
            "done_at": None,
        }

    monkeypatch.setattr(projects_export_module, "_EXPORT_JOB_TTL_SECONDS", 50.0)
    monkeypatch.setattr(
        projects_export_module, "_EXPORT_JOB_PRUNE_INTERVAL_SECONDS", 0.0
    )
    monkeypatch.setattr(projects_export_module, "_export_now", lambda: 100.0)

    active_job = projects_export_module._get_export_job("active")

    assert active_job["status"] == "running"
    with projects_export_module._export_lock:
        assert "expired" not in projects_export_module._export_jobs
        assert "active" in projects_export_module._export_jobs


def test_export_job_blocks_when_pre_export_validation_has_errors(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    output_dir = tmp_path / "exports"
    job_id = "job-validation-errors"
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
    projects_export_module._create_export_job(job_id)

    export_kwargs = {
        "project_path": project_dir,
        "validation_mode": "both",
    }

    with patch(
        "src.web.validation.run_validation",
        return_value=(
            [("ERROR", "Broken dataset", str(project_dir))],
            SimpleNamespace(total_files=1),
        ),
    ):
        with patch("src.web.export_project.export_project") as mock_do_export:
            projects_export_module._run_export_job(
                job_id,
                export_kwargs,
                "study_export.zip",
                str(output_dir),
            )

    job = projects_export_module._get_export_job(job_id)
    assert job["status"] == "error"
    assert "Export blocked" in (job.get("error") or "")
    mock_do_export.assert_not_called()


def test_export_job_allows_warnings_only_pre_export_validation(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    output_dir = tmp_path / "exports"
    job_id = "job-validation-warnings"
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
    projects_export_module._create_export_job(job_id)

    def fake_export_project(**kwargs):
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 1, "files_anonymized": 0, "participant_count": 0}

    export_kwargs = {
        "project_path": project_dir,
        "validation_mode": "prism",
    }

    with patch(
        "src.web.validation.run_validation",
        return_value=(
            [("WARNING", "Missing optional metadata", str(project_dir))],
            SimpleNamespace(total_files=1),
        ),
    ):
        with patch(
            "src.web.export_project.export_project",
            side_effect=fake_export_project,
        ):
            projects_export_module._run_export_job(
                job_id,
                export_kwargs,
                "study_export.zip",
                str(output_dir),
            )

    job = projects_export_module._get_export_job(job_id)
    assert job["status"] == "complete"
    assert Path(job["zip_path"]).exists()


def test_export_job_skips_validation_when_mode_is_ignore(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    output_dir = tmp_path / "exports"
    job_id = "job-validation-ignore"
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
    projects_export_module._create_export_job(job_id)

    def fake_export_project(**kwargs):
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 1, "files_anonymized": 0, "participant_count": 0}

    export_kwargs = {
        "project_path": project_dir,
        "validation_mode": "ignore",
    }

    with patch("src.web.validation.run_validation") as mock_run_validation:
        with patch(
            "src.web.export_project.export_project",
            side_effect=fake_export_project,
        ):
            projects_export_module._run_export_job(
                job_id,
                export_kwargs,
                "study_export.zip",
                str(output_dir),
            )

    job = projects_export_module._get_export_job(job_id)
    assert job["status"] == "complete"
    mock_run_validation.assert_not_called()


def test_export_job_does_not_block_on_non_error_issue_levels(tmp_path):
    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    output_dir = tmp_path / "exports"
    job_id = "job-validation-info-only"
    with projects_export_module._export_lock:
        projects_export_module._export_jobs.clear()
    projects_export_module._create_export_job(job_id)

    def fake_export_project(**kwargs):
        Path(kwargs["output_zip"]).write_bytes(b"PK\x03\x04")
        return {"files_processed": 1, "files_anonymized": 0, "participant_count": 0}

    export_kwargs = {
        "project_path": project_dir,
        "validation_mode": "both",
    }

    with patch(
        "src.web.validation.run_validation",
        return_value=(
            [("INFO", "Dataset summary information", str(project_dir))],
            SimpleNamespace(total_files=1),
        ),
    ):
        with patch(
            "src.web.export_project.export_project",
            side_effect=fake_export_project,
        ):
            projects_export_module._run_export_job(
                job_id,
                export_kwargs,
                "study_export.zip",
                str(output_dir),
            )

    job = projects_export_module._get_export_job(job_id)
    assert job["status"] == "complete"


def test_template_export_route_uses_backend_exporter_and_output_folder(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "exports"
    captured: dict[str, object] = {}

    def fake_template_export(project_path, output_zip):
        captured["project_path"] = project_path
        captured["output_zip"] = output_zip
        Path(output_zip).write_bytes(b"PK\x03\x04")
        return {"files_written": 1, "files_skipped": 2}

    with patch(
        "src.project_template_export.export_project_template_zip",
        side_effect=fake_template_export,
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/template-export",
                json={
                    "project_path": str(project_dir),
                    "output_folder": str(out_dir),
                    "validation_mode": "ignore",
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("output_path", "").endswith("study_template_export.zip")
    assert captured["project_path"] == project_dir
    assert captured["output_zip"] == out_dir / "study_template_export.zip"


def test_template_export_route_blocks_when_validation_fails(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    with patch(
        "src.web.blueprints.projects_export_blueprint._run_pre_export_validation",
        return_value="Export blocked: validation found errors.",
    ):
        with patch(
            "src.project_template_export.export_project_template_zip"
        ) as mock_export:
            with app.test_client() as client:
                response = client.post(
                    "/api/projects/template-export",
                    json={
                        "project_path": str(project_dir),
                        "validation_mode": "both",
                    },
                )

    assert response.status_code == 400
    payload = response.get_json() or {}
    assert payload.get("success") is False
    assert "Export blocked" in str(payload.get("error", ""))
    mock_export.assert_not_called()


def test_project_folder_export_route_uses_project_manager_and_output_folder(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / ".datalad").mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "exports"

    with patch(
        "src.project_manager.ProjectManager.export_project_to_plain_folder",
        return_value={
            "success": True,
            "output_path": str(out_dir / "study_folder_export"),
            "excluded_repository_metadata": [".datalad", ".git"],
            "message": "ok",
        },
    ) as mock_export:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/folder",
                json={
                    "project_path": str(project_dir),
                    "output_folder": str(out_dir),
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("output_path", "").endswith("study_folder_export")
    assert payload.get("excluded_repository_metadata") == [".datalad", ".git"]
    mock_export.assert_called_once_with(
        project_dir,
        output_root=str(out_dir),
    )


def test_project_git_lfs_export_route_uses_project_manager_and_output_folder(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "exports"

    with patch(
        "src.project_manager.ProjectManager.export_project_to_git_lfs_folder",
        return_value={
            "success": True,
            "output_path": str(out_dir / "study_folder_export"),
            "excluded_repository_metadata": [".datalad", ".git"],
            "git_lfs": {"repo_initialized": True},
            "message": "ok",
        },
    ) as mock_export:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/git-lfs",
                json={
                    "project_path": str(project_dir),
                    "output_folder": str(out_dir),
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("output_path", "").endswith("study_folder_export")
    assert payload.get("git_lfs", {}).get("repo_initialized") is True
    mock_export.assert_called_once_with(
        project_dir,
        output_root=str(out_dir),
        init_git_lfs_repo=True,
    )


def test_project_git_lfs_export_route_forwards_init_repo_false(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    with patch(
        "src.project_manager.ProjectManager.export_project_to_git_lfs_folder",
        return_value={"success": True, "output_path": str(project_dir), "git_lfs": {}},
    ) as mock_export:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/git-lfs",
                json={
                    "project_path": str(project_dir),
                    "init_git_lfs_repo": False,
                },
            )

    assert response.status_code == 200
    mock_export.assert_called_once_with(
        project_dir,
        output_root=None,
        init_git_lfs_repo=False,
    )


def test_project_folder_export_route_forwards_scope_filters(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "exports"

    with patch(
        "src.project_manager.ProjectManager.export_project_to_plain_folder",
        return_value={
            "success": True,
            "output_path": str(out_dir / "study_folder_export"),
            "excluded_repository_metadata": [".datalad", ".git"],
            "message": "ok",
        },
    ) as mock_export:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/folder",
                json={
                    "project_path": str(project_dir),
                    "output_folder": str(out_dir),
                    "include_derivatives": False,
                    "include_sourcedata": True,
                    "include_code": True,
                    "include_analysis": False,
                    "exclude_sessions": ["ses-2", ""],
                    "exclude_modalities": ["dwi"],
                    "exclude_acq": {"dwi": ["1k20", ""]},
                    "exclude_tasks": {"func": ["rest"]},
                    "materialize_annex_content": True,
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    mock_export.assert_called_once_with(
        project_dir,
        output_root=str(out_dir),
        include_derivatives=False,
        include_sourcedata=True,
        include_code=True,
        include_analysis=False,
        exclude_sessions={"ses-2"},
        exclude_modalities={"dwi"},
        exclude_acq={"dwi": {"1k20"}},
        exclude_tasks={"func": {"rest"}},
        materialize_annex_content=True,
    )


def test_project_folder_export_route_forwards_mri_scrub_options(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "exports"

    with patch(
        "src.project_manager.ProjectManager.export_project_to_plain_folder",
        return_value={
            "success": True,
            "output_path": str(out_dir / "study_folder_export"),
            "excluded_repository_metadata": [".datalad", ".git"],
            "message": "ok",
        },
    ) as mock_export:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/folder",
                json={
                    "project_path": str(project_dir),
                    "output_folder": str(out_dir),
                    "scrub_mri_json": True,
                    "scrub_mri_json_groups": ["scanner_site", "timestamps"],
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    mock_export.assert_called_once_with(
        project_dir,
        output_root=str(out_dir),
        scrub_mri_json=True,
        scrub_mri_json_groups={"scanner_site", "timestamps"},
    )


def test_project_folder_export_route_forwards_subject_scope_filter(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    out_dir = tmp_path / "exports"

    with patch(
        "src.project_manager.ProjectManager.export_project_to_plain_folder",
        return_value={
            "success": True,
            "output_path": str(out_dir / "study_folder_export"),
            "excluded_repository_metadata": [".datalad", ".git"],
            "message": "ok",
        },
    ) as mock_export:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/folder",
                json={
                    "project_path": str(project_dir),
                    "output_folder": str(out_dir),
                    "exclude_subjects": ["sub-002", ""],
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    mock_export.assert_called_once_with(
        project_dir,
        output_root=str(out_dir),
        exclude_subjects={"sub-002"},
        include_derivatives=True,
        include_sourcedata=False,
        include_code=True,
        include_analysis=True,
        exclude_sessions=None,
        exclude_modalities=None,
        exclude_acq=None,
        exclude_tasks=None,
        materialize_annex_content=False,
    )


def test_project_annex_availability_route_uses_project_manager(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    with patch(
        "src.project_manager.ProjectManager.preview_plain_folder_export_availability",
        return_value={
            "success": True,
            "missing_files_count": 3,
            "missing_files_preview": ["sub-001/ses-1/anat/sub-001_T1w.nii.gz"],
            "message": "Detected 3 missing files.",
        },
    ) as mock_preview:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/annex-availability",
                json={
                    "project_path": str(project_dir),
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("missing_files_count") == 3
    mock_preview.assert_called_once_with(
        project_dir,
        include_derivatives=True,
        include_sourcedata=False,
        include_code=True,
        include_analysis=True,
        exclude_sessions=None,
        exclude_modalities=None,
        exclude_acq=None,
        exclude_tasks=None,
    )


def test_project_annex_availability_route_forwards_scope_filters(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    with patch(
        "src.project_manager.ProjectManager.preview_plain_folder_export_availability",
        return_value={"success": True, "missing_files_count": 0},
    ) as mock_preview:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/annex-availability",
                json={
                    "project_path": str(project_dir),
                    "include_derivatives": False,
                    "include_sourcedata": True,
                    "include_code": True,
                    "include_analysis": False,
                    "exclude_sessions": ["ses-2", ""],
                    "exclude_modalities": ["dwi"],
                    "exclude_acq": {"dwi": ["1k20", ""]},
                    "exclude_tasks": {"func": ["rest"]},
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    mock_preview.assert_called_once_with(
        project_dir,
        include_derivatives=False,
        include_sourcedata=True,
        include_code=True,
        include_analysis=False,
        exclude_sessions={"ses-2"},
        exclude_modalities={"dwi"},
        exclude_acq={"dwi": {"1k20"}},
        exclude_tasks={"func": {"rest"}},
    )


def test_project_annex_availability_route_forwards_subject_scope_filter(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    with patch(
        "src.project_manager.ProjectManager.preview_plain_folder_export_availability",
        return_value={"success": True, "missing_files_count": 0},
    ) as mock_preview:
        with app.test_client() as client:
            response = client.post(
                "/api/projects/export/annex-availability",
                json={
                    "project_path": str(project_dir),
                    "exclude_subjects": ["sub-003", ""],
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    mock_preview.assert_called_once_with(
        project_dir,
        include_derivatives=True,
        include_sourcedata=False,
        include_code=True,
        include_analysis=True,
        exclude_subjects={"sub-003"},
        exclude_sessions=None,
        exclude_modalities=None,
        exclude_acq=None,
        exclude_tasks=None,
    )


def test_openminds_get_tasks_returns_sorted_task_names(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text(
        '{"TaskDefinitions": {"rest": {}, "nback": {}}}', encoding="utf-8"
    )

    with app.test_client() as client:
        response = client.get(
            "/api/projects/openminds-tasks",
            query_string={"project_path": str(project_dir)},
        )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("tasks") == ["nback", "rest"]


def test_openminds_get_tasks_returns_empty_list_without_project_json(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)

    with app.test_client() as client:
        response = client.get(
            "/api/projects/openminds-tasks",
            query_string={"project_path": str(project_dir)},
        )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("tasks") == []


def test_openminds_get_tasks_rejects_invalid_project_path():
    app = _build_app()

    with app.test_client() as client:
        response = client.get(
            "/api/projects/openminds-tasks",
            query_string={"project_path": "/does/not/exist"},
        )

    assert response.status_code == 400
    payload = response.get_json() or {}
    assert payload.get("success") is False


def test_openminds_export_reports_missing_cli_with_actionable_error(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    # Force both the direct venv-bin-dir lookup and the PATH fallback to miss,
    # regardless of whether bids2openminds happens to be installed in the
    # environment running this test suite.
    with patch("pathlib.Path.is_file", return_value=False), patch(
        "shutil.which",
        return_value=None,
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/openminds-export",
                json={"project_path": str(project_dir)},
            )

    assert response.status_code == 500
    payload = response.get_json() or {}
    assert payload.get("success") is False
    assert "bids2openminds" in payload.get("error", "")
    assert "pip install" in payload.get("error", "")


def test_openminds_export_runs_bids2openminds_and_reports_success(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    def fake_run(cmd, **kwargs):
        # bids2openminds writes its output file as a side effect of running.
        output_path = Path(cmd[cmd.index("-o") + 1])
        output_path.write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    with patch(
        "shutil.which",
        return_value="/usr/bin/bids2openminds",
    ), patch(
        "src.web.blueprints.projects_export_blueprint.subprocess.run",
        side_effect=fake_run,
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/openminds-export",
                json={
                    "project_path": str(project_dir),
                    "single_file": True,
                    "include_empty": False,
                },
            )

    assert response.status_code == 200
    payload = response.get_json() or {}
    assert payload.get("success") is True
    assert payload.get("output_path", "").endswith("_openminds.jsonld")
    assert Path(payload["output_path"]).exists()


def test_openminds_export_reports_bids2openminds_failure(tmp_path):
    app = _build_app()

    project_dir = tmp_path / "study"
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "project.json").write_text("{}", encoding="utf-8")

    with patch(
        "shutil.which",
        return_value="/usr/bin/bids2openminds",
    ), patch(
        "src.web.blueprints.projects_export_blueprint.subprocess.run",
        return_value=SimpleNamespace(
            returncode=1, stdout="", stderr="conversion failed: unsupported BIDS layout"
        ),
    ):
        with app.test_client() as client:
            response = client.post(
                "/api/projects/openminds-export",
                json={"project_path": str(project_dir)},
            )

    assert response.status_code == 500
    payload = response.get_json() or {}
    assert payload.get("success") is False
    assert "conversion failed" in payload.get("error", "")
