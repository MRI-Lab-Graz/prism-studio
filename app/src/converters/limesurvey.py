import argparse
import json
import os
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
import defusedxml.ElementTree as ET
import pandas as pd

# Add project root to path to import from src
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from .survey_base import load_survey_library as load_schemas
    from ..utils.naming import sanitize_task_name
except (ImportError, ValueError):
    # Fallback for different execution contexts
    try:
        from survey_base import load_survey_library as load_schemas
        from ..utils.naming import sanitize_task_name
    except (ImportError, ValueError):
        from .survey_base import load_survey_library as load_schemas
        from utils.naming import sanitize_task_name

from .csv import process_dataframe  # noqa: E402


def parse_prismmeta_html(html_content: str) -> dict | None:
    """Parse PRISMMETA equation HTML to extract structured metadata.

    Extracts type, variables, and other metadata from the hidden
    ``<div class="prism-metadata">`` block embedded in PRISMMETA equations.

    Returns:
        Parsed metadata dict, or None if not PRISMMETA HTML.
    """
    if not html_content or "prism-metadata" not in html_content:
        return None

    meta: dict = {}
    span_map = {
        "meta-name": "name",
        "meta-abbrev": "abbrev",
        "meta-type": "type",
        "meta-variables": "variables",
    }
    for css_class, key in span_map.items():
        m = re.search(rf'<span class="{css_class}">(.*?)</span>', html_content)
        if m:
            meta[key] = m.group(1).strip()

    if "variables" in meta and meta["variables"]:
        meta["variables"] = [
            v.strip() for v in meta["variables"].split(",") if v.strip()
        ]

    return meta if meta else None


# LimeSurvey question type codes mapped to human-readable names
LIMESURVEY_QUESTION_TYPES = {
    # Single choice
    "L": "List (Radio)",
    "!": "List (Dropdown)",
    "O": "List with Comment",
    "G": "Gender",
    "Y": "Yes/No",
    "I": "Language Switch",
    # Multiple choice
    "M": "Multiple Choice",
    "P": "Multiple Choice with Comments",
    # Free text
    "S": "Short Free Text",
    "T": "Long Free Text",
    "U": "Huge Free Text",
    "Q": "Multiple Short Text",
    # Numerical
    "N": "Numerical Input",
    "K": "Multiple Numerical Input",
    # Date/Time
    "D": "Date/Time",
    # Arrays/Matrices
    "A": "Array (5 Point Choice)",
    "B": "Array (10 Point Choice)",
    "C": "Array (Yes/Uncertain/No)",
    "E": "Array (Increase/Same/Decrease)",
    "F": "Array (Flexible Labels)",
    "H": "Array by Column",
    ";": "Array (Texts)",
    ":": "Array (Numbers)",
    "1": "Array Dual Scale",
    # Ranking
    "R": "Ranking",
    # Special
    "X": "Text Display (Boilerplate)",
    "*": "Equation",
    "|": "File Upload",
}

# Implicit levels for question types that don't store answers in the XML <answers> section
# These are built-in response options in LimeSurvey
IMPLICIT_LEVELS = {
    "Y": {"Y": "Yes", "N": "No"},  # Yes/No question
    "G": {"M": "Male", "F": "Female"},  # Gender question
    "C": {"Y": "Yes", "U": "Uncertain", "N": "No"},  # Array (Yes/Uncertain/No)
    "E": {
        "I": "Increase",
        "S": "Same",
        "D": "Decrease",
    },  # Array (Increase/Same/Decrease)
    "A": {str(i): str(i) for i in range(1, 6)},  # Array (5 Point Choice): 1-5
    "B": {str(i): str(i) for i in range(1, 11)},  # Array (10 Point Choice): 1-10
    "5": {str(i): str(i) for i in range(1, 6)},  # 5 Point Choice (simple): 1-5
}


def _get_question_type_name(type_code):
    """Convert LimeSurvey type code to human-readable name."""
    return LIMESURVEY_QUESTION_TYPES.get(type_code, f"Unknown ({type_code})")


def _map_field_to_code(fieldname, qid_to_title):
    # Handle both with and without leading underscore (_569818X43542X590136 or 569818X43542X590136)
    m = re.match(r"_?(\d+)X(\d+)X(\d+)([A-Za-z0-9_]+)?", fieldname)
    if not m:
        return fieldname
    qid = m.group(3)
    suffix = m.group(4)
    if suffix:
        return suffix
    return qid_to_title.get(qid, fieldname)


def parse_lsa_responses(lsa_path):
    """Return (dataframe, qid->title mapping, groups_map) extracted from a LimeSurvey .lsa file."""
    with zipfile.ZipFile(lsa_path, "r") as z:
        xml_resp = z.read(next(n for n in z.namelist() if n.endswith("_responses.lsr")))
        xml_lss = z.read(next(n for n in z.namelist() if n.endswith(".lss")))

    lss_root = ET.fromstring(xml_lss)

    # Helper to find text of a child element
    def get_text(element, tag):
        child = element.find(tag)
        val = child.text if child is not None else ""
        return val or ""

    questions_map, groups_map = _parse_lss_structure(lss_root, get_text)

    # Build simple qid->title map for column renaming
    qid_to_title = {qid: d["title"] for qid, d in questions_map.items()}

    # Also include subquestions in qid_to_title if needed?
    # The original code did this:
    subquestion_count = 0
    for row in lss_root.findall(".//subquestions/rows/row"):
        qid = row.find("qid").text
        title = row.find("title").text
        if qid and title:
            qid_to_title[qid] = title
            subquestion_count += 1

    text = xml_resp.decode("utf-8")
    fieldnames = re.findall(r"<fieldname>(.*?)</fieldname>", text)

    # Parse rows by XML to preserve order and decode CDATA
    resp_root = ET.fromstring(xml_resp)
    rows = resp_root.findall("./responses/rows/row")
    records = []
    for row in rows:
        rec = {}
        for child in row:
            tag = child.tag.lstrip("_")
            rec[tag] = child.text
        records.append(rec)

    df = pd.DataFrame(records)

    rename_map = {f: _map_field_to_code(f, qid_to_title) for f in fieldnames}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    return df, questions_map, groups_map


def parse_lsa_timings(lsa_path):
    """Extract and parse the _timings.lsi file from a .lsa archive."""
    if not os.path.exists(lsa_path):
        return None

    try:
        with zipfile.ZipFile(lsa_path, "r") as zf:
            timings_files = [f for f in zf.namelist() if f.endswith("_timings.lsi")]
            if not timings_files:
                return None

            with zf.open(timings_files[0]) as f:
                xml_content = f.read()

        root = ET.fromstring(xml_content)
        rows = root.findall(".//row")
        if not rows:
            return None

        records = []
        for row in rows:
            rec = {}
            for child in row:
                # Tag is like _244841X43550time
                tag = child.tag
                val = child.text
                rec[tag] = val
            records.append(rec)

        try:
            return pd.DataFrame(records)
        except Exception as e:
            print(f"Error creating DataFrame in parse_lsa_timings: {e}")
            return None
    except Exception as e:
        print(f"Warning: Failed to parse timings from {lsa_path}: {e}")
        return None


def _extract_media_urls(html_content):
    """Extract media URLs from HTML content (audio, video, img sources)."""
    if not html_content:
        return []
    urls = []
    # Find src attributes in video, audio, img tags
    src_pattern = r'src=["\']([^"\']+)["\']'
    matches = re.findall(src_pattern, html_content)
    urls.extend(matches)
    return urls


def _clean_html_preserve_info(html_content):
    """Clean HTML but preserve useful information like media URLs."""
    if not html_content:
        return "", []

    media_urls = _extract_media_urls(html_content)

    # Remove HTML tags
    clean_text = re.sub("<[^<]+?>", "", html_content).strip()
    # Clean up whitespace
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    return clean_text, media_urls


