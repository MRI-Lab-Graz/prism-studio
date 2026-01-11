"""Survey conversion utilities.

This module provides a programmatic API for converting wide survey tables (e.g. .xlsx)
into a PRISM/BIDS-style survey dataset.

It is extracted from the CLI implementation in `prism_tools.py` so the Web UI and
GUI can call the same logic without invoking subprocesses or relying on `sys.exit`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import csv
import json
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
import re
from typing import Iterable

from ..utils.io import ensure_dir as _ensure_dir, read_json as _read_json, write_json as _write_json
from ..utils.naming import sanitize_id

_NON_ITEM_TOPLEVEL_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    # Template metadata (not survey response columns)
    "I18n",
    "LimeSurvey",
    "_aliases",
    "_reverse_aliases",
}

_MISSING_TOKEN = "n/a"
_LANGUAGE_KEY_RE = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$", re.IGNORECASE)


@dataclass(frozen=True)
class SurveyConvertResult:
    tasks_included: list[str]
    unknown_columns: list[str]
    missing_items_by_task: dict[str, int]
    id_column: str
    session_column: str | None
    missing_cells_by_subject: dict[str, int] = field(default_factory=dict)
    missing_value_token: str = _MISSING_TOKEN
    conversion_warnings: list[str] = field(default_factory=list)


def _load_participants_template(library_dir: Path) -> dict | None:
    """Load a participant template from the survey library, if present.

    We prioritize a library-level `participants.json` (sibling of the survey/
    folder) and fall back to legacy names `survey-participants.json` and
    `survey-participant.json` placed alongside the survey templates.
    """

    library_dir = library_dir.resolve()
    candidates: list[Path] = []
    if library_dir.name == "survey":
        candidates.append(library_dir.parent / "participants.json")

    candidates.extend(
        [
            library_dir / "participants.json",
            library_dir / "survey-participants.json",
            library_dir / "survey-participant.json",
        ]
    )

    # Also try a few ancestor folders (code/library -> project root) for participants.json
    for ancestor in library_dir.parents[:3]:
        candidates.append(ancestor / "participants.json")

    seen: set[Path] = set()
    for p in candidates:
        if p in seen:
            continue
        seen.add(p)
        if p.exists() and p.is_file():
            try:
                return _read_json(p)
            except Exception:
                return None
    return None


def _is_participant_template(path: Path) -> bool:
    stem = path.stem.lower()
    return stem in {"survey-participant", "survey-participants"}


def _normalize_participant_template_dict(template: dict | None) -> dict | None:
    """Extract column definitions from a participant template structure."""

    if not isinstance(template, dict):
        return None
    if "Columns" in template and isinstance(template.get("Columns"), dict):
        return template.get("Columns")
    return template


def _participants_json_from_template(*, columns: list[str], template: dict | None) -> dict:
    """Create a BIDS-style participants.json for the given TSV columns."""

    template = _normalize_participant_template_dict(template)
    out: dict[str, dict] = {}

    def _template_meta(col: str) -> dict:
        if not template:
            return {}
        if col not in template:
            return {}
        v = template.get(col)
        if not isinstance(v, dict):
            return {}
        meta: dict[str, object] = {}
        desc = v.get("Description")
        if desc:
            meta["Description"] = desc
        levels = v.get("Levels")
        if isinstance(levels, dict) and levels:
            meta["Levels"] = levels
        unit = v.get("Units") or v.get("Unit")
        if unit:
            meta["Units"] = unit
        return meta

    for col in columns:
        if col == "participant_id":
            out[col] = {
                "Description": "Participant identifier (BIDS subject label)",
            }
            continue

        meta = _template_meta(col)
        if not meta:
            # Minimal, valid fallback.
            meta = {"Description": col}
            if col == "age":
                meta["Description"] = "Age"
                meta["Units"] = "years"

        out[col] = dict(meta)

    return out


def _normalize_language(lang: str | None) -> str | None:
    if not lang:
        return None
    norm = str(lang).strip().lower()
    return norm or None


def _default_language_from_template(template: dict) -> str:
    i18n = template.get("I18n")
    if isinstance(i18n, dict):
        default = i18n.get("DefaultLanguage") or i18n.get("defaultlanguage")
        if default:
            return str(default).strip().lower() or "en"

    tech = template.get("Technical")
    if isinstance(tech, dict):
        lang = tech.get("Language")
        if lang:
            return str(lang).strip().lower() or "en"

    return "en"


def _is_language_dict(value: dict) -> bool:
    if not value:
        return False
    return all(_LANGUAGE_KEY_RE.match(str(k)) for k in value.keys())


def _pick_language_value(value: dict, language: str) -> object:
    preference = [language, language.split("-")[0] if "-" in language else language]
    for candidate in preference:
        if candidate in value and value[candidate] not in (None, ""):
            return value[candidate]

    for fallback in value.values():
        if fallback not in (None, ""):
            return fallback
    return next(iter(value.values()))


def _localize_survey_template(template: dict, language: str | None) -> dict:
    if not isinstance(template, dict):
        return template

    lang = _normalize_language(language) or _default_language_from_template(template)

    def _recurse(value):
        if isinstance(value, dict):
            if _is_language_dict(value):
                return _pick_language_value(value, lang)
            return {k: _recurse(v) for k, v in value.items()}
        if isinstance(value, list):
            return [_recurse(v) for v in value]
        return value

    return _recurse(deepcopy(template))


def convert_survey_xlsx_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    session: str | None = None,
    sheet: str | int = 0,
    unknown: str = "warn",
    dry_run: bool = False,
    force: bool = False,
    name: str | None = None,
    authors: list[str] | None = None,
    language: str | None = None,
    alias_file: str | Path | None = None,
) -> SurveyConvertResult:
    """Convert a wide survey Excel table into a PRISM dataset.

    Parameters mirror `prism_tools.py survey convert`.

    Raises:
        ValueError: for user errors (missing files, invalid columns, etc.)
        RuntimeError: for unexpected conversion failures
    """

    input_path = Path(input_path).resolve()
    sheet_arg: str | int = sheet
    if isinstance(sheet_arg, str) and sheet_arg.isdigit():
        sheet_arg = int(sheet_arg)

    suffix = input_path.suffix.lower()
    if suffix not in {".xlsx", ".csv", ".tsv"}:
        raise ValueError("Supported formats: .xlsx, .csv, .tsv")

    kind = "xlsx" if suffix == ".xlsx" else ("csv" if suffix == ".csv" else "tsv")
    df = _read_table_as_dataframe(input_path=input_path, kind=kind, sheet=sheet_arg)

    return _convert_survey_dataframe_to_prism_dataset(
        df=df,
        library_dir=library_dir,
        output_root=output_root,
        survey=survey,
        id_column=id_column,
        session_column=session_column,
        session=session,
        unknown=unknown,
        dry_run=dry_run,
        force=force,
        name=name,
        authors=authors,
        language=language,
        alias_file=alias_file,
        strict_levels=True,
    )


def convert_survey_lsa_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    session: str | None = None,
    unknown: str = "warn",
    dry_run: bool = False,
    force: bool = False,
    name: str | None = None,
    authors: list[str] | None = None,
    language: str | None = None,
    alias_file: str | Path | None = None,
    strict_levels: bool | None = None,
) -> SurveyConvertResult:
    """Convert a LimeSurvey response archive (.lsa) into a PRISM dataset.

    The .lsa file is a zip archive. We extract the embedded *_responses.lsr XML and
    treat it as a wide table where each column is a survey item / variable.
    """

    input_path = Path(input_path).resolve()
    if input_path.suffix.lower() not in {".lsa"}:
        raise ValueError("Currently only .lsa input is supported.")

    df = _read_table_as_dataframe(input_path=input_path, kind="lsa")

    # If language was not explicitly specified, try to infer it from the LSA.
    inferred_lang, inferred_tech = _infer_lsa_language_and_tech(input_path=input_path, df=df)
    effective_language = language
    if not effective_language or effective_language.strip().lower() == "auto":
        effective_language = inferred_lang

    effective_strict_levels = False if strict_levels is None else bool(strict_levels)

    return _convert_survey_dataframe_to_prism_dataset(
        df=df,
        library_dir=library_dir,
        output_root=output_root,
        survey=survey,
        id_column=id_column,
        session_column=session_column,
        session=session,
        unknown=unknown,
        dry_run=dry_run,
        force=force,
        name=name,
        authors=authors,
        language=effective_language,
        technical_overrides=inferred_tech,
        alias_file=alias_file,
        strict_levels=effective_strict_levels,
    )


def _debug_print_file_head(input_path: Path, num_lines: int = 4):
    """Print the first few lines of a text file for debugging/visibility in terminal."""
    try:
        # Avoid binary files
        if input_path.suffix.lower() in {".xlsx", ".xls", ".lsa", ".zip", ".gz"}:
            return

        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            print(f"\n[DEBUG] --- First {num_lines} lines of {input_path.name} ---")
            for i in range(num_lines):
                line = f.readline()
                if not line:
                    break
                print(f"L{i+1}: {line.rstrip()}")
            header_len = 26 + len(input_path.name)
            print("-" * header_len + "\n")
    except Exception:
        # Silently fail if we can't read/print
        pass


def _read_table_as_dataframe(*, input_path: Path, kind: str, sheet: str | int = 0):
    # Print head for visibility in terminal
    _debug_print_file_head(input_path)

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    EmptyDataError = getattr(pd.errors, "EmptyDataError", ValueError)

    if kind == "xlsx":
        try:
            df = pd.read_excel(input_path, sheet_name=sheet)
        except EmptyDataError:
            raise ValueError("Input Excel is empty (no content in file).")
        except Exception as e:
            raise ValueError(f"Failed to read Excel: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input Excel is empty (no content in file).")

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "csv":
        try:
            df = pd.read_csv(input_path)
        except EmptyDataError:
            raise ValueError("Input CSV is empty (no content in file).")
        except Exception as e:
            raise ValueError(f"Failed to read CSV: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input CSV is empty (no content in file).")

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "tsv":
        try:
            df = pd.read_csv(input_path, sep="\t")
        except EmptyDataError:
            raise ValueError("Input TSV is empty (no content in file).")
        except Exception as e:
            raise ValueError(f"Failed to read TSV: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input TSV is empty (no content in file).")

        # Check if file was parsed correctly (wrong delimiter detection)
        if len(df.columns) == 1:
            col_name = str(df.columns[0])
            # If the single column name contains semicolons or commas, likely wrong delimiter
            if ";" in col_name:
                raise ValueError(
                    f"TSV file appears to use semicolons (;) as delimiter instead of tabs. "
                    f"Please convert to tab-separated format or save as CSV."
                )
            elif "," in col_name:
                raise ValueError(
                    f"TSV file appears to use commas as delimiter instead of tabs. "
                    f"Please save as .csv file or convert to tab-separated format."
                )

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "lsa":
        def _normalize_lsa_columns(cols: list[str]) -> list[str]:
            """Normalize LimeSurvey export column names.

            LimeSurvey often uses SGQA-like identifiers in exports.
            In our test dataset we see names like:
              _569818X43541X590135ADS01
            where the trailing part is the question code used in templates.
            We strip the leading '_<digits>X<digits>X<digits>' prefix when a
            non-empty suffix exists.
            """

            pattern = re.compile(r"^_\d+X\d+X\d+(.*)$")
            used: set[str] = set()
            out_cols: list[str] = []
            for c in cols:
                s = str(c).strip()
                m = pattern.match(s)
                candidate = s
                if m:
                    suffix = (m.group(1) or "").strip()
                    if suffix:
                        candidate = suffix
                # avoid collisions
                if candidate in used:
                    candidate = s
                used.add(candidate)
                out_cols.append(candidate)
            return out_cols

        def _find_responses_member(zf: zipfile.ZipFile) -> str:
            matches = [name for name in zf.namelist() if name.endswith("_responses.lsr")]
            if not matches:
                raise ValueError("No *_responses.lsr found inside the .lsa archive")
            matches.sort()
            return matches[0]

        def _parse_rows(xml_bytes: bytes) -> list[dict[str, str]]:
            root = ET.fromstring(xml_bytes)
            rows: list[dict[str, str]] = []
            for row in root.findall(".//row"):
                record: dict[str, str] = {}
                for child in row:
                    tag = child.tag
                    if "}" in tag:
                        tag = tag.split("}", 1)[1]
                    record[tag] = child.text or ""
                rows.append(record)
            return rows

        try:
            with zipfile.ZipFile(input_path) as zf:
                member = _find_responses_member(zf)
                xml_bytes = zf.read(member)
        except zipfile.BadZipFile as e:
            raise ValueError(f"Invalid .lsa archive: {e}") from e
        except Exception as e:
            raise ValueError(f"Failed to read .lsa archive: {e}") from e

        try:
            rows = _parse_rows(xml_bytes)
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse LimeSurvey responses XML: {e}") from e

        df = pd.DataFrame(rows)
        if df is None or df.empty:
            raise ValueError("No response rows found inside the .lsa archive")

        df = df.rename(columns={c: str(c).strip() for c in df.columns})
        df.columns = _normalize_lsa_columns([str(c) for c in df.columns])
        return df

    raise ValueError(f"Unsupported table kind: {kind}")


def _convert_survey_dataframe_to_prism_dataset(
    *,
    df,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None,
    id_column: str | None,
    session_column: str | None,
    session: str | None = None,
    unknown: str,
    dry_run: bool,
    force: bool,
    name: str | None,
    authors: list[str] | None,
    language: str | None,
    technical_overrides: dict | None = None,
    alias_file: str | Path | None = None,
    strict_levels: bool = True,
) -> SurveyConvertResult:
    if unknown not in {"error", "warn", "ignore"}:
        raise ValueError("unknown must be one of: error, warn, ignore")

    library_dir = Path(library_dir).resolve()
    output_root = Path(output_root).resolve()

    if not library_dir.exists() or not library_dir.is_dir():
        raise ValueError(f"Library folder does not exist or is not a directory: {library_dir}")

    if output_root.exists() and any(output_root.iterdir()) and not force:
        raise ValueError(
            f"Output directory is not empty: {output_root}. Use force=True to write into a non-empty directory."
        )

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    # Determine normalization logic
    def _normalize_sub_id(val) -> str:
        s = sanitize_id(str(val).strip())
        if not s:
            return s
        if s.startswith("sub-"):
            return s
        if s.isdigit() and len(s) < 3:
            s = s.zfill(3)
        return f"sub-{s}"

    def _normalize_ses_id(val) -> str:
        s = sanitize_id(str(val).strip())
        if not s:
            return "ses-1"
        if s.startswith("ses-"):
            return s
        return f"ses-{s}"

    def _is_missing_value(val) -> bool:
        if pd.isna(val):
            return True
        if isinstance(val, str) and val.strip() == "":
            return True
        return False

    # --- Load Aliases and Templates ---
    alias_map: dict[str, str] | None = None
    canonical_aliases: dict[str, list[str]] | None = None
    if alias_file:
        alias_path = Path(alias_file).resolve()
        if alias_path.exists() and alias_path.is_file():
            rows = _read_alias_rows(alias_path)
            if rows:
                alias_map = _build_alias_map(rows)
                canonical_aliases = _build_canonical_aliases(rows)

    participant_template = _normalize_participant_template_dict(_load_participants_template(library_dir))
    participant_columns_lower: set[str] = set()
    if participant_template:
        participant_columns_lower = {
            str(k).strip().lower() for k in participant_template.keys() if isinstance(k, str)
        }

    templates, item_to_task, duplicates = _load_and_preprocess_templates(library_dir, canonical_aliases)
    if duplicates:
        msg_lines = ["Duplicate item IDs found across survey templates (ambiguous mapping):"]
        for it_id, tsks in sorted(duplicates.items()):
            msg_lines.append(f"- {it_id}: {', '.join(sorted(tsks))}")
        raise ValueError("\n".join(msg_lines))

    # --- Survey Filtering ---
    selected_tasks: set[str] | None = None
    if survey:
        parts = [p.strip() for p in str(survey).replace(";", ",").split(",")]
        parts = [p for p in parts if p]
        selected = {p.lower().replace("survey-", "") for p in parts}
        unknown_surveys = sorted([t for t in selected if t not in templates])
        if unknown_surveys:
            raise ValueError(
                "Unknown surveys: " + ", ".join(unknown_surveys) + ". Available: " + ", ".join(sorted(templates.keys()))
            )
        selected_tasks = selected

    # --- Determine Columns ---
    res_id_col, res_ses_col = _resolve_id_and_session_cols(df, id_column, session_column)

    if alias_map:
        df = _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)

    # Detect duplicate IDs after normalization
    normalized_ids = df[res_id_col].astype(str).map(_normalize_sub_id)
    if normalized_ids.duplicated().any():
        dup_ids = sorted(set(normalized_ids[normalized_ids.duplicated()]))
        raise ValueError(f"Duplicate participant_id values after normalization: {', '.join(dup_ids[:5])}")

    col_to_task, unknown_cols, conversion_warnings = _map_survey_columns(
        df=df,
        item_to_task=item_to_task,
        participant_columns_lower=participant_columns_lower,
        id_col=res_id_col,
        ses_col=res_ses_col,
        unknown_mode=unknown,
    )

    tasks_with_data = set(col_to_task.values())
    if selected_tasks is not None:
        tasks_with_data = tasks_with_data.intersection(selected_tasks)
    if not tasks_with_data:
        raise ValueError("No survey item columns matched the selected templates.")

    # --- Results Preparation ---
    missing_items_by_task = _compute_missing_items_report(tasks_with_data, templates, col_to_task)

    if dry_run:
        return SurveyConvertResult(
            tasks_included=sorted(tasks_with_data),
            unknown_columns=unknown_cols,
            missing_items_by_task=missing_items_by_task,
            id_column=res_id_col,
            session_column=res_ses_col,
            conversion_warnings=conversion_warnings,
        )

    # --- Write Output ---
    _ensure_dir(output_root)
    _write_survey_description(output_root, name, authors)
    _write_survey_participants(
        df=df,
        output_root=output_root,
        id_col=res_id_col,
        ses_col=res_ses_col,
        participant_template=participant_template,
        normalize_sub_fn=_normalize_sub_id,
        is_missing_fn=_is_missing_value,
    )

    # Write task sidecars
    for task in sorted(tasks_with_data):
        sidecar_path = output_root / f"task-{task}_survey.json"
        if not sidecar_path.exists() or force:
            localized = _localize_survey_template(templates[task]["json"], language=language)
            localized = _inject_missing_token(localized, token=_MISSING_TOKEN)
            if technical_overrides:
                localized = _apply_technical_overrides(localized, technical_overrides)
            _write_json(sidecar_path, localized)

    # --- Process and Write Responses ---
    missing_cells_by_subject: dict[str, int] = {}
    items_using_tolerance: dict[str, set[str]] = {}

    for _, row in df.iterrows():
        sub_id = _normalize_sub_id(row[res_id_col])
        ses_id = _normalize_ses_id(session) if session else (
            _normalize_ses_id(row[res_ses_col]) if res_ses_col else "ses-1"
        )
        modality_dir = _ensure_dir(output_root / sub_id / ses_id / "survey")

        for task in sorted(tasks_with_data):
            if selected_tasks is not None and task not in selected_tasks:
                continue

            schema = templates[task]["json"]
            out_row, missing_count = _process_survey_row(
                row=row,
                df_cols=df.columns,
                task=task,
                schema=schema,
                col_to_task=col_to_task,
                sub_id=sub_id,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                is_missing_fn=_is_missing_value,
                normalize_val_fn=_normalize_item_value,
            )
            missing_cells_by_subject[sub_id] = missing_cells_by_subject.get(sub_id, 0) + missing_count

            # Write TSV
            expected_cols = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS and k not in schema.get("_aliases", {})]
            res_file = modality_dir / f"{sub_id}_{ses_id}_task-{task}_survey.tsv"
            with open(res_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=expected_cols, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerow(out_row)

    # Add summary for items using numeric range tolerance
    if items_using_tolerance:
        for task, item_ids in sorted(items_using_tolerance.items()):
            sorted_items = sorted(list(item_ids))
            shown = ", ".join(sorted_items[:10])
            more = "" if len(sorted_items) <= 10 else f" (+{len(sorted_items)-10} more)"
            conversion_warnings.append(
                f"Task '{task}': Numeric values for items [{shown}{more}] were accepted via range tolerance."
            )

    return SurveyConvertResult(
        tasks_included=sorted(tasks_with_data),
        unknown_columns=unknown_cols,
        missing_items_by_task=missing_items_by_task,
        id_column=res_id_col,
        session_column=res_ses_col,
        missing_cells_by_subject=missing_cells_by_subject,
        missing_value_token=_MISSING_TOKEN,
        conversion_warnings=conversion_warnings,
    )


def _normalize_item_value(val) -> str:
    from pandas import isna
    if isna(val) or (isinstance(val, str) and str(val).strip() == ""):
        return _MISSING_TOKEN
    if isinstance(val, bool):
        return str(val).lower()
    if isinstance(val, int):
        return str(int(val))
    if isinstance(val, float):
        if val.is_integer():
            return str(int(val))
        return str(val)
    return str(val)


def _resolve_id_and_session_cols(
    df, id_column: str | None, session_column: str | None
) -> tuple[str, str | None]:
    """Helper to determine participant ID and session columns from dataframe."""

    def _find_col(candidates: set[str]) -> str | None:
        lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
        for c in candidates:
            if c in lower_map:
                return lower_map[c]
        return None

    resolved_id = id_column
    if resolved_id:
        if resolved_id not in df.columns:
            raise ValueError(
                f"id_column '{resolved_id}' not found. Columns: {', '.join([str(c) for c in df.columns])}"
            )
    else:
        # LimeSurvey response archives commonly use `token`.
        resolved_id = _find_col(
            {"participant_id", "subject", "id", "sub_id", "participant", "code", "token"}
        )
        if not resolved_id:
            raise ValueError(
                "Could not determine participant id column. Provide id_column explicitly (e.g., participant_id, CODE)."
            )

    resolved_ses: str | None
    if session_column:
        if session_column not in df.columns:
            raise ValueError(f"session_column '{session_column}' not found in input columns")
        resolved_ses = session_column
    else:
        resolved_ses = _find_col({"session", "ses", "visit", "timepoint"})

    return str(resolved_id), resolved_ses


def _map_survey_columns(
    *,
    df,
    item_to_task: dict[str, str],
    participant_columns_lower: set[str],
    id_col: str,
    ses_col: str | None,
    unknown_mode: str,
) -> tuple[dict[str, str], list[str], list[str]]:
    """Determine which columns map to which surveys and identify unmapped columns."""
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}

    # Detect participant-related columns first so they are not treated as unmapped survey items.
    participant_fallbacks = {
        "age",
        "sex",
        "gender",
        "education",
        "handedness",
        "completion_date",
    }

    participant_columns_present = {
        lower_to_col[c]
        for c in (participant_columns_lower | participant_fallbacks)
        if c in lower_to_col
    }

    cols = [c for c in df.columns if c not in {id_col} and c != ses_col]
    col_to_task: dict[str, str] = {}
    unknown_cols: list[str] = []
    for c in cols:
        col_lower = str(c).strip().lower()
        if c in item_to_task:
            col_to_task[c] = item_to_task[c]
        elif c in participant_columns_present or col_lower in participant_columns_present:
            continue
        elif col_lower in participant_columns_lower:
            continue
        else:
            unknown_cols.append(c)

    warnings: list[str] = []
    bookkeeping = {
        "id", "submitdate", "lastpage", "startlanguage", "seed", "startdate", "datestamp",
        "token", "refurl", "ipaddr", "googleid", "session_id", "participant_id",
        "attribute_1", "attribute_2", "attribute_3"
    }
    filtered_unknown = [c for c in unknown_cols if str(c).lower() not in bookkeeping]

    if filtered_unknown:
        if unknown_mode == "error":
            raise ValueError("Unmapped columns: " + ", ".join(filtered_unknown))
        if unknown_mode == "warn":
            shown = ", ".join(filtered_unknown[:10])
            more = "" if len(filtered_unknown) <= 10 else f" (+{len(filtered_unknown)-10} more)"
            warnings.append(f"Unmapped columns (not in any survey template): {shown}{more}")

    return col_to_task, unknown_cols, warnings


def _write_survey_description(output_root: Path, name: str | None, authors: list[str] | None):
    """Write dataset_description.json if it doesn't exist."""
    ds_desc = output_root / "dataset_description.json"
    if ds_desc.exists():
        return

    dataset_description = {
        "Name": name or "PRISM Survey Dataset",
        "BIDSVersion": "1.10.1",
        "DatasetType": "raw",
        "Authors": authors or ["PRISM Survey Converter"],
        "HowToAcknowledge": "Please cite the original survey publication and the PRISM framework.",
        "GeneratedBy": [
            {
                "Name": "PRISM Survey Converter",
                "Version": "1.1.1",
                "Description": "Manual survey template mapping and TSV conversion."
            }
        ],
        "HEDVersion": "8.2.0"
    }
    _write_json(ds_desc, dataset_description)


