"""Export PRISM survey/ data to a vanilla BIDS phenotype/ directory.

This is a compatibility bridge, not PRISM's native survey format. PRISM
stores survey data per-subject/session (``sub-*/ses-*/survey/*_survey.tsv``)
because different acquisition variants of the same instrument can have
different item sets and scale ranges (see ``VariantScales``/
``ApplicableVersions`` in the survey schema) - a single wide
``phenotype/<name>.tsv`` table cannot express that without either losing
information or padding mismatched columns with NaNs. Exporting to
phenotype/ is therefore intentionally lossy: only participant/session item
*values* are guaranteed to transfer, not PRISM's richer instrument metadata
(Reversed, MinValue/MaxValue, VariantDefinitions, Citation, ...).

Each (TaskName, VariantID) pair becomes its own phenotype file so item sets
and scales never get silently blended. Multiple runs of the same
task/variant for one subject/session are not supported (no ``run-``
equivalent in phenotype/); such cases are skipped and reported as warnings
rather than guessed at.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from src.bids_entity_parser import BidsEntityParser

_SURVEY_FILENAME_PATTERN = re.compile(
    # TaskName/VariantID allow internal hyphens (see survey.schema.json's
    # TaskName pattern ^[a-zA-Z0-9][-a-zA-Z0-9]*$), unlike sub-/ses- labels.
    r"^sub-(?P<subject>[A-Za-z0-9]+)_ses-(?P<session>[A-Za-z0-9]+)_"
    r"task-(?P<task>[A-Za-z0-9][-A-Za-z0-9]*)(?:_acq-(?P<acq>[A-Za-z0-9][-A-Za-z0-9]*))?"
    r"(?:_run-(?P<run>[A-Za-z0-9]+))?_survey\.tsv$"
)

@dataclass
class PhenotypeExportFile:
    """One phenotype/<name>.tsv + sidecar, ready to be written out."""

    name: str
    dataframe: pd.DataFrame
    sidecar: dict[str, Any]


@dataclass
class PhenotypeExportResult:
    """All phenotype files produced for a dataset, plus any skip warnings."""

    files: list[PhenotypeExportFile] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _parse_survey_filename(path: Path) -> Optional[dict[str, Optional[str]]]:
    match = _SURVEY_FILENAME_PATTERN.match(path.name)
    if match is None:
        return None
    return match.groupdict()


def _discover_survey_files(
    dataset_root: Path,
    *,
    exclude_subjects: Optional[set[str]] = None,
    exclude_sessions: Optional[set[str]] = None,
) -> list[Path]:
    exclude_subjects = exclude_subjects or set()
    exclude_sessions = exclude_sessions or set()
    found: list[Path] = []
    for subject_dir in sorted(dataset_root.glob("sub-*")):
        if not subject_dir.is_dir() or subject_dir.name in exclude_subjects:
            continue
        for session_dir in sorted(subject_dir.glob("ses-*")):
            if not session_dir.is_dir() or session_dir.name in exclude_sessions:
                continue
            survey_dir = session_dir / "survey"
            if not survey_dir.is_dir():
                continue
            found.extend(sorted(survey_dir.glob("*_survey.tsv")))
    return found


def _group_survey_files(
    survey_files: list[Path],
) -> tuple[dict[tuple[str, Optional[str]], list[Path]], list[str]]:
    """Group survey TSVs by (task, variant); flag any per-subject/session runs."""
    groups: dict[tuple[str, Optional[str]], list[Path]] = {}
    seen_subject_session: dict[tuple[str, Optional[str], str, str], Path] = {}
    warnings: list[str] = []

    for path in survey_files:
        parsed = _parse_survey_filename(path)
        if parsed is None:
            warnings.append(f"Skipped unrecognized survey filename: {path.name}")
            continue

        task = parsed["task"]
        variant = parsed["acq"]
        subject = parsed["subject"]
        session = parsed["session"]
        assert task is not None and subject is not None and session is not None

        dedup_key = (task, variant, subject, session)
        if dedup_key in seen_subject_session:
            warnings.append(
                "Skipped multiple runs for the same subject/session/task/variant "
                f"(phenotype/ has no run- equivalent): {path.name}"
            )
            continue
        seen_subject_session[dedup_key] = path

        groups.setdefault((task, variant), []).append(path)

    return groups, warnings


def _load_sidecars(
    dataset_root: Path, task: str, variant: Optional[str]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (task-level sidecar, variant-level sidecar) parsed JSON, {} if missing."""
    task_sidecar_path = dataset_root / f"task-{task}_survey.json"
    task_sidecar = {}
    if task_sidecar_path.is_file():
        task_sidecar = json.loads(task_sidecar_path.read_text(encoding="utf-8"))

    if variant:
        variant_sidecar_path = dataset_root / f"task-{task}_acq-{variant}_survey.json"
    else:
        variant_sidecar_path = task_sidecar_path
    variant_sidecar = task_sidecar
    if variant_sidecar_path.is_file():
        variant_sidecar = json.loads(variant_sidecar_path.read_text(encoding="utf-8"))

    return task_sidecar, variant_sidecar