def _parse_survey_metadata(root, get_text):
    """Extract survey-level metadata from surveys and surveys_languagesettings sections."""
    metadata = {
        "title": "",
        "admin": "",
        "admin_email": "",
        "language": "en",
        "anonymized": False,
        "format": "G",  # G=group, S=single, A=all
        "template": "",
        "datestamp": False,
        "welcome_message": "",
        "end_message": "",
        "description": "",
    }

    # Parse surveys section
    surveys_section = root.find("surveys")
    if surveys_section is not None:
        rows = surveys_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                metadata["admin"] = get_text(row, "admin")
                metadata["admin_email"] = get_text(row, "adminemail")
                metadata["language"] = get_text(row, "language") or "en"
                metadata["anonymized"] = get_text(row, "anonymized") == "Y"
                metadata["format"] = get_text(row, "format") or "G"
                metadata["template"] = get_text(row, "template")
                metadata["datestamp"] = get_text(row, "datestamp") == "Y"
                break  # Only first survey row

    # Parse surveys_languagesettings for title and messages
    lang_section = root.find("surveys_languagesettings")
    if lang_section is not None:
        rows = lang_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                title = get_text(row, "surveyls_title")
                welcome = get_text(row, "surveyls_welcometext")
                end = get_text(row, "surveyls_endtext")
                desc = get_text(row, "surveyls_description")

                if title:
                    metadata["title"] = re.sub("<[^<]+?>", "", title).strip()
                if welcome:
                    metadata["welcome_message"] = re.sub(
                        "<[^<]+?>", "", welcome
                    ).strip()
                if end:
                    metadata["end_message"] = re.sub("<[^<]+?>", "", end).strip()
                if desc:
                    metadata["description"] = re.sub("<[^<]+?>", "", desc).strip()
                break  # Take first language settings

    return metadata


def _parse_answers_into_questions(root, questions_map, get_text, *, track_scales=False):
    """Parse <answers> section and attach levels to questions_map entries.

    Args:
        root: XML root element containing <answers> section
        questions_map: Dict mapping qid -> question data (modified in place)
        get_text: Helper to extract text from XML elements
        track_scales: If True, also populate levels_by_scale for dual-scale
                      array questions (needed by parse_lss_xml_by_questions)
    """
    answers_section = root.find("answers")
    if answers_section is None:
        return

    rows = answers_section.find("rows")
    if rows is None:
        return

    for row in rows.findall("row"):
        qid = get_text(row, "qid")
        code = get_text(row, "code")
        answer = get_text(row, "answer")
        lang = get_text(row, "language")

        if qid not in questions_map:
            continue

        if track_scales:
            scale_id = get_text(row, "scale_id") or "0"

            # Handle "None" text from LimeSurvey (unlabeled scale points)
            if answer and answer.lower() == "none":
                answer = ""

            # Support multiple scales (for dual-scale arrays)
            if "levels" not in questions_map[qid]:
                questions_map[qid]["levels"] = {}
            if "levels_by_scale" not in questions_map[qid]:
                questions_map[qid]["levels_by_scale"] = {}
            if scale_id not in questions_map[qid]["levels_by_scale"]:
                questions_map[qid]["levels_by_scale"][scale_id] = {}

            # Store as multilingual dict if language is present
            if lang and lang.strip():
                if code not in questions_map[qid]["levels"]:
                    questions_map[qid]["levels"][code] = {}
                if isinstance(questions_map[qid]["levels"][code], dict):
                    questions_map[qid]["levels"][code][lang] = answer
                else:
                    questions_map[qid]["levels"][code] = {lang: answer}

                if code not in questions_map[qid]["levels_by_scale"][scale_id]:
                    questions_map[qid]["levels_by_scale"][scale_id][code] = {}
                if isinstance(
                    questions_map[qid]["levels_by_scale"][scale_id][code], dict
                ):
                    questions_map[qid]["levels_by_scale"][scale_id][code][lang] = answer
                else:
                    questions_map[qid]["levels_by_scale"][scale_id][code] = {
                        lang: answer
                    }
            else:
                questions_map[qid]["levels"][code] = answer
                questions_map[qid]["levels_by_scale"][scale_id][code] = answer
        else:
            # Simple mode: just map code -> answer text (possibly multilingual)
            if lang and lang.strip():
                if code not in questions_map[qid]["levels"]:
                    questions_map[qid]["levels"][code] = {}
                if isinstance(questions_map[qid]["levels"][code], dict):
                    questions_map[qid]["levels"][code][lang] = answer
                else:
                    questions_map[qid]["levels"][code] = {lang: answer}
            else:
                questions_map[qid]["levels"][code] = answer


def _detect_languages(root, get_text):
    """Detect all languages present in a LimeSurvey XML structure.

    Checks surveys_languagesettings, questions, and answers sections for
    language attributes.

    Returns:
        tuple: (languages_list, default_language)
    """
    languages = set()
    default_language = "en"

    # Check surveys_languagesettings
    lang_section = root.find("surveys_languagesettings")
    if lang_section is not None:
        rows = lang_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                lang = get_text(row, "surveyls_language")
                if lang and lang.strip():
                    languages.add(lang.strip())

    # Check surveys section for base language
    surveys_section = root.find("surveys")
    if surveys_section is not None:
        rows = surveys_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                lang = get_text(row, "language")
                if lang and lang.strip():
                    default_language = lang.strip()
                    languages.add(lang.strip())
                # Check additional_languages
                addl = get_text(row, "additional_languages")
                if addl and addl.strip():
                    for al in addl.strip().split():
                        if al.strip():
                            languages.add(al.strip())
                break

    # Check questions section for language diversity
    questions_section = root.find("questions")
    if questions_section is not None:
        rows = questions_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                lang = get_text(row, "language")
                if lang and lang.strip():
                    languages.add(lang.strip())

    # Check answers section
    answers_section = root.find("answers")
    if answers_section is not None:
        rows = answers_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                lang = get_text(row, "language")
                if lang and lang.strip():
                    languages.add(lang.strip())

    if not languages:
        languages.add(default_language)

    return sorted(languages), default_language


