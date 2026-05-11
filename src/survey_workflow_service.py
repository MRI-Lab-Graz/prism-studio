from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


_BOOLEAN_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_VALID_DUPLICATE_HANDLING = {"error", "keep_first", "keep_last", "sessions"}
_NEAR_MATCH_CONFIRMATION_MESSAGE = (
    "Exact matching left item-like columns unmapped. "
    "Safe near matches are available (minimal separator/zero-padding differences). "
    "Confirm to apply them."
)
_WORKFLOW_STALE_FOLLOWUP_ERRORS = {
    "near_item_match_confirmation_required",
    "value_offset_manual_review_required",
}

SUPPORTED_SURVEY_TABULAR_SUFFIXES = {
    ".xlsx",
    ".csv",
    ".tsv",
    ".sav",
    ".rds",
    ".rdata",
    ".rda",
}
SUPPORTED_SURVEY_INPUT_SUFFIXES = SUPPORTED_SURVEY_TABULAR_SUFFIXES | {".lsa"}
SUPPORTED_SURVEY_INPUT_MESSAGE = (
    "Supported formats: .xlsx, .lsa, .csv, .tsv, .sav, .rds, .rdata, .rda"
)


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
    template_version_overrides: dict[str, Any] | list[dict[str, Any]] = field(
        default_factory=dict
    )
    allow_near_item_match: bool = False
    near_match_tasks: list[str] | None = None
    task_value_offsets: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SurveyWorkflowStageFormFields:
    id_column: str | None
    session_column: str | None
    run_column: str | None
    session_override: str | None
    sheet: str | int
    unknown: str
    dataset_name: str | None
    language: str | None
    strict_levels: bool
    allow_near_item_match: bool
    duplicate_handling: str


class SurveyWorkflowStageService:
    def __init__(self, *, tabular_suffixes: Iterable[str]):
        self._tabular_suffixes = {str(value).lower() for value in tabular_suffixes}

    @staticmethod
    def _parse_optional_string(value: Any) -> str | None:
        parsed = str(value or "").strip()
        return parsed or None

    def parse_stage_form_fields(
        self,
        *,
        form: Mapping[str, Any],
    ) -> SurveyWorkflowStageFormFields:
        strict_levels_raw = str(form.get("strict_levels") or "").strip().lower()
        allow_near_item_match_raw = (
            str(form.get("allow_near_item_match") or "").strip().lower()
        )
        duplicate_handling = str(form.get("duplicate_handling") or "error").strip()
        if duplicate_handling not in _VALID_DUPLICATE_HANDLING:
            duplicate_handling = "error"

        sheet = str(form.get("sheet") or "0").strip() or 0
        unknown = str(form.get("unknown") or "warn").strip() or "warn"

        return SurveyWorkflowStageFormFields(
            id_column=self._parse_optional_string(form.get("id_column")),
            session_column=self._parse_optional_string(form.get("session_column")),
            run_column=self._parse_optional_string(form.get("run_column")),
            session_override=self._parse_optional_string(form.get("session")),
            sheet=sheet,
            unknown=unknown,
            dataset_name=self._parse_optional_string(form.get("dataset_name")),
            language=self._parse_optional_string(form.get("language")),
            strict_levels=strict_levels_raw in _BOOLEAN_TRUTHY_VALUES,
            allow_near_item_match=allow_near_item_match_raw
            in _BOOLEAN_TRUTHY_VALUES,
            duplicate_handling=duplicate_handling,
        )

    @staticmethod
    def parse_prepared_workflow_flag(raw_value: Any) -> bool:
        return str(raw_value or "").strip().lower() in _BOOLEAN_TRUTHY_VALUES

    @staticmethod
    def build_near_match_confirmation_payload(
        *,
        near_match_candidates: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        candidates = list(near_match_candidates or [])
        return {
            "error": "near_item_match_confirmation_required",
            "message": _NEAR_MATCH_CONFIRMATION_MESSAGE,
            "near_match_candidates": candidates,
            "near_match_count": len(candidates),
        }

    @staticmethod
    def build_template_completion_required_payload(
        *,
        workflow_gate: Mapping[str, Any],
        template_issues: list[dict[str, Any]] | None,
    ) -> dict[str, Any]:
        return {
            "error": "project_template_completion_required",
            "message": str(workflow_gate.get("message") or "").strip(),
            "workflow_gate": dict(workflow_gate),
            "template_issues": list(template_issues or []),
        }

    @staticmethod
    def format_workflow_preparation_stale_response(
        *,
        payload: Mapping[str, Any] | None,
        prepared_workflow: bool,
        log_messages: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        normalized_payload: dict[str, Any] = dict(payload or {})
        blocking_error = str(normalized_payload.get("error") or "").strip()

        if log_messages is not None:
            normalized_payload["log"] = log_messages

        if not prepared_workflow or not blocking_error:
            return normalized_payload

        message = str(normalized_payload.get("message") or "").strip()
        if not message:
            message = "Survey setup changed after preparation."

        if (
            blocking_error in _WORKFLOW_STALE_FOLLOWUP_ERRORS
            and "Run Preview again" not in message
        ):
            message = f"{message} Run Preview again to refresh setup before continuing."

        normalized_payload["blocking_error"] = blocking_error
        normalized_payload["error"] = "workflow_preparation_stale"
        normalized_payload["message"] = message
        return normalized_payload

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
        template_version_overrides_payload: Any
        if isinstance(options.template_version_overrides, dict):
            template_version_overrides_payload = dict(options.template_version_overrides)
        elif isinstance(options.template_version_overrides, list):
            template_version_overrides_payload = [
                dict(entry) if isinstance(entry, dict) else entry
                for entry in options.template_version_overrides
            ]
        else:
            template_version_overrides_payload = options.template_version_overrides

        task_value_offsets_payload: Any
        if isinstance(options.task_value_offsets, dict):
            task_value_offsets_payload = dict(options.task_value_offsets)
        else:
            task_value_offsets_payload = options.task_value_offsets

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
            "template_version_overrides": template_version_overrides_payload,
            "allow_near_item_match": options.allow_near_item_match,
            "near_match_tasks": list(options.near_match_tasks) if options.near_match_tasks is not None else None,
            "task_value_offsets": task_value_offsets_payload,
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