"""Import a vanilla BIDS phenotype/ directory into PRISM's survey/ layout.

This is a compatibility bridge, not a replacement for PRISM's native survey
converters (Excel/CSV/LimeSurvey). It intentionally does the minimum useful
thing: every phenotype/*.tsv file becomes one PRISM task with no acquisition
variant, every non-structural column becomes a survey item with only the
metadata the phenotype .json sidecar (if any) actually provides - there is
no attempt to fuzzy-match columns against the instrument library or to
recover scale semantics (Reversed, MinValue/MaxValue, ...) that were never
present in phenotype/ to begin with. Import is designed to run
automatically and silently (see ProjectManager.init_on_existing_bids), so
it must never guess in a way that could silently misrepresent data.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

_TASK_NAME_SANITIZE_PATTERN = re.compile(r"[^A-Za-z0-9-]+")
_TASK_NAME_COLLAPSE_HYPHENS = re.compile(r"-{2,}")

_STRUCTURAL_COLUMNS = ("participant_id", "session_id")

_LIKELY_NON_ITEM_COLUMN_HINTS = {
    "age",
    "sex",
    "gender",
    "group",
    "handedness",
    "education",
}

DEFAULT_IMPORT_SESSION_LABEL = "import"


@dataclass
class PhenotypeImportSummary:
    """Result of importing one or more phenotype/*.tsv files."""

    created_files: list[str] = field(default_factory=list)
    log: list[dict[str, str]] = field(default_factory=list)
    imported_task_count: int = 0
    flagged_columns: list[str] = field(default_factory=list)

    def add_log(self, message: str, level: str = "info") -> None:
        self.log.append({"message": message, "level": level})


def sanitize_task_name_from_phenotype_filename(stem: str) -> str:
    """Derive a PRISM-valid TaskName from a phenotype/<stem>.tsv filename.

    TaskName allows internal hyphens (pattern ``^[a-zA-Z0-9][-a-zA-Z0-9]*$``),
    so this is deliberately less aggressive than the physio-converter's
    ``_sanitize_bids_label`` (which strips all non-alphanumerics including
    hyphens): underscores/whitespace become hyphens instead of vanishing,
    keeping multi-word measurement tool names readable.
    """
    name = stem.split("_desc-", 1)[0]
    name = name.strip().lower().replace("_", "-")
    name = re.sub(r"\s+", "-", name)
    name = _TASK_NAME_SANITIZE_PATTERN.sub("", name)
    name = _TASK_NAME_COLLAPSE_HYPHENS.sub("-", name)
    name = name.strip("-")
    return name or "phenotype"


def flag_non_item_columns(columns: list[str]) -> list[str]:
    """Return columns that look like they might belong in participants.tsv instead.

    Advisory only - flagged columns are still imported as survey items
    verbatim; this never auto-routes data into participants.tsv, which
    would risk clobbering real participant-level data.
    """
    return [c for c in columns if c.lower() in _LIKELY_NON_ITEM_COLUMN_HINTS]


def _build_minimal_sidecar(
    task_name: str,
    item_columns: list[str],
    phenotype_sidecar: dict[str, Any],
) -> dict[str, Any]:
    items: dict[str, Any] = {}
    for column in item_columns:
        column_meta = phenotype_sidecar.get(column)
        item_def: dict[str, Any] = {
            "Description": column,
            "Reversed": False,
        }
        if isinstance(column_meta, dict):
            if column_meta.get("Description"):
                item_def["Description"] = column_meta["Description"]
            if column_meta.get("Levels"):
                item_def["Levels"] = column_meta["Levels"]
        items[column] = item_def

    return {
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "tsv",
            "SoftwarePlatform": "",
            "Language": "",
            "Respondent": "self",
            "AdministrationMethod": "",
        },
        "Metadata": {
            "SchemaVersion": "1.2.0",
            "CreationDate": "",
        },
        "Study": {
            "TaskName": task_name,
            "OriginalName": task_name,
            "Citation": "Imported from a BIDS phenotype/ directory; no citation available.",
            "LicenseID": "Other",
        },
        **items,
    }


def import_phenotype_file(
    tsv_path: Path,
    project_root: Path,
    *,
    json_path: Optional[Path] = None,
    default_session_label: str = DEFAULT_IMPORT_SESSION_LABEL,
) -> PhenotypeImportSummary:
    """Import one phenotype/<name>.tsv (+ optional sidecar) into PRISM survey/."""
    summary = PhenotypeImportSummary()

    df = pd.read_csv(tsv_path, sep="\t", dtype=str)
    if "participant_id" not in df.columns:
        summary.add_log(
            f"Skipped {tsv_path.name}: no 'participant_id' column found.",
            "warning",
        )
        return summary

    phenotype_sidecar: dict[str, Any] = {}
    if json_path is not None and json_path.is_file():
        phenotype_sidecar = json.loads(json_path.read_text(encoding="utf-8"))

    task_name = sanitize_task_name_from_phenotype_filename(tsv_path.stem)
    has_session_column = "session_id" in df.columns
    item_columns = [c for c in df.columns if c not in _STRUCTURAL_COLUMNS]

    flagged = flag_non_item_columns(item_columns)
    if flagged:
        summary.flagged_columns.extend(flagged)
        summary.add_log(
            f"Task '{task_name}': column(s) {', '.join(flagged)} look like "
            "participant-level variables - consider moving them to "
            "participants.tsv instead of keeping them as survey items.",
            "warning",
        )

    if not has_session_column:
        summary.add_log(
            f"Task '{task_name}': phenotype/{tsv_path.name} has no session_id "
            f"column; imported under a synthetic 'ses-{default_session_label}' "
            "since PRISM's survey/ layout is organized per session.",
            "warning",
        )

    written_any_row = False
    for _, row in df.iterrows():
        participant_id = str(row["participant_id"]).strip()
        if not participant_id.startswith("sub-"):
            summary.add_log(
                f"Skipped row with unexpected participant_id '{participant_id}' "
                f"in {tsv_path.name} (expected a 'sub-' prefix).",
                "warning",
            )
            continue

        if has_session_column:
            session_id = str(row["session_id"]).strip()
            if not session_id.startswith("ses-"):
                summary.add_log(
                    f"Skipped row with unexpected session_id '{session_id}' "
                    f"in {tsv_path.name} (expected a 'ses-' prefix).",
                    "warning",
                )
                continue
        else:
            session_id = f"ses-{default_session_label}"

        survey_dir = project_root / participant_id / session_id / "survey"
        survey_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"{participant_id}_{session_id}_task-{task_name}_survey.tsv"
        out_path = survey_dir / out_name

        row_df = pd.DataFrame([{c: row[c] for c in item_columns}])
        row_df.to_csv(out_path, sep="\t", index=False, lineterminator="\n")
        summary.created_files.append(
            str(out_path.relative_to(project_root))
        )
        written_any_row = True

    if not written_any_row:
        return summary

    sidecar_path = project_root / f"task-{task_name}_survey.json"
    if not sidecar_path.is_file():
        sidecar = _build_minimal_sidecar(task_name, item_columns, phenotype_sidecar)
        sidecar_path.write_text(
            json.dumps(sidecar, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        summary.created_files.append(sidecar_path.name)

    summary.imported_task_count = 1
    summary.add_log(
        f"Imported phenotype/{tsv_path.name} as PRISM task '{task_name}' "
        f"({len(item_columns)} item column(s)).",
        "success",
    )
    return summary


def import_phenotype_directory(
    phenotype_dir: Path,
    project_root: Path,
    *,
    default_session_label: str = DEFAULT_IMPORT_SESSION_LABEL,
) -> PhenotypeImportSummary:
    """Import every phenotype/*.tsv file found in ``phenotype_dir``."""
    aggregate = PhenotypeImportSummary()

    for tsv_path in sorted(phenotype_dir.glob("*.tsv")):
        json_path = tsv_path.with_suffix(".json")
        file_summary = import_phenotype_file(
            tsv_path,
            project_root,
            json_path=json_path if json_path.is_file() else None,
            default_session_label=default_session_label,
        )
        aggregate.created_files.extend(file_summary.created_files)
        aggregate.log.extend(file_summary.log)
        aggregate.imported_task_count += file_summary.imported_task_count
        aggregate.flagged_columns.extend(file_summary.flagged_columns)

    if aggregate.imported_task_count:
        aggregate.log.insert(
            0,
            {
                "message": (
                    f"Detected phenotype/ directory: imported "
                    f"{aggregate.imported_task_count} task(s) into PRISM's "
                    "survey/ layout as a compatibility bridge. Review the "
                    "generated sidecars - metadata like scale definitions is "
                    "not recoverable from phenotype/ and was left minimal."
                ),
                "level": "info",
            },
        )

    return aggregate