def _parse_lss_structure(root, get_text):
    """Parse LimeSurvey XML structure to extract questions, groups, subquestions, and attributes.

    Returns:
        questions_map: dict mapping qid -> {title, question, type, type_name, mandatory,
                                            question_order, parent_qid, gid, levels,
                                            subquestions, attributes, other, help, preg}
        groups_map: dict mapping gid -> {name, order, description}
    """
    # Map qid -> {title, question, type, ...}
    questions_map = {}
    # Map gid -> {name, order, description}
    groups_map = {}
    # Temporary map for subquestions: parent_qid -> list of subquestion dicts
    subquestions_map = {}
    # Temporary map for question attributes: qid -> {attribute_name: value}
    attributes_map = {}

    # 1. Parse Groups
    groups_section = root.find("groups")
    if groups_section is not None:
        rows = groups_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                gid = get_text(row, "gid")
                name = get_text(row, "group_name")
                group_order = get_text(row, "group_order")
                description = get_text(row, "description")
                randomization_group = get_text(row, "randomization_group")
                grelevance = get_text(row, "grelevance")  # Group relevance equation

                try:
                    order_int = int(group_order) if group_order else 0
                except ValueError:
                    order_int = 0

                # Clean HTML from description
                clean_desc = re.sub("<[^<]+?>", "", description or "").strip()

                groups_map[gid] = {
                    "name": name if name else "",
                    "order": order_int,
                    "description": clean_desc,
                    "randomization_group": (
                        randomization_group if randomization_group else None
                    ),
                    "relevance": (
                        grelevance if grelevance and grelevance != "1" else None
                    ),
                }

    # 2. Parse Subquestions first (so we can attach them to parent questions)
    subquestions_section = root.find("subquestions")
    if subquestions_section is not None:
        rows = subquestions_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                qid = get_text(row, "qid")
                parent_qid = get_text(row, "parent_qid")
                title = get_text(row, "title")  # Subquestion code (e.g., SQ001)
                question_text = get_text(row, "question")
                question_order = get_text(row, "question_order")
                scale_id = get_text(row, "scale_id")  # 0 or 1 for dual-scale arrays

                try:
                    sq_order = int(question_order) if question_order else 0
                except ValueError:
                    sq_order = 0

                try:
                    scale = int(scale_id) if scale_id else 0
                except ValueError:
                    scale = 0

                # Clean text but preserve media URLs
                clean_text, media_urls = _clean_html_preserve_info(question_text)

                subq = {
                    "qid": qid,
                    "code": title,
                    "text": clean_text,
                    "order": sq_order,
                    "scale_id": scale,
                    "media_urls": media_urls if media_urls else None,
                }

                if parent_qid not in subquestions_map:
                    subquestions_map[parent_qid] = []
                subquestions_map[parent_qid].append(subq)

    # Sort subquestions by order within each parent
    for parent_qid in subquestions_map:
        subquestions_map[parent_qid].sort(key=lambda x: (x["scale_id"], x["order"]))

    # 3. Parse Question Attributes
    attributes_section = root.find("question_attributes")
    if attributes_section is not None:
        rows = attributes_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                qid = get_text(row, "qid")
                attribute = get_text(row, "attribute")
                value = get_text(row, "value")
                language = get_text(row, "language")  # Empty for non-language-specific

                if qid not in attributes_map:
                    attributes_map[qid] = {}

                # Store attribute (use language suffix if language-specific)
                if language and language.strip():
                    attr_key = f"{attribute}_{language}"
                else:
                    attr_key = attribute

                # Parse numeric values
                if value and value.isdigit():
                    value = int(value)
                elif value and value.lower() in ("true", "false"):
                    value = value.lower() == "true"

                attributes_map[qid][attr_key] = value

    # 4. Parse Main Questions
    questions_section = root.find("questions")
    if questions_section is not None:
        rows = questions_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                qid = get_text(row, "qid")
                gid = get_text(row, "gid")
                title = get_text(row, "title")  # Variable name (e.g. 'ADS01')
                question_text = get_text(row, "question")
                q_type = get_text(row, "type")
                parent_qid = get_text(row, "parent_qid")
                mandatory = get_text(row, "mandatory")  # Y or N
                question_order = get_text(row, "question_order")
                other = get_text(row, "other")  # Y or N - has "Other" option
                help_text = get_text(row, "help")  # Help text shown to user
                preg = get_text(row, "preg")  # Validation regex
                relevance = get_text(row, "relevance")  # Relevance equation

                try:
                    q_order_int = int(question_order) if question_order else 0
                except ValueError:
                    q_order_int = 0

                # Clean up HTML tags from text fields
                clean_question = re.sub("<[^<]+?>", "", question_text or "").strip()
                clean_help = re.sub("<[^<]+?>", "", help_text or "").strip()

                questions_map[qid] = {
                    "title": title,
                    "question": clean_question,
                    "type": q_type,
                    "type_name": _get_question_type_name(q_type),
                    "mandatory": mandatory.upper() == "Y" if mandatory else False,
                    "question_order": q_order_int,
                    "parent_qid": parent_qid,
                    "gid": gid,
                    "levels": {},
                    "subquestions": subquestions_map.get(qid, []),
                    "attributes": attributes_map.get(qid, {}),
                    "other": other.upper() == "Y" if other else False,
                    "help": clean_help if clean_help else None,
                    "validation_regex": preg if preg else None,
                    "relevance": relevance if relevance and relevance != "1" else None,
                }

                # Update group name with a representative title if not set
                if gid in groups_map and not groups_map[gid]["name"]:
                    prefix = re.match(r"([a-zA-Z]+)", title)
                    if prefix:
                        groups_map[gid]["name"] = prefix.group(1)
                    else:
                        groups_map[gid]["name"] = title

    return questions_map, groups_map


def _build_standard_prism_questions(questions_map, groups_map, language="en"):
    """Convert LimeSurvey question data to standard PRISM template format.

    Standard PRISM format:
    - Questions are flat at top level (matrix subquestions become individual questions)
    - Each question has Description and optional Levels
    - Multilingual structure: {"en": "text", "de": "text"}
    - No LimeSurvey-specific fields (QuestionType, Position, Mandatory)

    Args:
        questions_map: Dict from _parse_lss_structure with question data
        groups_map: Dict from _parse_lss_structure with group data
        language: Language code for the template (default: "en")

    Returns:
        Dict of question_code -> {Description: {...}, Levels: {...}}
    """
    prism_questions = {}

    # Sort questions by group order, then question order
    sorted_questions = sorted(
        questions_map.items(),
        key=lambda x: (
            groups_map.get(x[1]["gid"], {}).get("order", 0),
            x[1]["question_order"],
        ),
    )

    for qid, q_data in sorted_questions:
        q_type = q_data.get("type", "")
        title = q_data.get("title", "")
        question_text = q_data.get("question", "")
        levels = q_data.get("levels", {})
        subquestions = q_data.get("subquestions", [])

        # Array/Matrix types (F, A, B, C, E, H, 1, ;, :) have subquestions
        # These should be flattened - each subquestion becomes a top-level question
        array_types = {"F", "A", "B", "C", "E", "H", "1", ";", ":"}

        if q_type in array_types and subquestions:
            # Matrix question: flatten subquestions to individual questions
            # Convert levels to multilingual format once (shared by all subquestions)
            # Use implicit levels for array types that don't have explicit answers
            effective_levels = levels if levels else IMPLICIT_LEVELS.get(q_type, {})
            multilingual_levels = {}
            for code, answer_text in effective_levels.items():
                if isinstance(answer_text, dict):
                    multilingual_levels[code] = answer_text
                else:
                    multilingual_levels[code] = {
                        language: str(answer_text) if answer_text else ""
                    }

            for sq in subquestions:
                sq_code = sq.get("code", "")
                sq_text = sq.get("text", "")

                # Create individual question entry
                # Use subquestion code as the question key
                q_key = sq_code

                # Build description: combine parent question text with subquestion text if different
                if question_text and sq_text and question_text != sq_text:
                    # If parent has a prompt, include it
                    full_desc = sq_text  # Usually subquestion text is the actual item
                else:
                    full_desc = sq_text or question_text

                entry = {
                    "Description": (
                        {language: full_desc} if full_desc else {language: ""}
                    )
                }

                # Add Levels if present
                if multilingual_levels:
                    entry["Levels"] = multilingual_levels

                prism_questions[q_key] = entry

        else:
            # Non-matrix question: add as single entry
            q_key = title

            # Convert description to multilingual format
            entry = {
                "Description": (
                    {language: question_text} if question_text else {language: ""}
                )
            }

            # Convert levels to multilingual format if present
            # Use implicit levels for question types that don't have explicit answers
            effective_levels = levels if levels else IMPLICIT_LEVELS.get(q_type, {})
            if effective_levels:
                multilingual_levels = {}
                for code, answer_text in effective_levels.items():
                    if isinstance(answer_text, dict):
                        multilingual_levels[code] = answer_text
                    else:
                        multilingual_levels[code] = {
                            language: str(answer_text) if answer_text else ""
                        }
                entry["Levels"] = multilingual_levels

            prism_questions[q_key] = entry

    return prism_questions


