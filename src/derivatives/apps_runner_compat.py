import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken

from src.cross_platform import safe_path_join

SUPPORTED_ENGINES = {"apptainer", "singularity", "docker"}


def _get_fernet() -> Optional[Fernet]:
    key = (os.environ.get("PRISM_REMOTE_PROFILE_ENC_KEY") or "").strip()
    if not key:
        return None
    try:
        return Fernet(key.encode("utf-8"))
    except Exception as exc:
        raise ValueError(
            "PRISM_REMOTE_PROFILE_ENC_KEY is invalid. Provide a valid Fernet key."
        ) from exc


def _encrypt_secret(value: str) -> str:
    fernet = _get_fernet()
    if fernet is None:
        raise ValueError(
            "Encrypted secret storage requires PRISM_REMOTE_PROFILE_ENC_KEY to be set."
        )
    token = fernet.encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def _decrypt_secret(token: str) -> str:
    fernet = _get_fernet()
    if fernet is None:
        raise ValueError(
            "Decrypting secrets requires PRISM_REMOTE_PROFILE_ENC_KEY to be set."
        )
    try:
        value = fernet.decrypt(token.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError(
            "Could not decrypt stored passphrase (invalid token/key)."
        ) from exc
    return value.decode("utf-8")


def _profiles_file(project_path: str) -> Path:
    project_root = Path(project_path).expanduser().resolve()
    apps_runner_root = Path(
        safe_path_join(str(project_root), "derivatives", "apps_runner")
    )
    apps_runner_root.mkdir(parents=True, exist_ok=True)
    return Path(safe_path_join(str(apps_runner_root), "remote_profiles.json"))


def _normalize_profile_name(name: str) -> str:
    profile_name = (name or "").strip()
    if not profile_name:
        raise ValueError("Profile name is required.")
    safe = re.sub(r"[^a-zA-Z0-9_.\- ]+", "", profile_name).strip()
    if not safe:
        raise ValueError("Profile name contains no valid characters.")
    return safe


def _load_profiles(project_path: str) -> Dict[str, Any]:
    file_path = _profiles_file(project_path)
    if not file_path.exists():
        return {"profiles": {}}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {"profiles": {}}
    if not isinstance(data, dict):
        return {"profiles": {}}
    if not isinstance(data.get("profiles"), dict):
        data["profiles"] = {}
    return data


def _save_profiles(project_path: str, data: Dict[str, Any]) -> Path:
    file_path = _profiles_file(project_path)
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return file_path


def list_remote_profiles(project_path: str) -> Dict[str, Any]:
    data = _load_profiles(project_path)
    profiles = data.get("profiles", {})
    names = sorted(profiles.keys(), key=lambda s: s.lower())
    public_profiles = []
    for name in names:
        cfg = dict(profiles[name])
        has_passphrase = bool(cfg.get("passphrase_encrypted"))
        cfg.pop("passphrase_encrypted", None)
        cfg["has_encrypted_passphrase"] = has_passphrase
        public_profiles.append({"name": name, "config": cfg})
    return {
        "profiles": public_profiles,
        "count": len(names),
    }


def get_remote_profile(project_path: str, profile_name: str) -> Dict[str, Any]:
    normalized = _normalize_profile_name(profile_name)
    data = _load_profiles(project_path)
    profiles = data.get("profiles", {})
    if normalized not in profiles:
        raise ValueError(f"Remote profile not found: {normalized}")
    cfg = dict(profiles[normalized])
    has_passphrase = bool(cfg.get("passphrase_encrypted"))
    cfg.pop("passphrase_encrypted", None)
    cfg["has_encrypted_passphrase"] = has_passphrase
    return {"name": normalized, "config": cfg}


def save_remote_profile(
    project_path: str, profile_name: str, remote_config: Dict[str, Any]
) -> Dict[str, Any]:
    normalized = _normalize_profile_name(profile_name)
    if not isinstance(remote_config, dict):
        raise ValueError("remote_config must be an object.")

    allowed_keys = {
        "host",
        "user",
        "python_exec",
        "project_path",
        "runner_repo_path",
        "port",
        "identity_file",
        "strict_host_key_checking",
        "user_known_hosts_file",
        "proxy_jump",
        "connect_timeout",
        "passphrase",
        "store_encrypted_passphrase",
    }
    cleaned: Dict[str, Any] = {}
    for key, value in remote_config.items():
        if key not in allowed_keys:
            continue
        if value is None:
            continue
        if isinstance(value, str):
            trimmed = value.strip()
            if trimmed:
                cleaned[key] = trimmed
        else:
            cleaned[key] = value

    if not cleaned.get("host"):
        raise ValueError("remote_config.host is required for saved profiles.")
    if not cleaned.get("project_path"):
        raise ValueError("remote_config.project_path is required for saved profiles.")
    if not cleaned.get("runner_repo_path"):
        raise ValueError(
            "remote_config.runner_repo_path is required for saved profiles."
        )

    passphrase = str(cleaned.pop("passphrase", "") or "").strip()
    store_flag = bool(cleaned.pop("store_encrypted_passphrase", False))

    existing = _load_profiles(project_path).get("profiles", {}).get(normalized, {})
    existing_token = (
        existing.get("passphrase_encrypted") if isinstance(existing, dict) else None
    )
    if passphrase and store_flag:
        cleaned["passphrase_encrypted"] = _encrypt_secret(passphrase)
    elif store_flag and existing_token:
        cleaned["passphrase_encrypted"] = existing_token

    data = _load_profiles(project_path)
    profiles = data.setdefault("profiles", {})
    profiles[normalized] = cleaned
    file_path = _save_profiles(project_path, data)
    public_cfg = dict(cleaned)
    has_passphrase = bool(public_cfg.get("passphrase_encrypted"))
    public_cfg.pop("passphrase_encrypted", None)
    public_cfg["has_encrypted_passphrase"] = has_passphrase
    return {"name": normalized, "config": public_cfg, "file": str(file_path)}


def delete_remote_profile(project_path: str, profile_name: str) -> Dict[str, Any]:
    normalized = _normalize_profile_name(profile_name)
    data = _load_profiles(project_path)
    profiles = data.get("profiles", {})
    if normalized not in profiles:
        raise ValueError(f"Remote profile not found: {normalized}")
    removed = profiles.pop(normalized)
    file_path = _save_profiles(project_path, data)
    public_cfg = dict(removed)
    has_passphrase = bool(public_cfg.get("passphrase_encrypted"))
    public_cfg.pop("passphrase_encrypted", None)
    public_cfg["has_encrypted_passphrase"] = has_passphrase
    return {"name": normalized, "config": public_cfg, "file": str(file_path)}


def resolve_remote_passphrase(
    project_path: str, remote: Dict[str, Any]
) -> Optional[str]:
    direct = str(remote.get("passphrase") or "").strip()
    if direct:
        return direct

    profile_name = str(remote.get("profile_name") or "").strip()
    use_saved = bool(remote.get("use_saved_passphrase", False))
    if not profile_name or not use_saved:
        return None

    data = _load_profiles(project_path)
    profiles = data.get("profiles", {})
    profile = profiles.get(profile_name)
    if not isinstance(profile, dict):
        return None

    token = profile.get("passphrase_encrypted")
    if not token:
        return None
    return _decrypt_secret(str(token))


def _tool_info(command: str) -> Dict[str, Any]:
    resolved = shutil.which(command)
    return {
        "available": bool(resolved),
        "path": resolved,
    }


def _resolve_bids_input(project_path: str) -> str:
    project_root = Path(project_path).expanduser().resolve()
    rawdata = project_root / "rawdata"
    if rawdata.is_dir() and any(rawdata.glob("sub-*")):
        return str(rawdata)
    return str(project_root)


def _ensure_runner_files(runner_repo_path: str) -> Tuple[Path, Path]:
    repo_root = Path(runner_repo_path).expanduser().resolve()
    if not repo_root.exists() or not repo_root.is_dir():
        raise ValueError(f"Runner repository path is invalid: {repo_root}")

    runner_script = repo_root / "scripts" / "prism_runner.py"
    if not runner_script.exists():
        raise ValueError(f"Runner script not found at expected path: {runner_script}")
    return repo_root, runner_script


def _parse_subjects(subjects: Any) -> List[str]:
    if subjects is None:
        return []
    if isinstance(subjects, list):
        values = [str(item).strip() for item in subjects]
    else:
        values = [part.strip() for part in str(subjects).split(",")]
    return [s for s in values if s]


def _build_runner_cli_command(
    *,
    python_exec: str,
    runner_script: str,
    config_path: str,
    mode: str,
    dry_run: bool,
    log_level: str,
    subjects: Any,
    slurm_only: bool,
    monitor: bool,
) -> List[str]:
    mode_norm = (mode or "local").strip().lower()
    if mode_norm not in {"local", "hpc"}:
        raise ValueError("mode must be 'local' or 'hpc'")

    cmd: List[str] = [
        python_exec,
        runner_script,
        "-c",
        config_path,
        "--log-level",
        (log_level or "INFO").upper(),
    ]

    if mode_norm == "hpc":
        cmd.append("--hpc")
    else:
        cmd.append("--local")

    if dry_run:
        cmd.append("--dry-run")

    subject_list = _parse_subjects(subjects)
    if subject_list:
        cmd.append("--subjects")
        cmd.extend(subject_list)

    if mode_norm == "hpc" and slurm_only:
        cmd.append("--slurm-only")
    if mode_norm == "hpc" and monitor:
        cmd.append("--monitor")

    return cmd


def _remote_join(base: str, *parts: str) -> str:
    segment_list = [str(base).rstrip("/")]
    segment_list.extend([str(part).strip("/") for part in parts])
    return "/".join([s for s in segment_list if s])


def _build_ssh_command_prefix(ssh_target: str, remote: Dict[str, Any]) -> List[str]:
    cmd: List[str] = ["ssh"]

    port = remote.get("port")
    if port is not None and str(port).strip():
        try:
            cmd.extend(["-p", str(int(port))])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid remote port: {port}") from exc

    identity_file = str(remote.get("identity_file") or "").strip()
    if identity_file:
        cmd.extend(["-i", identity_file])

    strict = str(remote.get("strict_host_key_checking") or "").strip().lower()
    if strict:
        if strict not in {"yes", "no", "accept-new"}:
            raise ValueError(
                "strict_host_key_checking must be one of: yes, no, accept-new"
            )
        cmd.extend(["-o", f"StrictHostKeyChecking={strict}"])

    known_hosts_file = str(remote.get("user_known_hosts_file") or "").strip()
    if known_hosts_file:
        cmd.extend(["-o", f"UserKnownHostsFile={known_hosts_file}"])

    connect_timeout = remote.get("connect_timeout")
    if connect_timeout is not None and str(connect_timeout).strip():
        try:
            connect_timeout_int = int(connect_timeout)
            if connect_timeout_int < 1:
                raise ValueError("connect_timeout must be >= 1")
            cmd.extend(["-o", f"ConnectTimeout={connect_timeout_int}"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid connect_timeout: {connect_timeout}") from exc

    proxy_jump = str(remote.get("proxy_jump") or "").strip()
    if proxy_jump:
        cmd.extend(["-J", proxy_jump])

    cmd.append(ssh_target)
    return cmd


def _run_ssh_with_optional_passphrase(
    *, ssh_cmd: List[str], timeout: int, passphrase: Optional[str]
) -> subprocess.CompletedProcess:
    if not passphrase:
        if timeout > 0:
            return subprocess.run(
                ssh_cmd, timeout=timeout, capture_output=True, text=True
            )
        return subprocess.run(ssh_cmd, capture_output=True, text=True)

    askpass_dir = Path(tempfile.mkdtemp(prefix="prism_askpass_"))
    askpass_script = askpass_dir / "askpass.sh"
    askpass_script.write_text(
        "#!/bin/sh\nprintf '%s\\n' \"$PRISM_SSH_PASSPHRASE\"\n",
        encoding="utf-8",
    )
    askpass_script.chmod(0o700)

    env = os.environ.copy()
    env["SSH_ASKPASS"] = str(askpass_script)
    env["SSH_ASKPASS_REQUIRE"] = "force"
    env["PRISM_SSH_PASSPHRASE"] = passphrase
    env.setdefault("DISPLAY", ":0")

    cmd = ssh_cmd
    if shutil.which("setsid"):
        cmd = ["setsid", *ssh_cmd]

    try:
        if timeout > 0:
            return subprocess.run(
                cmd,
                timeout=timeout,
                capture_output=True,
                text=True,
                env=env,
            )
        return subprocess.run(cmd, capture_output=True, text=True, env=env)
    finally:
        try:
            askpass_script.unlink(missing_ok=True)
            askpass_dir.rmdir()
        except Exception:
            pass


def list_apptainer_images(images_folder: str) -> Dict[str, Any]:
    folder = Path(images_folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Images folder is invalid: {folder}")

    files: List[str] = []
    for ext in ("*.sif", "*.img", "*.simg"):
        files.extend([p.name for p in folder.glob(ext) if p.is_file()])

    files = sorted(set(files), key=lambda s: s.lower())
    return {
        "folder": str(folder),
        "images": files,
        "count": len(files),
    }


def list_docker_tags(repository: str, page_size: int = 100) -> Dict[str, Any]:
    repo = str(repository or "").strip()
    if not repo:
        raise ValueError("repository is required")

    if "/" in repo:
        namespace, name = repo.split("/", 1)
    else:
        namespace, name = "library", repo

    url = f"https://hub.docker.com/v2/repositories/{namespace}/{name}/tags"
    try:
        response = requests.get(
            url, params={"page_size": max(int(page_size), 1)}, timeout=10
        )
    except requests.RequestException as exc:
        raise ValueError(f"Could not fetch Docker tags: {exc}") from exc

    if response.status_code == 404:
        raise ValueError(f"Docker repository not found: {repo}")
    if response.status_code >= 400:
        raise ValueError(
            f"Docker Hub returned {response.status_code} for repository {repo}"
        )

    payload = response.json() if response.content else {}
    results = payload.get("results") if isinstance(payload, dict) else []
    tags = []
    for item in results or []:
        if not isinstance(item, dict):
            continue
        tag = str(item.get("name") or "").strip()
        if tag:
            tags.append(tag)

    tags = sorted(set(tags), key=lambda s: s.lower())
    return {
        "repository": repo,
        "tags": tags,
        "count": len(tags),
    }


def pull_docker_image(image: str) -> Dict[str, Any]:
    image_ref = str(image or "").strip()
    if not image_ref:
        raise ValueError("image is required")
    if not shutil.which("docker"):
        raise ValueError("docker is not available on this host.")

    result = subprocess.run(
        ["docker", "pull", image_ref],
        capture_output=True,
        text=True,
    )
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    exit_code = int(result.returncode)
    return {
        "image": image_ref,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "success": exit_code == 0,
    }


def _extract_help_options(help_text: str) -> List[str]:
    options: List[str] = []
    pattern = re.compile(r"--[a-zA-Z0-9][a-zA-Z0-9\-]*")
    for line in (help_text or "").splitlines():
        found = pattern.findall(line)
        for opt in found:
            options.append(opt)
    return sorted(set(options), key=lambda s: s.lower())


def load_app_help(
    *,
    container_engine: str,
    container: str,
    timeout_seconds: int = 30,
) -> Dict[str, Any]:
    engine = (container_engine or "").strip().lower()
    if engine not in SUPPORTED_ENGINES:
        raise ValueError(
            "container_engine must be one of: apptainer, singularity, docker"
        )
    if not container or not str(container).strip():
        raise ValueError("Container path/image is required.")

    container_ref = str(container).strip()
    timeout = max(int(timeout_seconds), 1)

    commands: List[List[str]] = []
    if engine in {"apptainer", "singularity"}:
        binary = engine
        if not shutil.which(binary):
            raise ValueError(f"{binary} is not available on this host.")
        path_ref = Path(container_ref).expanduser()
        if not path_ref.exists():
            raise ValueError(f"Container image not found: {path_ref}")
        commands = [
            [binary, "run-help", str(path_ref)],
            [binary, "exec", str(path_ref), "--help"],
        ]
    else:
        if not shutil.which("docker"):
            raise ValueError("docker is not available on this host.")
        inspect = subprocess.run(
            ["docker", "image", "inspect", container_ref],
            capture_output=True,
            text=True,
        )
        if inspect.returncode != 0:
            raise ValueError(
                f'Docker image "{container_ref}" not found locally. Pull it before loading options.'
            )
        commands = [
            ["docker", "run", "--rm", container_ref, "--help"],
            ["docker", "run", "--rm", container_ref, "-h"],
        ]

    last_stdout = ""
    last_stderr = ""
    last_code = None
    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            continue

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        combined = (stdout + "\n" + stderr).strip()
        last_stdout = stdout
        last_stderr = stderr
        last_code = int(result.returncode)
        if combined:
            return {
                "engine": engine,
                "container": container_ref,
                "command": cmd,
                "exit_code": int(result.returncode),
                "help_text": combined,
                "options": _extract_help_options(combined),
            }

    return {
        "engine": engine,
        "container": container_ref,
        "command": commands[-1],
        "exit_code": last_code,
        "help_text": (last_stdout + "\n" + last_stderr).strip(),
        "options": _extract_help_options(last_stdout + "\n" + last_stderr),
    }


def prepare_project_runner_config(
    *,
    project_path: str,
    app_name: str,
    container_engine: str,
    container: str,
    analysis_level: str = "participant",
    bids_folder: Optional[str] = None,
    output_folder: Optional[str] = None,
    output_subdir: Optional[str] = None,
    jobs: int = 1,
    tmp_folder: Optional[str] = None,
    templateflow_dir: Optional[str] = None,
    app_options: Optional[Dict[str, Any]] = None,
    apptainer_args: Optional[str] = None,
    mounts: Optional[List[Dict[str, Any]]] = None,
    hpc: Optional[Dict[str, Any]] = None,
    datalad: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    project_root = Path(project_path).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        raise ValueError(f"Invalid PRISM project path: {project_root}")

    if not app_name.strip():
        raise ValueError("App name is required.")
    if container_engine.strip().lower() not in SUPPORTED_ENGINES:
        raise ValueError(
            "container_engine must be one of: apptainer, singularity, docker"
        )
    if not container.strip():
        raise ValueError("Container image/path is required.")

    resolved_bids_folder = (
        bids_folder.strip()
        if isinstance(bids_folder, str) and bids_folder.strip()
        else _resolve_bids_input(str(project_root))
    )

    out_name = (output_subdir or app_name).strip().replace(" ", "_")
    derivatives_root = Path(safe_path_join(str(project_root), "derivatives"))
    resolved_output_folder = (
        output_folder.strip()
        if isinstance(output_folder, str) and output_folder.strip()
        else str(Path(safe_path_join(str(derivatives_root), out_name)))
    )
    output_folder_path = Path(resolved_output_folder).expanduser().resolve()
    apps_runner_root = Path(safe_path_join(str(derivatives_root), "apps_runner"))
    config_dir = Path(safe_path_join(str(apps_runner_root), "configs"))
    log_dir = Path(safe_path_join(str(apps_runner_root), "logs"))

    config_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    output_folder_path.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    config_path = Path(safe_path_join(str(config_dir), f"{app_name}_{now}.json"))

    default_tmp = str(Path(safe_path_join(str(apps_runner_root), "tmp")))
    config: Dict[str, Any] = {
        "common": {
            "bids_folder": resolved_bids_folder,
            "output_folder": str(output_folder_path),
            "tmp_folder": tmp_folder or default_tmp,
            "container_engine": container_engine.strip().lower(),
            "container": container.strip(),
            "jobs": max(int(jobs), 1),
        },
        "app": {
            "name": app_name.strip(),
            "analysis_level": analysis_level.strip() or "participant",
            "options": app_options or {},
        },
    }

    if templateflow_dir:
        config["common"]["templateflow_dir"] = templateflow_dir.strip()
    if apptainer_args:
        config["app"]["apptainer_args"] = apptainer_args.strip()
    if mounts:
        config["app"]["mounts"] = mounts
    if isinstance(hpc, dict) and hpc:
        config["hpc"] = hpc
    if isinstance(datalad, dict) and datalad:
        config["datalad"] = datalad

    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    return {
        "config": config,
        "config_path": str(config_path),
        "bids_folder": resolved_bids_folder,
        "output_folder": str(output_folder_path),
        "apps_runner_root": str(apps_runner_root),
        "log_dir": str(log_dir),
    }


def run_runner_with_project(
    *,
    project_path: str,
    runner_repo_path: str,
    app_name: str,
    container_engine: str,
    container: str,
    mode: str = "local",
    dry_run: bool = True,
    analysis_level: str = "participant",
    bids_folder: Optional[str] = None,
    output_folder: Optional[str] = None,
    output_subdir: Optional[str] = None,
    jobs: int = 1,
    subjects: Any = None,
    monitor: bool = False,
    slurm_only: bool = False,
    log_level: str = "INFO",
    timeout_seconds: int = 180,
    app_options: Optional[Dict[str, Any]] = None,
    hpc: Optional[Dict[str, Any]] = None,
    datalad: Optional[Dict[str, Any]] = None,
    apptainer_args: Optional[str] = None,
    mounts: Optional[List[Dict[str, Any]]] = None,
    templateflow_dir: Optional[str] = None,
    tmp_folder: Optional[str] = None,
    execution_target: str = "local",
    remote: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    target = (execution_target or "local").strip().lower()
    if target not in {"local", "remote_ssh"}:
        raise ValueError("execution_target must be 'local' or 'remote_ssh'")

    if target == "local":
        repo_root, runner_script = _ensure_runner_files(runner_repo_path)
        prepared = prepare_project_runner_config(
            project_path=project_path,
            app_name=app_name,
            container_engine=container_engine,
            container=container,
            analysis_level=analysis_level,
            bids_folder=bids_folder,
            output_folder=output_folder,
            output_subdir=output_subdir,
            jobs=jobs,
            tmp_folder=tmp_folder,
            templateflow_dir=templateflow_dir,
            app_options=app_options,
            apptainer_args=apptainer_args,
            mounts=mounts,
            hpc=hpc,
            datalad=datalad,
        )

        cmd = _build_runner_cli_command(
            python_exec=sys.executable,
            runner_script=str(runner_script),
            config_path=prepared["config_path"],
            mode=mode,
            dry_run=dry_run,
            log_level=log_level,
            subjects=subjects,
            slurm_only=slurm_only,
            monitor=monitor,
        )

        timeout = max(int(timeout_seconds), 0)

        try:
            if timeout > 0:
                result = subprocess.run(
                    cmd,
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            else:
                result = subprocess.run(
                    cmd,
                    cwd=str(repo_root),
                    capture_output=True,
                    text=True,
                )
            timed_out = False
            stdout = result.stdout or ""
            stderr = result.stderr or ""
            exit_code = int(result.returncode)
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
            stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
            exit_code = 124

        return {
            "prepared": prepared,
            "command": cmd,
            "cwd": str(repo_root),
            "mode": (mode or "local").strip().lower(),
            "dry_run": dry_run,
            "execution_target": "local",
            "timed_out": timed_out,
            "timeout_seconds": timeout,
            "exit_code": exit_code,
            "stdout": stdout,
            "stderr": stderr,
            "success": (exit_code == 0 and not timed_out),
        }

    remote = remote or {}
    host = str(remote.get("host") or "").strip()
    user = str(remote.get("user") or "").strip()
    remote_project_path = str(remote.get("project_path") or "").strip()
    remote_runner_repo_path = (
        str(remote.get("runner_repo_path") or "").strip() or runner_repo_path
    )
    remote_python = str(remote.get("python_exec") or "python3").strip() or "python3"
    remote_execute = bool(remote.get("execute", False))
    remote_passphrase = resolve_remote_passphrase(project_path, remote)

    if not host:
        raise ValueError("Remote host is required for execution_target=remote_ssh")
    if not remote_project_path:
        raise ValueError(
            "Remote project_path is required for execution_target=remote_ssh"
        )
    if not remote_runner_repo_path:
        raise ValueError(
            "Remote runner_repo_path is required for execution_target=remote_ssh"
        )

    out_name = (output_subdir or app_name).strip().replace(" ", "_")
    remote_derivatives = _remote_join(remote_project_path, "derivatives")
    remote_apps_runner_root = _remote_join(remote_derivatives, "apps_runner")
    remote_config_dir = _remote_join(remote_apps_runner_root, "configs")
    remote_logs_dir = _remote_join(remote_apps_runner_root, "logs")
    remote_output_folder = (
        str(output_folder).strip()
        if isinstance(output_folder, str) and str(output_folder).strip()
        else _remote_join(remote_derivatives, out_name)
    )
    remote_bids_folder = (
        str(bids_folder).strip()
        if isinstance(bids_folder, str) and str(bids_folder).strip()
        else _remote_join(remote_project_path, "rawdata")
    )

    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    remote_config_path = _remote_join(remote_config_dir, f"{app_name}_{now}.json")

    config: Dict[str, Any] = {
        "common": {
            "bids_folder": remote_bids_folder,
            "output_folder": remote_output_folder,
            "tmp_folder": tmp_folder or _remote_join(remote_apps_runner_root, "tmp"),
            "container_engine": container_engine.strip().lower(),
            "container": container.strip(),
            "jobs": max(int(jobs), 1),
        },
        "app": {
            "name": app_name.strip(),
            "analysis_level": analysis_level.strip() or "participant",
            "options": app_options or {},
        },
    }
    if templateflow_dir:
        config["common"]["templateflow_dir"] = templateflow_dir.strip()
    if apptainer_args:
        config["app"]["apptainer_args"] = apptainer_args.strip()
    if mounts:
        config["app"]["mounts"] = mounts
    if isinstance(hpc, dict) and hpc:
        config["hpc"] = hpc
    if isinstance(datalad, dict) and datalad:
        config["datalad"] = datalad

    runner_script_remote = _remote_join(
        remote_runner_repo_path, "scripts", "prism_runner.py"
    )
    runner_cmd = _build_runner_cli_command(
        python_exec=remote_python,
        runner_script=runner_script_remote,
        config_path=remote_config_path,
        mode=mode,
        dry_run=dry_run,
        log_level=log_level,
        subjects=subjects,
        slurm_only=slurm_only,
        monitor=monitor,
    )

    config_json = json.dumps(config, indent=2)
    remote_shell = (
        f"mkdir -p {shlex.quote(remote_config_dir)} {shlex.quote(remote_logs_dir)} {shlex.quote(remote_output_folder)} && "
        f"cat > {shlex.quote(remote_config_path)} <<'PRISM_JSON'\n"
        f"{config_json}\n"
        "PRISM_JSON\n"
        f"cd {shlex.quote(remote_runner_repo_path)} && "
        + " ".join([shlex.quote(token) for token in runner_cmd])
    )

    ssh_target = f"{user}@{host}" if user else host
    ssh_cmd = _build_ssh_command_prefix(ssh_target=ssh_target, remote=remote)
    ssh_cmd.append(remote_shell)

    if not remote_execute:
        prepared = {
            "config": config,
            "config_path": remote_config_path,
            "bids_folder": remote_bids_folder,
            "output_folder": remote_output_folder,
            "apps_runner_root": remote_apps_runner_root,
            "log_dir": remote_logs_dir,
        }
        return {
            "prepared": prepared,
            "command": runner_cmd,
            "cwd": remote_runner_repo_path,
            "mode": (mode or "local").strip().lower(),
            "dry_run": dry_run,
            "execution_target": "remote_ssh",
            "remote_execute": False,
            "ssh_target": ssh_target,
            "ssh_command": ssh_cmd,
            "remote_shell": remote_shell,
            "timed_out": False,
            "timeout_seconds": timeout_seconds,
            "exit_code": 0,
            "stdout": "",
            "stderr": "",
            "success": True,
        }

    timeout = max(int(timeout_seconds), 0)

    try:
        result = _run_ssh_with_optional_passphrase(
            ssh_cmd=ssh_cmd,
            timeout=timeout,
            passphrase=remote_passphrase,
        )
        timed_out = False
        stdout = result.stdout or ""
        stderr = result.stderr or ""
        exit_code = int(result.returncode)
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = (exc.stdout or "") if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "") if isinstance(exc.stderr, str) else ""
        exit_code = 124

    prepared = {
        "config": config,
        "config_path": remote_config_path,
        "bids_folder": remote_bids_folder,
        "output_folder": remote_output_folder,
        "apps_runner_root": remote_apps_runner_root,
        "log_dir": remote_logs_dir,
    }
    return {
        "prepared": prepared,
        "command": runner_cmd,
        "cwd": remote_runner_repo_path,
        "mode": (mode or "local").strip().lower(),
        "dry_run": dry_run,
        "execution_target": "remote_ssh",
        "remote_execute": True,
        "ssh_target": ssh_target,
        "ssh_command": ssh_cmd,
        "remote_shell": remote_shell,
        "timed_out": timed_out,
        "timeout_seconds": timeout,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "success": (exit_code == 0 and not timed_out),
    }


def check_environment_tools() -> Dict[str, Any]:
    docker = _tool_info("docker")
    apptainer = _tool_info("apptainer")
    singularity = _tool_info("singularity")
    datalad = _tool_info("datalad")
    git = _tool_info("git")
    sbatch = _tool_info("sbatch")
    squeue = _tool_info("squeue")
    scancel = _tool_info("scancel")
    ssh = _tool_info("ssh")

    slurm_ready = all([sbatch["available"], squeue["available"], scancel["available"]])
    container_ready = any(
        [
            docker["available"],
            apptainer["available"],
            singularity["available"],
        ]
    )

    return {
        "container": {
            "docker": docker,
            "apptainer": apptainer,
            "singularity": singularity,
            "any_available": container_ready,
        },
        "hpc": {
            "sbatch": sbatch,
            "squeue": squeue,
            "scancel": scancel,
            "slurm_ready": slurm_ready,
        },
        "datalad": datalad,
        "git": git,
        "ssh": ssh,
    }


def inspect_runner_repo(repo_path: Optional[str]) -> Dict[str, Any]:
    if not repo_path:
        return {
            "provided": False,
            "exists": False,
            "required_files": [],
            "missing_files": [],
        }

    repo_root = Path(repo_path).expanduser().resolve()
    required_files = [
        "prism_app_runner.py",
        "scripts/prism_runner.py",
        "scripts/build_apptainer.sh",
    ]

    missing_files: List[str] = []
    for rel in required_files:
        if not (repo_root / rel).exists():
            missing_files.append(rel)

    return {
        "provided": True,
        "path": str(repo_root),
        "exists": repo_root.exists() and repo_root.is_dir(),
        "required_files": required_files,
        "missing_files": missing_files,
    }


def load_config(
    config_path: Optional[str], config_json: Optional[str]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    if config_json:
        try:
            return json.loads(config_json), None
        except json.JSONDecodeError as exc:
            return None, f"Invalid config JSON: {exc}"

    if config_path:
        path = Path(config_path).expanduser()
        if not path.exists() or not path.is_file():
            return None, f"Config file not found: {path}"
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f), None
        except json.JSONDecodeError as exc:
            return None, f"Invalid JSON in config file: {exc}"
        except OSError as exc:
            return None, f"Could not read config file: {exc}"

    return None, None


def validate_runner_config(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not config:
        return {
            "present": False,
            "errors": [],
            "warnings": [
                "No runner config provided. Environment-only compatibility assessment was performed."
            ],
            "derived": {},
        }

    errors: List[str] = []
    warnings: List[str] = []

    common = config.get("common")
    app = config.get("app")
    hpc = config.get("hpc")

    if not isinstance(common, dict):
        errors.append("Missing or invalid 'common' section in config.")
        common = {}
    if not isinstance(app, dict):
        errors.append("Missing or invalid 'app' section in config.")
        app = {}

    bids_folder = common.get("bids_folder")
    output_folder = common.get("output_folder")
    container_engine = str(common.get("container_engine") or "").strip().lower()
    container = common.get("container")

    if not bids_folder:
        errors.append("common.bids_folder is required.")
    if not output_folder:
        errors.append("common.output_folder is required.")
    if not container_engine:
        warnings.append(
            "common.container_engine not set. Expected one of: apptainer, singularity, docker."
        )
    elif container_engine not in SUPPORTED_ENGINES:
        errors.append(
            f"Unsupported common.container_engine '{container_engine}'. Supported: apptainer, singularity, docker."
        )

    if not container:
        warnings.append(
            "common.container not set. Execution cannot run until a container image is configured."
        )

    analysis_level = str(app.get("analysis_level") or "").strip()
    if analysis_level and analysis_level not in {"participant", "group"}:
        warnings.append(
            "app.analysis_level should usually be 'participant' or 'group'."
        )

    if isinstance(hpc, dict):
        missing_hpc = [
            k for k in ("partition", "time", "mem", "cpus") if not hpc.get(k)
        ]
        if missing_hpc:
            warnings.append(
                f"hpc section present but missing common SLURM fields: {', '.join(missing_hpc)}"
            )
        cpus = hpc.get("cpus")
        if cpus is not None:
            try:
                if int(cpus) < 1:
                    errors.append("hpc.cpus must be >= 1.")
            except (TypeError, ValueError):
                errors.append("hpc.cpus must be an integer.")

    if output_folder:
        norm_out = str(output_folder).replace("\\", "/").lower()
        if "/derivatives" not in norm_out and not norm_out.endswith("derivatives"):
            warnings.append(
                "common.output_folder does not appear to target a derivatives directory. For BIDS compatibility, write outputs under derivatives/."
            )

    return {
        "present": True,
        "errors": errors,
        "warnings": warnings,
        "derived": {
            "container_engine": container_engine or None,
            "has_hpc_section": isinstance(hpc, dict),
            "analysis_level": analysis_level or None,
            "output_folder": output_folder,
            "bids_folder": bids_folder,
        },
    }


def build_compatibility_report(
    project_path: Optional[str] = None,
    runner_repo_path: Optional[str] = None,
    config_path: Optional[str] = None,
    config_json: Optional[str] = None,
) -> Dict[str, Any]:
    env = check_environment_tools()
    repo = inspect_runner_repo(runner_repo_path)

    auto_config_path = config_path
    if not auto_config_path and project_path:
        candidate = Path(project_path).expanduser() / "project.json"
        if candidate.exists():
            auto_config_path = str(candidate)

    config, config_error = load_config(auto_config_path, config_json)
    config_assessment = validate_runner_config(config)

    blocking: List[str] = []
    warnings: List[str] = []
    recommendations: List[str] = []

    if config_error:
        blocking.append(config_error)

    if not env["container"]["any_available"]:
        blocking.append(
            "No supported container runtime available (docker/apptainer/singularity)."
        )
        recommendations.append(
            "Install Docker or Apptainer/Singularity, then rerun compatibility check."
        )

    if config_assessment["errors"]:
        blocking.extend(config_assessment["errors"])

    warnings.extend(config_assessment["warnings"])

    if repo.get("provided") and not repo.get("exists"):
        blocking.append(
            "Provided runner repository path does not exist or is not a directory."
        )
    if repo.get("provided") and repo.get("exists") and repo.get("missing_files"):
        warnings.append(
            "Runner repository is missing expected files: "
            + ", ".join(repo["missing_files"])
        )

    if not env["git"]["available"]:
        warnings.append(
            "git is not available; runner workflows and project syncing may fail."
        )

    if not blocking and not warnings:
        status = "compatible"
    elif blocking:
        status = "incompatible"
    else:
        status = "partial"

    if not config_assessment["present"]:
        recommendations.append(
            "Ensure project metadata exists at code/project.json (or project.json) to complete config-level compatibility checks."
        )

    recommendations.append(
        "Keep PRISM validation in core and wire app execution only through derivatives-level routes."
    )
    recommendations.append(
        "Write app outputs under derivatives/ to preserve BIDS-app interoperability."
    )

    return {
        "status": status,
        "project_path": project_path,
        "resolved_config_path": auto_config_path,
        "environment": env,
        "runner_repo": repo,
        "config": config_assessment,
        "blocking_issues": blocking,
        "warnings": warnings,
        "recommendations": recommendations,
    }
