"""Survey conversion utilities.

This module provides a programmatic API for converting wide survey tables (e.g. .xlsx)
into a PRISM/BIDS-style survey dataset.

It is extracted from the CLI implementation in `prism_tools.py` so the Web UI and
GUI can call the same logic without invoking subprocesses or relying on `sys.exit`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import csv
import json
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
import re
from typing import Iterable


_NON_ITEM_TOPLEVEL_KEYS = {
    "Technical",
    "Study",
    "Metadata",
    # Template metadata (not survey response columns)
    "I18n",
    "LimeSurvey",
}


@dataclass(frozen=True)
class SurveyConvertResult:
    tasks_included: list[str]
    unknown_columns: list[str]
    missing_items_by_task: dict[str, int]
    id_column: str
    session_column: str | None


def sanitize_id(id_str: str) -> str:
    """Sanitize IDs by replacing German umlauts and special characters."""
    if not id_str:
        return id_str
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for char, repl in replacements.items():
        id_str = id_str.replace(char, repl)
    return id_str


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def _load_participants_template(library_dir: Path) -> dict | None:
    """Load a participant template from the survey library, if present.

    The repo currently ships `survey-participant.json` (singular). Some users may
    refer to `survey-participants.json` (plural), so we accept both.
    """

    for name in ("survey-participants.json", "survey-participant.json"):
        p = library_dir / name
        if p.exists() and p.is_file():
            try:
                return _read_json(p)
            except Exception:
                return None
    return None


def _is_participant_template(path: Path) -> bool:
    stem = path.stem.lower()
    return stem in {"survey-participant", "survey-participants"}


def _participants_json_from_template(*, columns: list[str], template: dict | None) -> dict:
    """Create a BIDS-style participants.json for the given TSV columns."""

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


def convert_survey_xlsx_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
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
        unknown=unknown,
        dry_run=dry_run,
        force=force,
        name=name,
        authors=authors,
        language=language,
        alias_file=alias_file,
    )


def convert_survey_lsa_to_prism_dataset(
    *,
    input_path: str | Path,
    library_dir: str | Path,
    output_root: str | Path,
    survey: str | None = None,
    id_column: str | None = None,
    session_column: str | None = None,
    unknown: str = "warn",
    dry_run: bool = False,
    force: bool = False,
    name: str | None = None,
    authors: list[str] | None = None,
    language: str | None = None,
    alias_file: str | Path | None = None,
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

    return _convert_survey_dataframe_to_prism_dataset(
        df=df,
        library_dir=library_dir,
        output_root=output_root,
        survey=survey,
        id_column=id_column,
        session_column=session_column,
        unknown=unknown,
        dry_run=dry_run,
        force=force,
        name=name,
        authors=authors,
        language=effective_language,
        technical_overrides=inferred_tech,
        alias_file=alias_file,
    )


def _read_table_as_dataframe(*, input_path: Path, kind: str, sheet: str | int = 0):
    try:
        import pandas as pd
    except Exception as e:  # pragma: no cover
        raise RuntimeError(
            "pandas is required for survey conversion. Ensure dependencies are installed via setup.sh"
        ) from e

    if kind == "xlsx":
        try:
            df = pd.read_excel(input_path, sheet_name=sheet)
        except Exception as e:
            raise ValueError(f"Failed to read Excel: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input table is empty.")

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "csv":
        try:
            df = pd.read_csv(input_path)
        except Exception as e:
            raise ValueError(f"Failed to read CSV: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input CSV is empty.")

        return df.rename(columns={c: str(c).strip() for c in df.columns})

    if kind == "tsv":
        try:
            df = pd.read_csv(input_path, sep="\t")
        except Exception as e:
            raise ValueError(f"Failed to read TSV: {e}") from e

        if df is None or df.empty:
            raise ValueError("Input TSV is empty.")

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
    unknown: str,
    dry_run: bool,
    force: bool,
    name: str | None,
    authors: list[str] | None,
    language: str | None,
    technical_overrides: dict | None = None,
    alias_file: str | Path | None = None,
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

    alias_map: dict[str, str] | None = None
    canonical_aliases: dict[str, list[str]] | None = None
    if alias_file:
        alias_path = Path(alias_file).resolve()
        if not alias_path.exists() or not alias_path.is_file():
            raise ValueError(f"Alias file not found: {alias_path}")
        rows = _read_alias_rows(alias_path)
        if rows:
            alias_map = _build_alias_map(rows)
            canonical_aliases = _build_canonical_aliases(rows)

    # --- Load survey templates ---
    templates: dict[str, dict] = {}
    item_to_task: dict[str, str] = {}
    duplicate_items: dict[str, set[str]] = {}

    for json_path in sorted(library_dir.glob("survey-*.json")):
        if _is_participant_template(json_path):
            continue
        try:
            sidecar = _read_json(json_path)
        except Exception:
            continue

        task_from_name = json_path.stem.replace("survey-", "")
        task = str(sidecar.get("Study", {}).get("TaskName") or task_from_name).strip()
        if not task:
            task = task_from_name
        task_norm = task.lower()
        if canonical_aliases:
            sidecar = _canonicalize_template_items(sidecar=sidecar, canonical_aliases=canonical_aliases)

        templates[task_norm] = {"path": json_path, "json": sidecar, "task": task_norm}

        for k in sidecar.keys():
            if k in _NON_ITEM_TOPLEVEL_KEYS:
                continue
            if k in item_to_task and item_to_task[k] != task_norm:
                duplicate_items.setdefault(k, set()).update({item_to_task[k], task_norm})
            else:
                item_to_task[k] = task_norm

    if not templates:
        raise ValueError(f"No survey templates found in: {library_dir} (expected survey-*.json)")

    if duplicate_items:
        msg_lines = ["Duplicate item IDs found across survey templates (ambiguous mapping):"]
        for item_id, tasks in sorted(duplicate_items.items()):
            msg_lines.append(f"- {item_id}: {', '.join(sorted(tasks))}")
        raise ValueError("\n".join(msg_lines))

    # --- Parse --survey filter ---
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

    def _find_col(candidates: set[str]) -> str | None:
        lower_map = {str(c).strip().lower(): str(c).strip() for c in df.columns}
        for c in candidates:
            if c in lower_map:
                return lower_map[c]
        return None

    resolved_id_col = id_column
    if resolved_id_col:
        if resolved_id_col not in df.columns:
            raise ValueError(
                f"id_column '{resolved_id_col}' not found. Columns: {', '.join([str(c) for c in df.columns])}"
            )
    else:
        # LimeSurvey response archives commonly use `token`.
        resolved_id_col = _find_col({"participant_id", "subject", "id", "sub_id", "participant", "code", "token"})
        if not resolved_id_col:
            raise ValueError(
                "Could not determine participant id column. Provide id_column explicitly (e.g., participant_id, CODE)."
            )

    resolved_session_col: str | None
    if session_column:
        if session_column not in df.columns:
            raise ValueError(f"session_column '{session_column}' not found in input columns")
        resolved_session_col = session_column
    else:
        resolved_session_col = _find_col({"session", "ses", "visit", "timepoint"})

    # --- Optional alias mapping (canonical_id + aliases) ---
    # Apply after ID/session detection to avoid surprises.
    if alias_map:
        df = _apply_alias_map_to_dataframe(df=df, alias_map=alias_map)

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

    # --- Determine which columns map to which surveys ---
    cols = [c for c in df.columns if c not in {resolved_id_col} and c != resolved_session_col]
    col_to_task: dict[str, str] = {}
    unknown_cols: list[str] = []
    for c in cols:
        if c in item_to_task:
            col_to_task[c] = item_to_task[c]
        else:
            unknown_cols.append(c)

    tasks_with_data = set(col_to_task.values())
    if selected_tasks is not None:
        tasks_with_data = tasks_with_data.intersection(selected_tasks)

    if not tasks_with_data:
        raise ValueError("No survey item columns matched the selected templates.")

    # Missing-items report
    missing_items_by_task: dict[str, int] = {}
    for task in sorted(tasks_with_data):
        schema = templates[task]["json"]
        expected = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS]
        present = [c for c, t in col_to_task.items() if t == task]
        missing = [k for k in expected if k not in present]
        missing_items_by_task[task] = len(missing)

    if unknown_cols and unknown == "error":
        raise ValueError("Unmapped columns: " + ", ".join(unknown_cols))

    if dry_run:
        return SurveyConvertResult(
            tasks_included=sorted(tasks_with_data),
            unknown_columns=unknown_cols,
            missing_items_by_task=missing_items_by_task,
            id_column=resolved_id_col,
            session_column=resolved_session_col,
        )

    # --- Write output dataset ---
    _ensure_dir(output_root)

    ds_desc = output_root / "dataset_description.json"
    if not ds_desc.exists():
        dataset_description = {
            "Name": name or "PRISM Survey Dataset",
            "BIDSVersion": "1.8.0",
            "DatasetType": "raw",
            "Authors": authors or ["prism-validator"],
        }
        _write_json(ds_desc, dataset_description)

    # participants.tsv
    df_part = pd.DataFrame({"participant_id": df[resolved_id_col].astype(str).map(_normalize_sub_id)})
    lower_to_col = {str(c).strip().lower(): str(c).strip() for c in df.columns}
    extra_part_cols: list[str] = []
    for candidate in ["age", "sex", "gender"]:
        col = lower_to_col.get(candidate)
        if col and col not in {resolved_id_col, resolved_session_col}:
            extra_part_cols.append(col)

    if extra_part_cols:
        df_extra = df[[resolved_id_col] + extra_part_cols].copy()
        for c in extra_part_cols:
            df_extra[c] = df_extra[c].apply(lambda v: "n/a" if pd.isna(v) else v)
        df_extra[resolved_id_col] = df_extra[resolved_id_col].astype(str).map(_normalize_sub_id)
        df_extra = df_extra.groupby(resolved_id_col, dropna=False)[extra_part_cols].first().reset_index()
        df_extra = df_extra.rename(columns={resolved_id_col: "participant_id"})
        df_part = df_part.merge(df_extra, on="participant_id", how="left")

    df_part = df_part.drop_duplicates(subset=["participant_id"]).reset_index(drop=True)
    df_part.to_csv(output_root / "participants.tsv", sep="\t", index=False)

    # participants.json (column metadata)
    participants_json_path = output_root / "participants.json"
    participant_template = _load_participants_template(library_dir)
    participants_json = _participants_json_from_template(
        columns=[str(c) for c in df_part.columns],
        template=participant_template,
    )
    _write_json(participants_json_path, participants_json)

    # inherited sidecars at dataset root (inheritance principle)
    for task in sorted(tasks_with_data):
        sidecar_path = output_root / f"survey-{task}_beh.json"
        if not sidecar_path.exists() or force:
            localized = _localize_survey_template(templates[task]["json"], language=language)
            if technical_overrides:
                localized = _apply_technical_overrides(localized, technical_overrides)
            _write_json(sidecar_path, localized)

    def _normalize_item_value(val) -> str:
        if pd.isna(val):
            return "n/a"
        if isinstance(val, bool):
            return str(val)
        if isinstance(val, int):
            return str(int(val))
        if isinstance(val, float):
            if val.is_integer():
                return str(int(val))
            return str(val)
        return str(val)

    # per-subject TSVs
    for _, row in df.iterrows():
        sub_id = _normalize_sub_id(row[resolved_id_col])
        ses_id = _normalize_ses_id(row[resolved_session_col]) if resolved_session_col else "ses-1"

        modality_dir = _ensure_dir(output_root / sub_id / ses_id / "survey")

        for task in sorted(tasks_with_data):
            if selected_tasks is not None and task not in selected_tasks:
                continue

            schema = templates[task]["json"]
            expected = [k for k in schema.keys() if k not in _NON_ITEM_TOPLEVEL_KEYS]
            present_cols = [c for c, t in col_to_task.items() if t == task]
            if not present_cols:
                continue

            out: dict[str, str] = {}
            for item_id in expected:
                if item_id in df.columns:
                    out[item_id] = _normalize_item_value(row[item_id])
                else:
                    out[item_id] = "n/a"

            # stable column order
            with open(modality_dir / f"{sub_id}_{ses_id}_task-{task}_beh.tsv", "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=expected, delimiter="\t", lineterminator="\n")
                writer.writeheader()
                writer.writerow(out)

    return SurveyConvertResult(
        tasks_included=sorted(tasks_with_data),
        unknown_columns=unknown_cols,
        missing_items_by_task=missing_items_by_task,
        id_column=resolved_id_col,
        session_column=resolved_session_col,
    )


def _localize_survey_template(template: dict, *, language: str | None) -> dict:
    """Convert i18n-capable survey templates into schema-valid single-language sidecars.

    The stable survey schema expects:
    - item `Description` as string
    - item `Levels` values as string
    - `Study.OriginalName` as string
    and does not allow arbitrary top-level keys like `I18n`.

    If `language` is None or "auto", uses `I18n.DefaultLanguage` if present, else `Technical.Language`.
    """

    out = deepcopy(template)

    i18n = out.get("I18n")
    default_lang = None
    if isinstance(i18n, dict):
        v = i18n.get("DefaultLanguage")
        if isinstance(v, str) and v.strip():
            default_lang = v.strip()

    tech_lang = None
    if isinstance(out.get("Technical"), dict):
        v = out["Technical"].get("Language")
        if isinstance(v, str) and v.strip():
            tech_lang = v.strip()

    chosen = (language or "").strip() or None
    if chosen and chosen.lower() == "auto":
        chosen = None
    chosen = chosen or default_lang or tech_lang or "en"

    # Drop top-level keys that are not survey items / not allowed by schema.
    out.pop("I18n", None)
    out.pop("LimeSurvey", None)

    def pick_lang(val):
        if isinstance(val, dict):
            preferred = val.get(chosen)
            if isinstance(preferred, str) and preferred != "":
                return preferred
            if default_lang:
                fallback = val.get(default_lang)
                if isinstance(fallback, str) and fallback != "":
                    return fallback
            for _, v in val.items():
                if isinstance(v, str) and v != "":
                    return v
            return ""
        if val is None:
            return ""
        return str(val)

    # Technical.Language must be a string.
    if isinstance(out.get("Technical"), dict):
        out["Technical"]["Language"] = chosen

    # Study fields that are often i18n dicts in templates.
    if isinstance(out.get("Study"), dict):
        for key in ("OriginalName", "Version", "Description"):
            if key in out["Study"]:
                out["Study"][key] = pick_lang(out["Study"][key])

    # Item fields
    for key, item in list(out.items()):
        if key in _NON_ITEM_TOPLEVEL_KEYS:
            continue
        if not isinstance(item, dict):
            continue

        if "Description" in item:
            item["Description"] = pick_lang(item.get("Description"))

        levels = item.get("Levels")
        if isinstance(levels, dict):
            new_levels: dict[str, str] = {}
            for lvl_key, lvl_val in levels.items():
                new_levels[str(lvl_key)] = pick_lang(lvl_val)
            item["Levels"] = new_levels

        out[key] = item

    return out


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