def _build_prism_template_from_parsed(
    questions_map, groups_map, languages, default_language="en", source_type="lsq"
):
    """Convert parsed LimeSurvey data into a PRISM template with per-item LimeSurvey dicts.

    Produces a template suitable for the Template Editor, with full LimeSurvey
    tool-specific properties on each item for round-trip export.

    Args:
        questions_map: Dict from _parse_lss_structure with question data
        groups_map: Dict from _parse_lss_structure with group data
        languages: List of language codes found in the source
        default_language: Primary language code
        source_type: "lsq" or "lsg" (affects metadata)

    Returns:
        Dict: Complete PRISM template with metadata sections and per-item entries
    """
    prism_questions = {}

    # Sort questions by group order, then question order
    sorted_questions = sorted(
        questions_map.items(),
        key=lambda x: (
            groups_map.get(x[1]["gid"], {}).get("order", 0),
            x[1]["question_order"],
        ),
    )

    array_types = {"F", "A", "B", "C", "E", "H", "1", ";", ":"}

    for qid, q_data in sorted_questions:
        q_type = q_data.get("type", "")
        title = q_data.get("title", "")
        question_text = q_data.get("question", "")
        levels = q_data.get("levels", {})
        subquestions = q_data.get("subquestions", [])
        attributes = q_data.get("attributes", {})

        # Build LimeSurvey tool-specific properties
        ls_props = {
            "questionType": q_type,
            "questionTypeName": _get_question_type_name(q_type),
            "mandatory": q_data.get("mandatory", False),
            "inputWidth": attributes.get("text_input_width", None),
            "hidden": bool(attributes.get("hidden", False)),
            "other": q_data.get("other", False),
            "helpText": {},
            "relevance": q_data.get("relevance") or "1",
            "displayRows": attributes.get("display_rows", None),
            "equation": None,
            "validation": {
                "min": attributes.get("min_num_value_n", None),
                "max": attributes.get("max_num_value_n", None),
                "integerOnly": bool(attributes.get("num_value_int_only", False)),
            },
        }

        # Handle help text - could be per-language in attributes
        help_text = q_data.get("help") or ""
        if help_text:
            ls_props["helpText"] = {default_language: help_text}
        # Check for language-specific help in attributes
        for attr_key, attr_val in attributes.items():
            if attr_key.startswith("help_"):
                lang = attr_key[5:]
                if lang and isinstance(attr_val, str):
                    ls_props["helpText"][lang] = attr_val

        # Equation type
        if q_type == "*":
            ls_props["equation"] = question_text

        # Ensure inputWidth is numeric or None
        if ls_props["inputWidth"] is not None:
            try:
                ls_props["inputWidth"] = int(ls_props["inputWidth"])
            except (ValueError, TypeError):
                ls_props["inputWidth"] = None

        # Ensure validation numbers are numeric or None
        for vk in ("min", "max"):
            if ls_props["validation"][vk] is not None:
                try:
                    ls_props["validation"][vk] = float(ls_props["validation"][vk])
                    if ls_props["validation"][vk] == int(ls_props["validation"][vk]):
                        ls_props["validation"][vk] = int(ls_props["validation"][vk])
                except (ValueError, TypeError):
                    ls_props["validation"][vk] = None

        if q_type in array_types and subquestions:
            # Matrix question: flatten subquestions to individual items
            # Use implicit levels for array types that don't have explicit answers
            effective_levels = levels if levels else IMPLICIT_LEVELS.get(q_type, {})
            multilingual_levels = {}
            for code, answer_text in effective_levels.items():
                if isinstance(answer_text, dict):
                    multilingual_levels[code] = answer_text
                else:
                    multilingual_levels[code] = {
                        default_language: str(answer_text) if answer_text else ""
                    }

            for sq in subquestions:
                sq_code = sq.get("code", "")
                sq_text = sq.get("text", "")

                full_desc = sq_text if sq_text else question_text
                entry = {
                    "Description": (
                        {default_language: full_desc}
                        if full_desc
                        else {default_language: ""}
                    ),
                    "LimeSurvey": dict(ls_props),  # Copy for each subquestion
                }
                if multilingual_levels:
                    entry["Levels"] = multilingual_levels

                prism_questions[sq_code] = entry
        else:
            # Non-matrix question: single entry
            entry = {
                "Description": (
                    {default_language: question_text}
                    if question_text
                    else {default_language: ""}
                ),
                "LimeSurvey": ls_props,
            }

            # Use implicit levels for question types that don't have explicit answers
            effective_levels = levels if levels else IMPLICIT_LEVELS.get(q_type, {})
            if effective_levels:
                multilingual_levels = {}
                for code, answer_text in effective_levels.items():
                    if isinstance(answer_text, dict):
                        multilingual_levels[code] = answer_text
                    else:
                        multilingual_levels[code] = {
                            default_language: str(answer_text) if answer_text else ""
                        }
                entry["Levels"] = multilingual_levels

            prism_questions[title] = entry

    # Infer DataType from question type for each item
    numeric_types = {"N", "K", "A", "B"}
    text_types = {"S", "T", "U", "Q"}
    for key, entry in prism_questions.items():
        ls = entry.get("LimeSurvey", {})
        qt = ls.get("questionType", "")
        if qt in numeric_types:
            entry["DataType"] = "integer"
        elif qt in text_types:
            entry["DataType"] = "string"

    # Determine task name from groups or questions
    task_name = ""
    if groups_map:
        first_group = min(groups_map.values(), key=lambda g: g.get("order", 0))
        task_name = first_group.get("name", "")
    if not task_name and sorted_questions:
        first_q = sorted_questions[0][1]
        title = first_q.get("title", "")
        prefix = re.match(r"([a-zA-Z]+)", title)
        task_name = prefix.group(1) if prefix else title

    normalized_task = sanitize_task_name(task_name) if task_name else "imported"

    # Build template with metadata
    template = {
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "tsv",
            "SoftwarePlatform": "LimeSurvey",
            "Language": default_language,
            "Respondent": "self",
            "ResponseType": ["online"],
        },
        "Study": {
            "TaskName": normalized_task,
            "OriginalName": task_name,
            "Version": "1.0",
            "Description": f"Imported from LimeSurvey .{source_type}: {task_name}",
            "ItemCount": len(prism_questions),
            "LicenseID": "Proprietary",
            "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
        },
        "Metadata": {
            "SchemaVersion": "1.1.1",
            "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "Creator": "limesurvey_to_prism.py",
        },
    }

    # Add I18n section if multiple languages detected
    if len(languages) > 1:
        template["I18n"] = {
            "Languages": languages,
            "DefaultLanguage": default_language,
        }

    template.update(prism_questions)
    return template


def parse_lsq_xml(xml_content):
    """Parse a .lsq (LimeSurvey single question export) into a PRISM template dict.

    .lsq files contain: <questions>, <subquestions>, <answers>, <question_attributes>
    but no <groups> or <surveys> sections.

    Args:
        xml_content: XML content as bytes or string

    Returns:
        dict: PRISM template with per-item LimeSurvey properties, or None on error
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing .lsq XML: {e}")
        return None

    def get_text(element, tag):
        child = element.find(tag)
        val = child.text if child is not None else ""
        return val or ""

    questions_map, groups_map = _parse_lss_structure(root, get_text)
    _parse_answers_into_questions(root, questions_map, get_text)

    languages, default_language = _detect_languages(root, get_text)

    return _build_prism_template_from_parsed(
        questions_map, groups_map, languages, default_language, source_type="lsq"
    )


def parse_lsg_xml(xml_content):
    """Parse a .lsg (LimeSurvey question group export) into a PRISM template dict.

    .lsg files contain: <groups>, <questions>, <subquestions>, <answers>,
    <question_attributes> but no <surveys> section.

    Args:
        xml_content: XML content as bytes or string

    Returns:
        dict: PRISM template with per-item LimeSurvey properties, or None on error
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing .lsg XML: {e}")
        return None

    def get_text(element, tag):
        child = element.find(tag)
        val = child.text if child is not None else ""
        return val or ""

    questions_map, groups_map = _parse_lss_structure(root, get_text)
    _parse_answers_into_questions(root, questions_map, get_text)

    languages, default_language = _detect_languages(root, get_text)

    return _build_prism_template_from_parsed(
        questions_map, groups_map, languages, default_language, source_type="lsg"
    )


