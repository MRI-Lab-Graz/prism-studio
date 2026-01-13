import json
import defusedxml.ElementTree as ET
from datetime import datetime
import os
import io


def add_row(parent, data):
    """Add a <row> element with child tags based on dictionary"""
    row = ET.SubElement(parent, "row")
    for key, value in data.items():
        child = ET.SubElement(row, key)
        child.text = str(value)


def generate_lss(json_files, output_path=None, language="en", ls_version="6"):
    """
    Generate a LimeSurvey Structure (.lss) file from a list of Prism JSON sidecars.

    Args:
        json_files (list): List of paths to JSON files.
        output_path (str, optional): Path to write the .lss file. If None, returns the XML string.
        language (str): The language to use for the export.
        ls_version (str): Target LimeSurvey version ("3" or "6").

    Returns:
        str: The XML content if output_path is None, else None.
    """

    def get_text(obj, lang, i18n_data=None, path=None):
        """
        Get localized text.
        1. Checks i18n_data[lang] using the provided path (e.g. "age.Description")
        2. If not found, checks if obj is a dict (inline translation)
        3. Otherwise returns obj as string
        """
        if i18n_data and lang in i18n_data and path:
            parts = path.split(".")
            curr = i18n_data[lang]
            for p in parts:
                if isinstance(curr, dict) and p in curr:
                    curr = curr[p]
                else:
                    curr = None
                    break
            if curr:
                return str(curr)

        if isinstance(obj, dict):
            return obj.get(lang, obj.get("en", next(iter(obj.values()), "")))
        return str(obj)

    is_v6 = str(ls_version) == "6"
    db_version = "640" if is_v6 else "366"

    # IDs
    sid = "123456"  # Dummy Survey ID

    # Root element
    root = ET.Element("document")
    ET.SubElement(root, "LimeSurveyDocType").text = "Survey"
    ET.SubElement(root, "DBVersion").text = db_version

    # Languages
    langs = ET.SubElement(root, "languages")
    ET.SubElement(langs, "language").text = language

    # Sections
    answers_elem = ET.SubElement(root, "answers")
    answers_rows = ET.SubElement(answers_elem, "rows")

    questions_elem = ET.SubElement(root, "questions")
    questions_rows = ET.SubElement(questions_elem, "rows")

    groups_elem = ET.SubElement(root, "groups")
    groups_rows = ET.SubElement(groups_elem, "rows")

    subquestions_elem = ET.SubElement(root, "subquestions")
    subquestions_rows = ET.SubElement(subquestions_elem, "rows")

    # LS6 specific localization tables
    if is_v6:
        answer_l10ns_elem = ET.SubElement(root, "answer_l10ns")
        answer_l10ns_rows = ET.SubElement(answer_l10ns_elem, "rows")

        question_l10ns_elem = ET.SubElement(root, "question_l10ns")
        question_l10ns_rows = ET.SubElement(question_l10ns_elem, "rows")

        group_l10ns_elem = ET.SubElement(root, "group_l10ns")
        group_l10ns_rows = ET.SubElement(group_l10ns_elem, "rows")

    surveys_elem = ET.SubElement(root, "surveys")
    surveys_rows = ET.SubElement(surveys_elem, "rows")

    surveys_lang_elem = ET.SubElement(root, "surveys_languagesettings")
    surveys_lang_rows = ET.SubElement(surveys_lang_elem, "rows")

    # Counters
    gid_counter = 10
    qid_counter = 100
    group_sort_order = 0

    # --- Process Each JSON as a Group ---
    for item in json_files:
        # Determine path and filter
        if isinstance(item, str):
            json_path = item
            include_keys = None
            matrix_mode = False
            matrix_global = False
        elif isinstance(item, dict):
            json_path = item.get("path")
            include_keys = item.get("include")
            matrix_mode = item.get("matrix", False)
            matrix_global = item.get("matrix_global", False)
        else:
            continue

        try:
            with open(json_path, "r") as f:
                data = json.load(f)
                i18n_data = data.get("I18n", {})
        except Exception as e:
            print(f"Error reading {json_path}: {e}")
            continue

        # Filter out metadata keys to get questions
        if "Questions" in data and isinstance(data["Questions"], dict):
            all_questions = data["Questions"]
        else:
            all_questions = {
                k: v
                for k, v in data.items()
                if k
                not in [
                    "Technical",
                    "Study",
                    "Metadata",
                    "Categories",
                    "TaskName",
                    "I18n",
                    "Scoring",
                    "Normative",
                ]
            }

        # Apply inclusion filter if provided
        if include_keys is not None:
            questions_data = {
                k: v for k, v in all_questions.items() if k in include_keys
            }
        else:
            questions_data = all_questions

        gid = str(gid_counter)
        gid_counter += 1
        group_sort_order += 1

        study_info = data.get("Study", {})
        group_name = get_text(
            study_info.get(
                "OriginalName",
                data.get("TaskName", os.path.splitext(os.path.basename(json_path))[0]),
            ),
            language,
            i18n_data,
            "Study.OriginalName",
        )
        group_desc = get_text(
            study_info.get("Description", ""), language, i18n_data, "Study.Description"
        )

        # Add Group
        group_data = {
            "gid": gid,
            "sid": sid,
            "group_order": str(group_sort_order),
            "randomization_group": "",
            "grelevance": "",
        }
        if not is_v6:
            group_data["group_name"] = group_name
            group_data["description"] = group_desc
            group_data["language"] = language

        add_row(groups_rows, group_data)

        if is_v6:
            add_row(
                group_l10ns_rows,
                {
                    "id": gid,  # In LS6, l10ns often use the main ID as reference
                    "gid": gid,
                    "group_name": group_name,
                    "description": group_desc,
                    "language": language,
                    "sid": sid,
                },
            )

        # Prepare Groups of Questions
        grouped_questions = []
        if matrix_mode:
            if matrix_global:
                # Global grouping: group all questions with identical levels
                groups = []
                level_to_group_idx = {}

                for q_code, q_data in questions_data.items():
                    if not isinstance(q_data, dict):
                        continue

                    levels = q_data.get("Levels")
                    if levels and isinstance(levels, dict) and len(levels) > 0:
                        l_str = json.dumps(levels, sort_keys=True)
                        if l_str in level_to_group_idx:
                            groups[level_to_group_idx[l_str]].append((q_code, q_data))
                        else:
                            level_to_group_idx[l_str] = len(groups)
                            groups.append([(q_code, q_data)])
                    else:
                        groups.append([(q_code, q_data)])
                grouped_questions = groups
            else:
                # Consecutive grouping only
                current_group = []
                last_levels_str = None

                for q_code, q_data in questions_data.items():
                    if not isinstance(q_data, dict):
                        continue

                    levels = q_data.get("Levels")
                    levels_str = (
                        json.dumps(levels, sort_keys=True) if levels else "NO_LEVELS"
                    )

                    if not current_group:
                        current_group.append((q_code, q_data))
                        last_levels_str = levels_str
                    else:
                        if levels and levels_str == last_levels_str:
                            current_group.append((q_code, q_data))
                        else:
                            grouped_questions.append(current_group)
                            current_group = [(q_code, q_data)]
                            last_levels_str = levels_str
                if current_group:
                    grouped_questions.append(current_group)
        else:
            # No grouping
            for q_code, q_data in questions_data.items():
                if isinstance(q_data, dict):
                    grouped_questions.append([(q_code, q_data)])

        # Process Questions in this Group
        q_sort_order = 0
        for group in grouped_questions:
            # group is a list of (q_code, q_data)

            first_code, first_data = group[0]
            levels = first_data.get("Levels", {})
            is_matrix = len(group) > 1

            qid = str(qid_counter)
            qid_counter += 1
            q_sort_order += 1

            # Logic / Relevance
            relevance = "1"
            if "Relevance" in first_data:
                relevance = first_data["Relevance"]
            elif "LimeSurvey" in first_data and "Relevance" in first_data["LimeSurvey"]:
                relevance = first_data["LimeSurvey"]["Relevance"]

            if is_matrix:
                # Matrix Question (Array)
                # Type 'F' is Array (Flexible Labels)
                q_type = "F"

                # Matrix Title
                matrix_title = f"M_{first_code}"

                # Matrix Text - Use a generic prompt
                matrix_text = "Please answer the following questions:"
                if language == "de":
                    matrix_text = "Bitte beantworten Sie die folgenden Fragen:"

                # Add Matrix Parent Question
                q_data_row = {
                    "qid": qid,
                    "parent_qid": "0",
                    "sid": sid,
                    "gid": gid,
                    "type": q_type,
                    "title": matrix_title,
                    "other": "N",
                    "mandatory": "Y",
                    "question_order": str(q_sort_order),
                    "scale_id": "0",
                    "same_default": "0",
                    "relevance": relevance,
                }
                if not is_v6:
                    q_data_row["question"] = matrix_text
                    q_data_row["language"] = language

                add_row(questions_rows, q_data_row)

                if is_v6:
                    add_row(
                        question_l10ns_rows,
                        {
                            "id": qid,
                            "qid": qid,
                            "question": matrix_text,
                            "help": "",
                            "language": language,
                        },
                    )

                # Add Subquestions
                sub_sort = 0
                for code, data_item in group:
                    sub_sort += 1
                    sub_qid = str(qid_counter)
                    qid_counter += 1

                    # Add Subquestion
                    sub_q_text = get_text(
                        data_item.get("Description", code),
                        language,
                        i18n_data,
                        f"{code}.Description",
                    )
                    sub_q_row = {
                        "qid": sub_qid,
                        "parent_qid": qid,
                        "sid": sid,
                        "gid": gid,
                        "type": "T",
                        "title": code,
                        "question_order": str(sub_sort),
                        "scale_id": "0",
                        "same_default": "0",
                        "relevance": "1",
                    }
                    if not is_v6:
                        sub_q_row["question"] = sub_q_text
                        sub_q_row["language"] = language

                    add_row(subquestions_rows, sub_q_row)

                    if is_v6:
                        add_row(
                            question_l10ns_rows,
                            {
                                "id": sub_qid,
                                "qid": sub_qid,
                                "question": sub_q_text,
                                "help": "",
                                "language": language,
                            },
                        )

                    # Add Answers (Only once for the matrix parent)
                    if levels:
                        sort_ans = 0
                        for code, answer_text in levels.items():
                            sort_ans += 1
                            ans_text = get_text(
                                answer_text,
                                language,
                                i18n_data,
                                f"{first_code}.Levels.{code}",
                            )
                            ans_row = {
                                "qid": qid,
                                "code": code,
                                "sortorder": str(sort_ans),
                                "assessment_value": "0",
                                "scale_id": "0",
                            }
                            if not is_v6:
                                ans_row["answer"] = ans_text
                                ans_row["language"] = language

                            add_row(answers_rows, ans_row)

                            if is_v6:
                                add_row(
                                    answer_l10ns_rows,
                                    {
                                        "id": f"{qid}_{code}",  # Dummy unique ID for l10n row
                                        "qid": qid,
                                        "code": code,
                                        "answer": ans_text,
                                        "language": language,
                                    },
                                )

            else:
                # Single Question
                q_code = first_code
                q_data = first_data
                description = get_text(
                    q_data.get("Description", q_code),
                    language,
                    i18n_data,
                    f"{q_code}.Description",
                )

                # Determine Type
                q_type = "L" if levels else "T"  # List (Radio) or Long Free Text

                # Add Single Question
                q_data_row = {
                    "qid": qid,
                    "parent_qid": "0",
                    "sid": sid,
                    "gid": gid,
                    "type": q_type,
                    "title": q_code,
                    "other": "N",
                    "mandatory": "Y",
                    "question_order": str(q_sort_order),
                    "scale_id": "0",
                    "same_default": "0",
                    "relevance": relevance,
                }
                if not is_v6:
                    q_data_row["question"] = description
                    q_data_row["language"] = language

                add_row(questions_rows, q_data_row)

                if is_v6:
                    add_row(
                        question_l10ns_rows,
                        {
                            "id": qid,
                            "qid": qid,
                            "question": description,
                            "help": "",
                            "language": language,
                        },
                    )

                # Add Answers
                if levels:
                    sort_ans = 0
                    for code, answer_text in levels.items():
                        sort_ans += 1
                        ans_text = get_text(
                            answer_text, language, i18n_data, f"{q_code}.Levels.{code}"
                        )
                        ans_row = {
                            "qid": qid,
                            "code": code,
                            "sortorder": str(sort_ans),
                            "assessment_value": "0",
                            "scale_id": "0",
                        }
                        if not is_v6:
                            ans_row["answer"] = ans_text
                            ans_row["language"] = language

                        add_row(answers_rows, ans_row)

                        if is_v6:
                            add_row(
                                answer_l10ns_rows,
                                {
                                    "id": f"{qid}_{code}",
                                    "qid": qid,
                                    "code": code,
                                    "answer": ans_text,
                                    "language": language,
                                },
                            )

    # --- Survey Settings ---
    survey_settings = {
        "sid": sid,
        "owner_id": "1",
        "admin": "Administrator",
        "active": "N",
        "anonymized": "N",
        "format": "G",  # Group by Group
        "savetimings": "Y",
        "template": "vanilla",
        "language": language,
    }
    add_row(surveys_rows, survey_settings)

    # --- Survey Language Settings ---
    survey_title = "Combined Survey"
    if len(json_files) == 1:
        # If only one file, try to use its name
        try:
            f_item = json_files[0]
            f_path = f_item if isinstance(f_item, str) else f_item.get("path")
            with open(f_path, "r") as f:
                d = json.load(f)
                s_info = d.get("Study", {})
                i_data = d.get("I18n", {})
                survey_title = get_text(
                    s_info.get("OriginalName", d.get("TaskName", "Combined Survey")),
                    language,
                    i_data,
                    "Study.OriginalName",
                )
        except Exception:
            pass

    add_row(
        surveys_lang_rows,
        {
            "surveyls_survey_id": sid,
            "surveyls_language": language,
            "surveyls_title": survey_title,
            "surveyls_description": f"Generated from {len(json_files)} Prism JSON files on {datetime.now().isoformat()}",
            "surveyls_welcometext": "",
            "surveyls_endtext": "",
        },
    )

    # --- Themes (Required for LS 3+) ---
    themes_elem = ET.SubElement(root, "themes")
    themes_rows = ET.SubElement(themes_elem, "rows")

    add_row(
        themes_rows,
        {
            "sid": sid,
            "template_name": "vanilla",
            "config": '{"options":{"ajaxmode":"on","brandlogo":"on","container":"on","hideprivacyinfo":"off","brandlogofile":"./files/logo.png","font":"noto","showpopups":"1"}}',
        },
    )

    # --- Themes Inherited (Required for LS 3+) ---
    themes_inh_elem = ET.SubElement(root, "themes_inherited")
    themes_inh_rows = ET.SubElement(themes_inh_elem, "rows")

    add_row(
        themes_inh_rows,
        {
            "sid": sid,
            "template_name": "vanilla",
            "config": '{"options":{"ajaxmode":"on","brandlogo":"on","container":"on","hideprivacyinfo":"off","brandlogofile":"./files/logo.png","font":"noto","showpopups":"1"}}',
        },
    )

    # Generate XML
    tree = ET.ElementTree(root)
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ", level=0)

    if output_path:
        tree.write(output_path, encoding="UTF-8", xml_declaration=True)
        return output_path
    else:
        f = io.BytesIO()
        tree.write(f, encoding="UTF-8", xml_declaration=True)
        return f.getvalue().decode("utf-8")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python limesurvey_exporter.py <json_file1> [json_file2 ...] <output.lss>"
        )
        sys.exit(1)

    # Last arg is output if it ends with .lss, otherwise all are inputs
    output = None
    inputs = sys.argv[1:]
    if inputs[-1].endswith(".lss"):
        output = inputs.pop()

    generate_lss(inputs, output)
