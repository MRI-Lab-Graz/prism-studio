#!/usr/bin/env python3
"""Excel to Biometrics JSON Library Converter

Converts an Excel data dictionary into a library of PRISM-compliant biometrics JSON sidecars.

This mirrors `scripts/excel_to_library.py` (survey) but targets the biometrics schema.

Recommended Excel format (header row, case-insensitive):
- item_id: variable name / column name in the biometrics TSV
- description: description of the metric
- units: unit of measurement (required by biometrics schema)
- datatype: string | integer | float (optional)
- minvalue / maxvalue: numeric bounds (optional)
- warnminvalue / warnmaxvalue: warning bounds (optional)
- allowedvalues: comma/semicolon list or "1=foo;2=bar" (optional)
- group: groups variables into one biometrics JSON per test (e.g., ybalance, cmj)
- alias_of, session, run: accepted for parity with survey import (optional)

If you omit a header row, positional columns map in order:
item_id, description, units, datatype, minvalue, maxvalue, allowedvalues, group, alias_of, session, run.

Usage:
  python scripts/excel_to_biometrics_library.py --excel sport.xlsx --sheet Description --output biometrics_library
"""

import argparse
import json
import re
import sys
import os

import pandas as pd


ID_ALIASES = {"item_id", "id", "code", "variable", "var", "name", "variablename", "variable name"}
DESC_ALIASES = {"description", "question", "text", "item"}
UNITS_ALIASES = {"units", "unit"}
DTYPE_ALIASES = {"datatype", "data_type", "type"}
MIN_ALIASES = {"minvalue", "min", "minimum"}
MAX_ALIASES = {"maxvalue", "max", "maximum"}
WARN_MIN_ALIASES = {"warnminvalue", "warn_min", "warnminimum"}
WARN_MAX_ALIASES = {"warnmaxvalue", "warn_max", "warnmaximum"}
ALLOWED_ALIASES = {"allowedvalues", "allowed_values", "allowed", "values", "options"}
GROUP_ALIASES = {"group", "survey", "section", "domain", "category", "test", "instrument"}
ALIAS_ALIASES = {"alias_of", "alias", "canonical", "duplicate_of", "merge_into"}
SESSION_ALIASES = {"session", "visit", "wave", "timepoint"}
RUN_ALIASES = {"run", "repeat"}
SCALING_ALIASES = {"scale", "scaling", "levels"}

# Optional group-level metadata columns (repeatable on rows; first non-empty per group wins)
TEST_NAME_ALIASES = {"testname", "test_name", "originalname", "original_name", "instrument_name"}
STUDY_DESC_ALIASES = {"studydescription", "study_description", "testdescription", "test_description", "description_long"}
PROTOCOL_ALIASES = {"protocol", "procedure", "method"}
INSTRUCTIONS_ALIASES = {"instructions", "instruction"}
REFERENCE_ALIASES = {"reference", "citation", "doi"}
ESTIMATED_DURATION_ALIASES = {"estimatedduration", "estimated_duration", "duration"}
EQUIPMENT_ALIASES = {"equipment", "device"}
SUPERVISOR_ALIASES = {"supervisor"}


def _norm(s: str) -> str:
    return str(s).replace(" ", "").replace("_", "").lower()


def _find_idx(header_lower, aliases) -> int | None:
    aliases_norm = {_norm(a) for a in aliases}
    for i, val in enumerate(header_lower):
        if _norm(val) in aliases_norm:
            return i
    return None