def _write_survey_participants(
    *,
    df,
    output_root: Path,
    id_col: str,
    ses_col: str | None,
    participant_template: dict | None,
    normalize_sub_fn,
    is_missing_fn,
):
    """Write participants.tsv and participants.json."""
    import pandas as pd
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}

    df_part = pd.DataFrame({"participant_id": df[id_col].astype(str).map(normalize_sub_fn)})

    # Determine extra columns from template + standard fallbacks
    extra_cols: list[str] = []
    template_cols = set(participant_template.keys()) if participant_template else set()
    for col in (template_cols | {"age", "sex", "gender", "education", "handedness"}):
        if col in lower_to_col:
            actual = lower_to_col[col]
            if actual not in {id_col, ses_col}:
                extra_cols.append(actual)

    if extra_cols:
        extra_cols = list(dict.fromkeys(extra_cols))
        df_extra = df[[id_col] + extra_cols].copy()
        for c in extra_cols:
            df_extra[c] = df_extra[c].apply(lambda v: _MISSING_TOKEN if is_missing_fn(v) else v)
        df_extra[id_col] = df_extra[id_col].astype(str).map(normalize_sub_fn)
        df_extra = df_extra.groupby("participant_id", dropna=False)[extra_cols].first().reset_index()
        df_part = df_part.merge(df_extra, on="participant_id", how="left")

    df_part = df_part.drop_duplicates(subset=["participant_id"]).reset_index(drop=True)
    df_part.to_csv(output_root / "participants.tsv", sep="\t", index=False)

    # participants.json
    parts_json_path = output_root / "participants.json"
    p_json = _participants_json_from_template(
        columns=[str(c) for c in df_part.columns],
        template=participant_template,
    )
    _write_json(parts_json_path, p_json)