def parse_lss_xml(xml_content, task_name=None, use_standard_format=True):
    """Parse a LimeSurvey .lss XML blob into a Prism sidecar dict.

    Args:
        xml_content: XML content as bytes or string
        task_name: Optional task name override
        use_standard_format: If True, produce standard PRISM format compatible with
                           Survey Customizer. If False, use legacy format with
                           LimeSurvey-specific fields.
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

    # Helper to find text of a child element
    def get_text(element, tag):
        child = element.find(tag)
        val = child.text if child is not None else ""
        return val or ""

    # Get survey-level metadata
    survey_meta = _parse_survey_metadata(root, get_text)

    questions_map, groups_map = _parse_lss_structure(root, get_text)

    # 2. Parse Answers
    _parse_answers_into_questions(root, questions_map, get_text)

    # 3. Construct Prism JSON
    language = survey_meta.get("language", "en")

    if use_standard_format:
        # Use standard PRISM format (compatible with Survey Customizer)
        prism_json = _build_standard_prism_questions(
            questions_map, groups_map, language
        )
    else:
        # Legacy format with LimeSurvey-specific fields
        prism_json = {}

        # Sort questions by group order, then question order for proper sequencing
        sorted_questions = sorted(
            questions_map.items(),
            key=lambda x: (
                groups_map.get(x[1]["gid"], {}).get("order", 0),
                x[1]["question_order"],
            ),
        )

        for qid, q_data in sorted_questions:
            key = q_data["title"]
            gid = q_data["gid"]
            q_type = q_data.get("type", "")

            # Get group info
            group_info = groups_map.get(
                gid, {"name": "", "order": 0, "description": ""}
            )

            entry = {
                "Description": q_data["question"],
                "QuestionType": q_data["type_name"],
                "Mandatory": q_data["mandatory"],
                "Position": {
                    "Group": group_info["name"],
                    "GroupOrder": group_info["order"],
                    "QuestionOrder": q_data["question_order"],
                },
            }

            # Add answer levels if present, or use implicit levels
            effective_levels = (
                q_data["levels"]
                if q_data["levels"]
                else IMPLICIT_LEVELS.get(q_type, {})
            )
            if effective_levels:
                entry["Levels"] = effective_levels

            # Add subquestions/items for array-type questions
            if q_data["subquestions"]:
                items = {}
                for sq in q_data["subquestions"]:
                    item_entry = {
                        "Description": sq["text"],
                        "Order": sq["order"],
                    }
                    # Only include ScaleId if not 0 (dual-scale arrays)
                    if sq["scale_id"] != 0:
                        item_entry["ScaleId"] = sq["scale_id"]
                    # Include media URLs if present
                    if sq.get("media_urls"):
                        item_entry["MediaUrls"] = sq["media_urls"]
                    items[sq["code"]] = item_entry
                entry["Items"] = items

            # Add "Other" option flag
            if q_data["other"]:
                entry["HasOtherOption"] = True

            # Add help text if present
            if q_data["help"]:
                entry["HelpText"] = q_data["help"]

            # Add validation regex if present
            if q_data["validation_regex"]:
                entry["ValidationRegex"] = q_data["validation_regex"]

            # Add relevance/condition if present (conditional display)
            if q_data["relevance"]:
                entry["Condition"] = q_data["relevance"]

            # Add question attributes (design options, etc.)
            if q_data["attributes"]:
                # Filter out empty values and organize attributes
                attrs = {
                    k: v
                    for k, v in q_data["attributes"].items()
                    if v not in (None, "", 0)
                }
                if attrs:
                    entry["Attributes"] = attrs

            prism_json[key] = entry

    # Use survey title if available, otherwise use task_name
    survey_title = survey_meta.get("title") or task_name or "survey"
    normalized_task = sanitize_task_name(survey_title)

    # Build description from survey metadata
    description = (
        survey_meta.get("description") or f"Imported from LimeSurvey: {survey_title}"
    )

    metadata = {
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "tsv",
            "SoftwarePlatform": "LimeSurvey",
            "Language": survey_meta.get("language", "en"),
            "Respondent": "self",
            "ResponseType": ["online"],
        },
        "Study": {
            "TaskName": normalized_task,
            "OriginalName": survey_title,
            "Version": "1.0",
            "Description": description,
            "ItemCount": len(prism_json),
            "LicenseID": "Proprietary",
            "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
        },
        "Metadata": {
            "SchemaVersion": "1.1.1",
            "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "Creator": "limesurvey_to_prism.py",
        },
    }

    # Add survey-level settings if present
    if survey_meta.get("admin"):
        metadata["Study"]["Author"] = survey_meta["admin"]
    if survey_meta.get("admin_email"):
        metadata["Study"]["ContactEmail"] = survey_meta["admin_email"]
    if survey_meta.get("anonymized"):
        metadata["Technical"]["Anonymized"] = survey_meta["anonymized"]
    if survey_meta.get("template"):
        metadata["Technical"]["Template"] = survey_meta["template"]

    metadata.update(prism_json)
    return metadata


def parse_lss_xml_by_groups(xml_content, use_standard_format=True):
    """Parse a LimeSurvey .lss XML blob and split into separate questionnaires by group.

    Args:
        xml_content: XML content as bytes or string
        use_standard_format: If True, produce standard PRISM format (flat questions,
                           multilingual structure). If False, use legacy format.

    Returns:
        dict: {group_name: prism_json_dict, ...} or None on error
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

    def get_text(element, tag):
        child = element.find(tag)
        val = child.text if child is not None else ""
        return val or ""

    # Get survey-level metadata
    survey_meta = _parse_survey_metadata(root, get_text)
    language = survey_meta.get("language", "en")

    questions_map, groups_map = _parse_lss_structure(root, get_text)

    # Parse Answers
    _parse_answers_into_questions(root, questions_map, get_text)

    # Group questions by their group ID, preserving full question data
    grouped_questions = {}  # gid -> list of (qid, q_data)
    for qid, q_data in questions_map.items():
        gid = q_data.get("gid", "")
        if gid not in grouped_questions:
            grouped_questions[gid] = []
        grouped_questions[gid].append((qid, q_data))

    # Sort groups by group order, then sort questions within each group
    sorted_groups = sorted(
        grouped_questions.items(),
        key=lambda x: groups_map.get(x[0], {}).get("order", 0),
    )

    # Build separate PRISM JSONs for each group
    result = {}
    for gid, questions_list in sorted_groups:
        if not questions_list:
            continue

        # Get group info
        group_info = groups_map.get(
            gid, {"name": f"group_{gid}", "order": 0, "description": ""}
        )
        group_name = group_info["name"] if group_info["name"] else f"group_{gid}"
        group_order = group_info["order"]
        group_description = group_info.get("description", "")

        # Sort questions by question_order within the group
        sorted_questions_list = sorted(
            questions_list, key=lambda x: x[1]["question_order"]
        )

        # Build question entries based on format
        questions_dict = {}

        if use_standard_format:
            # Standard PRISM format: flatten matrix questions, use multilingual structure
            for qid, q_data in sorted_questions_list:
                q_type = q_data.get("type", "")
                title = q_data.get("title", "")
                question_text = q_data.get("question", "")
                levels = q_data.get("levels", {})
                subquestions = q_data.get("subquestions", [])

                # Array/Matrix types should be flattened
                array_types = {"F", "A", "B", "C", "E", "H", "1", ";", ":"}

                if q_type in array_types and subquestions:
                    # Convert levels to multilingual format
                    # Use implicit levels for array types without explicit answers
                    effective_levels = (
                        levels if levels else IMPLICIT_LEVELS.get(q_type, {})
                    )
                    multilingual_levels = {}
                    for code, answer_text in effective_levels.items():
                        if isinstance(answer_text, dict):
                            multilingual_levels[code] = answer_text
                        else:
                            multilingual_levels[code] = {
                                language: str(answer_text) if answer_text else ""
                            }

                    for sq in subquestions:
                        sq_code = sq.get("code", "")
                        sq_text = sq.get("text", "")

                        entry = {
                            "Description": (
                                {language: sq_text} if sq_text else {language: ""}
                            )
                        }
                        if multilingual_levels:
                            entry["Levels"] = multilingual_levels

                        questions_dict[sq_code] = entry
                else:
                    # Non-matrix question
                    entry = {
                        "Description": (
                            {language: question_text}
                            if question_text
                            else {language: ""}
                        )
                    }
                    # Use implicit levels for question types without explicit answers
                    effective_levels = (
                        levels if levels else IMPLICIT_LEVELS.get(q_type, {})
                    )
                    if effective_levels:
                        multilingual_levels = {}
                        for code, answer_text in effective_levels.items():
                            if isinstance(answer_text, dict):
                                multilingual_levels[code] = answer_text
                            else:
                                multilingual_levels[code] = {
                                    language: str(answer_text) if answer_text else ""
                                }
                        entry["Levels"] = multilingual_levels

                    questions_dict[title] = entry
        else:
            # Legacy format with LimeSurvey-specific fields
            for qid, q_data in sorted_questions_list:
                key = q_data["title"]
                q_type = q_data.get("type", "")
                entry = {
                    "Description": q_data["question"],
                    "QuestionType": q_data["type_name"],
                    "Mandatory": q_data["mandatory"],
                    "Position": {
                        "Group": group_name,
                        "GroupOrder": group_order,
                        "QuestionOrder": q_data["question_order"],
                    },
                }

                # Add answer levels if present, or use implicit levels
                effective_levels = (
                    q_data["levels"]
                    if q_data["levels"]
                    else IMPLICIT_LEVELS.get(q_type, {})
                )
                if effective_levels:
                    entry["Levels"] = effective_levels

                # Add subquestions/items for array-type questions
                if q_data["subquestions"]:
                    items = {}
                    for sq in q_data["subquestions"]:
                        item_entry = {
                            "Description": sq["text"],
                            "Order": sq["order"],
                        }
                        if sq["scale_id"] != 0:
                            item_entry["ScaleId"] = sq["scale_id"]
                        if sq.get("media_urls"):
                            item_entry["MediaUrls"] = sq["media_urls"]
                        items[sq["code"]] = item_entry
                    entry["Items"] = items

                # Add "Other" option flag
                if q_data["other"]:
                    entry["HasOtherOption"] = True

                # Add help text if present
                if q_data["help"]:
                    entry["HelpText"] = q_data["help"]

                # Add validation regex if present
                if q_data["validation_regex"]:
                    entry["ValidationRegex"] = q_data["validation_regex"]

                # Add relevance/condition if present
                if q_data["relevance"]:
                    entry["Condition"] = q_data["relevance"]

                # Add question attributes (design options, etc.)
                if q_data["attributes"]:
                    attrs = {
                        k: v
                        for k, v in q_data["attributes"].items()
                        if v not in (None, "", 0)
                    }
                    if attrs:
                        entry["Attributes"] = attrs

                questions_dict[key] = entry

            questions_dict[key] = entry

        normalized_name = sanitize_task_name(group_name)

        # Use group description if available, otherwise generate one
        study_description = (
            group_description
            if group_description
            else f"Imported from LimeSurvey group: {group_name}"
        )

        prism_json = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "SoftwarePlatform": "LimeSurvey",
                "Language": survey_meta.get("language", "en"),
                "Respondent": "self",
                "ResponseType": ["online"],
            },
            "Study": {
                "TaskName": normalized_name,
                "OriginalName": group_name,
                "SurveyTitle": survey_meta.get("title", ""),
                "Version": "1.0",
                "Description": study_description,
                "GroupOrder": group_order,
                "ItemCount": len(questions_dict),
                "LicenseID": "Proprietary",
                "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
                "Creator": "limesurvey_to_prism.py",
            },
        }

        # Add survey-level settings if present
        if survey_meta.get("admin"):
            prism_json["Study"]["Author"] = survey_meta["admin"]
        if survey_meta.get("admin_email"):
            prism_json["Study"]["ContactEmail"] = survey_meta["admin_email"]
        if survey_meta.get("anonymized"):
            prism_json["Technical"]["Anonymized"] = survey_meta["anonymized"]

        prism_json.update(questions_dict)

        # Extract PRISMMETA if present in this group
        for _qid, q_data in sorted_questions_list:
            title = q_data.get("title", "")
            if title.upper().startswith("PRISMMETA") and q_data.get("type") == "*":
                equation_html = q_data.get("attributes", {}).get("equation", "")
                if not equation_html:
                    equation_html = q_data.get("question", "")
                parsed = parse_prismmeta_html(equation_html)
                if parsed:
                    prism_json["_prismmeta"] = parsed
                    break

        result[normalized_name] = prism_json

    return result


