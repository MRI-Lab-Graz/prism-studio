import sys
from pathlib import Path

from flask import current_app, jsonify, request, session


def handle_limesurvey_to_prism():
    """Convert LimeSurvey (.lss/.lsa) or Excel/CSV/TSV file to PRISM JSON sidecar(s)."""
    logs = []

    def log(msg, type="info"):
        logs.append({"message": msg, "type": type})

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    filename = file.filename.lower()
    is_excel = any(filename.endswith(ext) for ext in [".xlsx", ".csv", ".tsv"])
    is_limesurvey = any(filename.endswith(ext) for ext in [".lss", ".lsa"])

    if not (is_excel or is_limesurvey):
        return (
            jsonify({"error": "Please upload a .lss, .lsa, .xlsx, .csv, or .tsv file"}),
            400,
        )

    task_name = request.form.get("task_name", "").strip()
    log(f"Starting template generation from: {file.filename}")

    mode = request.form.get("mode", "").strip().lower()
    if not mode:
        split_by_groups = request.form.get("split_by_groups", "false").lower() == "true"
        mode = "groups" if split_by_groups else "combined"

    if mode not in ("combined", "groups", "questions"):
        return (
            jsonify(
                {"error": f"Invalid mode '{mode}'. Use: combined, groups, or questions"}
            ),
            400,
        )

    if not task_name:
        task_name = Path(file.filename).stem

    try:
        from src.utils.naming import sanitize_task_name
        from jsonschema import ValidationError, validate
        from src.schema_manager import load_schema

        survey_schema = load_schema("survey")

        def validate_template(sidecar, name):
            if not survey_schema:
                return
            try:
                validate(instance=sidecar, schema=survey_schema)
                log(f"✓ {name} matches PRISM survey schema", "success")
            except ValidationError as e:
                log(f"⚠ {name} validation issue: {e.message}", "warning")
            except Exception as e:
                log(f"⚠ Could not validate {name}: {str(e)}", "warning")

        if is_excel:
            import io
            from src.converters.excel_to_survey import extract_excel_templates

            log(
                "Detected Excel/CSV source. Running data dictionary extraction...",
                "step",
            )

            file_bytes = io.BytesIO(file.read())
            file_bytes.name = file.filename

            extracted = extract_excel_templates(file_bytes)

            if not extracted:
                return (
                    jsonify(
                        {"error": "No data found in the Excel/CSV file", "log": logs}
                    ),
                    400,
                )

            log(f"Extracted {len(extracted)} potential survey(s)", "info")

            if mode == "questions":
                log("Splitting by individual questions...", "step")
                all_questions = {}
                by_group = {}

                for prefix, sidecar in extracted.items():
                    shared_technical = sidecar.get("Technical", {})
                    shared_study = sidecar.get("Study", {})
                    shared_metadata = sidecar.get("Metadata", {})
                    shared_i18n = sidecar.get("I18n", {})

                    for key, q_entry in sidecar.items():
                        if key in [
                            "Technical",
                            "Study",
                            "Metadata",
                            "I18n",
                            "Scoring",
                            "Normative",
                        ]:
                            continue

                        question_prism = {
                            "Technical": shared_technical,
                            "Study": {
                                **shared_study,
                                "TaskName": sanitize_task_name(key),
                                "OriginalName": key,
                            },
                            "Metadata": shared_metadata,
                            "I18n": shared_i18n,
                            key: q_entry,
                        }

                        validate_template(question_prism, f"Item {key}")

                        all_questions[key] = {
                            "prism_json": question_prism,
                            "question_code": key,
                            "question_type": "string",
                            "limesurvey_type": "N/A",
                            "item_count": 1,
                            "mandatory": False,
                            "group_name": prefix,
                            "group_order": 0,
                            "question_order": 0,
                            "suggested_filename": f"question-{sanitize_task_name(key)}.json",
                        }

                        if prefix not in by_group:
                            by_group[prefix] = {"group_order": 0, "questions": []}

                        by_group[prefix]["questions"].append(
                            {
                                "code": key,
                                "type": "string",
                                "limesurvey_type": "N/A",
                                "item_count": 1,
                                "mandatory": False,
                                "order": 0,
                            }
                        )

                log("Individual template generation complete.", "success")
                return jsonify(
                    {
                        "success": True,
                        "mode": "questions",
                        "questions": all_questions,
                        "by_group": by_group,
                        "question_count": len(all_questions),
                        "group_count": len(by_group),
                        "log": logs,
                    }
                )

            elif mode == "groups":
                log("Splitting by questionnaire prefixes...", "step")
                result = {
                    "success": True,
                    "mode": "groups",
                    "questionnaires": {},
                    "questionnaire_count": len(extracted),
                    "total_questions": 0,
                    "log": logs,
                }

                for prefix, prism_json in extracted.items():
                    validate_template(prism_json, f"Survey {prefix}")
                    q_count = len(
                        [
                            k
                            for k in prism_json.keys()
                            if k
                            not in [
                                "Technical",
                                "Study",
                                "Metadata",
                                "I18n",
                                "Scoring",
                                "Normative",
                            ]
                        ]
                    )
                    result["questionnaires"][prefix] = {
                        "prism_json": prism_json,
                        "suggested_filename": f"survey-{prefix}.json",
                        "question_count": q_count,
                    }
                    result["total_questions"] += q_count

                try:
                    from src.converters.survey_templates import (
                        match_groups_against_library,
                    )

                    groups_for_matching = {
                        name: data["prism_json"]
                        for name, data in result["questionnaires"].items()
                    }
                    matches = match_groups_against_library(
                        groups_for_matching,
                        project_path=session.get("current_project_path"),
                    )
                    for name, match in matches.items():
                        result["questionnaires"][name]["template_match"] = (
                            match.to_dict() if match else None
                        )
                        if match:
                            log(
                                f"Library match: {name} → {match.template_key} "
                                f"({match.confidence}, {match.overlap_count}/{match.template_items} items)",
                                "info",
                            )
                        else:
                            log(f"No library match for: {name}", "info")
                except Exception as e:
                    log(f"Template matching skipped: {e}", "warning")

                log("Group template generation complete.", "success")
                return jsonify(result)

            else:
                log("Merging all extracted items into a single template...", "step")
                combined_json = {}
                total_q = 0
                for _prefix, prism_json in extracted.items():
                    for k, v in prism_json.items():
                        if k not in [
                            "Technical",
                            "Study",
                            "Metadata",
                            "I18n",
                            "Scoring",
                            "Normative",
                        ]:
                            combined_json[k] = v
                            total_q += 1
                        elif k not in combined_json:
                            combined_json[k] = v

                validate_template(combined_json, "Combined template")
                safe_name = sanitize_task_name(task_name)

                combined_result = {
                    "success": True,
                    "mode": "combined",
                    "prism_json": combined_json,
                    "suggested_filename": f"survey-{safe_name}.json",
                    "question_count": total_q,
                    "log": logs,
                }

                try:
                    from src.converters.survey_templates import (
                        match_against_library,
                    )

                    match = match_against_library(
                        combined_json,
                        project_path=session.get("current_project_path"),
                    )
                    combined_result["template_match"] = (
                        match.to_dict() if match else None
                    )
                except Exception as e:
                    log(f"Template matching skipped: {e}", "warning")

                log("Combined template generation complete.", "success")
                return jsonify(combined_result)

        log("Detected LimeSurvey source. Parsing XML structure...", "info")
        try:
            from src.converters.limesurvey import (
                parse_lss_xml,
                parse_lss_xml_by_groups,
                parse_lss_xml_by_questions,
            )
        except ImportError:
            sys.path.insert(0, str(Path(current_app.root_path)))
            from src.converters.limesurvey import (
                parse_lss_xml,
                parse_lss_xml_by_groups,
                parse_lss_xml_by_questions,
            )

        xml_content = None
        if filename.endswith(".lsa"):
            import io
            import zipfile as zf_module

            file_bytes = io.BytesIO(file.read())
            try:
                with zf_module.ZipFile(file_bytes, "r") as zf:
                    lss_files = [f for f in zf.namelist() if f.endswith(".lss")]
                    if not lss_files:
                        return (
                            jsonify(
                                {
                                    "error": "No .lss file found in the .lsa archive",
                                    "log": logs,
                                }
                            ),
                            400,
                        )
                    with zf.open(lss_files[0]) as file_handle:
                        xml_content = file_handle.read()
            except zf_module.BadZipFile:
                return jsonify({"error": "Invalid .lsa archive", "log": logs}), 400
        else:
            xml_content = file.read()

        if not xml_content:
            return jsonify({"error": "Could not read file content", "log": logs}), 400

        if mode == "questions":
            log("Splitting LimeSurvey into individual question templates...", "step")
            questions = parse_lss_xml_by_questions(xml_content)

            if not questions:
                return (
                    jsonify(
                        {
                            "error": "Failed to parse LimeSurvey structure or no questions found",
                            "log": logs,
                        }
                    ),
                    400,
                )

            by_group = {}
            for code, q_data in questions.items():
                validate_template(q_data["prism_json"], f"Item {code}")
                g = q_data["group_name"]
                if g not in by_group:
                    by_group[g] = {
                        "group_order": q_data["group_order"],
                        "questions": [],
                    }
                by_group[g]["questions"].append(
                    {
                        "code": code,
                        "type": q_data["question_type"],
                        "limesurvey_type": q_data["limesurvey_type"],
                        "item_count": q_data["item_count"],
                        "mandatory": q_data["mandatory"],
                        "order": q_data["question_order"],
                    }
                )

            for group in by_group.values():
                group["questions"].sort(key=lambda x: x["order"])

            log("Individual template generation complete.", "success")
            return jsonify(
                {
                    "success": True,
                    "mode": "questions",
                    "questions": questions,
                    "by_group": by_group,
                    "question_count": len(questions),
                    "group_count": len(by_group),
                    "log": logs,
                }
            )

        elif mode == "groups":
            log("Splitting LimeSurvey into separate questionnaires by group...", "step")
            questionnaires = parse_lss_xml_by_groups(xml_content)

            if not questionnaires:
                return (
                    jsonify(
                        {
                            "error": "Failed to parse LimeSurvey structure or no groups found",
                            "log": logs,
                        }
                    ),
                    400,
                )

            result = {
                "success": True,
                "mode": "groups",
                "questionnaires": {},
                "questionnaire_count": len(questionnaires),
                "total_questions": 0,
                "log": logs,
            }

            for name, prism_json in questionnaires.items():
                validate_template(prism_json, f"Questionnaire {name}")
                q_count = len(
                    [
                        k
                        for k in prism_json.keys()
                        if k
                        not in [
                            "Technical",
                            "Study",
                            "Metadata",
                            "I18n",
                            "Scoring",
                            "Normative",
                        ]
                    ]
                )
                result["questionnaires"][name] = {
                    "prism_json": prism_json,
                    "suggested_filename": f"survey-{name}.json",
                    "question_count": q_count,
                }
                result["total_questions"] += q_count

            try:
                from src.converters.survey_templates import (
                    match_groups_against_library,
                )

                groups_for_matching = {
                    name: data["prism_json"]
                    for name, data in result["questionnaires"].items()
                }
                matches = match_groups_against_library(
                    groups_for_matching,
                    project_path=session.get("current_project_path"),
                )
                for name, match in matches.items():
                    result["questionnaires"][name]["template_match"] = (
                        match.to_dict() if match else None
                    )
                    if match:
                        log(
                            f"Library match: {name} → {match.template_key} "
                            f"({match.confidence}, {match.overlap_count}/{match.template_items} items)",
                            "info",
                        )
                    else:
                        log(f"No library match for: {name}", "info")
            except Exception as e:
                log(f"Template matching skipped: {e}", "warning")

            log("Group template generation complete.", "success")
            return jsonify(result)

        else:
            log("Converting entire LimeSurvey to a single PRISM template...", "step")
            prism_data = parse_lss_xml(xml_content, task_name=task_name)

            if not prism_data:
                return (
                    jsonify(
                        {"error": "Failed to parse LimeSurvey structure", "log": logs}
                    ),
                    400,
                )

            validate_template(prism_data, "Combined LimeSurvey template")
            safe_name = sanitize_task_name(task_name)
            suggested_filename = f"survey-{safe_name}.json"

            combined_result = {
                "success": True,
                "mode": "combined",
                "prism_json": prism_data,
                "suggested_filename": suggested_filename,
                "question_count": len(
                    [
                        k
                        for k in prism_data.keys()
                        if k
                        not in [
                            "Technical",
                            "Study",
                            "Metadata",
                            "I18n",
                            "Scoring",
                            "Normative",
                        ]
                    ]
                ),
                "log": logs,
            }

            try:
                from src.converters.survey_templates import (
                    match_against_library,
                )

                match = match_against_library(
                    prism_data,
                    group_name=task_name,
                    project_path=session.get("current_project_path"),
                )
                combined_result["template_match"] = match.to_dict() if match else None
            except Exception as e:
                log(f"Template matching skipped: {e}", "warning")

            log("Combined template generation complete.", "success")
            return jsonify(combined_result)

    except Exception as e:
        log(f"Critical error: {str(e)}", "error")
        return jsonify({"error": str(e), "log": logs}), 500