def _item_levels_for_variant(item_def: dict[str, Any], variant: Optional[str]) -> Any:
    if variant:
        for scale in item_def.get("VariantScales") or []:
            if scale.get("VariantID") == variant and "Levels" in scale:
                return scale["Levels"]
    return item_def.get("Levels")


def build_phenotype_sidecar(
    variant_sidecar: dict[str, Any],
    columns: list[str],
    *,
    task: str,
    variant: Optional[str],
) -> dict[str, Any]:
    """Reshape PRISM's nested survey sidecar into a flat, column-keyed dict.

    Vanilla BIDS phenotype/ sidecars are plain ``{column_name: {Description,
    Levels, ...}}`` maps, not PRISM's nested Technical/Study/Items structure -
    only Description and Levels are meaningful to a generic BIDS consumer,
    so everything else (Reversed, MinValue/MaxValue, Citation, ...) is
    dropped rather than copied through.
    """
    sidecar: dict[str, Any] = {
        "MeasurementToolMetadata": {
            "PrismTaskName": task,
            "PrismVariantID": variant,
        }
    }
    for column in columns:
        if column == "participant_id":
            sidecar[column] = {"Description": "Participant identifier"}
            continue
        if column == "session_id":
            sidecar[column] = {"Description": "Session identifier"}
            continue

        item_def = variant_sidecar.get(column)
        if not isinstance(item_def, dict):
            continue
        entry: dict[str, Any] = {}
        if "Description" in item_def:
            entry["Description"] = item_def["Description"]
        levels = _item_levels_for_variant(item_def, variant)
        if levels:
            entry["Levels"] = levels
        if entry:
            sidecar[column] = entry
    return sidecar


def _phenotype_file_name(task: str, variant: Optional[str], has_multiple_variants: bool) -> str:
    if variant and has_multiple_variants:
        return f"{task}-{variant}"
    return task


def collect_phenotype_bridge_files(
    dataset_root: Path,
    *,
    exclude_subjects: Optional[set[str]] = None,
    exclude_sessions: Optional[set[str]] = None,
) -> PhenotypeExportResult:
    """Aggregate PRISM survey/ data into one PhenotypeExportFile per (task, variant)."""
    survey_files = _discover_survey_files(
        dataset_root,
        exclude_subjects=exclude_subjects,
        exclude_sessions=exclude_sessions,
    )
    if not survey_files:
        return PhenotypeExportResult()

    groups, warnings = _group_survey_files(survey_files)
    variants_per_task: dict[str, set[Optional[str]]] = {}
    for task, variant in groups:
        variants_per_task.setdefault(task, set()).add(variant)

    results: list[PhenotypeExportFile] = []
    for (task, variant), paths in groups.items():
        rows: list[dict[str, Any]] = []
        has_session = False
        columns_order: list[str] = []

        for path in paths:
            parsed = _parse_survey_filename(path)
            assert parsed is not None
            subject_dir = path.parent.parent.parent
            session_dir = path.parent.parent
            subject_label = BidsEntityParser.subject_label_from_dir(subject_dir.name)
            session_label = BidsEntityParser.session_label_from_dir(session_dir.name)

            df = pd.read_csv(path, sep="\t", dtype=str)
            if len(df) != 1:
                warnings.append(
                    f"Expected exactly one data row in {path.name}, found {len(df)}; skipped."
                )
                continue

            row: dict[str, Any] = {"participant_id": f"sub-{subject_label}"}
            if session_label:
                row["session_id"] = f"ses-{session_label}"
                has_session = True
            row.update(df.iloc[0].to_dict())
            rows.append(row)
            for column in row:
                if column not in columns_order:
                    columns_order.append(column)

        if not rows:
            continue

        if not has_session:
            columns_order = [c for c in columns_order if c != "session_id"]

        wide_df = pd.DataFrame(rows)
        ordered_columns = [c for c in columns_order if c in wide_df.columns]
        wide_df = wide_df[ordered_columns]

        _task_sidecar, variant_sidecar = _load_sidecars(dataset_root, task, variant)
        sidecar = build_phenotype_sidecar(
            variant_sidecar, ordered_columns, task=task, variant=variant
        )

        name = _phenotype_file_name(
            task, variant, has_multiple_variants=len(variants_per_task[task]) > 1
        )
        results.append(
            PhenotypeExportFile(name=name, dataframe=wide_df, sidecar=sidecar)
        )

    return PhenotypeExportResult(files=results, warnings=warnings)