def parse_lss_xml_by_questions(xml_content):
    """Parse a LimeSurvey .lss XML blob and return each question as a separate JSON template.

    Each question (including arrays with subquestions) becomes its own JSON file,
    suitable for use as a reusable template in the Survey & Boilerplate editor.

    Returns:
        dict: {question_code: {prism_json, group_name, group_order, ...}, ...} or None on error
    """
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing XML: {e}")
        return None

    def get_text(element, tag):
        child = element.find(tag)
        val = child.text if child is not None else ""
        return val or ""

    # Get survey-level metadata
    survey_meta = _parse_survey_metadata(root, get_text)

    questions_map, groups_map = _parse_lss_structure(root, get_text)

    # Parse Answers (with scale tracking for dual-scale arrays)
    _parse_answers_into_questions(root, questions_map, get_text, track_scales=True)

    # Build individual question JSONs
    result = {}

    for qid, q_data in questions_map.items():
        # Skip subquestions (they're included in their parent)
        if q_data.get("parent_qid") and q_data["parent_qid"] != "0":
            continue

        question_code = q_data["title"]
        gid = q_data["gid"]

        # Get group info
        group_info = groups_map.get(gid, {"name": "", "order": 0, "description": ""})
        group_name = group_info["name"] if group_info["name"] else f"group_{gid}"
        group_order = group_info["order"]

        # Build the question entry
        entry = {
            "Description": q_data["question"],
            "QuestionType": q_data["type_name"],
            "LimeSurveyType": q_data["type"],  # Original LS type code for re-export
            "Mandatory": q_data["mandatory"],
            "Position": {
                "Group": group_name,
                "GroupOrder": group_order,
                "QuestionOrder": q_data["question_order"],
            },
        }

        # Add answer levels if present, or use implicit levels for question types without explicit answers
        q_type = q_data.get("type", "")
        if q_data.get("levels"):
            # Filter out empty labels but keep the scale structure
            levels = {k: v for k, v in q_data["levels"].items()}
            if levels:
                entry["Levels"] = levels
        elif q_type in IMPLICIT_LEVELS:
            entry["Levels"] = IMPLICIT_LEVELS[q_type]

        # Add subquestions/items for array-type questions
        if q_data.get("subquestions"):
            items = {}
            for sq in q_data["subquestions"]:
                item_entry = {
                    "Description": sq["text"],
                    "Order": sq["order"],
                }
                if sq["scale_id"] != 0:
                    item_entry["ScaleId"] = sq["scale_id"]
                if sq.get("media_urls"):
                    item_entry["MediaUrls"] = sq["media_urls"]
                items[sq["code"]] = item_entry
            entry["Items"] = items

        # Add optional fields
        if q_data.get("other"):
            entry["HasOtherOption"] = True

        if q_data.get("help"):
            entry["HelpText"] = q_data["help"]

        if q_data.get("validation_regex"):
            entry["ValidationRegex"] = q_data["validation_regex"]

        if q_data.get("relevance"):
            entry["Condition"] = q_data["relevance"]

        if q_data.get("attributes"):
            attrs = {
                k: v for k, v in q_data["attributes"].items() if v not in (None, "", 0)
            }
            if attrs:
                entry["Attributes"] = attrs

        # Build complete question JSON template
        question_json = {
            "Technical": {
                "StimulusType": "Questionnaire",
                "FileFormat": "tsv",
                "SoftwarePlatform": "LimeSurvey",
                "Language": survey_meta.get("language", "en"),
                "Respondent": "self",
                "ResponseType": ["online"],
            },
            "Study": {
                "TaskName": sanitize_task_name(question_code),
                "OriginalName": question_code,
                "QuestionCode": question_code,
                "GroupName": group_name,
                "GroupOrder": group_order,
                "Version": "1.0",
                "Description": q_data["question"][:200] if q_data["question"] else "",
                "LicenseID": "Proprietary",
                "License": "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument.",
            },
            "Metadata": {
                "SchemaVersion": "1.1.1",
                "CreationDate": datetime.utcnow().strftime("%Y-%m-%d"),
                "Creator": "limesurvey_to_prism.py",
                "SourceSurvey": survey_meta.get("title", ""),
            },
            question_code: entry,
        }

        # Add survey-level author info
        if survey_meta.get("admin"):
            question_json["Study"]["Author"] = survey_meta["admin"]
        if survey_meta.get("admin_email"):
            question_json["Study"]["ContactEmail"] = survey_meta["admin_email"]

        # Calculate item count
        item_count = len(entry.get("Items", {})) if entry.get("Items") else 1
        question_json["Study"]["ItemCount"] = item_count

        # Store result with metadata for UI
        result[question_code] = {
            "prism_json": question_json,
            "question_code": question_code,
            "question_type": q_data["type_name"],
            "limesurvey_type": q_data["type"],
            "group_name": group_name,
            "group_order": group_order,
            "question_order": q_data["question_order"],
            "item_count": item_count,
            "mandatory": q_data["mandatory"],
            "suggested_filename": f"survey-{sanitize_task_name(question_code)}.json",
        }

    return result


