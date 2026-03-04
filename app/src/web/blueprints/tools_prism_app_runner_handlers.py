from pathlib import Path

from flask import jsonify, render_template

from src.derivatives.apps_runner_compat import (
    build_compatibility_report,
    delete_remote_profile,
    get_remote_profile,
    list_apptainer_images,
    list_docker_tags,
    list_remote_profiles,
    load_app_help,
    pull_docker_image,
    run_runner_with_project,
    save_remote_profile,
)


PRISM_APP_RUNNER_ENABLED = False
PRISM_APP_RUNNER_DISABLED_MESSAGE = (
    "PRISM App Runner is temporarily disabled while under construction."
)


def _disabled_payload() -> tuple[dict, int]:
    return {
        "error": PRISM_APP_RUNNER_DISABLED_MESSAGE,
        "status": "disabled",
    }, 503


def _resolve_local_runner_repo(project_root: Path) -> Path | None:
    candidates = [
        project_root / "code" / "bids_apps_runner",
        project_root / "code",
    ]
    for candidate in candidates:
        if (candidate / "scripts" / "prism_runner.py").exists():
            return candidate
    return None


def _app_bids_precheck(project_root: Path, app_name: str) -> list[str]:
    errors: list[str] = []

    if not (project_root / "dataset_description.json").exists():
        errors.append("dataset_description.json is missing in the current project root")

    if not any(project_root.glob("sub-*")):
        errors.append("No subject folders (sub-*) were found in the current project root")

    app = (app_name or "").strip().lower()

    def has_pattern(pattern: str) -> bool:
        return any(project_root.rglob(pattern))

    if app == "fmriprep" and not has_pattern("*_bold.nii*"):
        errors.append("fMRIPrep requires fMRI BOLD NIfTI files (*_bold.nii or *_bold.nii.gz)")
    elif app in {"qsiprep", "dsi_studio"} and not has_pattern("*_dwi.nii*"):
        errors.append(f"{app_name} requires diffusion NIfTI files (*_dwi.nii or *_dwi.nii.gz)")
    elif app == "freesurfer" and not has_pattern("*_T1w.nii*"):
        errors.append("FreeSurfer requires anatomical T1w NIfTI files (*_T1w.nii or *_T1w.nii.gz)")

    return errors


def handle_prism_app_runner(project_path: str | None):
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

    default_runner_repo_path = ""
    default_bids_folder = ""
    default_output_folder = ""
    default_tmp_folder = ""
    if project_path:
        project_root = Path(project_path).expanduser()
        resolved = _resolve_local_runner_repo(project_root)
        default_runner_repo_path = str(resolved) if resolved else str(project_root / "code" / "bids_apps_runner")

        default_bids_folder = str(project_root)
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
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

    project_path = (data.get("project_path") or "").strip() or None
    runner_repo_path = None

    config_path = None
    if project_path:
        project_root = Path(project_path).expanduser()
        resolved = _resolve_local_runner_repo(project_root)
        runner_repo_path = str(resolved) if resolved else str(project_root / "code" / "bids_apps_runner")
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
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

    active_project = (project_path or "").strip()
    if not active_project:
        return jsonify({"error": "No active PRISM project loaded."}), 400

    project_root = Path(active_project).expanduser()

    runner_repo_path = (data.get("runner_repo_path") or "").strip()
    execution_target = (data.get("execution_target") or "local").strip().lower()
    remote_profile = data.get("remote") if isinstance(data.get("remote"), dict) else {}

    if execution_target == "remote_ssh" and not runner_repo_path:
        runner_repo_path = str(remote_profile.get("runner_repo_path") or "").strip()
    elif execution_target != "remote_ssh" and not runner_repo_path:
        resolved = _resolve_local_runner_repo(project_root)
        runner_repo_path = str(resolved) if resolved else ""

    app_name = (data.get("app_name") or "").strip()
    container_engine = (data.get("container_engine") or "docker").strip()
    container = (data.get("container") or "").strip()

    if not runner_repo_path:
        return jsonify({"error": "Runner repository path is required."}), 400
    if not app_name:
        return jsonify({"error": "BIDS app name is required."}), 400
    if not container:
        return jsonify({"error": "Container path/image is required."}), 400

    precheck_errors = _app_bids_precheck(project_root, app_name)
    if precheck_errors:
        return jsonify({"error": "BIDS precheck failed: " + "; ".join(precheck_errors)}), 400

    output_subdir = app_name.strip().replace(" ", "_")
    fixed_bids_folder = str(project_root)
    fixed_output_folder = str(project_root / "derivatives" / output_subdir)
    fixed_tmp_folder = str(project_root / "derivatives" / "apps_runner" / "tmp")

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
            output_subdir=output_subdir,
            bids_folder=fixed_bids_folder,
            output_folder=fixed_output_folder,
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
            tmp_folder=fixed_tmp_folder,
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
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

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
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

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


def handle_api_prism_app_runner_docker_tags(data: dict):
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

    repository = (data.get("repository") or "").strip()
    if not repository:
        return jsonify({"error": "repository is required."}), 400

    try:
        result = list_docker_tags(repository=repository)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Could not load Docker tags: {exc}"}), 500

    return jsonify(result), 200


def handle_api_prism_app_runner_docker_pull(data: dict):
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

    image = (data.get("image") or "").strip()
    if not image:
        return jsonify({"error": "image is required."}), 400

    try:
        result = pull_docker_image(image=image)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Could not pull Docker image: {exc}"}), 500

    status_code = 200 if result.get("success") else 207
    return jsonify(result), status_code


def handle_api_prism_app_runner_list_profiles(project_path: str | None):
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

    active_project = (project_path or "").strip()
    if not active_project:
        return jsonify({"error": "No active PRISM project loaded."}), 400

    try:
        result = list_remote_profiles(active_project)
    except Exception as exc:
        return jsonify({"error": f"Could not list remote profiles: {exc}"}), 500
    return jsonify(result), 200


def handle_api_prism_app_runner_get_profile(project_path: str | None, profile_name: str):
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

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
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

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
    if not PRISM_APP_RUNNER_ENABLED:
        payload, status = _disabled_payload()
        return jsonify(payload), status

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
