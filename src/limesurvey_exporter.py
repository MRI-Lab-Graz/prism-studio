import json
import xml.etree.ElementTree as ET
from datetime import datetime
import os


def add_row(parent, data):
    """Add a <row> element with child tags based on dictionary"""
    row = ET.SubElement(parent, "row")
    for key, value in data.items():
        child = ET.SubElement(row, key)
        child.text = str(value)


def generate_lss(json_files, output_path=None):
    """
    Generate a LimeSurvey Structure (.lss) file from a list of Prism JSON sidecars.

    Args:
        json_files (list): List of paths to JSON files.
        output_path (str, optional): Path to write the .lss file. If None, returns the XML string.

    Returns:
        str: The XML content if output_path is None, else None.
    """

    # IDs
    sid = "123456"  # Dummy Survey ID

    # Root element
    root = ET.Element("document")
    ET.SubElement(root, "LimeSurveyDocType").text = "Survey"
    ET.SubElement(root, "DBVersion").text = "366"  # Approximate version

    # Languages
    langs = ET.SubElement(root, "languages")
    ET.SubElement(langs, "language").text = "en"

    # Sections
    answers_elem = ET.SubElement(root, "answers")
    answers_rows = ET.SubElement(answers_elem, "rows")

    questions_elem = ET.SubElement(root, "questions")
    questions_rows = ET.SubElement(questions_elem, "rows")

    groups_elem = ET.SubElement(root, "groups")
    groups_rows = ET.SubElement(groups_elem, "rows")

    subquestions_elem = ET.SubElement(root, "subquestions")
    subquestions_rows = ET.SubElement(subquestions_elem, "rows")

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
        elif isinstance(item, dict):
            json_path = item.get("path")
            include_keys = item.get("include")
            matrix_mode = item.get("matrix", False)
        else:
            continue

        try:
            with open(json_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error reading {json_path}: {e}")
            continue

        # Filter out metadata keys to get questions
        all_questions = {
            k: v
            for k, v in data.items()
            if k not in ["Technical", "Study", "Metadata", "Categories", "TaskName"]
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

        group_name = data.get(
            "TaskName", os.path.splitext(os.path.basename(json_path))[0]
        )
        group_desc = data.get("Study", {}).get("Description", "")

        # Add Group
        add_row(
            groups_rows,
            {
                "gid": gid,
                "sid": sid,
                "group_name": group_name,
                "group_order": str(group_sort_order),
                "description": group_desc,
                "language": "en",
                "randomization_group": "",
                "grelevance": "",
            },
        )

        # Prepare Groups of Questions
        grouped_questions = []
        if matrix_mode:
            current_group = []
            last_levels_str = None

            for q_code, q_data in questions_data.items():
                if not isinstance(q_data, dict):
                    continue

                levels = q_data.get("Levels", {})
                # Only group if levels exist. Text questions shouldn't be grouped this way usually.
                levels_str = json.dumps(levels, sort_keys=True) if levels else "NO_LEVELS"

                if not current_group:
                    current_group.append((q_code, q_data))
                    last_levels_str = levels_str
                else:
                    # Check if matches previous
                    if levels and levels_str == last_levels_str:
                        current_group.append((q_code, q_data))
                    else:
                        # Flush current group
                        grouped_questions.append(current_group)
                        # Start new
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
            is_matrix = (len(group) > 1)

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

                add_row(
                    questions_rows,
                    {
                        "qid": qid,
                        "parent_qid": "0",
                        "sid": sid,
                        "gid": gid,
                        "type": q_type,
                        "title": matrix_title,
                        "question": matrix_text,
                        "other": "N",
                        "mandatory": "Y",
                        "question_order": str(q_sort_order),
                        "language": "en",
                        "scale_id": "0",
                        "same_default": "0",
                        "relevance": relevance,
                    },
                )

                # Add Subquestions
                sub_sort = 0
                for code, data_item in group:
                    sub_sort += 1
                    sub_qid = str(qid_counter)
                    qid_counter += 1

                    add_row(
                        subquestions_rows,
                        {
                            "qid": sub_qid,
                            "parent_qid": qid,
                            "sid": sid,
                            "gid": gid,
                            "type": "T",
                            "title": code,
                            "question": data_item.get("Description", code),
                            "question_order": str(sub_sort),
                            "language": "en",
                            "scale_id": "0",
                            "same_default": "0",
                            "relevance": "1",
                        },
                    )

                # Add Answers (Only once for the matrix parent)
                if levels:
                    sort_ans = 0
                    for code, answer_text in levels.items():
                        sort_ans += 1
                        add_row(
                            answers_rows,
                            {
                                "qid": qid,
                                "code": code,
                                "answer": answer_text,
                                "sortorder": str(sort_ans),
                                "language": "en",
                                "assessment_value": "0",
                                "scale_id": "0",
                            },
                        )

            else:
                # Single Question
                q_code = first_code
                q_data = first_data
                description = q_data.get("Description", q_code)

                # Determine Type
                q_type = "L" if levels else "T"  # List (Radio) or Long Free Text

                # Add Question
                add_row(
                    questions_rows,
                    {
                        "qid": qid,
                        "parent_qid": "0",
                        "sid": sid,
                        "gid": gid,
                        "type": q_type,
                        "title": q_code,
                        "question": description,
                        "other": "N",
                        "mandatory": "Y",
                        "question_order": str(q_sort_order),
                        "language": "en",
                        "scale_id": "0",
                        "same_default": "0",
                        "relevance": relevance,
                    },
                )

                # Add Answers
                if levels:
                    sort_ans = 0
                    for code, answer_text in levels.items():
                        sort_ans += 1
                        add_row(
                            answers_rows,
                            {
                                "qid": qid,
                                "code": code,
                                "answer": answer_text,
                                "sortorder": str(sort_ans),
                                "language": "en",
                                "assessment_value": "0",
                                "scale_id": "0",
                            },
                        )

    # --- Survey Settings ---
    add_row(
        surveys_rows,
        {
            "sid": sid,
            "owner_id": "1",
            "admin": "Administrator",
            "active": "N",
            "anonymized": "N",
            "format": "G",  # Group by Group
            "savetimings": "Y",
            "template": "vanilla",
            "language": "en",
        },
    )

    # --- Survey Language Settings ---
    survey_title = "Combined Survey"
    if len(json_files) == 1:
        # If only one file, try to use its name
        try:
            with open(json_files[0], "r") as f:
                d = json.load(f)
                survey_title = d.get("TaskName", survey_title)
        except:
            pass

    add_row(
        surveys_lang_rows,
        {
            "surveyls_survey_id": sid,
            "surveyls_language": "en",
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
    import io

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