def _load_and_preprocess_templates(
    library_dir: Path, canonical_aliases: dict[str, list[str]] | None
) -> tuple[dict[str, dict], dict[str, str], dict[str, set[str]]]:
    """Load and prepare survey templates from library."""
    templates: dict[str, dict] = {}
    item_to_task: dict[str, str] = {}
    duplicates: dict[str, set[str]] = {}

    for json_path in sorted(library_dir.glob("survey-*.json")):
        if _is_participant_template(json_path):
            continue
        try:
            sidecar = _read_json(json_path)
        except Exception:
            continue

        task_from_name = json_path.stem.replace("survey-", "")
        task = str(sidecar.get("Study", {}).get("TaskName") or task_from_name).strip()
        task_norm = task.lower() or task_from_name.lower()

        if canonical_aliases:
            sidecar = _canonicalize_template_items(sidecar=sidecar, canonical_aliases=canonical_aliases)

        # Pre-process Aliases
        if "_aliases" not in sidecar:
            sidecar["_aliases"] = {}
        if "_reverse_aliases" not in sidecar:
            sidecar["_reverse_aliases"] = {}

        for k, v in list(sidecar.items()):
            if k in _NON_ITEM_TOPLEVEL_KEYS or not isinstance(v, dict):
                continue
            if "Aliases" in v and isinstance(v["Aliases"], list):
                for alias in v["Aliases"]:
                    sidecar["_aliases"][alias] = k
                    sidecar["_reverse_aliases"].setdefault(k, []).append(alias)
            if "AliasOf" in v:
                target = v["AliasOf"]
                sidecar["_aliases"][k] = target
                sidecar["_reverse_aliases"].setdefault(target, []).append(k)

        templates[task_norm] = {"path": json_path, "json": sidecar, "task": task_norm}

        for k, v in sidecar.items():
            if k in _NON_ITEM_TOPLEVEL_KEYS:
                continue
            if k in item_to_task and item_to_task[k] != task_norm:
                duplicates.setdefault(k, set()).update({item_to_task[k], task_norm})
            else:
                item_to_task[k] = task_norm
            # Aliases also mapped to task
            if isinstance(v, dict) and "Aliases" in v and isinstance(v["Aliases"], list):
                for alias in v["Aliases"]:
                    if alias in item_to_task and item_to_task[alias] != task_norm:
                        duplicates.setdefault(alias, set()).update({item_to_task[alias], task_norm})
                    else:
                        item_to_task[alias] = task_norm

    return templates, item_to_task, duplicates


