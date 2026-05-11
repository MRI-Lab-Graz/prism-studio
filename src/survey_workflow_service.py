from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class SurveyWorkflowStageOptions:
    suffix: str
    input_path: Path
    library_dir: Path
    output_root: Path
    survey: str | None = None
    id_column: str | None = None
    session_column: str | None = None
    run_column: str | None = None
    session: str | None = None
    sheet: str | int = 0
    unknown: str = "warn"
    dry_run: bool = False
    force: bool = True
    name: str | None = None
    authors: tuple[str, ...] = ()
    language: str | None = None
    alias_file: Path | None = None
    id_map_file: Path | None = None
    strict_levels: bool = False
    separator: str | None = None
    duplicate_handling: str = "error"
    skip_participants: bool = True
    project_path: str | None = None
    fallback_project_path: str | None = None
    log_fn: Callable[[str, str], Any] | None = None
    template_version_overrides: dict[str, Any] = field(default_factory=dict)
    allow_near_item_match: bool = False
    near_match_tasks: list[str] | None = None
    task_value_offsets: dict[str, Any] = field(default_factory=dict)


class SurveyWorkflowStageService:
    def __init__(self, *, tabular_suffixes: Iterable[str]):
        self._tabular_suffixes = {str(value).lower() for value in tabular_suffixes}

    def resolve_effective_survey_dir(
        self,
        *,
        library_path: Path,
        fallback_project_path: str | None = None,
        resolve_official_survey_dir: Callable[[str | None], Path | None] | None = None,
    ) -> Path:
        survey_dir = library_path / "survey" if (library_path / "survey").is_dir() else library_path
        survey_templates = list(survey_dir.glob("survey-*.json"))
        if survey_templates:
            return survey_dir

        if callable(resolve_official_survey_dir):
            official_fallback = resolve_official_survey_dir(fallback_project_path)
            if official_fallback:
                return Path(official_fallback)

        raise FileNotFoundError(f"No survey templates found in: {survey_dir}")

    def run_stage(
        self,
        *,
        workflow_runner: Callable[..., Any],
        tabular_converter: Any,
        lsa_converter: Any,
        options: SurveyWorkflowStageOptions,
    ) -> Any:
        common_kwargs: dict[str, Any] = {
            "input_path": options.input_path,
            "library_dir": str(options.library_dir),
            "output_root": options.output_root,
            "survey": options.survey,
            "id_column": options.id_column,
            "session_column": options.session_column,
            "run_column": options.run_column,
            "session": options.session,
            "unknown": options.unknown,
            "dry_run": options.dry_run,
            "force": options.force,
            "name": options.name,
            "authors": list(options.authors),
            "language": options.language,
            "alias_file": options.alias_file,
            "id_map_file": options.id_map_file,
            "duplicate_handling": options.duplicate_handling,
            "skip_participants": options.skip_participants,
            "fallback_project_path": options.fallback_project_path,
            "template_version_overrides": dict(options.template_version_overrides),
            "allow_near_item_match": options.allow_near_item_match,
            "near_match_tasks": list(options.near_match_tasks) if options.near_match_tasks is not None else None,
            "task_value_offsets": dict(options.task_value_offsets),
        }
        if options.log_fn is not None:
            common_kwargs["log_fn"] = options.log_fn

        normalized_suffix = str(options.suffix).lower()
        if normalized_suffix in self._tabular_suffixes:
            if tabular_converter is None:
                raise RuntimeError("Tabular survey converter is not available")
            return workflow_runner(
                tabular_converter,
                **common_kwargs,
                sheet=options.sheet,
                separator=options.separator,
            )

        if normalized_suffix == ".lsa":
            if lsa_converter is None:
                raise RuntimeError("LimeSurvey archive converter is not available")
            return workflow_runner(
                lsa_converter,
                **common_kwargs,
                strict_levels=True if options.strict_levels else None,
                project_path=options.project_path,
            )

        raise ValueError(f"Unsupported survey input suffix: {options.suffix}")