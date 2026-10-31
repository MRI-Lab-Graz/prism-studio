"""A project's remote targets and schema version, saved to its .prismrc.json.

One implementation for Studio's save buttons and the `datalad config`, `rsync config|sync` and
`project set-schema-version` commands. Raises ValueError with the sentence to show when a value is refused.
"""

from __future__ import annotations

from pathlib import Path

from src.config import load_config, save_config


def _save(config, project_root: Path) -> str:
    filename = Path(config._config_path).name if config._config_path else ".prismrc.json"
    return save_config(config, str(project_root), filename=filename)


def sanitize_exclude_patterns(raw) -> list[str]:
    """Rsync `--exclude` patterns from a list or a newline-separated string: blanks and duplicates dropped, order kept."""
    candidates = raw.splitlines() if isinstance(raw, str) else raw if isinstance(raw, list) else []
    return list(dict.fromkeys(p for p in (str(item or "").strip() for item in candidates) if p))


def set_schema_version(project_root: Path, version: str, available_versions: list[str]) -> dict:
    version = str(version or "stable").strip() or "stable"
    if version not in available_versions:
        raise ValueError(f"Unknown schema version: {version}")
    config = load_config(str(project_root))
    config.schema_version = version
    return {"schema_version": version, "available_versions": available_versions, "config_path": _save(config, project_root)}


def save_datalad_server_config(project_root: Path, ria_url=None, sibling_name=None, alias=None) -> dict:
    from src.datalad_execution import sibling_label_problem

    sibling_name = str(sibling_name or "").strip() or "ria-store"
    alias = str(alias or "").strip()
    for label, what in ((sibling_name, "sibling name"), (alias, "alias")):
        if label and (problem := sibling_label_problem(label, what)):
            raise ValueError(problem)
    config = load_config(str(project_root))
    config.datalad_ria_store_url = str(ria_url or "").strip() or None
    config.datalad_sibling_name = sibling_name
    config.datalad_sibling_alias = alias or None
    return {
        "ria_url": config.datalad_ria_store_url,
        "sibling_name": config.datalad_sibling_name,
        "sibling_alias": config.datalad_sibling_alias,
        "config_path": _save(config, project_root),
    }


def save_rsync_config(project_root: Path, remote_target=None, remote_label=None, exclude_patterns=None) -> dict:
    config = load_config(str(project_root))
    config.rsync_remote_target = str(remote_target or "").strip() or None
    config.rsync_remote_label = str(remote_label or "").strip() or None
    config.rsync_exclude_patterns = sanitize_exclude_patterns(exclude_patterns)
    return {
        "remote_target": config.rsync_remote_target,
        "remote_label": config.rsync_remote_label,
        "exclude_patterns": config.rsync_exclude_patterns,
        "config_path": _save(config, project_root),
    }


def rsync_sync_options(remote_target=None, remote_label=None, exclude_patterns=None, verify=False) -> dict:
    """What `ProjectManager.sync_project_to_remote` is given. Anything left empty falls back to the project's saved config there."""
    return {
        "remote_target": remote_target or None,
        "remote_label": remote_label or None,
        "exclude_patterns": sanitize_exclude_patterns(exclude_patterns) or None,
        "verify": bool(verify),
    }