def _compute_missing_items_report(tasks: set[str], templates: dict, col_to_task: dict) -> dict[str, int]:
    report: dict[str, int] = {}
    for task in sorted(tasks):
        schema = templates[task]["json"]
        expected = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS]
        present = [c for c, t in col_to_task.items() if t == task]
        missing = [k for k in expected if k not in present]
        report[task] = len(missing)
    return report


def _process_survey_row(
    *,
    row,
    df_cols,
    task: str,
    schema: dict,
    col_to_task: dict,
    sub_id: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    is_missing_fn,
    normalize_val_fn,
) -> tuple[dict[str, str], int]:
    """Process a single task's data for one subject/session."""
    all_items = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS]
    expected = [k for k in all_items if k not in schema.get("_aliases", {})]
    
    out: dict[str, str] = {}
    missing_count = 0

    for item_id in expected:
        candidates = [item_id] + schema.get("_reverse_aliases", {}).get(item_id, [])
        found_val = None
        found_col = None

        for cand in candidates:
            if cand in df_cols and not is_missing_fn(row[cand]):
                found_val = row[cand]
                found_col = cand
                break

        if found_col:
            # Inline validation using the helper's logic
            _validate_survey_item_value(
                item_id=item_id,
                val=found_val,
                item_schema=schema.get(item_id),
                sub_id=sub_id,
                task=task,
                strict_levels=strict_levels,
                items_using_tolerance=items_using_tolerance,
                normalize_fn=normalize_val_fn,
                is_missing_fn=is_missing_fn,
            )
            norm = normalize_val_fn(found_val)
            if norm == _MISSING_TOKEN:
                missing_count += 1
            out[item_id] = norm
        else:
            out[item_id] = _MISSING_TOKEN
            missing_count += 1
            
    return out, missing_count


