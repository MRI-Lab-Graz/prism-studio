"""
Shared utilities for conversion blueprints.
Helper functions and common logic used across survey, biometrics, physio converters.
"""

import json
import re
import unicodedata
from pathlib import Path
from flask import current_app
import pandas as pd
from src.converters.file_reader import read_tabular_file

SEPARATOR_MAP: dict[str, str] = {
    "comma": ",",
    "semicolon": ";",
    "tab": "\t",
    "pipe": "|",
}


def normalize_separator_option(value: str | None) -> str:
    """Normalize separator form value to supported options."""
    normalized = str(value or "auto").strip().lower()
    if normalized in {"", "auto", "default"}:
        return "auto"
    if normalized in SEPARATOR_MAP:
        return normalized
    raise ValueError(
        "Invalid separator option. Use one of: auto, comma, semicolon, tab, pipe"
    )


def expected_delimiter_for_suffix(suffix: str, separator_option: str) -> str | None:
    """Return delimiter to use for a file suffix and normalized separator option."""
    if separator_option != "auto":
        return SEPARATOR_MAP[separator_option]
    if suffix == ".tsv":
        return "\t"
    if suffix == ".csv":
        return ","
    return None


def resolve_existing_project_root(project_path_value: str | Path | None) -> Path | None:
    """Resolve a session project path to an existing project root directory."""
    raw_value = str(project_path_value or "").strip()
    if not raw_value:
        return None

    from .projects_helpers import _resolve_project_root_path

    return _resolve_project_root_path(raw_value)


def require_existing_project_root(
    project_path_value: str | Path | None,
    *,
    missing_message: str,
    missing_path_message: str,
) -> Path:
    """Resolve and require an existing project root for project-bound converters."""
    raw_value = str(project_path_value or "").strip()
    if not raw_value:
        raise ValueError(missing_message)

    project_root = resolve_existing_project_root(raw_value)
    if project_root is None:
        raise FileNotFoundError(missing_path_message)

    return project_root


def summarize_project_output_paths(
    copied_paths: list[Path],
    *,
    project_root: Path,
    limit: int | None = None,
) -> list[str]:
    """Return stable, deduplicated output paths relative to a project root."""
    summarized: list[str] = []
    seen: set[str] = set()

    for copied_path in copied_paths:
        try:
            path_text = copied_path.relative_to(project_root).as_posix()
        except ValueError:
            path_text = copied_path.as_posix()

        if path_text in seen:
            continue

        seen.add(path_text)
        summarized.append(path_text)

    summarized.sort()
    if limit is not None:
        return summarized[:limit]
    return summarized


def _coerce_template_version_value(raw_value: object) -> str:
    """Collapse template version payloads to a concrete version string."""
    if isinstance(raw_value, str):
        return raw_value.strip()
    if isinstance(raw_value, dict):
        if "version" in raw_value:
            nested_value = _coerce_template_version_value(raw_value.get("version"))
            if nested_value:
                return nested_value
        for lang in ("en", "de"):
            candidate = raw_value.get(lang)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        for candidate in raw_value.values():
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
    return ""


def _normalize_run_entity(run_value: object) -> str | None:
    text = str(run_value or "").strip()
    if not text:
        return None
    label = text[4:] if text[:4].lower() == "run-" else text
    label = re.sub(r"[^A-Za-z0-9]+", "", label)
    if not label:
        raise ValueError(
            "Invalid template version selection payload. Run must contain only letters and numbers."
        )
    return f"run-{label}"


