import os
import inspect
from pathlib import Path

from flask import current_app, jsonify

from .tools_helpers import _global_recipes_root


def handle_api_recipes_surveys(data: dict):
    """Run survey-recipes generation inside an existing PRISM dataset."""
    try:
        from src.recipes_surveys import compute_survey_recipes
    except ImportError:
        compute_survey_recipes = None

    if not compute_survey_recipes:
        return jsonify({"error": "Data processing module not available"}), 500

    dataset_path = (data.get("dataset_path") or "").strip()
    recipe_dir = (data.get("recipe_dir") or "").strip()
    modality = (data.get("modality") or "survey").strip().lower() or "survey"
    out_format = (data.get("format") or "csv").strip().lower() or "csv"
    survey_filter = (data.get("survey") or "").strip() or None
    sessions = (data.get("sessions") or "").strip() or None
    lang = (data.get("lang") or "en").strip().lower() or "en"
    layout = (data.get("layout") or "long").strip().lower() or "long"
    include_raw = bool(data.get("include_raw", False))
    boilerplate = bool(data.get("boilerplate", False))
    merge_all = bool(data.get("merge_all", False))
    anonymize = bool(data.get("anonymize", False))
    mask_questions = bool(data.get("mask_questions", False))
    id_length = int(data.get("id_length", 8))
    random_ids = bool(data.get("random_ids", False))
    force_overwrite = bool(data.get("force_overwrite", False))

    if not dataset_path or not os.path.exists(dataset_path) or not os.path.isdir(dataset_path):
        return jsonify({"error": "Invalid dataset path"}), 400

    derivatives_dir = (
        Path(dataset_path)
        / "derivatives"
        / ("survey" if modality == "survey" else "biometrics")
    )
    if derivatives_dir.exists() and not force_overwrite:
        existing_files = []
        format_exts = {
            "csv": [".csv"],
            "xlsx": [".xlsx"],
            "save": [".sav"],
            "r": [".feather"],
        }
        codebook_suffixes = {
            "csv": ["_codebook.json", "_codebook.tsv"],
            "xlsx": [],
            "save": ["_codebook.json"],
            "r": ["_codebook.json"],
        }

        exts = format_exts.get(out_format, [".csv"])
        suffixes = codebook_suffixes.get(out_format, [])

        if out_format == "save":
            try:
                import pyreadstat  # noqa: F401
            except Exception:
                exts = list(set(exts + [".csv"]))
                suffixes = list(set(suffixes + ["_codebook.json", "_codebook.tsv"]))
        if out_format == "r":
            try:
                import pyarrow  # noqa: F401
            except Exception:
                exts = list(set(exts + [".csv"]))
                suffixes = list(set(suffixes + ["_codebook.json", "_codebook.tsv"]))

        for ext in exts:
            existing_files.extend(derivatives_dir.glob(f"*{ext}"))
        for suffix in suffixes:
            existing_files.extend(derivatives_dir.glob(f"*{suffix}"))

        if existing_files:
            file_names = [f.name for f in existing_files[:10]]
            more_count = len(existing_files) - 10 if len(existing_files) > 10 else 0
            msg = f"Output files already exist in {derivatives_dir.name}/: {', '.join(file_names)}"
            if more_count > 0:
                msg += f" (and {more_count} more)"
            return (
                jsonify(
                    {
                        "confirm_overwrite": True,
                        "message": msg,
                        "existing_files": file_names,
                        "total_existing": len(existing_files),
                    }
                ),
                200,
            )

    from src.web import run_validation

    issues, _stats = run_validation(
        dataset_path, verbose=False, schema_version=None, run_bids=False
    )
    error_issues = [
        i for i in (issues or []) if (len(i) >= 1 and str(i[0]).upper() == "ERROR")
    ]

    validation_warning = None
    if error_issues:
        first = (
            error_issues[0][1]
            if len(error_issues[0]) > 1
            else "Dataset has validation errors"
        )
        validation_warning = (
            f"Dataset has {len(error_issues)} validation error(s). First: {first}"
        )

    try:
        repo_root = current_app.root_path
        global_recipes = _global_recipes_root()

        effective_recipe_dir = recipe_dir
        if global_recipes and not recipe_dir:
            if global_recipes.name == "recipes":
                repo_root = str(global_recipes.parent)
            else:
                effective_recipe_dir = str(global_recipes)

        cmd_parts = [
            "python",
            "prism_tools.py",
            "recipes",
            modality,
            f'--prism "{dataset_path}"',
        ]
        if repo_root != current_app.root_path:
            cmd_parts.append(f'--repo "{repo_root}"')
        if effective_recipe_dir:
            cmd_parts.append(f'--recipes "{effective_recipe_dir}"')
        if survey_filter:
            cmd_parts.append(f'--survey "{survey_filter}"')
        if sessions:
            cmd_parts.append(f'--sessions "{sessions}"')
        if out_format != "flat":
            cmd_parts.append(f"--format {out_format}")
        if layout != "long":
            cmd_parts.append(f"--layout {layout}")
        if include_raw:
            cmd_parts.append("--include-raw")
        if boilerplate:
            cmd_parts.append("--boilerplate")
        if lang != "en":
            cmd_parts.append(f"--lang {lang}")

        cli_cmd = " ".join(cmd_parts)
        print(f"\n[BACKEND-ACTION] {cli_cmd}\n")

        recipes_kwargs = {
            "prism_root": dataset_path,
            "repo_root": repo_root,
            "recipe_dir": effective_recipe_dir,
            "survey": survey_filter,
            "sessions": sessions,
            "out_format": out_format,
            "modality": modality,
            "lang": lang,
            "layout": layout,
            "include_raw": include_raw,
            "boilerplate": boilerplate,
        }

        try:
            sig = inspect.signature(compute_survey_recipes)
            if "merge_all" in sig.parameters:
                recipes_kwargs["merge_all"] = merge_all
            elif merge_all:
                print(
                    "[WARN] merge_all requested but current compute_survey_recipes "
                    "implementation does not support it; continuing without merge_all"
                )
        except Exception:
            if merge_all:
                print(
                    "[WARN] Could not inspect compute_survey_recipes signature; "
                    "continuing without merge_all"
                )

        result = compute_survey_recipes(**recipes_kwargs)

        mapping_file = None
        anonymized_count = 0
        if anonymize:
            try:
                from src.anonymizer import create_participant_mapping
                import pandas as pd
                import json

                participants_tsv = os.path.join(dataset_path, "rawdata", "participants.tsv")
                if not os.path.exists(participants_tsv):
                    participants_tsv = os.path.join(dataset_path, "participants.tsv")
                if not os.path.exists(participants_tsv):
                    raise FileNotFoundError(
                        f"participants.tsv not found in {dataset_path}/rawdata/ or {dataset_path}/"
                    )

                df = pd.read_csv(participants_tsv, sep="\t")
                if "participant_id" not in df.columns:
                    raise ValueError("participants.tsv must have a 'participant_id' column")
                participant_ids = df["participant_id"].tolist()

                output_dir = str(result.out_root)
                if not os.path.exists(output_dir):
                    raise FileNotFoundError(f"Output directory not found: {output_dir}")

                mapping_file = Path(output_dir) / "participants_mapping.json"

                if mapping_file.exists():
                    print(f"[ANONYMIZATION] Loading existing mapping from: {mapping_file}")
                    with open(mapping_file, "r", encoding="utf-8") as f:
                        mapping_data = json.load(f)
                        participant_mapping = mapping_data.get("mapping", {})
                    print(
                        f"[ANONYMIZATION] Loaded {len(participant_mapping)} existing ID mappings"
                    )
                else:
                    print("[ANONYMIZATION] Creating new participant mapping...")
                    participant_mapping = create_participant_mapping(
                        participant_ids,
                        mapping_file,
                        id_length=id_length,
                        deterministic=not random_ids,
                    )
                    print(f"[ANONYMIZATION] Created mapping: {mapping_file}")

                print(f"[ANONYMIZATION] Anonymizing files in: {output_dir}")
                print(f"[ANONYMIZATION] Output format: {out_format}")

                if out_format in ("save", "spss"):
                    try:
                        import pyreadstat
                    except ImportError:
                        print("[ANONYMIZATION] WARNING: pyreadstat not available, cannot anonymize .sav files")
                        print("[ANONYMIZATION] Install with: pip install pyreadstat")
                        raise ImportError("pyreadstat required for anonymizing SPSS files")

                    for root, dirs, files in os.walk(output_dir):
                        for file in files:
                            if file.endswith((".sav",)):
                                sav_path = os.path.join(root, file)
                                print(f"  Processing: {file}")

                                df_data, meta = pyreadstat.read_sav(sav_path)

                                if "participant_id" in df_data.columns:
                                    original_ids = df_data["participant_id"].unique()
                                    df_data["participant_id"] = df_data[
                                        "participant_id"
                                    ].map(lambda x: participant_mapping.get(x, x))
                                    anonymized_ids = df_data["participant_id"].unique()
                                    print(
                                        f"    ✓ {len(original_ids)} IDs → {len(anonymized_ids)} anonymized"
                                    )
                                    anonymized_count += 1

                                if mask_questions:
                                    question_cols = [
                                        col
                                        for col in df_data.columns
                                        if "question" in col.lower()
                                    ]
                                    for col in question_cols:
                                        if col in meta.column_names_to_labels:
                                            meta.column_names_to_labels[col] = "[MASKED]"

                                pyreadstat.write_sav(
                                    df_data,
                                    sav_path,
                                    column_labels=meta.column_names_to_labels,
                                )

                elif out_format in ("csv", "tsv", "flat", "prism"):
                    for root, dirs, files in os.walk(output_dir):
                        for file in files:
                            if file.endswith((".tsv", ".csv")):
                                file_path = os.path.join(root, file)
                                print(f"  Processing: {file}")

                                sep = "\t" if file.endswith(".tsv") else ","

                                df_data = pd.read_csv(file_path, sep=sep)
                                if "participant_id" in df_data.columns:
                                    original_ids = df_data["participant_id"].unique()
                                    df_data["participant_id"] = df_data[
                                        "participant_id"
                                    ].map(lambda x: participant_mapping.get(x, x))
                                    anonymized_ids = df_data["participant_id"].unique()
                                    print(
                                        f"    ✓ {len(original_ids)} IDs → {len(anonymized_ids)} anonymized"
                                    )
                                    anonymized_count += 1

                                if mask_questions and "question" in df_data.columns:
                                    df_data["question"] = "[MASKED]"

                                df_data.to_csv(file_path, sep=sep, index=False)

                elif out_format in ("xlsx", "excel"):
                    for root, dirs, files in os.walk(output_dir):
                        for file in files:
                            if file.endswith(".xlsx"):
                                file_path = os.path.join(root, file)
                                print(f"  Processing: {file}")

                                excel_file = pd.ExcelFile(file_path)
                                sheet_names = excel_file.sheet_names
                                sheet_frames = {
                                    sheet_name: pd.read_excel(
                                        file_path, sheet_name=sheet_name
                                    )
                                    for sheet_name in sheet_names
                                }

                                file_had_participant_ids = False
                                for sheet_name, df_data in sheet_frames.items():
                                    if "participant_id" in df_data.columns:
                                        original_ids = df_data["participant_id"].unique()
                                        df_data["participant_id"] = df_data[
                                            "participant_id"
                                        ].map(lambda x: participant_mapping.get(x, x))
                                        anonymized_ids = df_data["participant_id"].unique()
                                        print(
                                            f"    ✓ [{sheet_name}] {len(original_ids)} IDs → {len(anonymized_ids)} anonymized"
                                        )
                                        file_had_participant_ids = True

                                    if mask_questions and "question" in df_data.columns:
                                        df_data["question"] = "[MASKED]"

                                with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
                                    for sheet_name in sheet_names:
                                        sheet_frames[sheet_name].to_excel(
                                            writer, sheet_name=sheet_name, index=False
                                        )

                                if file_had_participant_ids:
                                    anonymized_count += 1

                print(f"[ANONYMIZATION] ✓ Anonymized {anonymized_count} file(s)")
                if mask_questions:
                    print("[ANONYMIZATION] ✓ Masked copyrighted question text")
                mapping_file = str(mapping_file)

            except Exception as anon_error:
                import traceback

                error_trace = traceback.format_exc()
                print(f"\n{'=' * 70}\n❌ ANONYMIZATION ERROR\n{'=' * 70}")
                print(error_trace)
                print(f"{'=' * 70}\n")
                return (
                    jsonify(
                        {
                            "error": f"Anonymization failed: {str(anon_error)}\n\nSee terminal for full traceback."
                        }
                    ),
                    500,
                )

    except Exception as e:
        import traceback

        error_trace = traceback.format_exc()
        print(f"\n{'=' * 70}\n❌ PROCESSING ERROR\n{'=' * 70}")
        print(error_trace)
        print(f"{'=' * 70}\n")
        return jsonify({"error": f"{str(e)}\n\nSee terminal for full traceback."}), 500

    msg = f"Data processing complete: wrote {result.written_files} file(s)"
    if result.flat_out_path:
        msg = f"Data processing complete: wrote {result.flat_out_path}"
    if result.fallback_note:
        msg += f" (note: {result.fallback_note})"

    if anonymize and mapping_file:
        if anonymized_count > 0:
            msg += f"\n🔒 Anonymized {anonymized_count} file(s) with {'random' if random_ids else 'deterministic'} IDs (length: {id_length})"
        else:
            msg += "\n⚠️  No output files with participant_id were anonymized"
        if mask_questions:
            msg += "\n🔒 Masked copyrighted question text"
        msg += f"\n⚠️  SECURITY: Keep mapping file secure: {os.path.basename(mapping_file)}"

    return jsonify(
        {
            "ok": True,
            "message": msg,
            "validation_warning": validation_warning,
            "written_files": result.written_files,
            "processed_files": result.processed_files,
            "out_format": result.out_format,
            "out_root": str(result.out_root),
            "flat_out_path": str(result.flat_out_path) if result.flat_out_path else None,
            "boilerplate_path": (
                str(result.boilerplate_path) if result.boilerplate_path else None
            ),
            "anonymized": anonymize,
            "anonymized_files": anonymized_count,
            "mapping_file": os.path.basename(mapping_file) if mapping_file else None,
            "boilerplate_html_path": (
                str(result.boilerplate_html_path)
                if result.boilerplate_html_path
                else None
            ),
            "nan_report": result.nan_report,
        }
    )