def _validate_survey_item_value(
    *,
    item_id: str,
    val,
    item_schema: dict | None,
    sub_id: str,
    task: str,
    strict_levels: bool,
    items_using_tolerance: dict[str, set[str]],
    normalize_fn,
    is_missing_fn,
):
    """Internal validation for a single survey item value."""
    if is_missing_fn(val) or not isinstance(item_schema, dict):
        return

    levels = item_schema.get("Levels")
    if not isinstance(levels, dict) or not levels:
        return

    v_str = normalize_fn(val)
    if v_str == _MISSING_TOKEN:
        return

    if v_str in levels:
        return

    # Try numeric range tolerance
    try:
        def _to_float(x):
            try: return float(str(x).strip())
            except: return None
        
        v_num = _to_float(v_str)
        min_v = _to_float(item_schema.get("MinValue"))
        max_v = _to_float(item_schema.get("MaxValue"))
        
        if v_num is not None and min_v is not None and max_v is not None:
            if min_v <= v_num <= max_v:
                return

        if not strict_levels:
            l_nums = [n for n in [_to_float(k) for k in levels.keys()] if n is not None]
            if len(l_nums) >= 2 and v_num is not None:
                if min(l_nums) <= v_num <= max(l_nums):
                    items_using_tolerance.setdefault(task, set()).add(item_id)
                    return
    except:
        pass

    allowed = ", ".join(sorted(levels.keys()))
    raise ValueError(f"Invalid value '{val}' for '{item_id}' (Sub: {sub_id}, Task: {task}). Expected: {allowed}")