def convert_lsa_to_prism(lsa_path, output_path=None, task_name=None):
    """Extract .lss from .lsa/.lss and convert to a Prism JSON sidecar."""
    if not os.path.exists(lsa_path):
        print(f"File not found: {lsa_path}")
        return

    xml_content = None

    if lsa_path.endswith(".lsa"):
        try:
            with zipfile.ZipFile(lsa_path, "r") as zip_ref:
                lss_files = [f for f in zip_ref.namelist() if f.endswith(".lss")]
                if not lss_files:
                    print("No .lss file found in the archive.")
                    return

                target_file = lss_files[0]
                print(f"Processing {target_file} from archive...")
                with zip_ref.open(target_file) as f:
                    xml_content = f.read()
        except zipfile.BadZipFile:
            print("Invalid zip file.")
            return
    elif lsa_path.endswith(".lss"):
        with open(lsa_path, "rb") as f:
            xml_content = f.read()
    else:
        print("Unsupported file extension. Please provide .lsa or .lss")
        return

    if xml_content:
        prism_data = parse_lss_xml(xml_content, task_name)

        if prism_data:
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(prism_data, f, indent=4, ensure_ascii=False)
                print(f"Successfully wrote Prism JSON to {output_path}")
            else:
                print(json.dumps(prism_data, indent=4, ensure_ascii=False))


def convert_lsa_to_dataset(
    lsa_path,
    output_root,
    session_label,
    library_path,
    task_name=None,
    id_priority=None,
    id_column=None,
    id_map=None,
):
    """Convert .lsa responses into a PRISM/BIDS dataset (tsv + json) using survey_library schemas."""
    from .id_detection import (
        detect_id_column,
        has_prismmeta_columns,
        IdColumnNotDetectedError,
    )

    df, questions_map, groups_map = parse_lsa_responses(lsa_path)

    has_pm = has_prismmeta_columns(list(df.columns))
    id_col = detect_id_column(
        list(df.columns),
        "lsa",
        explicit_id_column=id_column,
        has_prismmeta=has_pm,
    )
    if not id_col:
        raise IdColumnNotDetectedError(list(df.columns), "lsa")
    df = df.rename(columns={id_col: "participant_id"})

    # Apply ID mapping if provided
    if id_map:
        # Normalize IDs as strings
        df["participant_id"] = df["participant_id"].astype(str).str.strip()

        # Prepare mapping keys (also normalized)
        map_keys = set(str(k).strip() for k in id_map.keys())

        # Find any LimeSurvey IDs present in the data that are not covered by the mapping
        ids_in_data = set(df["participant_id"].unique())
        missing = sorted([i for i in ids_in_data if i not in map_keys])
        if missing:
            # Abort rather than silently keeping unmapped IDs
            sample = ", ".join(missing[:50])
            more = "..." if len(missing) > 50 else ""
            raise ValueError(
                f"ID mapping incomplete: {len(missing)} LimeSurvey IDs are missing mapping entries: {sample}{more}.\n"
                "Please update your ID mapping file so every LimeSurvey ID has a corresponding participant_id."
            )

        # All IDs covered: apply mapping
        df["participant_id"] = df["participant_id"].apply(lambda x: id_map.get(x, x))

    df["participant_id"] = df["participant_id"].apply(
        lambda x: f"sub-{x}" if pd.notna(x) and not str(x).startswith("sub-") else x
    )
    df["session"] = session_label

    # --- Calculate Survey Duration and Start Time ---
    # LimeSurvey typically provides 'startdate' and 'submitdate'
    if "startdate" in df.columns and "submitdate" in df.columns:
        try:
            start = pd.to_datetime(df["startdate"], errors="coerce")
            submit = pd.to_datetime(df["submitdate"], errors="coerce")

            # Duration in minutes
            df["SurveyDuration"] = (submit - start).dt.total_seconds() / 60.0
            # Round to 2 decimals
            df["SurveyDuration"] = df["SurveyDuration"].round(2)

            # Start Time (HH:MM:SS)
            df["SurveyStartTime"] = start.dt.strftime("%H:%M:%S")
        except Exception as e:
            print(f"Warning: Could not calculate duration/time: {e}")

    # --- Merge Group Timings ---
    try:
        timings_df = parse_lsa_timings(lsa_path)

        group_duration_fields = {}
        if timings_df is not None and not timings_df.empty:
            # Rename columns using groups_map
            # Pattern: _[SurveyID]X[GroupID]time
            new_cols = {}
            for col in timings_df.columns:
                # Remove leading underscore if present (xml tags often have it)
                clean_col = col.lstrip("_")
                # Regex to find GroupID before 'time'
                # The format is SurveyID X GroupID time. e.g. 244841X43550time
                m = re.match(r"\d+X(\d+)time", clean_col)
                if m:
                    gid = m.group(1)
                    if gid in groups_map:
                        title = groups_map[gid]["name"]
                        # Sanitize title for column name
                        safe_title = "".join(c if c.isalnum() else "_" for c in title)
                        col_name = f"Duration_{safe_title}"
                        new_cols[col] = col_name
                        group_duration_fields[col_name] = {
                            "Description": f"Duration for question group '{title}'",
                            "Unit": "seconds",
                        }

            if new_cols:
                timings_df = timings_df.rename(columns=new_cols)
                # Keep only the renamed columns
                # Use set to avoid duplicates if multiple groups map to same title (should be rare now)
                # Filter columns that exist in timings_df (after rename)
                timings_df = timings_df.loc[:, ~timings_df.columns.duplicated()]

                # Convert to numeric (seconds)
                for c in timings_df.columns:
                    if c.startswith("Duration_"):
                        timings_df[c] = pd.to_numeric(timings_df[c], errors="coerce")

                # Merge by index (assuming row alignment)
                if len(df) == len(timings_df):
                    df = pd.concat([df, timings_df], axis=1)
                else:
                    print(
                        f"Warning: Timings row count ({len(timings_df)}) does not match responses ({len(df)}). Skipping timings."
                    )
    except Exception as e:
        print(f"Error processing timings: {e}")
        # Continue without timings
        pass

    schemas = load_schemas(library_path)
    if not schemas:
        print(f"No schemas found in {library_path}, cannot build dataset.")
        return

    # Create a dedicated 'limesurvey' task for session-level metadata
    # instead of injecting it into every questionnaire.
    schemas["limesurvey"] = {
        "Technical": {"Description": "General metadata for the LimeSurvey session"},
        "SurveyDuration": {
            "Description": "Total duration of the LimeSurvey session in minutes (submitdate - startdate)",
            "Unit": "minutes",
        },
        "SurveyStartTime": {
            "Description": "Start time of the LimeSurvey session (HH:MM:SS)",
            "Unit": "hh:mm:ss",
        },
        **group_duration_fields,
    }

    # We iterate manually to inject task-specific durations if available
    for t_name, t_schema in schemas.items():
        # Skip the internal 'limesurvey' metadata container; it's not a task to be exported.
        if t_name == "limesurvey":
            continue

        # Work on a copy to avoid side effects between tasks
        task_df = df.copy()

        # 1. Check for granular duration
        # Strategy: Find which group the task's variables belong to.
        # Get variables in this task
        task_vars = [
            k
            for k in t_schema.keys()
            if k
            not in ["Technical", "Study", "Metadata", "I18n", "Scoring", "Normative"]
        ]

        # Find which group these variables belong to
        gids = []
        # Optimization: Create a map of title -> gid
        title_to_gid = {v["title"]: v["gid"] for v in questions_map.values()}

        for var in task_vars:
            if var in title_to_gid:
                gids.append(title_to_gid[var])
            else:
                # Fallback: check for prefix match (e.g. ADS01 -> ADS)
                # We look for the longest matching prefix in title_to_gid
                best_match = None
                for title in title_to_gid:
                    if var.startswith(title):
                        if best_match is None or len(title) > len(best_match):
                            best_match = title

                if best_match:
                    gids.append(title_to_gid[best_match])

        granular_col = None
        if gids:
            # Find mode
            from collections import Counter

            most_common_gid = Counter(gids).most_common(1)[0][0]
            if most_common_gid in groups_map:
                group_title = groups_map[most_common_gid]["name"]
                safe_title = "".join(c if c.isalnum() else "_" for c in group_title)
                candidate = f"Duration_{safe_title}"
                if candidate in task_df.columns:
                    granular_col = candidate

        # Fallback: try matching task name
        if not granular_col:
            for col in task_df.columns:
                if col.lower() == f"duration_{t_name}".lower():
                    granular_col = col
                    break

        if t_name == "ads" and not granular_col:
            pass

        # 2. Inject SurveyDuration/SurveyStartTime into schema if missing
        # This ensures every task gets these columns as requested
        if "SurveyDuration" not in t_schema:
            t_schema["SurveyDuration"] = {
                "Description": f"Duration for task {t_name}",
                "Unit": "minutes",  # Default to global unit
            }
        if "SurveyStartTime" not in t_schema:
            t_schema["SurveyStartTime"] = {
                "Description": "Start time of the LimeSurvey session (HH:MM:SS)",
                "Unit": "hh:mm:ss",
            }

        # 3. Overwrite SurveyDuration with granular data if available
        if granular_col:
            # Granular is in seconds, convert to minutes to match schema unit
            # or update schema unit to seconds.
            # Let's update schema to seconds for precision.
            t_schema["SurveyDuration"]["Unit"] = "seconds"
            t_schema["SurveyDuration"]["Description"] = (
                f"Duration for task {t_name} (derived from group timing)"
            )
            task_df["SurveyDuration"] = task_df[granular_col]

            # Debug: Compare durations
            pass

        # 4. Process this single task
        # print(f"DEBUG: Processing task {t_name}")
        process_dataframe(
            task_df,
            {t_name: t_schema},
            output_root,
            library_path,
            session_override=session_label,
        )


