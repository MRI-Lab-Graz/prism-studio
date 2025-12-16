#!/usr/bin/env python3
import argparse
import sys
import os
import shutil
import json
from pathlib import Path
import glob

# Enforce running from the repo-local virtual environment (skip for frozen/packaged apps)
venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
if not getattr(sys, "frozen", False) and not sys.prefix.startswith(venv_path):
    print("❌ Error: You are not running inside the prism-validator virtual environment!")
    print("   Please activate the venv first:")
    if os.name == "nt":
        print(f"     {venv_path}\\Scripts\\activate")
    else:
        print(f"     source {venv_path}/bin/activate")
    print("   Then run this script again.")
    sys.exit(1)

# Add project root to path to import helpers
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from helpers.physio.convert_varioport import convert_varioport
from scripts.check_survey_library import check_uniqueness
from scripts.limesurvey_to_prism import convert_lsa_to_prism, batch_convert_lsa
# excel_to_library might not be in python path if it's in scripts/ and we are in root.
# sys.path.append(str(project_root / "scripts")) # Already added project_root, but scripts is a subdir.
# We need to import from scripts.excel_to_library
from scripts.excel_to_library import process_excel
from scripts.excel_to_biometrics_library import process_excel_biometrics


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, obj: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def sanitize_id(id_str):
    """
    Sanitizes subject/session IDs by replacing German umlauts and special characters.
    """
    if not id_str:
        return id_str
    replacements = {
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'Ä': 'Ae', 'Ö': 'Oe', 'Ü': 'Ue',
        'ß': 'ss'
    }
    for char, repl in replacements.items():
        id_str = id_str.replace(char, repl)
    return id_str

import hashlib