def _read_alias_rows(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue
            parts = [p.strip() for p in (line.split("\t") if "\t" in line else line.split())]
            parts = [p for p in parts if p]
            if len(parts) < 2:
                continue
            rows.append(parts)
    # allow header row
    if rows:
        first = [p.lower() for p in rows[0]]
        if first[0] in {"canonical", "canonical_id", "canonicalid", "id"}:
            rows = rows[1:]
    return rows


def _build_alias_map(rows: Iterable[list[str]]) -> dict[str, str]:
    """Return mapping alias -> canonical (canonical maps to itself)."""
    out: dict[str, str] = {}
    for parts in rows:
        canonical = str(parts[0]).strip()
        if not canonical:
            continue
        # canonical maps to itself
        out.setdefault(canonical, canonical)
        for alias in parts[1:]:
            a = str(alias).strip()
            if not a:
                continue
            if a in out and out[a] != canonical:
                raise ValueError(f"Alias '{a}' maps to multiple canonical IDs: {out[a]} vs {canonical}")
            out[a] = canonical
    return out


def _build_canonical_aliases(rows: Iterable[list[str]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for parts in rows:
        canonical = str(parts[0]).strip()
        if not canonical:
            continue
        aliases = [str(p).strip() for p in parts[1:] if str(p).strip()]
        if not aliases:
            continue
        out.setdefault(canonical, [])
        for a in aliases:
            if a not in out[canonical]:
                out[canonical].append(a)
    return out


def _apply_alias_file_to_dataframe(*, df, alias_file: str | Path) -> "object":
    """Apply alias mapping to dataframe columns.

    Alias file format: TSV/whitespace; each line is:
      <canonical_id> <alias1> <alias2> ...
    """

    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    path = Path(alias_file).resolve()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Alias file not found: {path}")

    rows = _read_alias_rows(path)
    if not rows:
        return df
    alias_map = _build_alias_map(rows)

    return _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)


def _apply_alias_map_to_dataframe(*, df, alias_map: dict[str, str]) -> "object":
    """Apply an alias->canonical mapping to dataframe columns."""

    # Determine which existing columns would map to which canonical ID.
    canonical_to_cols: dict[str, list[str]] = {}
    for c in list(df.columns):
        canonical = alias_map.get(str(c), str(c))
        if canonical != str(c):
            canonical_to_cols.setdefault(canonical, []).append(str(c))

    if not canonical_to_cols:
        return df

    df = df.copy()

    def _as_na(series):
        # Treat empty/whitespace strings as missing for coalescing.
        if series.dtype == object:
            s = series.astype(str)
            s = s.map(lambda v: v.strip() if isinstance(v, str) else v)
            s = s.replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})
            return s
        return series

    for canonical, cols in canonical_to_cols.items():
        cols_present = [c for c in cols if c in df.columns]
        if not cols_present:
            continue

        # Also include canonical itself if present (and coalesce into it).
        if canonical in df.columns and canonical not in cols_present:
            cols_present = [canonical] + cols_present

        if len(cols_present) == 1:
            src = cols_present[0]
            if src != canonical:
                # Only rename if it doesn't collide.
                if canonical not in df.columns:
                    df = df.rename(columns={src: canonical})
            continue

        # Coalesce multiple columns into canonical.
        combined = _as_na(df[cols_present[0]])
        for c in cols_present[1:]:
            combined = combined.combine_first(_as_na(df[c]))

        df[canonical] = combined
        for c in cols_present:
            if c != canonical and c in df.columns:
                df = df.drop(columns=[c])

    return df


