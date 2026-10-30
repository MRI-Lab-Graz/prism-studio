"""Where a survey template comes from: the project, else the personal library, else the global one.

A conversion works on one merged folder: every ``survey-<task>.json`` from the nearest library
that has it. Templates it used that came from another library are copied into the project, so
the project carries what it was converted with (collaborators have no access to your personal
library).
"""

from __future__ import annotations

import inspect
import json
import shutil
import tempfile
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.config import get_effective_library_paths
from src.project_root import resolve_existing_project_root
from src.survey_library_resolution import survey_templates_dir
from src.system_files import filter_system_files


@dataclass(frozen=True)
class Tier:
    label: str  # project | project-official | personal | global
    directory: Path  # the folder holding survey-*.json


@dataclass
class EffectiveLibrary:
    directory: Path
    origins: dict[str, Tier] = field(default_factory=dict)  # task -> the library its template came from
    tiers: list[Tier] = field(default_factory=list)  # the libraries merged, nearest first
    _tmp: Any = field(default=None, repr=False)  # keeps the folder alive; cleaned up when this is dropped


def _templates(directory: Path) -> list[Path]:
    candidates = sorted(directory.glob("survey-*.json")) if directory.is_dir() else []
    allowed = set(filter_system_files([p.name for p in candidates]))
    return [p for p in candidates if p.name in allowed]


def _task(path: Path) -> str:
    return path.name[len("survey-"):-len(".json")]


def _project_root(project_path) -> Path:
    root = Path(project_path).expanduser()
    return root.parent if root.is_file() else root


def template_tiers(project_path, app_root, app_settings=None) -> list[Tier]:
    """The libraries that hold survey templates, nearest first."""
    paths = get_effective_library_paths(app_root=str(app_root), app_settings=app_settings)
    candidates: list[tuple[str, Path | None]] = []
    if project_path:
        root = _project_root(project_path)
        candidates += [("project", root / "code" / "library"), ("project-official", root / "official" / "library")]
    candidates += [
        ("personal", Path(paths["personal_library_path"]) if paths.get("personal_library_path") else None),
        ("global", Path(paths["global_library_path"]) if paths.get("global_library_path") else None),
    ]
    tiers = []
    for label, library in candidates:
        if library is not None and _templates(survey_templates_dir(library)):
            tiers.append(Tier(label, survey_templates_dir(library)))
    return tiers


def build_effective_library(project_path, app_root, app_settings=None) -> EffectiveLibrary:
    """A temporary folder with each task's template from the nearest library that has it."""
    tmp = tempfile.TemporaryDirectory(prefix="prism_survey_library_")
    library = EffectiveLibrary(Path(tmp.name), _tmp=tmp)
    library.tiers = template_tiers(project_path, app_root, app_settings)
    for tier in reversed(library.tiers):  # nearest copied last, wins
        for path in _templates(tier.directory):
            shutil.copy2(path, library.directory / path.name)
            library.origins[_task(path)] = tier
    return library


def is_standard_library(library_dir, project_path, app_root, app_settings=None) -> bool:
    """Is this folder one of the libraries that get merged (so not an explicit one the caller chose)?"""
    paths = get_effective_library_paths(app_root=str(app_root), app_settings=app_settings)
    roots = [paths.get("personal_library_path"), paths.get("global_library_path")]
    if project_path:
        root = _project_root(project_path)
        roots += [root / "code" / "library", root / "official" / "library"]
    def library_root(path) -> Path:  # a library or its survey/ folder: same library
        path = Path(path)
        return (path.parent if path.name == "survey" else path).resolve()

    return any(r and library_root(r) == library_root(library_dir) for r in roots)


def infer_technical_defaults(input_path) -> dict[str, str]:
    """Administration defaults for a project template when the source format is unambiguous."""
    if input_path and Path(input_path).suffix.lower() in {".lsa", ".lss"}:
        return {"SoftwarePlatform": "LimeSurvey", "AdministrationMethod": "online"}
    return {}


def prepare_project_survey_template_from_official(
    payload: Any, *, task: str, technical_defaults: dict[str, str] | None = None, selected_version: str | None = None
) -> Any:
    """Turn a library template into a project-local administration template."""
    if not isinstance(payload, dict):
        return payload

    out = deepcopy(payload)

    technical = out.get("Technical")
    if not isinstance(technical, dict):
        technical = {}
        out["Technical"] = technical

    technical.setdefault("StimulusType", "Questionnaire")
    technical.setdefault("FileFormat", "tsv")
    technical.setdefault("Language", "")
    technical.setdefault("Respondent", "")
    technical.setdefault("AdministrationMethod", "")
    technical.setdefault("SoftwarePlatform", "")
    technical.setdefault("SoftwareVersion", "")

    for key, value in (technical_defaults or {}).items():
        if not value:
            continue
        existing = technical.get(key)
        if isinstance(existing, str) and existing.strip():
            continue
        technical[key] = value

    study = out.get("Study")
    if not isinstance(study, dict):
        study = {}
        out["Study"] = study

    study.setdefault("TaskName", task)
    study.setdefault("LicenseID", "unknown")
    if isinstance(selected_version, str) and selected_version.strip():
        study["Version"] = selected_version.strip()

    return out