def _clean_key(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return str(value).strip()


_RANGE_RE_MIN = re.compile(r"\bmin\s*[:=]\s*([-+]?\d+(?:[\.,]\d+)?)", re.IGNORECASE)
_RANGE_RE_MAX = re.compile(r"\bmax\s*[:=]\s*([-+]?\d+(?:[\.,]\d+)?)", re.IGNORECASE)


def _parse_float(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _infer_units(units_cell, scaling_cell, description_cell):
    if units_cell is not None and not (isinstance(units_cell, float) and pd.isna(units_cell)):
        u = str(units_cell).strip()
        if u:
            return u

    for candidate in [scaling_cell, description_cell]:
        if candidate is None or (isinstance(candidate, float) and pd.isna(candidate)):
            continue
        s = str(candidate).strip()
        if not s:
            continue

        # common pattern: "cm; (min: 18 cm; max: 126cm)"
        m = re.match(r"^\s*([a-zA-Z%/]+)\s*;", s)
        if m:
            return m.group(1)

        # common tokens
        lowered = s.lower()
        if "%" in lowered or "percent" in lowered:
            return "percent"
        if "cm" in lowered:
            return "cm"
        if re.search(r"\bmm\b", lowered):
            return "mm"
        if re.search(r"\bsec\b|\bseconds\b|\bs\b", lowered):
            return "sec"
        if "scale" in lowered or "likert" in lowered or "score" in lowered:
            return "score"

    return "n/a"


def _parse_allowed_values(cell):
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None

    if isinstance(cell, (list, tuple)):
        vals = []
        for v in cell:
            vv = _clean_key(v)
            if vv is not None:
                vals.append(vv)
        return vals or None

    s = str(cell).strip()
    if not s or s.lower() == "none":
        return None

    # Range shorthand: "1-10" -> [1,2,...,10] (guard against huge expansions)
    m_range = re.match(r"^\s*([-+]?\d+)\s*-\s*([-+]?\d+)\s*$", s)
    if m_range:
        a = int(m_range.group(1))
        b = int(m_range.group(2))
        if b >= a and (b - a) <= 200:
            return list(range(a, b + 1))

    # "1=foo; 2=bar" -> allowed [1,2]
    if "=" in s:
        keys = []
        for part in re.split(r"[;,]\s*", s):
            if "=" not in part:
                continue
            k, _ = part.split("=", 1)
            k = k.strip()
            if not k:
                continue
            k_num = _parse_float(k)
            keys.append(int(k_num) if k_num is not None and k_num.is_integer() else (k_num if k_num is not None else k))
        return keys or None

    parts = [p.strip() for p in re.split(r"[;,]\s*", s) if p.strip()]
    if not parts:
        return None

    # cast numeric strings
    out = []
    for p in parts:
        n = _parse_float(p)
        if n is None:
            out.append(p)
        else:
            out.append(int(n) if n.is_integer() else n)
    return out


def _parse_levels(cell):
    """Parse a labeled scale like '0=Never; 1=Sometimes' into a Levels mapping."""
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None

    s = str(cell).strip()
    if not s or s.lower() == "none":
        return None

    if "=" not in s:
        return None

    levels = {}
    for part in re.split(r"[;,]\s*", s):
        if "=" not in part:
            continue
        val, label = part.split("=", 1)
        val = val.strip()
        label = label.strip()
        if not val or not label:
            continue
        levels[val] = label

    return levels or None


def _infer_datatype(datatype_cell, units, allowed_values, min_value, max_value):
    if datatype_cell is not None and not (isinstance(datatype_cell, float) and pd.isna(datatype_cell)):
        dt = str(datatype_cell).strip().lower()
        if dt in {"string", "integer", "float"}:
            return dt

    if allowed_values:
        all_int = True
        all_num = True
        for v in allowed_values:
            if isinstance(v, (int, float)):
                if isinstance(v, float) and not v.is_integer():
                    all_int = False
            else:
                all_num = False
                all_int = False
        if all_num:
            return "integer" if all_int else "float"
        return "string"

    if any(v is not None and (isinstance(v, float) and not v.is_integer()) for v in [min_value, max_value]):
        return "float"

    if units in {"n/a"}:
        return "string"

    return "float"


def _parse_minmax(min_cell, max_cell, scaling_cell):
    min_v = _parse_float(min_cell)
    max_v = _parse_float(max_cell)

    if (min_v is None or max_v is None) and scaling_cell is not None and not (isinstance(scaling_cell, float) and pd.isna(scaling_cell)):
        s = str(scaling_cell)
        if min_v is None:
            m = _RANGE_RE_MIN.search(s)
            if m:
                min_v = _parse_float(m.group(1))
        if max_v is None:
            m = _RANGE_RE_MAX.search(s)
            if m:
                max_v = _parse_float(m.group(1))

    return min_v, max_v


def process_excel_biometrics(
    excel_file: str,
    output_dir: str,
    sheet_name: str | int = 0,
    equipment: str = "Legacy/Imported",
    supervisor: str = "investigator",
):
    print(f"Loading biometrics metadata from {excel_file} (sheet={sheet_name})...")
    try:
        df_meta = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        sys.exit(1)

    header_row = df_meta.iloc[0].tolist()
    header_lower = [str(v).strip().lower() for v in header_row]

    id_idx = _find_idx(header_lower, ID_ALIASES)
    desc_idx = _find_idx(header_lower, DESC_ALIASES)
    units_idx = _find_idx(header_lower, UNITS_ALIASES)
    dtype_idx = _find_idx(header_lower, DTYPE_ALIASES)
    min_idx = _find_idx(header_lower, MIN_ALIASES)
    max_idx = _find_idx(header_lower, MAX_ALIASES)
    warn_min_idx = _find_idx(header_lower, WARN_MIN_ALIASES)
    warn_max_idx = _find_idx(header_lower, WARN_MAX_ALIASES)
    allowed_idx = _find_idx(header_lower, ALLOWED_ALIASES)
    group_idx = _find_idx(header_lower, GROUP_ALIASES)
    alias_idx = _find_idx(header_lower, ALIAS_ALIASES)
    session_idx = _find_idx(header_lower, SESSION_ALIASES)
    run_idx = _find_idx(header_lower, RUN_ALIASES)
    scaling_idx = _find_idx(header_lower, SCALING_ALIASES)

    test_name_idx = _find_idx(header_lower, TEST_NAME_ALIASES)
    study_desc_idx = _find_idx(header_lower, STUDY_DESC_ALIASES)
    protocol_idx = _find_idx(header_lower, PROTOCOL_ALIASES)
    instructions_idx = _find_idx(header_lower, INSTRUCTIONS_ALIASES)
    reference_idx = _find_idx(header_lower, REFERENCE_ALIASES)
    duration_idx = _find_idx(header_lower, ESTIMATED_DURATION_ALIASES)
    equipment_idx = _find_idx(header_lower, EQUIPMENT_ALIASES)
    supervisor_idx = _find_idx(header_lower, SUPERVISOR_ALIASES)

    header_detected = any(
        idx is not None
        for idx in [
            id_idx,
            desc_idx,
            units_idx,
            dtype_idx,
            min_idx,
            max_idx,
            allowed_idx,
            group_idx,
            alias_idx,
            session_idx,
            run_idx,
            scaling_idx,
            test_name_idx,
            study_desc_idx,
            protocol_idx,
            instructions_idx,
            reference_idx,
            duration_idx,
            equipment_idx,
            supervisor_idx,
        ]
    )

    if header_detected:
        print("Detected header row (named columns). Using column names.")
        data_rows = df_meta.iloc[1:]
    else:
        data_rows = df_meta
        id_idx = 0
        desc_idx = 1
        units_idx = 2
        dtype_idx = 3
        min_idx = 4
        max_idx = 5
        allowed_idx = 6
        group_idx = 7
        alias_idx = 8
        session_idx = 9
        run_idx = 10
        scaling_idx = None
        warn_min_idx = None
        warn_max_idx = None

    def get_val(row, idx):
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    biometrics = {}
    group_meta = {}

    for _, row in data_rows.iterrows():
        var_name = _clean_key(get_val(row, id_idx))
        if not var_name or var_name.lower() == "nan":
            continue

        manual_group = get_val(row, group_idx)
        if manual_group is not None and not (isinstance(manual_group, float) and pd.isna(manual_group)):
            grp = str(manual_group).strip().lower()
            if grp in {"disable", "skip", "omit", "ignore"}:
                continue
            group = grp if grp else "biometrics"
        else:
            group = "biometrics"

        if group not in biometrics:
            biometrics[group] = {}

        if group not in group_meta:
            group_meta[group] = {
                "OriginalName": None,
                "StudyDescription": None,
                "Protocol": None,
                "Instructions": None,
                "Reference": None,
                "EstimatedDuration": None,
                "Equipment": None,
                "Supervisor": None,
            }

        # Capture group-level metadata (first non-empty per group wins)
        def _set_once(key, idx):
            if idx is None:
                return
            if group_meta[group].get(key) is not None:
                return
            v = get_val(row, idx)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return
            s = str(v).strip()
            if not s or s.lower() == "none":
                return
            group_meta[group][key] = s

        _set_once("OriginalName", test_name_idx)
        _set_once("StudyDescription", study_desc_idx)
        _set_once("Protocol", protocol_idx)
        _set_once("Instructions", instructions_idx)
        _set_once("Reference", reference_idx)
        _set_once("EstimatedDuration", duration_idx)
        _set_once("Equipment", equipment_idx)

        # Supervisor is constrained by schema enum
        if supervisor_idx is not None and group_meta[group].get("Supervisor") is None:
            v = get_val(row, supervisor_idx)
            if v is not None and not (isinstance(v, float) and pd.isna(v)):
                s = str(v).strip().lower()
                if s in {"investigator", "physician", "trainer", "self"}:
                    group_meta[group]["Supervisor"] = s

        description = get_val(row, desc_idx)
        scaling = get_val(row, scaling_idx)
        units = _infer_units(get_val(row, units_idx), scaling, description)

        min_v, max_v = _parse_minmax(get_val(row, min_idx), get_val(row, max_idx), scaling)
        warn_min_v = _parse_float(get_val(row, warn_min_idx))
        warn_max_v = _parse_float(get_val(row, warn_max_idx))

        allowed_cell = get_val(row, allowed_idx)
        allowed = _parse_allowed_values(allowed_cell)
        # Preserve labels when provided (prefer AllowedValues column; fall back to Scaling)
        levels = _parse_levels(allowed_cell) or _parse_levels(scaling)
        if levels and not allowed:
            # Derive AllowedValues from Levels keys
            allowed = _parse_allowed_values(";".join(levels.keys()))
        dtype = _infer_datatype(get_val(row, dtype_idx), units, allowed, min_v, max_v)

        entry = {
            "Description": str(description).strip() if description is not None and not (isinstance(description, float) and pd.isna(description)) else var_name,
            "Units": units,
            "DataType": dtype,
        }

        if allowed:
            entry["AllowedValues"] = allowed

        if levels:
            entry["Levels"] = levels

        if min_v is not None:
            entry["MinValue"] = min_v
        if max_v is not None:
            entry["MaxValue"] = max_v
        if warn_min_v is not None:
            entry["WarnMinValue"] = warn_min_v
        if warn_max_v is not None:
            entry["WarnMaxValue"] = warn_max_v

        alias_of = get_val(row, alias_idx)
        if alias_of is not None and not (isinstance(alias_of, float) and pd.isna(alias_of)):
            alias_clean = str(alias_of).strip()
            if alias_clean:
                entry["AliasOf"] = alias_clean

        session_hint = get_val(row, session_idx)
        if session_hint is not None and not (isinstance(session_hint, float) and pd.isna(session_hint)):
            session_clean = str(session_hint).strip().lower().replace(" ", "")
            session_clean = session_clean.replace("session", "ses-")
            session_clean = session_clean.replace("visit", "ses-")
            if session_clean in {"t1", "wave1", "visit1"}:
                session_clean = "ses-1"
            elif session_clean in {"t2", "wave2", "visit2"}:
                session_clean = "ses-2"
            elif session_clean in {"t3", "wave3", "visit3"}:
                session_clean = "ses-3"
            if not session_clean.startswith("ses-"):
                session_clean = f"ses-{session_clean}"
            entry["SessionHint"] = session_clean

        run_hint = get_val(row, run_idx)
        if run_hint is not None and not (isinstance(run_hint, float) and pd.isna(run_hint)):
            run_clean = str(run_hint).strip().lower().replace(" ", "")
            if run_clean and not run_clean.startswith("run-"):
                run_clean = f"run-{run_clean}"
            if run_clean:
                entry["RunHint"] = run_clean

        biometrics[group][var_name] = entry

    print(f"Generating biometrics JSON sidecars in {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)

    participant_groups = {"participant", "participants"}

    for group, variables in biometrics.items():
        if group in participant_groups:
            sidecar = {}
            sidecar.update(variables)
            json_filename = "participants.json"
            json_path = os.path.join(output_dir, json_filename)
        else:
            meta = group_meta.get(group, {})
            equipment_value = meta.get("Equipment") or equipment
            supervisor_value = meta.get("Supervisor") or supervisor

            original_name = meta.get("OriginalName") or f"{group} assessment"
            study_description = meta.get("StudyDescription") or f"Imported {group} biometrics data"
            sidecar = {
                "Technical": {
                    "StimulusType": "Biometrics",
                    "FileFormat": "tsv",
                    "Equipment": equipment_value,
                    "Supervisor": supervisor_value,
                },
                "Study": {
                    "BiometricName": group,
                    "OriginalName": original_name,
                    "Protocol": meta.get("Protocol") or "",
                    "Description": study_description,
                },
                "Metadata": {
                    "SchemaVersion": "1.0.0",
                    "CreationDate": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "Creator": "excel_to_biometrics_library.py",
                },
            }

            if meta.get("Instructions"):
                sidecar["Study"]["Instructions"] = meta["Instructions"]
            if meta.get("Reference"):
                sidecar["Study"]["Reference"] = meta["Reference"]
            if meta.get("EstimatedDuration"):
                sidecar["Study"]["EstimatedDuration"] = meta["EstimatedDuration"]
            sidecar.update(variables)

            json_filename = f"biometrics-{group}.json"
            json_path = os.path.join(output_dir, json_filename)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(sidecar, f, indent=2, ensure_ascii=False)
        print(f"  - Created {json_path}")

    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Excel data dictionary to PRISM biometrics JSON library.")
    parser.add_argument("--excel", required=True, help="Path to the Excel metadata file.")
    parser.add_argument("--output", default="biometrics_library", help="Output directory for JSON files.")
    parser.add_argument(
        "--sheet",
        default=0,
        help="Sheet name or index containing the data dictionary (default: 0). For sport.xlsx use: --sheet Description",
    )
    parser.add_argument(
        "--equipment",
        default="Legacy/Imported",
        help="Default Equipment value written to Technical.Equipment (required by schema).",
    )
    parser.add_argument(
        "--supervisor",
        default="investigator",
        choices=["investigator", "physician", "trainer", "self"],
        help="Default Supervisor value written to Technical.Supervisor.",
    )

    args = parser.parse_args()
    sheet = int(args.sheet) if isinstance(args.sheet, str) and args.sheet.isdigit() else args.sheet
    process_excel_biometrics(args.excel, args.output, sheet_name=sheet, equipment=args.equipment, supervisor=args.supervisor)