def _canonicalize_template_items(*, sidecar: dict, canonical_aliases: dict[str, list[str]]) -> dict:
    """Remove/merge alias item IDs inside a survey template (in-memory).

    If a template contains both canonical and alias item IDs, keep only the canonical key.
    If it contains only the alias key, move it to the canonical key.
    """

    out = dict(sidecar)
    for canonical, aliases in (canonical_aliases or {}).items():
        for alias in aliases:
            if alias not in out:
                continue
            if canonical not in out:
                out[canonical] = out[alias]
            # Always drop the alias key to avoid duplicate columns.
            try:
                del out[alias]
            except Exception:
                pass
    return out


def _apply_technical_overrides(sidecar: dict, overrides: dict) -> dict:
    """Apply best-effort technical metadata without breaking existing templates."""
    out = deepcopy(sidecar)
    tech = out.get("Technical")
    if not isinstance(tech, dict):
        tech = {}
        out["Technical"] = tech

    for k, v in overrides.items():
        # Do not clobber required keys with empty values.
        if v is None:
            continue
        if isinstance(v, str) and v.strip() == "":
            continue
        tech[k] = v

    return out


def _infer_lsa_language_and_tech(*, input_path: Path, df) -> tuple[str | None, dict]:
    """Infer language and technical fields from a LimeSurvey .lsa archive.

    - Language:
      1) response column `startlanguage` if present (mode)
      2) first language found in embedded .lss (structure) export

    - Tech: inject LimeSurvey platform and (if found) version.
    """

    inferred_language: str | None = None
    tech: dict = {
        "SoftwarePlatform": "LimeSurvey",
        # More accurate than many library templates (paper-pencil).
        "CollectionMethod": "online",
        "ResponseType": ["mouse_click", "keypress"],
    }

    meta = infer_lsa_metadata(input_path)
    inferred_language = meta.get("language") or None
    if meta.get("software_version"):
        tech["SoftwareVersion"] = meta["software_version"]

    return inferred_language, tech


