from pathlib import Path

from flask import jsonify, render_template

from src.derivatives.apps_runner_compat import (
    build_compatibility_report,
    delete_remote_profile,
    get_remote_profile,
    list_apptainer_images,
    list_remote_profiles,
    load_app_help,
    run_runner_with_project,
    save_remote_profile,
)


def handle_prism_app_runner(project_path: str | None):
    default_runner_repo_path = ""
    default_bids_folder = ""
    default_output_folder = ""
    default_tmp_folder = ""
    if project_path:
        project_root = Path(project_path).expanduser()
        code_dir = project_root / "code"
        default_repo_candidate = code_dir / "bids_apps_runner"
        if default_repo_candidate.exists() and default_repo_candidate.is_dir():
            default_runner_repo_path = str(default_repo_candidate)
        elif code_dir.exists() and code_dir.is_dir():
            default_runner_repo_path = str(code_dir)

        rawdata = project_root / "rawdata"
        default_bids_folder = str(rawdata if rawdata.is_dir() else project_root)
        default_output_folder = str(project_root / "derivatives")
        default_tmp_folder = str(project_root / "derivatives" / "apps_runner" / "tmp")

    return render_template(
        "prism_app_runner.html",
        default_runner_repo_path=default_runner_repo_path,
        default_bids_folder=default_bids_folder,
        default_output_folder=default_output_folder,
        default_tmp_folder=default_tmp_folder,
    )


def handle_api_prism_app_runner_compatibility(data: dict):
    project_path = (data.get("project_path") or "").strip() or None
    runner_repo_path = (data.get("runner_repo_path") or "").strip() or None

    config_path = None
    if project_path:
        project_root = Path(project_path).expanduser()
        code_project = project_root / "code" / "project.json"
        root_project = project_root / "project.json"
        if code_project.exists():
            config_path = str(code_project)
        elif root_project.exists():
            config_path = str(root_project)

    report = build_compatibility_report(
        project_path=project_path,
        runner_repo_path=runner_repo_path,
        config_path=config_path,
        config_json=None,
    )
    return jsonify(report), 200


def handle_api_prism_app_runner_run(data: dict, project_path: str | None):
    active_project = (project_path or "").strip()
    if not active_project:
        return jsonify({"error": "No active PRISM project loaded."}), 400

    runner_repo_path = (data.get("runner_repo_path") or "").strip()
    execution_target = (data.get("execution_target") or "local").strip().lower()
    remote_profile = data.get("remote") if isinstance(data.get("remote"), dict) else {}

    if execution_target == "remote_ssh" and not runner_repo_path:
        runner_repo_path = str(remote_profile.get("runner_repo_path") or "").strip()

    app_name = (data.get("app_name") or "").strip()
    container_engine = (data.get("container_engine") or "docker").strip()
    container = (data.get("container") or "").strip()

    if not runner_repo_path:
        return jsonify({"error": "Runner repository path is required."}), 400
    if not app_name:
        return jsonify({"error": "BIDS app name is required."}), 400
    if not container:
        return jsonify({"error": "Container path/image is required."}), 400

    try:
        result = run_runner_with_project(
            project_path=active_project,
            runner_repo_path=runner_repo_path,
            app_name=app_name,
            container_engine=container_engine,
            container=container,
            mode=(data.get("mode") or "local"),
            dry_run=bool(data.get("dry_run", True)),
            analysis_level=(data.get("analysis_level") or "participant"),
            output_subdir=(data.get("output_subdir") or None),
            bids_folder=(data.get("bids_folder") or None),
            output_folder=(data.get("output_folder") or None),
            jobs=int(data.get("jobs") or 1),
            subjects=data.get("subjects"),
            monitor=bool(data.get("monitor", False)),
            slurm_only=bool(data.get("slurm_only", False)),
            log_level=(data.get("log_level") or "INFO"),
            timeout_seconds=int(data.get("timeout_seconds") or 180),
            app_options=(data.get("app_options") if isinstance(data.get("app_options"), dict) else None),
            hpc=(data.get("hpc") if isinstance(data.get("hpc"), dict) else None),
            datalad=(data.get("datalad") if isinstance(data.get("datalad"), dict) else None),
            apptainer_args=(data.get("apptainer_args") or None),
            mounts=(data.get("mounts") if isinstance(data.get("mounts"), list) else None),
            templateflow_dir=(data.get("templateflow_dir") or None),
            tmp_folder=(data.get("tmp_folder") or None),
            execution_target=execution_target,
            remote=remote_profile,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Runner execution failed: {exc}"}), 500

    status_code = 200 if result.get("success") else 207
    return jsonify(result), status_code


def handle_api_prism_app_runner_scan_images(data: dict):
    images_folder = (data.get("images_folder") or "").strip()
    if not images_folder:
        return jsonify({"error": "images_folder is required."}), 400

    try:
        result = list_apptainer_images(images_folder)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Could not scan images: {exc}"}), 500

    return jsonify(result), 200


def handle_api_prism_app_runner_help(data: dict):
    container_engine = (data.get("container_engine") or "apptainer").strip()
    container = (data.get("container") or "").strip()
    timeout_seconds = int(data.get("timeout_seconds") or 30)

    try:
        result = load_app_help(
            container_engine=container_engine,
            container=container,
            timeout_seconds=timeout_seconds,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Could not load app help: {exc}"}), 500

    return jsonify(result), 200


def handle_api_prism_app_runner_list_profiles(project_path: str | None):
    active_project = (project_path or "").strip()
    if not active_project:
        return jsonify({"error": "No active PRISM project loaded."}), 400

    try:
        result = list_remote_profiles(active_project)
    except Exception as exc:
        return jsonify({"error": f"Could not list remote profiles: {exc}"}), 500
    return jsonify(result), 200


def handle_api_prism_app_runner_get_profile(project_path: str | None, profile_name: str):
    active_project = (project_path or "").strip()
    if not active_project:
        return jsonify({"error": "No active PRISM project loaded."}), 400
    try:
        result = get_remote_profile(active_project, profile_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"Could not load profile: {exc}"}), 500
    return jsonify(result), 200


def handle_api_prism_app_runner_save_profile(data: dict, project_path: str | None):
    active_project = (project_path or "").strip()
    if not active_project:
        return jsonify({"error": "No active PRISM project loaded."}), 400

    profile_name = (data.get("name") or "").strip()
    remote_config = data.get("remote") if isinstance(data.get("remote"), dict) else {}

    try:
        result = save_remote_profile(active_project, profile_name, remote_config)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Could not save profile: {exc}"}), 500
    return jsonify(result), 200


def handle_api_prism_app_runner_delete_profile(project_path: str | None, profile_name: str):
    active_project = (project_path or "").strip()
    if not active_project:
        return jsonify({"error": "No active PRISM project loaded."}), 400

    try:
        result = delete_remote_profile(active_project, profile_name)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:
        return jsonify({"error": f"Could not delete profile: {exc}"}), 500
    return jsonify(result), 200
