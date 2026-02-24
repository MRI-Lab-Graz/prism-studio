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

# Import item registry for collision detection
try:
    from .item_registry import ItemRegistry, ItemCollisionError
    from .version_merger import (
        merge_survey_versions,
        save_merged_template,
        detect_version_name_from_import,
    )
except ImportError:
    ItemRegistry = None
    ItemCollisionError = None
    merge_survey_versions = None
    save_merged_template = None
    detect_version_name_from_import = None

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


def _get_question_type_name(type_code):
    """Convert LimeSurvey type code to human-readable name."""
    return LIMESURVEY_QUESTION_TYPES.get(type_code, f"Unknown ({type_code})")


def _map_field_to_code(fieldname, qid_to_title):
    m = re.match(r"(\d+)X(\d+)X(\d+)([A-Za-z0-9_]+)?", fieldname)
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
    for row in lss_root.findall(".//subquestions/rows/row"):
        qid = row.find("qid").text
        title = row.find("title").text
        qid_to_title[qid] = title

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


def parse_lss_xml(xml_content, task_name=None, check_collisions=True, local_library=None, official_library=None):
    """Parse a LimeSurvey .lss XML blob into a Prism sidecar dict.
    
    Args:
        xml_content: XML content as bytes or string
        task_name: Optional task name override
        check_collisions: Whether to check for item ID collisions (default: True)
        local_library: Optional path to local survey library
        official_library: Optional path to official survey library
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
    
    # Initialize item registry for collision detection
    item_registry = None
    if check_collisions and ItemRegistry is not None:
        # Auto-detect official library if not provided
        if official_library is None:
            script_dir = Path(__file__).parent.parent.resolve()
            for candidate in [
                script_dir / "official" / "library" / "survey",
                script_dir.parent / "official" / "library" / "survey",
            ]:
                if candidate.exists():
                    official_library = candidate
                    break
        
        try:
            item_registry = ItemRegistry.from_libraries(
                local_library=Path(local_library) if local_library else None,
                official_library=Path(official_library) if official_library else None
            )
            print(f"[PRISM] Item collision checking enabled ({item_registry.get_item_count()} existing items)")
        except Exception as e:
            print(f"[PRISM] Warning: Could not initialize item registry: {e}")
            item_registry = None

    # 2. Parse Answers
    # Map qid -> {code: answer, ...}
    answers_section = root.find("answers")
    if answers_section is not None:
        rows = answers_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                qid = get_text(row, "qid")
                code = get_text(row, "code")
                answer = get_text(row, "answer")

                if qid in questions_map:
                    questions_map[qid]["levels"][code] = answer

    # Determine task name early for registry
    survey_title = survey_meta.get("title") or task_name or "survey"
    normalized_task = sanitize_task_name(survey_title)

    # 3. Construct Prism JSON
    prism_json = {}
    version_collisions = []  # Track version candidate collisions

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

        # Get group info
        group_info = groups_map.get(gid, {"name": "", "order": 0, "description": ""})

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

        # Add answer levels if present
        if q_data["levels"]:
            entry["Levels"] = q_data["levels"]

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
                k: v for k, v in q_data["attributes"].items() if v not in (None, "", 0)
            }
            if attrs:
                entry["Attributes"] = attrs

        # Check for item ID collisions before assignment
        if item_registry is not None:
            desc_text = entry.get("Description", "")
            try:
                item_registry.register_item(
                    item_id=key,
                    template_name=f"survey-{normalized_task}",
                    description=str(desc_text)[:100],
                    item_data=entry
                )
            except ItemCollisionError as e:
                if e.collision_type == "version_candidate":
                    print(f"[PRISM] Detected version candidate: {key}")
                    version_collisions.append((key, entry, e))
                    # Don't add yet - will handle after loop
                    continue
                else:
                    print(f"\n[PRISM ERROR] {e}\n")
                    raise RuntimeError(f"Item collision detected: {key}") from e

        prism_json[key] = entry

    # Handle version candidate collisions
    if version_collisions and merge_survey_versions is not None:
        print(f"\n[PRISM] Processing {len(version_collisions)} version candidate collision(s)...")
        
        # Group by existing template
        collisions_by_template = {}
        for key, entry, error in version_collisions:
            existing_template = error.existing_meta.get('source_template')
            if existing_template not in collisions_by_template:
                collisions_by_template[existing_template] = {'items': {}, 'error': error}
            collisions_by_template[existing_template]['items'][key] = entry
        
        for existing_template_name, collision_info in collisions_by_template.items():
            new_items = collision_info['items']
            
            # Find existing template file
            existing_template_path = None
            if local_library:
                lib_path = Path(local_library) if isinstance(local_library, str) else local_library
                if lib_path.exists():
                    candidate = lib_path / f"{existing_template_name}.json"
                    if candidate.exists():
                        existing_template_path = candidate
            
            if official_library and not existing_template_path:
                lib_path = Path(official_library) if isinstance(official_library, str) else official_library
                if lib_path.exists():
                    candidate = lib_path / f"{existing_template_name}.json"
                    if candidate.exists():
                        existing_template_path = candidate
            
            if not existing_template_path:
                print(f"[PRISM WARNING] Could not find existing template {existing_template_name}, skipping merge")
                # Add items normally
                for item_id, item_data in new_items.items():
                    prism_json[item_id] = item_data
                continue
            
            # Prompt for version name
            print(f"\n{'='*60}")
            print(f"Survey '{normalized_task}' appears to be a version of '{existing_template_name}'")
            print(f"  Existing template: {existing_template_path.name}")
            print(f"  Colliding items: {len(new_items)}")
            
            suggested_new, suggested_existing = detect_version_name_from_import(
                new_items, existing_template_path
            )
            print(f"  Suggested new version name: '{suggested_new}'")
            version_name = input(f"Enter version name for this import (or press Enter for '{suggested_new}'): ").strip()
            if not version_name:
                version_name = suggested_new
            
            print(f"[PRISM] Merging as version: '{version_name}'")
            
            # Perform merge
            merged_template = merge_survey_versions(
                existing_template_path=existing_template_path,
                new_items=new_items,
                new_version_name=version_name
            )
            
            # Save merged template
            save_merged_template(merged_template, existing_template_path)
            
            # Add new items to prism_json
            for item_id, item_data in new_items.items():
                prism_json[item_id] = item_data
            
            print(f"[PRISM] ✓ Version merge complete\n")

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


def parse_lss_xml_by_groups(xml_content):
    """Parse a LimeSurvey .lss XML blob and split into separate questionnaires by group.

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

    questions_map, groups_map = _parse_lss_structure(root, get_text)

    # Parse Answers
    answers_section = root.find("answers")
    if answers_section is not None:
        rows = answers_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                qid = get_text(row, "qid")
                code = get_text(row, "code")
                answer = get_text(row, "answer")
                if qid in questions_map:
                    questions_map[qid]["levels"][code] = answer

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
        sorted_questions = sorted(questions_list, key=lambda x: x[1]["question_order"])

        # Build question entries
        questions_dict = {}
        for qid, q_data in sorted_questions:
            key = q_data["title"]
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

            # Add answer levels if present
            if q_data["levels"]:
                entry["Levels"] = q_data["levels"]

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

    # Parse Answers
    answers_section = root.find("answers")
    if answers_section is not None:
        rows = answers_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                qid = get_text(row, "qid")
                code = get_text(row, "code")
                answer = get_text(row, "answer")
                scale_id = get_text(row, "scale_id") or "0"

                # Handle "None" text from LimeSurvey (unlabeled scale points)
                if answer and answer.lower() == "none":
                    answer = ""

                if qid in questions_map:
                    # Support multiple scales (for dual-scale arrays)
                    if "levels" not in questions_map[qid]:
                        questions_map[qid]["levels"] = {}
                    if scale_id not in questions_map[qid].get("levels_by_scale", {}):
                        if "levels_by_scale" not in questions_map[qid]:
                            questions_map[qid]["levels_by_scale"] = {}
                        questions_map[qid]["levels_by_scale"][scale_id] = {}

                    questions_map[qid]["levels"][code] = answer
                    questions_map[qid]["levels_by_scale"][scale_id][code] = answer

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

        # Add answer levels if present
        if q_data.get("levels"):
            # Filter out empty labels but keep the scale structure
            levels = {k: v for k, v in q_data["levels"].items()}
            if levels:
                entry["Levels"] = levels

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
    base_priority = ["participant_id", "id", "code", "token", "subject"]
    if id_column:
        # Fail fast if the requested ID column is missing; do not silently fall back.
        df_preview, questions_map, groups_map = parse_lsa_responses(lsa_path)
        match = next(
            (c for c in df_preview.columns if c.lower() == id_column.lower()), None
        )
        if not match:
            available = ", ".join(df_preview.columns)
            raise ValueError(
                f"ID column '{id_column}' not found in LimeSurvey responses. Available columns: {available}"
            )
        # Ensure we still process the full dataframe below without re-reading from disk.
        df = df_preview
        id_priority = [match] + base_priority
    else:
        df, questions_map, groups_map = parse_lsa_responses(lsa_path)
        id_priority = id_priority or base_priority

    # Pick participant id column
    id_col = None
    for cand in id_priority:
        for col in df.columns:
            if col.lower() == cand.lower():
                id_col = col
                break
        if id_col:
            break
    if not id_col:
        # Fallback: first column
        id_col = df.columns[0]
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
                            "Units": "seconds",
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
            "Units": "minutes",
        },
        "SurveyStartTime": {
            "Description": "Start time of the LimeSurvey session (HH:MM:SS)",
            "Units": "hh:mm:ss",
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
                "Units": "minutes",  # Default to global unit
            }
        if "SurveyStartTime" not in t_schema:
            t_schema["SurveyStartTime"] = {
                "Description": "Start time of the LimeSurvey session (HH:MM:SS)",
                "Units": "hh:mm:ss",
            }

        # 3. Overwrite SurveyDuration with granular data if available
        if granular_col:
            # Granular is in seconds, convert to minutes to match schema unit
            # or update schema unit to seconds.
            # Let's update schema to seconds for precision.
            t_schema["SurveyDuration"]["Units"] = "seconds"
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