def infer_lsa_metadata(input_path: str | Path) -> dict:
    """Infer metadata from a LimeSurvey .lsa archive (best-effort).

    Returns keys:
      - language: str | None
      - software_platform: str (always 'LimeSurvey')
      - software_version: str | None
    """

    input_path = Path(input_path).resolve()
    language: str | None = None
    software_version: str | None = None

    def _mode(values: list[str]) -> str | None:
        if not values:
            return None
        counts: dict[str, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        # deterministic tie-breaker
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]

    def _find_first_text(root: ET.Element, *paths: str) -> str | None:
        for path in paths:
            el = root.find(path)
            if el is not None and el.text and el.text.strip():
                return el.text.strip()
        return None

    try:
        with zipfile.ZipFile(input_path) as zf:
            # responses (language per session)
            resp_members = [n for n in zf.namelist() if n.endswith("_responses.lsr")]
            resp_members.sort()
            if resp_members:
                xml_bytes = zf.read(resp_members[0])
                try:
                    root = ET.fromstring(xml_bytes)
                    vals: list[str] = []
                    for row in root.findall(".//row"):
                        for child in row:
                            tag = child.tag
                            if "}" in tag:
                                tag = tag.split("}", 1)[1]
                            if tag.lower() in {"startlanguage", "start_language"}:
                                v = (child.text or "").strip()
                                if v:
                                    vals.append(v)
                                break
                        if len(vals) >= 2000:
                            break
                    language = _mode(vals)
                except Exception:
                    pass

            # structure (survey language + version)
            lss_members = [n for n in zf.namelist() if n.lower().endswith(".lss")]
            lss_members.sort()
            if lss_members:
                lss_bytes = zf.read(lss_members[0])
                try:
                    root = ET.fromstring(lss_bytes)
                    if not language:
                        language = _find_first_text(
                            root,
                            ".//surveys/rows/row/language",
                            ".//surveys_languagesettings/rows/row/surveyls_language",
                        )
                    software_version = _find_first_text(
                        root,
                        ".//LimeSurveyVersion",
                        ".//limesurveyversion",
                        ".//dbversion",
                        ".//DBVersion",
                    )
                except Exception:
                    pass
    except Exception:
        pass

    return {
        "language": language,
        "software_platform": "LimeSurvey",
        "software_version": software_version,
    }

