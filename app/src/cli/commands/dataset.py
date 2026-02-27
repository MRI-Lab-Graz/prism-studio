"""Dataset-related prism_tools command handlers."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from src.converters.excel_to_biometrics import process_excel_biometrics
from src.utils.io import ensure_dir as _ensure_dir
from src.utils.io import read_json as _read_json
from src.utils.io import write_json as _write_json


def cmd_dataset_build_biometrics_smoketest(args) -> None:
    """Generate a small PRISM-valid dataset from a biometrics codebook and dummy CSV."""
    import numpy as np
    import pandas as pd

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
        m = __import__("re").match(
            r"^(?:t|visit)?\s*(\d+)\s*$", ses, flags=__import__("re").IGNORECASE
        )
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
    sheet = (
        int(args.sheet)
        if isinstance(args.sheet, str) and args.sheet.isdigit()
        else args.sheet
    )
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
        print(
            "Error: dummy data must include a participant id column (e.g., 'participant_id')"
        )
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
        "Authors": args.authors or [],
    }
    _write_json(output_root / "dataset_description.json", dataset_description)

    # participants.tsv (+ optional participants.json from library if present)
    df_part = pd.DataFrame(
        {"participant_id": df_data[col_pid].astype(str).map(_normalize_sub_id)}
    )
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
            print(
                f"Warning: Missing biometrics template for group '{grp}': {template_path}"
            )
            return
        sidecar = _read_json(template_path)
        if add_instance_meta and "instance" not in sidecar:
            sidecar["instance"] = {
                "Description": "Instance index (e.g., trial/repetition)",
                "Units": "n/a",
                "DataType": "integer",
            }
        _write_json(sidecar_path, sidecar)

    def _write_task_files(
        sub_id: str, ses_id: str, grp: str, df_out: "pd.DataFrame"
    ) -> None:
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

        df_long["participant_id"] = (
            df_long["participant_id"].astype(str).map(_normalize_sub_id)
        )
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

        for (sub_id, ses_id), df_ps in df_long.groupby(
            ["participant_id", "session"], dropna=True
        ):
            for grp, items in group_to_items.items():
                df_grp = df_ps[df_ps["group"] == grp]
                if df_grp.empty:
                    continue

                if has_instance:
                    wide = df_grp.pivot_table(
                        index="instance",
                        columns="item_id",
                        values="value",
                        aggfunc="first",
                    ).reset_index()
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