def parse_template_version_overrides(
    raw_value: str | None,
) -> dict[str, str] | list[dict[str, object]]:
    """Parse template version overrides from a JSON form field.

    Supported payloads:
    - {"task": "version"}
    - [{"task": "task", "version": "version", "session": "ses-pre", "run": "run-A"}]
    """
    text = str(raw_value or "").strip()
    if not text:
        return []

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Invalid template version selection payload. Expected JSON object."
        ) from exc

    if isinstance(payload, dict):
        legacy_overrides: dict[str, str] = {}
        contextual_overrides: list[dict[str, object]] = []
        for raw_task, raw_value in payload.items():
            task = str(raw_task or "").strip().lower()
            if not task:
                continue
            if isinstance(raw_value, dict):
                version = _coerce_template_version_value(raw_value)
                session_name = str(raw_value.get("session") or "").strip() or None
                run_value = raw_value.get("run")
            else:
                version = _coerce_template_version_value(raw_value)
                session_name = None
                run_value = None
            if not version:
                continue
            run_entity = None
            if run_value not in {None, ""}:
                try:
                    run_entity = _normalize_run_entity(run_value)
                except ValueError as exc:
                    raise ValueError(str(exc)) from exc
            if run_entity is None and session_name is None:
                legacy_overrides[task] = version
            else:
                contextual_overrides.append(
                    {
                        "task": task,
                        "version": version,
                        "session": session_name,
                        "run": run_entity,
                    }
                )
        if contextual_overrides:
            contextual_overrides.extend(
                {"task": task, "version": version, "session": None, "run": None}
                for task, version in sorted(legacy_overrides.items())
            )
            return contextual_overrides
        return legacy_overrides

    if not isinstance(payload, list):
        raise ValueError(
            "Invalid template version selection payload. Expected JSON object or array."
        )

    overrides: list[dict[str, object]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise ValueError(
                "Invalid template version selection payload. Expected array entries to be objects."
            )
        task = str(entry.get("task") or "").strip().lower()
        version = _coerce_template_version_value(entry.get("version"))
        if not task or not version:
            continue
        session_name = str(entry.get("session") or "").strip() or None
        run_entity = None
        run_value = entry.get("run")
        if run_value not in {None, ""}:
            try:
                run_entity = _normalize_run_entity(run_value)
            except ValueError as exc:
                raise ValueError(str(exc)) from exc
        overrides.append(
            {
                "task": task,
                "version": version,
                "session": session_name,
                "run": run_entity,
            }
        )

    return overrides


def collect_multivariant_tasks_from_library(
    *,
    library_dir: str | Path,
    tasks: list[str] | None = None,
    selected_versions: list[dict[str, object]] | dict[str, str] | None = None,
) -> dict[str, dict]:
    """Return multi-version task metadata for templates in a survey library."""
    survey_dir = Path(library_dir).expanduser().resolve()
    if (survey_dir / "survey").is_dir() and not list(survey_dir.glob("survey-*.json")):
        survey_dir = survey_dir / "survey"
    if not survey_dir.is_dir():
        return {}

    selected_tasks = {
        str(task).strip().lower() for task in (tasks or []) if str(task).strip()
    }
    requested_versions: dict[str, str] = {}
    if isinstance(selected_versions, dict):
        requested_versions = {
            str(task).strip().lower(): _coerce_template_version_value(version)
            for task, version in selected_versions.items()
            if str(task).strip() and _coerce_template_version_value(version)
        }
    elif isinstance(selected_versions, list):
        for entry in selected_versions:
            if not isinstance(entry, dict):
                continue
            task = str(entry.get("task") or "").strip().lower()
            version = _coerce_template_version_value(entry.get("version"))
            run_value = entry.get("run")
            if not task or not version or run_value not in {None, ""}:
                continue
            requested_versions[task] = version

    result: dict[str, dict] = {}
    for json_file in sorted(survey_dir.glob("survey-*.json")):
        try:
            payload = json.loads(json_file.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(payload, dict):
            continue

        study = payload.get("Study", {})
        if not isinstance(study, dict):
            continue

        task_from_name = json_file.stem.replace("survey-", "")
        task_name = str(study.get("TaskName") or task_from_name).strip().lower()
        if not task_name:
            continue
        if selected_tasks and task_name not in selected_tasks:
            continue

        versions_raw = study.get("Versions")
        versions = []
        if isinstance(versions_raw, list):
            versions = [
                str(value).strip() for value in versions_raw if str(value).strip()
            ]

        if len(versions) <= 1:
            continue

        default_version = _coerce_template_version_value(study.get("Version"))
        if not default_version and versions:
            default_version = versions[0]

        result[task_name] = {
            "versions": versions,
            "default_version": default_version,
            "selected_version": requested_versions.get(task_name, default_version),
            "variant_definitions": study.get("VariantDefinitions", []),
        }

    return result


def normalize_filename(name: str) -> str:
    """Normalize filename to ASCII-safe characters (e.g., remove umlauts)."""
    dash_map = {
        ord("–"): "-",  # en dash
        ord("—"): "-",  # em dash
        ord("‑"): "-",  # non-breaking hyphen
        ord("−"): "-",  # minus sign
        ord("‐"): "-",  # hyphen
    }
    normalized = name.translate(dash_map)
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"\s+", "_", normalized)
    return normalized


def read_tabular_dataframe_robust(
    input_path: Path,
    *,
    expected_delimiter: str | None,
    dtype=str,
) -> pd.DataFrame:
    """Read CSV/TSV robustly across BOM and delimiter mismatch cases.

    This helper keeps parser behavior consistent across converter endpoints.
    """
    suffix = input_path.suffix.lower()
    if suffix == ".xlsx":
        kind = "xlsx"
    elif suffix == ".tsv":
        kind = "tsv"
    elif suffix == ".csv":
        kind = "csv"
    else:
        kind = "tsv" if expected_delimiter == "\t" else "csv"

    try:
        result = read_tabular_file(
            input_path,
            kind=kind,
            separator=expected_delimiter,
        )
        if kind != "xlsx" and looks_like_wrong_delimiter(result.df, expected_delimiter):
            raise ValueError(
                "Likely wrong delimiter; retrying with compatibility fallback"
            )
        return result.df
    except ValueError as primary_error:
        if kind == "xlsx":
            raise

        attempts: list[dict] = []

        if expected_delimiter:
            attempts.append({"sep": expected_delimiter})

        for candidate in (",", "\t", ";"):
            if candidate != expected_delimiter:
                attempts.append({"sep": candidate})

        attempts.append({"sep": None, "engine": "python"})

        if expected_delimiter:
            attempts.append(
                {
                    "sep": expected_delimiter,
                    "engine": "python",
                    "on_bad_lines": "skip",
                }
            )
        for candidate in (",", "\t", ";"):
            if candidate != expected_delimiter:
                attempts.append(
                    {
                        "sep": candidate,
                        "engine": "python",
                        "on_bad_lines": "skip",
                    }
                )
        attempts.append({"sep": None, "engine": "python", "on_bad_lines": "skip"})

        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            for read_kwargs in attempts:
                try:
                    df = pd.read_csv(
                        input_path,
                        dtype=dtype,
                        encoding=encoding,
                        **read_kwargs,
                    )
                except Exception as error:
                    last_error = error
                    continue

                if looks_like_wrong_delimiter(df, read_kwargs.get("sep")):
                    continue

                return df

        if last_error is not None:
            raise ValueError(
                "Could not parse tabular input. Check delimiter (CSV vs TSV), "
                "encoding (UTF-8/CP1252), and header row integrity."
            ) from last_error

        raise primary_error


def looks_like_wrong_delimiter(df: pd.DataFrame, used_delimiter: str | None) -> bool:
    """Detect likely delimiter mismatch by inspecting single-column headers."""
    if len(df.columns) != 1:
        return False

    header = str(df.columns[0])
    candidate_delimiters = {",", "\t", ";"}
    if used_delimiter in candidate_delimiters:
        candidate_delimiters.remove(used_delimiter)

    return any(delimiter in header for delimiter in candidate_delimiters)


def should_retry_with_official_library(err: Exception) -> bool:
    """Return true when converter error suggests official-template fallback."""
    msg = str(err).lower()
    return isinstance(err, ValueError) and (
        "no survey item columns matched" in msg or "unknown surveys:" in msg
    )


def is_project_code_library(library_dir: str | Path, project_path: str | None) -> bool:
    """Check if selected library path points to current project's code/library."""
    if not project_path:
        return False
    project_root = Path(project_path).expanduser().resolve()
    if project_root.is_file():
        project_root = project_root.parent

    library_dir = Path(library_dir).expanduser().resolve()
    code_library = project_root / "code" / "library"
    return library_dir in {code_library, code_library / "survey"}


def extract_tasks_from_output(output_root: Path) -> list[str]:
    """Extract unique task names from BIDS-style filenames in output directory."""
    tasks = set()
    for file_path in output_root.rglob("*"):
        if file_path.is_file() and "_task-" in file_path.name:
            match = re.search(r"_task-([a-zA-Z0-9]+)", file_path.name)
            if match:
                tasks.add(match.group(1))
    return sorted(tasks)


def participant_json_candidates(library_root: Path, depth: int = 3):
    """List possible participants.json locations above a library root."""
    library_root = library_root.resolve()
    candidates = [library_root / "participants.json"]
    for parent in library_root.parents[:depth]:
        candidates.append(parent / "participants.json")
    return candidates


def log_file_head(input_path: Path, suffix: str, log_func):
    """Helper to log the first few lines of a file to debug delimiter or structure issues."""
    try:
        if suffix in {".csv", ".tsv"}:
            with open(input_path, "r", encoding="utf-8", errors="replace") as f:
                head_lines = []
                for i in range(4):
                    line = f.readline()
                    if not line:
                        break
                    head_lines.append(f"  L{i + 1}: {line.strip()}")
                if head_lines:
                    log_func(
                        "Detected file content (first 4 lines):\n"
                        + "\n".join(head_lines),
                        "info",
                    )
        elif suffix == ".xlsx":
            try:
                df = read_tabular_file(input_path, kind="xlsx").df.head(4)
                head_lines = []
                # Header row
                cols = [str(c) for c in df.columns]
                head_lines.append("  H:  " + "\t".join(cols))
                # Data rows
                for i, row in df.iterrows():
                    vals = [str(v) for v in row.values]
                    head_lines.append(f"  R{i + 1}: " + "\t".join(vals))
                if head_lines:
                    log_func(
                        "Detected Excel structure (first 4 rows):\n"
                        + "\n".join(head_lines),
                        "info",
                    )
            except Exception as e:
                log_func(f"Could not read Excel preview: {str(e)}", "warning")
    except Exception as e:
        log_func(f"Could not log file head: {str(e)}", "warning")


def resolve_effective_library_path(project_path_value: str | Path | None = None) -> Path:
    """
    Automatically resolve library path:
    1. First, try project's /code/library (only if it has templates)
    2. Then try project's /official/library (or /official/library/survey)
    3. Fall back to global library

    Returns the resolved Path to the library root.
    Raises an error if no valid library is found.
    """

    def _safe_resolve(path: Path) -> Path:
        """Safely resolve path, handling network drives."""
        try:
            return path.resolve()
        except (OSError, ValueError):
            # For network paths that can't be resolved, return as-is
            return path

    def _safe_expand(path_str: str) -> Path:
        """Safely expand path, handling network drives."""
        try:
            candidate = Path(path_str)
            if "~" in path_str:
                candidate = candidate.expanduser()
            return candidate
        except (OSError, ValueError):
            return Path(path_str)

    from src.web.blueprints.projects import get_current_project

    # Try project library first, then project official templates.
    project_path = str(project_path_value or "").strip()
    if not project_path:
        project = get_current_project()
        project_path = project.get("path")

    if project_path:
        project_root = _safe_expand(project_path)
        try:
            project_root = _safe_resolve(project_root)
        except Exception:
            pass

        def _has_survey_templates(path: Path) -> bool:
            if not path.exists() or not path.is_dir():
                return False
            survey_dir = path / "survey" if (path / "survey").is_dir() else path
            try:
                return bool(list(survey_dir.glob("survey-*.json")))
            except (OSError, ValueError):
                return False

        # Preferred: project code/library — use it even if empty so project-local
        # templates are always tried first. Missing templates are pulled from the
        # official library on demand by the fallback mechanism.
        project_library = project_root / "code" / "library"
        if project_library.is_dir() or (project_library / "survey").is_dir():
            # Ensure the directory exists so the converter can write into it
            (project_library / "survey").mkdir(parents=True, exist_ok=True)
            return project_library

        # Next: project official library
        official_library = project_root / "official" / "library"
        if _has_survey_templates(official_library):
            return official_library

        # Also accept direct official/library/survey as root
        official_survey = official_library / "survey"
        if _has_survey_templates(official_survey):
            return official_survey
        # If project libraries exist but lack templates, fall through to global library

    # Fall back to global library
    from src.config import get_effective_library_paths

    # current_app.root_path points to /app directory, we need to go up one level to get to the workspace root
    base_dir = Path(current_app.root_path)
    try:
        base_dir = base_dir.parent.resolve()
    except (OSError, ValueError):
        base_dir = base_dir.parent

    lib_paths = get_effective_library_paths(app_root=str(base_dir))

    if lib_paths.get("global_library_path"):
        global_lib = _safe_expand(lib_paths["global_library_path"])
        try:
            global_lib = _safe_resolve(global_lib)
        except Exception:
            pass
        if global_lib.exists() and global_lib.is_dir():
            return global_lib

    # Last resort: check default locations
    default_locations = [
        base_dir / "library" / "survey_i18n",
        base_dir / "survey_library",
        base_dir / "official" / "library",
    ]

    for location in default_locations:
        try:
            if location.exists() and location.is_dir():
                return location
        except (OSError, ValueError):
            continue

    raise FileNotFoundError(
        "No survey library found. Please provide templates in project /code/library (preferred), project /official/library, or configure a global library."
    )


def resolve_validation_library_path(
    *,
    project_path: str | None,
    fallback_library_root: str | Path,
) -> Path:
    """Resolve a single library root for validation.

    Validation should run against exactly one context:
    - project library when a project is active
    - otherwise the provided fallback library root
    """
    if project_path:
        project_root = Path(project_path).expanduser().resolve()
        if project_root.is_file():
            project_root = project_root.parent

        project_code_library = project_root / "code" / "library"
        if project_code_library.exists() and project_code_library.is_dir():
            return project_code_library

        project_library = project_root / "library"
        if project_library.exists() and project_library.is_dir():
            return project_library

    return Path(fallback_library_root)
