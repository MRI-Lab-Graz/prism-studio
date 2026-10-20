"""Gather everything the methods section needs for a project (one entry point for CLI and GUI)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_MODALITY_DIRS = ("survey", "biometrics", "physio", "eeg", "eyetracking", "func", "anat")


@dataclass
class MethodsResult:
    md: str
    sections_used: list[str]
    warnings: list[str] = field(default_factory=list)
    template_data: dict[str, dict] = field(default_factory=dict)


def candidate_template_names(task_name: str, task_definition: dict) -> list[str]:
    """Likely template filenames from task metadata and naming conventions, deduplicated."""
    candidates: list[str] = []

    def _add(value) -> None:
        text = str(value or "").strip()
        if not text:
            return
        candidates.append(text)
        if not text.lower().endswith(".json"):
            candidates.append(f"{text}.json")

    tpl_filename = task_definition.get("template")
    modality = str(task_definition.get("modality") or "").strip().lower()
    _add(tpl_filename)

    if tpl_filename and modality:
        plain_name = str(tpl_filename).strip()
        if plain_name.lower().endswith(".json"):
            plain_name = plain_name[:-5]
        if plain_name and not plain_name.lower().startswith(f"{modality}-"):
            _add(f"{modality}-{plain_name}")

    names = {
        n
        for n in (
            str(task_name).strip(),
            str(task_name).replace("_", "-").strip(),
            str(task_name).replace("-", "_").strip(),
        )
        if n
    }
    prefixes = list(_MODALITY_DIRS)
    if modality:
        prefixes = [modality] + [p for p in prefixes if p != modality]
    for name in names:
        _add(name)
        for prefix in prefixes:
            _add(f"{prefix}-{name}")

    seen: set[str] = set()
    out: list[str] = []
    for candidate in candidates:
        if candidate.casefold() not in seen:
            seen.add(candidate.casefold())
            out.append(candidate)
    return out


def _library_dirs(project_path: Path, app_root: str) -> list[Path]:
    from src.config import get_effective_template_library_path, load_app_settings

    lib_info = get_effective_template_library_path(
        str(project_path), load_app_settings(app_root=app_root), app_root=app_root
    )
    dirs: list[Path] = []
    yoda_lib = project_path / "code" / "library"
    legacy_lib = project_path / "library"
    if yoda_lib.exists():
        dirs.append(yoda_lib)
    elif legacy_lib.exists():
        dirs.append(legacy_lib)
    for key in ("effective_external_path", "global_library_path"):
        if lib_info.get(key):
            dirs.append(Path(lib_info[key]))
    return dirs


def _find_template(search_dirs: list[Path], names: list[str]) -> dict | None:
    for search_dir in search_dirs:
        for name in names:
            for sub in (search_dir, *(search_dir / m for m in _MODALITY_DIRS)):
                candidate = sub / name
                if not candidate.exists():
                    continue
                try:
                    return json.loads(candidate.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    return None
    return None


def build_methods(
    project_path: Path,
    *,
    lang: str = "en",
    detail_level: str = "standard",
    app_root: str | None = None,
    project_data: dict | None = None,
    compute_participant_stats=None,
) -> MethodsResult:
    """Methods section for a project. ``project_data`` / ``compute_participant_stats`` can be injected.

    Raises FileNotFoundError when the project has no project metadata.
    """
    from src.methods_acquisition import acquisition_summary
    from src.methods_processing import processing_summary
    from src.reporting import generate_full_methods, methods_warnings

    project_path = Path(project_path)
    if project_data is None:
        from src.web.blueprints.projects_metadata_helpers import _read_project_json

        project_data = _read_project_json(project_path)
    if not project_data:
        raise FileNotFoundError(
            "No project metadata available. Fill in your project.json to generate a methods section."
        )

    dataset_desc = None
    desc_path = project_path / "dataset_description.json"
    if desc_path.exists():
        try:
            dataset_desc = json.loads(desc_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

    # ponytail: default app_root is the repo's app/ dir; a frozen build must pass app_root explicitly
    app_root = app_root or str(Path(__file__).resolve().parents[1] / "app")
    search_dirs = _library_dirs(project_path, app_root)
    template_data: dict[str, dict] = {}
    for task_name, task_definition in (project_data.get("TaskDefinitions") or {}).items():
        template = _find_template(
            search_dirs, candidate_template_names(task_name, task_definition)
        )
        if template is not None:
            template_data[task_name] = template

    if compute_participant_stats is None:
        from src.web.blueprints.projects_metadata_helpers import (
            _compute_participant_stats as compute_participant_stats,
        )

    participant_stats = compute_participant_stats(project_path, lang=lang)
    md, sections_used = generate_full_methods(
        project_data,
        dataset_desc,
        template_data,
        participant_stats=participant_stats,
        acquisition=acquisition_summary(project_path),
        processing=processing_summary(project_path),
        lang=lang,
        detail_level=detail_level,
        continuous=True,  # methods output is always continuous prose
    )
    return MethodsResult(
        md,
        sections_used,
        methods_warnings(project_data, participant_stats, template_data),
        template_data,
    )


def render_methods(result: MethodsResult, fmt: str) -> bytes:
    """Bytes of a methods result in ``fmt`` (md/html/docx/tex, or bib for the references)."""
    from src.text_export import convert, references_bib

    if fmt == "bib":
        return references_bib(result.template_data).encode("utf-8")
    return convert(result.md, fmt)