def load_id_mapping(map_path):
    """Load ID mapping from a TSV/CSV file.
    Expected columns: 'limesurvey_id', 'participant_id' (or first two columns).
    Returns a dict: {str(limesurvey_id): str(participant_id)}
    """
    if not map_path:
        return None

    path = Path(map_path)
    if not path.exists():
        print(f"Warning: ID map file {path} not found.")
        return None

    try:
        sep = "\t" if path.suffix.lower() == ".tsv" else ","
        df = pd.read_csv(path, sep=sep, dtype=str)

        # Try to find standard columns, else take first two
        src_col = next(
            (
                c
                for c in df.columns
                if c.lower() in ["limesurvey_id", "source_id", "code", "id"]
            ),
            None,
        )
        dst_col = next(
            (
                c
                for c in df.columns
                if c.lower() in ["participant_id", "bids_id", "sub_id", "subject_id"]
            ),
            None,
        )

        if not src_col or not dst_col:
            if len(df.columns) >= 2:
                src_col = df.columns[0]
                dst_col = df.columns[1]
            else:
                print(f"Warning: ID map file {path} must have at least 2 columns.")
                return None

        # Create dict
        mapping = dict(zip(df[src_col], df[dst_col]))
        # Clean up destination: remove 'sub-' prefix if present, as it's added later?
        # Actually, the code adds 'sub-' if missing.
        # If mapping has 'sub-123', code sees it starts with 'sub-' and leaves it.
        # If mapping has '123', code adds 'sub-'.
        # So we just pass the value as is.
        return mapping
    except Exception as e:
        print(f"Error loading ID map {path}: {e}")
        return None


def batch_convert_lsa(
    input_root,
    output_root,
    session_map,
    library_path,
    task_fallback=None,
    id_column=None,
    id_map_file=None,
):
    """Batch-convert .lsa/.lss under input_root into BIDS/PRISM datasets using survey library."""
    input_root = Path(input_root)
    output_root = Path(output_root)

    id_map = load_id_mapping(id_map_file)
    if id_map:
        print(f"Loaded {len(id_map)} ID mappings from {id_map_file}")

    files = list(input_root.rglob("*.lsa")) + list(input_root.rglob("*.lss"))
    if not files:
        print(f"No .lsa/.lss files found under {input_root}")
        return

    normalized_map = {k.lower(): v for k, v in session_map.items()}

    for lsa_file in files:
        parts_lower = [p.name.lower() for p in lsa_file.parents]
        stem_lower = lsa_file.stem.lower()
        session_raw = next((p for p in parts_lower if p in normalized_map), None)
        if not session_raw:
            session_raw = next((k for k in normalized_map if k in stem_lower), None)
        if not session_raw:
            print(
                f"Skipping {lsa_file}: no session key found (looked for {list(normalized_map.keys())}) in path or filename."
            )
            continue
        session_label = normalized_map[session_raw]

        task_hint = lsa_file.stem
        for raw in normalized_map.keys():
            task_hint = re.sub(rf"[_\-]{raw}$", "", task_hint, flags=re.IGNORECASE)
        task_name = sanitize_task_name(
            task_hint if task_hint else (task_fallback or "survey")
        )

        print(f"Converting {lsa_file} -> session {session_label}, task {task_name}")
        convert_lsa_to_dataset(
            str(lsa_file),
            str(output_root),
            session_label,
            library_path,
            task_name=task_name,
            id_column=id_column,
            id_map=id_map,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert LimeSurvey .lsa/.lss to Prism JSON sidecar."
    )
    parser.add_argument("input_file", help="Path to .lsa or .lss file")
    parser.add_argument("-o", "--output", help="Path to output .json file")

    args = parser.parse_args()

    convert_lsa_to_prism(args.input_file, args.output)
