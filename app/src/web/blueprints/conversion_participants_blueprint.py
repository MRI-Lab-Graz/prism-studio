import re
import shutil
import tempfile
from pathlib import Path

from flask import Blueprint, jsonify, request, session
from werkzeug.utils import secure_filename

from .conversion_participants_helpers import (
    _collect_default_participant_columns,
    _detect_repeated_questionnaire_prefixes,
    _generate_neurobagel_schema,
    _is_likely_questionnaire_column,
    _load_project_participant_filter_config,
    _load_survey_template_item_ids,
    _normalize_column_name,
)
from .conversion_utils import resolve_effective_library_path

conversion_participants_bp = Blueprint("conversion_participants", __name__)


@conversion_participants_bp.route("/api/save-participant-mapping", methods=["POST"])
def save_participant_mapping():
    """Save additional-variables mapping JSON file to the project library directory."""
    try:
        import json

        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        mapping = data.get("mapping")
        library_path = data.get("library_path")
        project_path = session.get("current_project_path")

        if not mapping:
            return jsonify({"error": "Missing mapping data"}), 400

        target_lib_path = None
        used_source = None

        if project_path:
            try:
                project_lib = Path(str(project_path)).resolve() / "code" / "library"
                project_lib.mkdir(parents=True, exist_ok=True)
                target_lib_path = project_lib
                used_source = "project"
            except Exception:
                pass

        if not target_lib_path and library_path:
            try:
                lib_path = Path(str(library_path)).resolve()
                if lib_path.exists() and lib_path.is_dir():
                    target_lib_path = lib_path
                    used_source = "provided"
            except Exception as e:
                return jsonify({"error": f"Invalid library path: {str(e)}"}), 400

        if not target_lib_path:
            return (
                jsonify(
                    {
                        "error": "No valid library path found. Please ensure project is loaded or select a library path."
                    }
                ),
                400,
            )

        normalized_mapping = mapping
        if isinstance(mapping, dict) and "mappings" not in mapping:
            mappings_block = {}
            for source_column, standard_variable in mapping.items():
                src = str(source_column).strip()
                if not src:
                    continue

                std_raw = str(standard_variable).strip() or src
                std = re.sub(r"[^a-zA-Z0-9_]+", "_", std_raw).strip("_").lower()
                if not std:
                    std = re.sub(r"[^a-zA-Z0-9_]+", "_", src).strip("_").lower()
                if not std:
                    continue

                mappings_block[std] = {
                    "source_column": src,
                    "standard_variable": std,
                    "type": "string",
                }

            normalized_mapping = {
                "version": "1.0",
                "description": "Additional variables mapping created from PRISM web UI",
                "mappings": mappings_block,
            }

        mapping_file = target_lib_path / "participants_mapping.json"

        with open(mapping_file, "w") as f:
            json.dump(normalized_mapping, f, indent=2)

        return jsonify(
            {
                "status": "success",
                "file_path": str(mapping_file),
                "library_source": used_source,
                "message": (
                    f"Saved {mapping_file.name}. "
                    "This mapping is applied when you run Extract & Convert."
                ),
            }
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        return jsonify({"error": f"Error saving mapping: {str(e)}"}), 500


@conversion_participants_bp.route("/api/participants-check", methods=["GET"])
def api_participants_check():
    """Check if participants.tsv and participants.json exist in the project/dataset."""
    project_path = session.get("current_project_path")
    if not project_path:
        return jsonify({"error": "No project selected"}), 400

    project_root = Path(project_path)

    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"
    exists_root = participants_tsv.exists() or participants_json.exists()

    return jsonify(
        {
            "exists": exists_root,
            "location": ("root" if exists_root else None),
            "files": {
                "participants_tsv": (
                    str(participants_tsv) if participants_tsv.exists() else None
                ),
                "participants_json": (
                    str(participants_json) if participants_json.exists() else None
                ),
            },
        }
    )


@conversion_participants_bp.route("/api/participants-detect-id", methods=["POST"])
def api_participants_detect_id():
    """Detect participant ID column for an uploaded participant file."""
    try:
        import pandas as pd
    except ImportError as e:
        return jsonify({"error": f"Required module not available: {str(e)}"}), 500

    uploaded_file = request.files.get("file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify({"error": "Missing input file"}), 400

    filename = secure_filename(uploaded_file.filename)
    suffix = Path(filename).suffix.lower()

    if suffix not in {".xlsx", ".csv", ".tsv", ".lsa"}:
        return jsonify({"error": "Supported formats: .xlsx, .csv, .tsv, .lsa"}), 400

    tmp_dir = tempfile.mkdtemp(prefix="prism_participants_detect_id_")
    try:
        tmp_path = Path(tmp_dir)
        input_path = tmp_path / filename
        uploaded_file.save(str(input_path))

        sheet = request.form.get("sheet", "0").strip() or "0"
        try:
            sheet_arg = int(sheet) if sheet.isdigit() else sheet
        except (ValueError, TypeError):
            sheet_arg = 0

        if suffix == ".xlsx":
            df = pd.read_excel(input_path, sheet_name=sheet_arg, dtype=str)
        elif suffix in {".csv", ".tsv"}:
            sep = "\t" if suffix == ".tsv" else ","
            df = pd.read_csv(input_path, sep=sep, dtype=str)
        else:
            from src.converters.survey import _read_lsa_as_dataframe

            df = _read_lsa_as_dataframe(input_path)

        from src.converters.id_detection import (
            detect_id_column as _detect_id,
            has_prismmeta_columns as _has_pm_cols,
        )

        source_fmt = "lsa" if suffix == ".lsa" else "xlsx"
        detected_id = _detect_id(
            list(df.columns),
            source_fmt,
            explicit_id_column=None,
            has_prismmeta=_has_pm_cols(list(df.columns)),
        )

        return jsonify(
            {
                "status": "success",
                "id_found": bool(detected_id),
                "id_column": detected_id,
                "columns": [str(c) for c in df.columns],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@conversion_participants_bp.route("/api/participants-preview", methods=["POST"])
def api_participants_preview():
    """Preview participant data extraction from uploaded file."""
    try:
        import pandas as pd
    except ImportError as e:
        return jsonify({"error": f"Required module not available: {str(e)}"}), 500

    mode = request.form.get("mode", "file")

    if mode == "file":
        uploaded_file = request.files.get("file")
        if not uploaded_file or not uploaded_file.filename:
            return jsonify({"error": "Missing input file"}), 400

        filename = secure_filename(uploaded_file.filename)
        suffix = Path(filename).suffix.lower()

        if suffix not in {".xlsx", ".csv", ".tsv", ".lsa"}:
            return jsonify({"error": "Supported formats: .xlsx, .csv, .tsv, .lsa"}), 400

        tmp_dir = tempfile.mkdtemp(prefix="prism_participants_preview_")
        try:
            tmp_path = Path(tmp_dir)
            input_path = tmp_path / filename
            uploaded_file.save(str(input_path))

            sheet = request.form.get("sheet", "0").strip() or "0"
            try:
                sheet_arg = int(sheet) if sheet.isdigit() else sheet
            except (ValueError, TypeError):
                sheet_arg = 0

            if suffix == ".xlsx":
                df = pd.read_excel(input_path, sheet_name=sheet_arg, dtype=str)
            elif suffix in {".csv", ".tsv"}:
                sep = "\t" if suffix == ".tsv" else ","
                df = pd.read_csv(input_path, sep=sep, dtype=str)
            elif suffix == ".lsa":
                try:
                    from src.converters.survey import _read_lsa_as_dataframe

                    df = _read_lsa_as_dataframe(input_path)
                except ImportError:
                    return jsonify({"error": "LimeSurvey support not available"}), 500

            from src.converters.id_detection import (
                detect_id_column as _detect_id,
                has_prismmeta_columns as _has_pm_cols,
            )

            id_column = request.form.get("id_column", "").strip() or None
            source_fmt = "lsa" if suffix == ".lsa" else "xlsx"
            _has_pm = _has_pm_cols(list(df.columns))
            id_column = _detect_id(
                list(df.columns),
                source_fmt,
                explicit_id_column=id_column,
                has_prismmeta=_has_pm,
            )

            if not id_column:
                return (
                    jsonify(
                        {
                            "error": "id_column_required",
                            "message": f"Could not auto-detect ID column. Available columns: {', '.join(df.columns)}",
                            "columns": list(df.columns),
                        }
                    ),
                    409,
                )

            library_path = resolve_effective_library_path()
            participant_filter_config = _load_project_participant_filter_config(
                session.get("current_project_path")
            )

            template_item_ids = _load_survey_template_item_ids(library_path)
            repeated_prefixes = _detect_repeated_questionnaire_prefixes(
                [str(c) for c in df.columns],
                participant_filter_config=participant_filter_config,
            )
            questionnaire_like_columns = [
                str(col)
                for col in df.columns
                if str(col) != id_column
                and _is_likely_questionnaire_column(
                    str(col),
                    _normalize_column_name(str(col)),
                    template_item_ids,
                    repeated_prefixes,
                )
            ]

            output_columns = _collect_default_participant_columns(df, id_column)

            if len(output_columns) <= 1:
                if id_column in df.columns:
                    output_df = df[[id_column]]
                    simulation_note = "Detected participant ID only. Additional variables can be added via Add Additional Variables."
                else:
                    output_df = df[list(df.columns)]
                    simulation_note = "Could not detect a participant ID column. Showing raw file structure."
            else:
                output_df = df[output_columns]
                simulation_note = (
                    f"Simulated output with {len(output_columns)} default participant columns."
                )

            preview_df = output_df.head(20)

            neurobagel_schema = _generate_neurobagel_schema(
                output_df,
                id_column,
                library_path=library_path,
                participant_filter_config=participant_filter_config,
            )

            return jsonify(
                {
                    "status": "success",
                    "columns": list(output_df.columns),
                    "source_columns": list(df.columns),
                    "questionnaire_like_columns": questionnaire_like_columns,
                    "id_column": id_column,
                    "participant_count": len(df),
                    "preview_rows": preview_df.to_dict(orient="records"),
                    "library_path": str(library_path),
                    "simulation_note": simulation_note,
                    "total_source_columns": len(df.columns),
                    "extracted_columns": len(output_df.columns),
                    "neurobagel_schema": neurobagel_schema,
                }
            )

        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    elif mode == "dataset":
        project_path = session.get("current_project_path")
        if not project_path:
            return jsonify({"error": "No project selected"}), 400

        project_root = Path(project_path)
        extract_from_survey = (
            request.form.get("extract_from_survey", "true").lower() == "true"
        )
        extract_from_biometrics = (
            request.form.get("extract_from_biometrics", "true").lower() == "true"
        )

        participants = set()

        if extract_from_survey:
            survey_files = list(project_root.rglob("**/survey/*_survey.tsv"))
            for f in survey_files:
                match = re.search(r"(sub-[A-Za-z0-9]+)", f.name)
                if match:
                    participants.add(match.group(1))

        if extract_from_biometrics:
            biometrics_files = list(
                project_root.rglob("**/biometrics/*_biometrics.tsv")
            )
            for f in biometrics_files:
                match = re.search(r"(sub-[A-Za-z0-9]+)", f.name)
                if match:
                    participants.add(match.group(1))

        if not participants:
            return jsonify({"error": "No participant data found in dataset"}), 400

        participants_list = sorted(list(participants))

        return jsonify(
            {
                "status": "success",
                "participant_count": len(participants_list),
                "participants": participants_list[:20],
                "total_participants": len(participants_list),
            }
        )

    else:
        return jsonify({"error": f"Unknown mode: {mode}"}), 400


@conversion_participants_bp.route("/api/participants-convert", methods=["POST"])
def api_participants_convert():
    """Convert/extract participant data and create participants.tsv and participants.json."""
    try:
        from src.participants_converter import ParticipantsConverter
        import pandas as pd
        import json
    except ImportError as e:
        return jsonify({"error": f"Required module not available: {str(e)}"}), 500

    mode = request.form.get("mode", "file")
    force_overwrite = request.form.get("force_overwrite", "false").lower() == "true"
    neurobagel_schema_json = request.form.get("neurobagel_schema")

    neurobagel_schema = {}
    if neurobagel_schema_json:
        try:
            neurobagel_schema = json.loads(neurobagel_schema_json)
        except json.JSONDecodeError:
            pass

    project_path = session.get("current_project_path")
    if not project_path:
        return jsonify({"error": "No project selected"}), 400

    project_root = Path(project_path)

    participants_tsv = project_root / "participants.tsv"
    participants_json = project_root / "participants.json"

    existing_files = []
    if participants_tsv.exists():
        existing_files.append(str(participants_tsv))
    if participants_json.exists():
        existing_files.append(str(participants_json))

    if existing_files and not force_overwrite:
        return (
            jsonify(
                {
                    "error": "Participant files already exist. Enable 'force overwrite' to replace them.",
                    "existing_files": existing_files,
                }
            ),
            409,
        )

    logs = []

    def log_msg(level, message):
        logs.append({"level": level, "message": message})

    try:
        if mode == "file":
            uploaded_file = request.files.get("file")
            if not uploaded_file or not uploaded_file.filename:
                return jsonify({"error": "Missing input file"}), 400

            filename = secure_filename(uploaded_file.filename)

            tmp_dir = tempfile.mkdtemp(prefix="prism_participants_convert_")
            try:
                tmp_path = Path(tmp_dir)
                input_path = tmp_path / filename
                uploaded_file.save(str(input_path))

                log_msg("INFO", f"Processing {filename}...")

                converter = ParticipantsConverter(project_root, log_callback=log_msg)

                mapping = None
                mapping_candidates = [
                    project_root / "participants_mapping.json",
                    project_root / "code" / "participants_mapping.json",
                    project_root / "code" / "library" / "participants_mapping.json",
                    project_root
                    / "code"
                    / "library"
                    / "survey"
                    / "participants_mapping.json",
                ]
                for candidate in mapping_candidates:
                    if candidate.exists() and candidate.is_file():
                        mapping = converter.load_mapping_from_file(candidate)
                        if mapping:
                            log_msg(
                                "INFO",
                                f"Using participants_mapping.json from {candidate}",
                            )
                            break

                if isinstance(mapping, dict) and "mappings" not in mapping:
                    legacy_mappings = {}
                    for source_column, standard_variable in mapping.items():
                        src = str(source_column).strip()
                        if not src:
                            continue
                        std_raw = str(standard_variable).strip() or src
                        std = re.sub(r"[^a-zA-Z0-9_]+", "_", std_raw).strip("_").lower()
                        if not std:
                            std = re.sub(r"[^a-zA-Z0-9_]+", "_", src).strip("_").lower()
                        if not std:
                            continue
                        legacy_mappings[std] = {
                            "source_column": src,
                            "standard_variable": std,
                            "type": "string",
                        }
                    mapping = {
                        "version": "1.0",
                        "description": "Normalized legacy participant mapping",
                        "mappings": legacy_mappings,
                    }
                    log_msg(
                        "INFO", "Normalized legacy participants_mapping.json format"
                    )

                if not mapping:
                    import pandas as pd

                    try:
                        test_df = pd.read_csv(
                            str(input_path), sep=None, engine="python", nrows=0
                        )
                        columns = list(test_df.columns)
                        log_msg("INFO", f"Auto-detected columns: {', '.join(columns)}")

                        mapping = {"version": "1.0", "mappings": {}}

                        for col in columns:
                            col_lower = col.lower()
                            if col_lower in ["participant_id", "sub", "subject", "id"]:
                                mapping["mappings"]["participant_id"] = {
                                    "source_column": col,
                                    "standard_variable": "participant_id",
                                }
                            elif col_lower in ["age"]:
                                mapping["mappings"]["age"] = {
                                    "source_column": col,
                                    "standard_variable": "age",
                                }
                            elif col_lower in ["sex", "biological_sex", "biologicalsex"]:
                                mapping["mappings"]["sex"] = {
                                    "source_column": col,
                                    "standard_variable": "sex",
                                }
                            elif col_lower in ["gender", "gender_identity", "genderidentity"]:
                                mapping["mappings"]["gender"] = {
                                    "source_column": col,
                                    "standard_variable": "gender",
                                }
                            elif col_lower in ["handedness"]:
                                mapping["mappings"]["handedness"] = {
                                    "source_column": col,
                                    "standard_variable": "handedness",
                                }
                            elif col_lower in ["education", "education_level", "educationlevel"]:
                                mapping["mappings"]["education"] = {
                                    "source_column": col,
                                    "standard_variable": "education",
                                }

                        if mapping["mappings"]:
                            log_msg(
                                "INFO",
                                f"Auto-created mapping for {len(mapping['mappings'])} columns",
                            )
                    except Exception as e:
                        log_msg("WARNING", f"Could not auto-detect columns: {e}")
                        mapping = {"version": "1.0", "mappings": {}}
                else:
                    if mapping.get("mappings"):
                        log_msg(
                            "INFO",
                            f"Using explicit participant mapping for {len(mapping.get('mappings', {}))} columns",
                        )

                try:
                    import pandas as pd
                    from src.converters.id_detection import (
                        detect_id_column as _detect_id,
                        has_prismmeta_columns as _has_pm_cols,
                    )

                    suffix = input_path.suffix.lower()
                    if suffix == ".xlsx":
                        sheet = request.form.get("sheet", "0").strip() or "0"
                        try:
                            sheet_arg = int(sheet) if sheet.isdigit() else sheet
                        except (ValueError, TypeError):
                            sheet_arg = 0
                        df_for_merge = pd.read_excel(
                            input_path, sheet_name=sheet_arg, dtype=str
                        )
                    elif suffix == ".csv":
                        df_for_merge = pd.read_csv(input_path, sep=",", dtype=str)
                    elif suffix == ".tsv":
                        df_for_merge = pd.read_csv(input_path, sep="\t", dtype=str)
                    elif suffix == ".lsa":
                        from src.converters.survey import _read_lsa_as_dataframe

                        df_for_merge = _read_lsa_as_dataframe(input_path)
                    else:
                        df_for_merge = pd.read_csv(
                            input_path, sep=None, engine="python", dtype=str
                        )

                    explicit_id_col = request.form.get("id_column", "").strip() or None
                    source_fmt = "lsa" if suffix == ".lsa" else "xlsx"
                    detected_id_col = _detect_id(
                        list(df_for_merge.columns),
                        source_fmt,
                        explicit_id_column=explicit_id_col,
                        has_prismmeta=_has_pm_cols(list(df_for_merge.columns)),
                    )
                    if not detected_id_col and explicit_id_col in df_for_merge.columns:
                        detected_id_col = explicit_id_col
                    if not detected_id_col and len(df_for_merge.columns) > 0:
                        detected_id_col = str(df_for_merge.columns[0])

                    auto_columns = _collect_default_participant_columns(
                        df_for_merge, detected_id_col
                    )

                    if not isinstance(mapping, dict):
                        mapping = {"version": "1.0", "mappings": {}}
                    mapping.setdefault("version", "1.0")
                    mapping_block = mapping.setdefault("mappings", {})

                    used_sources = {
                        str(spec.get("source_column")).strip()
                        for spec in mapping_block.values()
                        if isinstance(spec, dict) and spec.get("source_column")
                    }
                    used_targets = {
                        str(spec.get("standard_variable")).strip()
                        for spec in mapping_block.values()
                        if isinstance(spec, dict) and spec.get("standard_variable")
                    }

                    added_auto = 0
                    for col in auto_columns:
                        source_col = str(col).strip()
                        if not source_col:
                            continue

                        standard_var = (
                            "participant_id"
                            if detected_id_col and source_col == detected_id_col
                            else source_col
                        )

                        if source_col in used_sources or standard_var in used_targets:
                            continue

                        mapping_block[standard_var] = {
                            "source_column": source_col,
                            "standard_variable": standard_var,
                            "type": "string",
                        }
                        used_sources.add(source_col)
                        used_targets.add(standard_var)
                        added_auto += 1

                    if added_auto:
                        log_msg(
                            "INFO",
                            f"Added {added_auto} default participant columns to mapping (additive merge)",
                        )
                except Exception as merge_error:
                    log_msg(
                        "WARNING",
                        f"Could not merge default participant columns into mapping: {merge_error}",
                    )

                success, df, messages = converter.convert_participant_data(
                    source_file=str(input_path),
                    mapping=mapping,
                    output_file=str(participants_tsv),
                )

                for msg in messages:
                    log_msg("INFO", msg)

                if not success or df is None:
                    return jsonify({"error": "Conversion failed", "log": logs}), 400

                df.to_csv(participants_tsv, sep="\t", index=False)
                log_msg("INFO", f"✓ Created {participants_tsv.name}")

                import json as json_module

                participants_json_data = {}
                for col in df.columns:
                    participants_json_data[col] = {"Description": f"Participant {col}"}

                if neurobagel_schema:
                    try:
                        for col, schema_def in neurobagel_schema.items():
                            if col not in participants_json_data:
                                participants_json_data[col] = {}

                            if "Annotations" in schema_def:
                                if "Annotations" not in participants_json_data[col]:
                                    participants_json_data[col]["Annotations"] = {}
                                participants_json_data[col]["Annotations"].update(
                                    schema_def["Annotations"]
                                )

                            for key, value in schema_def.items():
                                if (
                                    key != "Annotations"
                                    and key not in participants_json_data[col]
                                ):
                                    participants_json_data[col][key] = value

                        log_msg(
                            "INFO",
                            "Merged NeuroBagel annotations into participants.json",
                        )
                    except Exception as e:
                        log_msg(
                            "WARNING", f"Could not merge NeuroBagel schema: {str(e)}"
                        )

                with open(participants_json, "w") as f:
                    json_module.dump(participants_json_data, f, indent=2)

                log_msg("INFO", f"✓ Created {participants_json.name}")

                log_msg("INFO", f"✓ Created {participants_tsv.name}")
                log_msg("INFO", f"✓ Created {participants_json.name}")

                return jsonify(
                    {
                        "status": "success",
                        "log": logs,
                        "files_created": [
                            str(participants_tsv),
                            str(participants_json),
                        ],
                    }
                )

            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

        elif mode == "dataset":
            extract_from_survey = (
                request.form.get("extract_from_survey", "true").lower() == "true"
            )
            extract_from_biometrics = (
                request.form.get("extract_from_biometrics", "true").lower() == "true"
            )

            log_msg("INFO", "Extracting participant data from dataset...")

            participants = set()

            if extract_from_survey:
                survey_files = list(project_root.rglob("**/survey/*_survey.tsv"))
                log_msg("INFO", f"Found {len(survey_files)} survey files")
                for f in survey_files:
                    match = re.search(r"(sub-[A-Za-z0-9]+)", f.name)
                    if match:
                        participants.add(match.group(1))

            if extract_from_biometrics:
                biometrics_files = list(
                    project_root.rglob("**/biometrics/*_biometrics.tsv")
                )
                log_msg("INFO", f"Found {len(biometrics_files)} biometrics files")
                for f in biometrics_files:
                    match = re.search(r"(sub-[A-Za-z0-9]+)", f.name)
                    if match:
                        participants.add(match.group(1))

            if not participants:
                return (
                    jsonify(
                        {"error": "No participant data found in dataset", "log": logs}
                    ),
                    400,
                )

            participants_list = sorted(list(participants))
            log_msg("INFO", f"Found {len(participants_list)} unique participants")

            df = pd.DataFrame({"participant_id": participants_list})
            df.to_csv(participants_tsv, sep="\t", index=False)

            participants_json_data = {
                "participant_id": {"Description": "Unique participant identifier"}
            }

            if neurobagel_schema:
                for col, schema_def in neurobagel_schema.items():
                    if col not in participants_json_data:
                        participants_json_data[col] = {}

                    if "Annotations" in schema_def:
                        if "Annotations" not in participants_json_data[col]:
                            participants_json_data[col]["Annotations"] = {}
                        participants_json_data[col]["Annotations"].update(
                            schema_def["Annotations"]
                        )

                    for key, value in schema_def.items():
                        if (
                            key != "Annotations"
                            and key not in participants_json_data[col]
                        ):
                            participants_json_data[col][key] = value

            import json as json_module

            with open(participants_json, "w") as f:
                json_module.dump(participants_json_data, f, indent=2)

            log_msg(
                "INFO",
                f"✓ Created {participants_tsv.name} with {len(participants_list)} participants",
            )
            log_msg("INFO", f"✓ Created {participants_json.name}")

            return jsonify(
                {
                    "status": "success",
                    "log": logs,
                    "participant_count": len(participants_list),
                    "files_created": [str(participants_tsv), str(participants_json)],
                }
            )

        else:
            return jsonify({"error": f"Unknown mode: {mode}", "log": logs}), 400

    except Exception as e:
        import traceback

        log_msg("ERROR", f"Error: {str(e)}")
        log_msg("ERROR", traceback.format_exc())
        return jsonify({"error": str(e), "log": logs}), 500