def copy_templates_to_project(
    tasks: list[str],
    source_of: Callable[[str], Path | None],
    project_path,
    technical_defaults: dict[str, str] | None = None,
    selected_versions: dict[str, str] | None = None,
    log_fn=None,
) -> dict[str, list[str]]:
    """Put each task's template (``source_of(task)``) into the project's code/library/survey, never
    overwriting one the project already has."""
    summary: dict[str, list[str]] = {"copied_tasks": [], "existing_tasks": [], "missing_tasks": []}
    if not project_path or not tasks:
        return summary
    project_root = resolve_existing_project_root(project_path)
    if project_root is None:
        return summary

    dest_dir = project_root / "code" / "library" / "survey"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for task in tasks:
        src = source_of(task)
        dest = dest_dir / f"survey-{task}.json"
        if src is None or not src.exists():
            summary["missing_tasks"].append(task)
            continue
        if dest.exists():
            summary["existing_tasks"].append(task)
            continue
        try:
            payload = json.loads(src.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload = prepare_project_survey_template_from_official(
                    payload, task=task, technical_defaults=technical_defaults,
                    selected_version=(selected_versions or {}).get(task),
                )
                dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            else:
                shutil.copy2(src, dest)
        except Exception:
            shutil.copy2(src, dest)
        summary["copied_tasks"].append(task)

    if summary["copied_tasks"]:
        message = f"Copied {len(summary['copied_tasks'])} survey template(s) into the project library."
        log_fn(message, "info") if log_fn else print(f"[PRISM DEBUG] {message}")
    return summary


def copy_used_templates_to_project(library: EffectiveLibrary, tasks, project_path, **kwargs) -> dict[str, list[str]]:
    return copy_templates_to_project(
        list(tasks),
        lambda task: library.directory / f"survey-{task}.json" if task in library.origins else None,
        project_path,
        **kwargs,
    )


def _accepted_kwargs(converter_fn, kwargs: dict, log_fn=None) -> dict:
    """Drop the options an older converter does not take (and say so)."""
    try:
        parameters = inspect.signature(converter_fn).parameters
    except (TypeError, ValueError):
        return kwargs
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
        return kwargs
    unsupported = sorted(k for k in kwargs if k not in parameters)
    if unsupported:
        message = (
            f"Converter '{getattr(converter_fn, '__name__', 'converter')}' does not accept options "
            f"{', '.join(unsupported)}; skipping unsupported options."
        )
        log_fn(message, "warning") if log_fn else print(f"[PRISM WARN] {message}")
    return {k: v for k, v in kwargs.items() if k in parameters}


def run_survey_with_template_sources(
    converter_fn, *, library_dir, fallback_project_path, app_root, log_fn=None, **kwargs
):
    """Run a survey conversion: the CLI's and Studio's one way to do it.

    The standard libraries are merged (project, then personal, then global); a library folder the caller
    chose is used as given. The templates the conversion used end up in the project. ``force`` left unset
    means: on when the output is a PRISM project (writing there is what a conversion is for), else off.
    """
    technical_defaults = infer_technical_defaults(kwargs.get("input_path"))
    versions = kwargs.get("template_version_overrides") or {}
    if fallback_project_path:
        kwargs.setdefault("project_path", fallback_project_path)
    if kwargs.get("force") is None:
        kwargs["force"] = bool(fallback_project_path) or (Path(kwargs.get("output_root") or ".") / "project.json").is_file()
    kwargs = _accepted_kwargs(converter_fn, kwargs, log_fn)

    effective = (
        build_effective_library(fallback_project_path, app_root)
        if is_standard_library(library_dir, fallback_project_path, app_root)
        else None
    )
    merged = effective is not None and bool(effective.origins)
    result = converter_fn(library_dir=str(effective.directory if merged else library_dir), **kwargs)
    tasks = list(getattr(result, "tasks_included", []) or [])
    if merged:
        copy_used_templates_to_project(effective, tasks, fallback_project_path,
                                       technical_defaults=technical_defaults, selected_versions=versions, log_fn=log_fn)
    else:
        given = survey_templates_dir(Path(library_dir))
        copy_templates_to_project(tasks, lambda task: given / f"survey-{task}.json", fallback_project_path,
                                  technical_defaults=technical_defaults, selected_versions=versions, log_fn=log_fn)
    return result
