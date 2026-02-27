"""Task sidecar writing helpers for survey conversion."""

from __future__ import annotations

from datetime import datetime


def _write_task_sidecars(
    *,
    tasks_with_data: set[str],
    dataset_root,
    templates: dict,
    language: str | None,
    force: bool,
    technical_overrides: dict | None,
    missing_token: str,
    localize_survey_template_fn,
    inject_missing_token_fn,
    apply_technical_overrides_fn,
    strip_internal_keys_fn,
    write_json_fn,
) -> None:
    """Write task-level survey sidecars with required PRISM fields."""
    for task in sorted(tasks_with_data):
        sidecar_path = dataset_root / f"task-{task}_survey.json"
        if not sidecar_path.exists() or force:
            localized = localize_survey_template_fn(
                templates[task]["json"], language=language
            )
            localized = inject_missing_token_fn(localized, token=missing_token)
            if technical_overrides:
                localized = apply_technical_overrides_fn(localized, technical_overrides)

            if "Metadata" not in localized:
                localized["Metadata"] = {
                    "SchemaVersion": "1.1.1",
                    "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
                    "Creator": "prism-studio",
                }

            if "Technical" not in localized or not isinstance(
                localized.get("Technical"), dict
            ):
                localized["Technical"] = {}
            tech = localized["Technical"]
            if "StimulusType" not in tech:
                tech["StimulusType"] = "Questionnaire"
            if "FileFormat" not in tech:
                tech["FileFormat"] = "tsv"
            if "Language" not in tech:
                tech["Language"] = language or ""
            if "Respondent" not in tech:
                tech["Respondent"] = "self"

            if "Study" not in localized or not isinstance(localized.get("Study"), dict):
                localized["Study"] = {}
            study = localized["Study"]
            if "TaskName" not in study:
                study["TaskName"] = task
            if "OriginalName" not in study:
                study["OriginalName"] = study.get("TaskName", task)
            if "LicenseID" not in study:
                study["LicenseID"] = "Other"
            if "License" not in study:
                study["License"] = ""

            cleaned = strip_internal_keys_fn(localized)
            write_json_fn(sidecar_path, cleaned)