def get_json_hash(json_path):
    """Calculates hash of a JSON file's semantic content."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.md5(canonical.encode("utf-8")).hexdigest()
    except Exception:
        # Fallback: raw bytes hash
        with open(json_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

def consolidate_sidecars(output_dir, task, suffix):
    """
    Consolidates identical JSON sidecars into a single file in the root directory.
    """
    print("\nConsolidating JSON sidecars...")
    # Find all generated JSONs for this task/suffix
    # Pattern: sub-*/ses-*/physio/*_task-<task>_<suffix>.json
    pattern = f"sub-*/ses-*/physio/*_task-{task}_{suffix}.json"
    json_files = list(output_dir.glob(pattern))
    
    if not json_files:
        print("No sidecars found to consolidate.")
        return

    first_json = json_files[0]
    first_hash = get_json_hash(first_json)
    
    all_identical = True
    for jf in json_files[1:]:
        if get_json_hash(jf) != first_hash:
            all_identical = False
            break
    
    if all_identical:
        print(f"All {len(json_files)} sidecars are identical. Consolidating to root.")
        # Create root sidecar name: task-<task>_<suffix>.json
        root_json_name = f"task-{task}_{suffix}.json"
        root_json_path = output_dir / root_json_name
        
        # Copy first json to root
        shutil.copy(first_json, root_json_path)
        print(f"Created root sidecar: {root_json_path}")
        
        # Delete individual sidecars
        for jf in json_files:
            jf.unlink()
        print("Deleted individual sidecars.")
    else:
        print("Sidecars differ. Keeping individual files.")

def cmd_convert_physio(args):
    """
    Handles the 'convert physio' command.
    """
    input_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    print(f"Scanning {input_dir} for raw physio files...")
    
    # Expected structure: sourcedata/sub-XXX/ses-YYY/physio/filename.raw
    # We search recursively for the raw files
    # The pattern should be flexible but ideally match the BIDS-like structure
    
    # Find all files matching the pattern
    # We assume files end with .raw or .RAW (case insensitive check later if needed)
    # But glob is case sensitive on Linux.
    files = list(input_dir.rglob("*.[rR][aA][wW]"))
    
    if not files:
        print("No .raw files found in input directory.")
        return

    print(f"Found {len(files)} files to process.")
    
    success_count = 0
    error_count = 0
    
    for raw_file in files:
        # Infer subject and session from path or filename
        # Expected filename: sub-<id>_ses-<id>_physio.raw
        filename = raw_file.name
        
        # Simple parsing logic
        parts = raw_file.stem.split('_')
        sub_id = None
        ses_id = None
        
        for part in parts:
            if part.startswith('sub-'):
                sub_id = part
            elif part.startswith('ses-'):
                ses_id = part
        
        # Fallback: try to get from parent folders if not in filename
        if not sub_id:
            for parent in raw_file.parents:
                if parent.name.startswith('sub-'):
                    sub_id = parent.name
                    break
        
        if not ses_id:
            for parent in raw_file.parents:
                if parent.name.startswith('ses-'):
                    ses_id = parent.name
                    break
        
        if not sub_id or not ses_id:
            print(f"Skipping {filename}: Could not determine subject or session ID.")
            continue
        
        # Sanitize IDs
        sub_id = sanitize_id(sub_id)
        ses_id = sanitize_id(ses_id)
            
        # Construct output path
        # rawdata/sub-XXX/ses-YYY/physio/
        target_dir = output_dir / sub_id / ses_id / "physio"
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Construct output filename
        # sub-XXX_ses-YYY_task-<task>_<suffix>.edf
        out_base = f"{sub_id}_{ses_id}_task-{args.task}_{args.suffix}"
        out_edf = target_dir / f"{out_base}.edf"
        out_json = target_dir / f"{out_base}.json"
        
        print(f"Converting {filename} -> {out_base}.edf")
        
        try:
            convert_varioport(
                str(raw_file),
                str(out_edf),
                str(out_json),
                task_name=args.task,
                base_freq=args.sampling_rate
            )
            
            # Check file size
            if out_edf.exists():
                size_kb = out_edf.stat().st_size / 1024
                if size_kb < 10: # Warn if smaller than 10KB
                    print(f"⚠️  WARNING: Output file is suspiciously small ({size_kb:.2f} KB): {out_edf}")
                else:
                    print(f"✅ Created {out_edf.name} ({size_kb:.2f} KB)")
            else:
                 print(f"❌ Error: Output file was not created: {out_edf}")
                 error_count += 1
                 continue

            success_count += 1
        except Exception as e:
            print(f"Error converting {filename}: {e}")
            error_count += 1
            
    # Consolidate sidecars if requested (or always?)
    # BIDS inheritance principle
    consolidate_sidecars(output_dir, args.task, args.suffix)

    print(f"\nConversion finished. Success: {success_count}, Errors: {error_count}")

def cmd_demo_create(args):
    """
    Creates a demo dataset.
    """
    output_path = Path(args.output)
    demo_source = project_root / "prism_demo"
    
    if output_path.exists():
        print(f"Error: Output path '{output_path}' already exists.")
        sys.exit(1)
        
    print(f"Creating demo dataset at {output_path}...")
    try:
        shutil.copytree(demo_source, output_path)
        print("✅ Demo dataset created successfully.")
    except Exception as e:
        print(f"Error creating demo dataset: {e}")
        sys.exit(1)

def cmd_survey_import_excel(args):
    """
    Imports survey library from Excel.
    """
    print(f"Importing survey library from {args.excel}...")
    try:
        output_dir = args.output
        if getattr(args, "library_root", None):
            output_dir = str(_ensure_dir(Path(args.library_root) / "survey"))
        process_excel(args.excel, output_dir)
    except Exception as e:
        print(f"Error importing Excel: {e}")
        sys.exit(1)


def cmd_biometrics_import_excel(args):
    """Imports biometrics templates/library from Excel."""
    print(f"Importing biometrics library from {args.excel} (sheet={args.sheet})...")
    try:
        sheet = int(args.sheet) if isinstance(args.sheet, str) and args.sheet.isdigit() else args.sheet
        output_dir = args.output
        if getattr(args, "library_root", None):
            output_dir = str(_ensure_dir(Path(args.library_root) / "biometrics"))
        process_excel_biometrics(
            args.excel,
            output_dir,
            sheet_name=sheet,
            equipment=args.equipment,
            supervisor=args.supervisor,
        )
    except Exception as e:
        print(f"Error importing Excel: {e}")
        sys.exit(1)


def cmd_dataset_build_biometrics_smoketest(args):
    """Generate a small PRISM-valid dataset from a biometrics codebook and dummy CSV."""
    import pandas as pd
    import numpy as np

    def _norm_col(s: str) -> str:
        return str(s).strip().lower().replace(" ", "").replace("_", "")

    def _find_col(df: "pd.DataFrame", candidates: set[str]) -> str | None:
        wanted = {_norm_col(c) for c in candidates}
        for c in df.columns:
            if _norm_col(c) in wanted:
                return c
        return None

    def _normalize_sub_id(pid: str) -> str:
        pid = str(pid).strip()
        if not pid:
            return ""
        return pid if pid.startswith("sub-") else f"sub-{pid}"

    def _normalize_ses_id(ses: str) -> str:
        ses = str(ses).strip()
        if not ses or ses.lower() == "nan":
            return args.session
        if ses.startswith("ses-"):
            return ses
        m = __import__("re").match(r"^(?:t|visit)?\s*(\d+)\s*$", ses, flags=__import__("re").IGNORECASE)
        if m:
            return f"ses-{int(m.group(1)):02d}"
        # fallback: make it a ses-* label
        return f"ses-{ses}"

    output_root = Path(args.output).resolve()
    if output_root.exists() and any(output_root.iterdir()):
        print(f"Error: Output directory is not empty: {output_root}")
        sys.exit(1)

    library_root = Path(args.library_root).resolve()
    biometrics_library = _ensure_dir(library_root / "biometrics")

    # 1) Generate biometrics templates into the library
    sheet = int(args.sheet) if isinstance(args.sheet, str) and args.sheet.isdigit() else args.sheet
    process_excel_biometrics(
        args.codebook,
        str(biometrics_library),
        sheet_name=sheet,
        equipment=args.equipment,
        supervisor=args.supervisor,
    )

    # 2) Load codebook to map item_id -> group
    df_codebook = pd.read_excel(args.codebook, sheet_name=sheet)
    if "item_id" not in df_codebook.columns:
        print("Error: codebook must contain an 'item_id' column")
        sys.exit(1)
    if "group" not in df_codebook.columns:
        print("Error: codebook must contain a 'group' column")
        sys.exit(1)

    item_to_group: dict[str, str] = {}
    for _, row in df_codebook.iterrows():
        item_id = str(row.get("item_id", "")).strip()
        if not item_id or item_id.lower() == "nan":
            continue
        grp = row.get("group", "biometrics")
        if grp is None or (isinstance(grp, float) and np.isnan(grp)):
            grp = "biometrics"
        grp_s = str(grp).strip().lower() or "biometrics"
        if grp_s in {"disable", "skip", "omit", "ignore"}:
            continue
        item_to_group[item_id] = grp_s

    # Ignore participant-only variables for biometrics TSV creation
    participant_groups = {"participant", "participants"}

    group_to_items: dict[str, list[str]] = {}
    for item_id, grp in item_to_group.items():
        if grp in participant_groups:
            continue
        group_to_items.setdefault(grp, []).append(item_id)

    # 3) Load dummy data (wide or long)
    df_data = pd.read_csv(args.data)

    col_pid = _find_col(df_data, {"participant_id", "participant", "subject", "sub"})
    if not col_pid:
        print("Error: dummy data must include a participant id column (e.g., 'participant_id')")
        sys.exit(1)

    col_ses = _find_col(df_data, {"session", "ses", "visit", "timepoint"})
    col_item = _find_col(df_data, {"item_id", "item", "variable", "id", "code"})
    col_val = _find_col(df_data, {"value", "val", "measurement", "data"})
    col_group = _find_col(df_data, {"group", "task", "test", "instrument"})
    col_instance = _find_col(df_data, {"instance", "trial", "repeat", "rep", "run"})

    is_long = bool(col_item and col_val)

    # 4) Create dataset root files
    _ensure_dir(output_root)
    dataset_description = {
        "Name": args.name,
        "BIDSVersion": "1.8.0",
        "DatasetType": "raw",
        "Authors": args.authors or ["PRISM smoketest"],
    }
    _write_json(output_root / "dataset_description.json", dataset_description)

    # participants.tsv (+ optional participants.json from library if present)
    df_part = pd.DataFrame({"participant_id": df_data[col_pid].astype(str).map(_normalize_sub_id)})
    df_part.to_csv(output_root / "participants.tsv", sep="\t", index=False)
    participants_json = biometrics_library / "participants.json"
    if participants_json.exists():
        shutil.copy(participants_json, output_root / "participants.json")

    def _ensure_inherited_sidecar(grp: str, add_instance_meta: bool) -> None:
        """Write an inherited (dataset-level) sidecar for this biometrics task.

        Uses BIDS inheritance: `task-<grp>_biometrics.json` in the dataset root.
        """
        sidecar_path = output_root / f"task-{grp}_biometrics.json"
        if sidecar_path.exists():
            # If we later discover that we need instance metadata, patch it in.
            if add_instance_meta:
                try:
                    sidecar = _read_json(sidecar_path)
                    if "instance" not in sidecar:
                        sidecar["instance"] = {
                            "Description": "Instance index (e.g., trial/repetition)",
                            "Units": "n/a",
                            "DataType": "integer",
                        }
                        _write_json(sidecar_path, sidecar)
                except Exception:
                    pass
            return

        template_path = biometrics_library / f"biometrics-{grp}.json"
        if not template_path.exists():
            print(f"Warning: Missing biometrics template for group '{grp}': {template_path}")
            return
        sidecar = _read_json(template_path)
        if add_instance_meta and "instance" not in sidecar:
            sidecar["instance"] = {
                "Description": "Instance index (e.g., trial/repetition)",
                "Units": "n/a",
                "DataType": "integer",
            }
        _write_json(sidecar_path, sidecar)

    def _write_task_files(sub_id: str, ses_id: str, grp: str, df_out: "pd.DataFrame") -> None:
        if df_out is None or df_out.empty:
            return

        modality_dir = _ensure_dir(output_root / sub_id / ses_id / "biometrics")
        stem = f"{sub_id}_{ses_id}_task-{grp}_biometrics"
        tsv_path = modality_dir / f"{stem}.tsv"
        df_out.to_csv(tsv_path, sep="\t", index=False)

    # 5) Generate per-subject biometrics TSVs + matching sidecars
    if is_long:
        # Expected columns: participant_id, session, item_id, value (+ optional group/instance)
        df_long = df_data.copy()
        df_long = df_long.rename(
            columns={
                col_pid: "participant_id",
                (col_ses or ""): "session",
                col_item: "item_id",
                col_val: "value",
                (col_group or ""): "group",
                (col_instance or ""): "instance",
            }
        )

        df_long["participant_id"] = df_long["participant_id"].astype(str).map(_normalize_sub_id)
        if "session" not in df_long.columns or not col_ses:
            df_long["session"] = args.session
        df_long["session"] = df_long["session"].astype(str).map(_normalize_ses_id)

        df_long["item_id"] = df_long["item_id"].astype(str).str.strip()
        df_long = df_long[df_long["item_id"].astype(str).str.len() > 0]

        # Determine group per row
        if "group" in df_long.columns and col_group:
            df_long["group"] = df_long["group"].astype(str).str.strip().str.lower()
        else:
            df_long["group"] = df_long["item_id"].map(item_to_group)

        df_long = df_long[df_long["group"].notna()]
        df_long = df_long[~df_long["group"].isin(participant_groups)]

        # Optional instance -> multi-row TSV
        has_instance = "instance" in df_long.columns and col_instance is not None
        if has_instance:
            df_long["instance"] = pd.to_numeric(df_long["instance"], errors="coerce")
            df_long = df_long[df_long["instance"].notna()]
            df_long["instance"] = df_long["instance"].astype(int)

        # Ensure dataset-level inherited sidecars (one per biometrics task)
        for grp in group_to_items.keys():
            _ensure_inherited_sidecar(grp, add_instance_meta=has_instance)

        for (sub_id, ses_id), df_ps in df_long.groupby(["participant_id", "session"], dropna=True):
            for grp, items in group_to_items.items():
                df_grp = df_ps[df_ps["group"] == grp]
                if df_grp.empty:
                    continue

                if has_instance:
                    wide = (
                        df_grp.pivot_table(
                            index="instance",
                            columns="item_id",
                            values="value",
                            aggfunc="first",
                        )
                        .reset_index()
                    )
                    # Ensure full column set and stable order
                    for col in items:
                        if col not in wide.columns:
                            wide[col] = "n/a"
                    wide = wide[["instance"] + items]
                    _write_task_files(sub_id, ses_id, grp, wide)
                else:
                    values = {col: "n/a" for col in items}
                    for col in items:
                        s = df_grp.loc[df_grp["item_id"] == col, "value"]
                        if len(s) > 0:
                            values[col] = s.iloc[0]
                    df_out = pd.DataFrame([values], columns=items)
                    _write_task_files(sub_id, ses_id, grp, df_out)

    else:
        # Wide: one row per subject (optionally with session column)

        # Ensure dataset-level inherited sidecars (one per biometrics task)
        for grp in group_to_items.keys():
            _ensure_inherited_sidecar(grp, add_instance_meta=False)

        for _, row in df_data.iterrows():
            pid = str(row[col_pid]).strip()
            if not pid:
                continue
            sub_id = _normalize_sub_id(pid)
            ses_id = _normalize_ses_id(row[col_ses]) if col_ses else args.session

            for grp, items in group_to_items.items():
                # Write single-row TSV
                values = {}
                for col in items:
                    if col in df_data.columns:
                        v = row[col]
                        if v is None or (isinstance(v, float) and np.isnan(v)):
                            values[col] = "n/a"
                        else:
                            values[col] = v
                    else:
                        values[col] = "n/a"
                df_out = pd.DataFrame([values], columns=items)
                _write_task_files(sub_id, ses_id, grp, df_out)

    print(f"✅ Created dataset: {output_root}")
    print(f"✅ Biometrics library: {biometrics_library}")

def cmd_survey_validate(args):
    """
    Validates the survey library.
    """
    print(f"Validating survey library at {args.library}...")
    if check_uniqueness(args.library):
        sys.exit(0)
    else:
        sys.exit(1)

def cmd_survey_import_limesurvey(args):
    """
    Imports LimeSurvey structure.
    """
    print(f"Importing LimeSurvey structure from {args.input}...")
    try:
        convert_lsa_to_prism(args.input, args.output, task_name=args.task)
    except Exception as e:
        print(f"Error importing LimeSurvey: {e}")
        sys.exit(1)


def parse_session_map(map_str):
    mapping = {}
    for item in map_str.split(','):
        token = item.strip()
        if not token:
            continue
        sep = ':' if ':' in token else ('=' if '=' in token else None)
        if not sep:
            # allow shorthand like t1_ses-1
            if '_' in token:
                raw, mapped = token.split('_', 1)
            else:
                continue
        else:
            raw, mapped = token.split(sep, 1)
        mapping[raw.strip().lower()] = mapped.strip()
    return mapping


def cmd_survey_import_limesurvey_batch(args):
    """Batch convert LimeSurvey archives with session mapping (t1/t2/t3 -> ses-1/2/3)."""
    session_map = parse_session_map(args.session_map)
    if not session_map:
        print("No valid session mapping provided. Example: t1:ses-1,t2:ses-2,t3:ses-3")
        sys.exit(1)
    try:
        batch_convert_lsa(
            args.input_dir,
            args.output_dir,
            session_map,
            library_path=args.library,
            task_fallback=args.task,
            id_column=args.subject_id_col,
            id_map_file=args.id_map,
        )
    except Exception as e:
        print(f"Error importing LimeSurvey: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Prism Tools: Utilities for PRISM/BIDS datasets")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Command: convert
    parser_convert = subparsers.add_parser("convert", help="Convert raw data to BIDS format")
    convert_subparsers = parser_convert.add_subparsers(dest="modality", help="Modality to convert")
    
    # Subcommand: convert physio
    parser_physio = convert_subparsers.add_parser("physio", help="Convert physiological data (Varioport)")
    parser_physio.add_argument("--input", required=True, help="Path to sourcedata directory")
    parser_physio.add_argument("--output", required=True, help="Path to output rawdata directory")
    parser_physio.add_argument("--task", default="rest", help="Task name (default: rest)")
    parser_physio.add_argument("--suffix", default="physio", help="Output suffix (default: physio)")
    parser_physio.add_argument("--sampling-rate", type=float, help="Override sampling rate (e.g. 256)")
    
    # Command: demo
    parser_demo = subparsers.add_parser("demo", help="Demo dataset operations")
    demo_subparsers = parser_demo.add_subparsers(dest="action", help="Action")
    
    # Subcommand: demo create
    parser_demo_create = demo_subparsers.add_parser("create", help="Create a demo dataset")
    parser_demo_create.add_argument("--output", default="prism_demo_copy", help="Output path for the demo dataset")

    # Command: survey
    parser_survey = subparsers.add_parser("survey", help="Survey library operations")
    survey_subparsers = parser_survey.add_subparsers(dest="action", help="Action")
    
    # Subcommand: survey import-excel
    parser_survey_excel = survey_subparsers.add_parser("import-excel", help="Import survey library from Excel")
    parser_survey_excel.add_argument("--excel", required=True, help="Path to Excel file")
    parser_survey_excel.add_argument("--output", default="survey_library", help="Output directory")
    parser_survey_excel.add_argument(
        "--library-root",
        dest="library_root",
        help="If set, writes to <library-root>/survey instead of --output.",
    )

    # Command: biometrics
    parser_biometrics = subparsers.add_parser("biometrics", help="Biometrics library operations")
    biometrics_subparsers = parser_biometrics.add_subparsers(dest="action", help="Action")

    # Subcommand: biometrics import-excel
    parser_biometrics_excel = biometrics_subparsers.add_parser(
        "import-excel", help="Import biometrics templates/library from Excel"
    )
    parser_biometrics_excel.add_argument("--excel", required=True, help="Path to Excel file")
    parser_biometrics_excel.add_argument("--output", default="biometrics_library", help="Output directory")
    parser_biometrics_excel.add_argument(
        "--library-root",
        dest="library_root",
        help="If set, writes to <library-root>/biometrics instead of --output.",
    )
    parser_biometrics_excel.add_argument(
        "--sheet",
        default=0,
        help="Sheet name or index containing the data dictionary (e.g., 'Description').",
    )
    parser_biometrics_excel.add_argument(
        "--equipment",
        default="Legacy/Imported",
        help="Default Technical.Equipment value written to biometrics JSON (required by schema).",
    )
    parser_biometrics_excel.add_argument(
        "--supervisor",
        default="investigator",
        choices=["investigator", "physician", "trainer", "self"],
        help="Default Technical.Supervisor value written to biometrics JSON.",
    )

    # Command: dataset
    parser_dataset = subparsers.add_parser("dataset", help="Dataset helper commands")
    dataset_subparsers = parser_dataset.add_subparsers(dest="action", help="Action")

    parser_ds_bio = dataset_subparsers.add_parser(
        "build-biometrics-smoketest",
        help="Build a small PRISM-valid biometrics dataset from a codebook and dummy CSV",
    )
    parser_ds_bio.add_argument(
        "--codebook",
        default="test_dataset/Biometrics_variables.xlsx",
        help="Path to Biometrics codebook Excel (default: test_dataset/Biometrics_variables.xlsx)",
    )
    parser_ds_bio.add_argument(
        "--sheet",
        default="biometrics_codebook",
        help="Sheet name or index for the codebook (default: biometrics_codebook)",
    )
    parser_ds_bio.add_argument(
        "--data",
        default="test_dataset/Biometrics_dummy_data.csv",
        help="Path to dummy biometrics data CSV with participant_id column",
    )
    parser_ds_bio.add_argument(
        "--output",
        default="test_dataset/_tmp_prism_biometrics_dataset",
        help="Output dataset directory (must be empty or non-existent)",
    )
    parser_ds_bio.add_argument(
        "--library-root",
        default="library",
        help="Library root directory to write templates into (creates <library-root>/biometrics)",
    )
    parser_ds_bio.add_argument(
        "--name",
        default="PRISM Biometrics Smoketest",
        help="Dataset name for dataset_description.json",
    )
    parser_ds_bio.add_argument(
        "--authors",
        nargs="+",
        default=None,
        help="Authors for dataset_description.json (default: 'PRISM smoketest')",
    )
    parser_ds_bio.add_argument(
        "--session",
        default="ses-01",
        help="Session folder label to use (default: ses-01)",
    )
    parser_ds_bio.add_argument(
        "--equipment",
        default="Legacy/Imported",
        help="Default Technical.Equipment value for generated biometrics templates",
    )
    parser_ds_bio.add_argument(
        "--supervisor",
        default="investigator",
        choices=["investigator", "physician", "trainer", "self"],
        help="Default Technical.Supervisor value for generated biometrics templates",
    )
    
    # Subcommand: survey validate
    parser_survey_validate = survey_subparsers.add_parser("validate", help="Validate survey library")
    parser_survey_validate.add_argument("--library", default="survey_library", help="Path to survey library")
    
    # Subcommand: survey import-limesurvey
    parser_survey_limesurvey = survey_subparsers.add_parser("import-limesurvey", help="Import LimeSurvey structure")
    parser_survey_limesurvey.add_argument("--input", required=True, help="Path to .lsa/.lss file")
    parser_survey_limesurvey.add_argument("--output", help="Path to output .json file")
    parser_survey_limesurvey.add_argument("--task", help="Optional task name override (defaults from file name)")

    parser_survey_limesurvey_batch = survey_subparsers.add_parser(
        "import-limesurvey-batch", help="Batch import LimeSurvey files with session mapping"
    )
    parser_survey_limesurvey_batch.add_argument("--input-dir", required=True, help="Root directory containing .lsa/.lss files")
    parser_survey_limesurvey_batch.add_argument("--output-dir", required=True, help="Output root for generated PRISM dataset")
    parser_survey_limesurvey_batch.add_argument(
        "--session-map",
        default="t1:ses-1,t2:ses-2,t3:ses-3",
        help="Comma-separated mapping, e.g. t1:ses-1,t2:ses-2,t3:ses-3",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--task",
        help="Optional task name fallback (otherwise derived from file name)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--library",
        default="survey_library",
        help="Path to survey library (survey-*.json and optional participants.json)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--subject-id-col",
        dest="subject_id_col",
        help="Preferred column name to use for participant ID (e.g., ID, code, token)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--id-map",
        dest="id_map",
        help="Path to TSV/CSV file mapping LimeSurvey IDs to BIDS participant IDs (cols: limesurvey_id, participant_id)",
    )

    args = parser.parse_args()
    
    if args.command == "convert" and args.modality == "physio":
        cmd_convert_physio(args)
    elif args.command == "demo" and args.action == "create":
        cmd_demo_create(args)
    elif args.command == "survey":
        if args.action == "import-excel":
            cmd_survey_import_excel(args)
        elif args.action == "validate":
            cmd_survey_validate(args)
        elif args.action == "import-limesurvey":
            cmd_survey_import_limesurvey(args)
        elif args.action == "import-limesurvey-batch":
            cmd_survey_import_limesurvey_batch(args)
        else:
            parser_survey.print_help()
    elif args.command == "biometrics":
        if args.action == "import-excel":
            cmd_biometrics_import_excel(args)
        else:
            parser_biometrics.print_help()
    elif args.command == "dataset":
        if args.action == "build-biometrics-smoketest":
            cmd_dataset_build_biometrics_smoketest(args)
        else:
            parser_dataset.print_help()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
