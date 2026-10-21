"""Gather everything the methods section needs for a project (one entry point for CLI and GUI)."""

from __future__ import annotations

import csv
import json
import re
import statistics
from datetime import datetime
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


def _task_files(project_path: Path):
    """``(modality, task, subject, session label or "")`` for every task data file in the dataset."""
    from src.environment_mri_scan import resolve_bids_rawdata_root

    root = resolve_bids_rawdata_root(project_path)
    for modality in ("survey", "biometrics"):
        for path in sorted(root.glob(f"sub-*/**/{modality}/*_task-*")):
            match = re.search(r"_task-([A-Za-z0-9]+)", path.name)
            if match and path.suffix in (".tsv", ".gz", ".json"):
                parts = path.relative_to(root).parts
                session = next((p[4:] for p in parts if p.startswith("ses-")), "")
                yield modality, match.group(1), parts[0], session


def discover_tasks(project_path: Path) -> dict[str, dict]:
    """``{task: {"modality": ...}}`` for every ``task-<name>`` data file under the dataset's modality folders."""
    found: dict[str, dict] = {}
    for modality, task, _, _ in _task_files(project_path):
        found.setdefault(task, {"modality": modality})
    return found


def discover_sessions(project_path: Path) -> list[dict]:
    """Sessions found in the dataset, ``{"id", "label", "tasks": [{"task", "n"}], "ordered"}``.

    Labels are kept exactly as found. They are put in numeric order only when all are
    digits (``ordered`` True); any other set is sorted lexically and ``ordered`` is False,
    because the true order of labels like ``pre``/``post`` cannot be known.
    """
    by_session: dict[str, dict[str, set]] = {}
    for _, task, subject, session in _task_files(project_path):
        by_session.setdefault(session, {}).setdefault(task, set()).add(subject)
    labels = list(by_session)
    ordered = len(labels) <= 1 or all(label.isdigit() for label in labels)
    labels.sort(key=lambda label: (int(label), label) if ordered and label.isdigit() else (0, label))
    return [
        {
            "id": f"ses-{label}" if label else "",
            "label": label,
            "tasks": [{"task": t, "n": len(subs)} for t, subs in sorted(by_session[label].items())],
            "ordered": ordered,
        }
        for label in labels
    ]


def _dated_sessions(project_path: Path, pattern: str, read) -> dict[str, dict[str, float]]:
    """``{subject: {session label: earliest time as epoch seconds}}`` from the TSVs matching ``pattern``.

    ``read(tsv_path)`` yields ``(session label, raw time text)``; unparsable times are skipped.
    """
    from src.environment_mri_scan import resolve_bids_rawdata_root

    root = resolve_bids_rawdata_root(project_path)
    found: dict[str, dict[str, float]] = {}
    for tsv in sorted(root.glob(pattern)):
        subject = tsv.relative_to(root).parts[0]
        try:
            for label, raw in read(tsv):
                try:
                    when = datetime.fromisoformat((raw or "").strip()).timestamp()
                except ValueError:  # "n/a", empty, other formats
                    continue
                times = found.setdefault(subject, {})
                times[label] = min(when, times.get(label, when))
        except (OSError, UnicodeDecodeError):
            continue
    return found


def _tsv_rows(tsv: Path):
    with tsv.open(encoding="utf-8", newline="") as fh:
        yield from csv.DictReader(fh, delimiter="\t")


def _from_survey_dates(tsv: Path):
    label = next((p[4:] for p in tsv.parts if p.startswith("ses-")), "")
    return ((label, row.get("SurveyStartDate")) for row in _tsv_rows(tsv))


def _from_sessions_tsv(tsv: Path):
    return (((row.get("session_id") or "")[4:], row.get("acq_time")) for row in _tsv_rows(tsv))


def _from_scans_tsv(tsv: Path):
    return ((tsv.parent.name[4:], row.get("acq_time")) for row in _tsv_rows(tsv))


def add_session_timing(project_path: Path, sessions: list[dict]) -> None:
    """Set ``timingRelativeToBaseline`` (whole days) on sessions, from dates in the data.

    Per subject, a session's offset is the days from that subject's earliest dated session;
    the session gets the median offset over subjects. Sources, first with any data wins:
    ``SurveyStartDate`` in survey TSVs, ``acq_time`` in sessions.tsv, then in scans.tsv.
    Sessions without a later date than the subject's baseline get no key.
    """
    for pattern, read in (
        ("sub-*/**/survey/*.tsv", _from_survey_dates),
        ("sub-*/*_sessions.tsv", _from_sessions_tsv),
        ("sub-*/ses-*/*_scans.tsv", _from_scans_tsv),
    ):
        by_subject = _dated_sessions(project_path, pattern, read)
        if by_subject:
            break
    offsets: dict[str, list[float]] = {}
    for times in by_subject.values():
        if len(times) < 2:
            continue
        baseline = min(times.values())
        for label, when in times.items():
            if when > baseline:
                offsets.setdefault(label, []).append((when - baseline) / 86400)
    for session in sessions:
        if session["label"] in offsets:
            session["timingRelativeToBaseline"] = {
                "Value": round(statistics.median(offsets[session["label"]])),
                "Unit": "days",
            }


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
    if project_path.is_file():  # a project.json path
        project_path = project_path.parent
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

    if not project_data.get("Sessions"):  # declared sessions win over what the files show
        sessions = discover_sessions(project_path)
        add_session_timing(project_path, sessions)
        project_data = {**project_data, "Sessions": sessions}

    # surveys present as data but not declared in project.json still belong in the text
    declared = project_data.get("TaskDefinitions") or {}
    task_defs = {**discover_tasks(project_path), **declared}
    project_data = {**project_data, "TaskDefinitions": task_defs}

    # ponytail: default app_root is the repo's app/ dir; a frozen build must pass app_root explicitly
    app_root = app_root or str(Path(__file__).resolve().parents[1] / "app")
    search_dirs = _library_dirs(project_path, app_root)
    template_data: dict[str, dict] = {}
    for task_name, task_definition in task_defs.items():
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
    from src.text_export import citation_keys, convert, references_bib

    if fmt == "bib":
        return references_bib(result.template_data).encode("utf-8")
    cites = citation_keys(result.template_data) if fmt == "tex" else None
    return convert(result.md, fmt, cites)
