import json
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
import os
import io

logger = logging.getLogger(__name__)


def add_row(parent, data):
    """Add a <row> element with child tags based on dictionary"""
    row = ET.SubElement(parent, "row")
    for key, value in data.items():
        child = ET.SubElement(row, key)
        child.text = str(value)


# LimeSurvey question code limits:
# - Official limit is 20 characters, but codes at exactly 20 chars can cause import issues
# - We use 15 as a safe maximum to avoid edge cases and keep codes readable
# - Must start with a letter (a-z, A-Z)
# - Only alphanumeric characters allowed (no underscores, hyphens, spaces)
LS_QUESTION_CODE_MAX_LENGTH = 15

# LimeSurvey answer code limits:
# - Default limit is 5 characters (can be increased in LS settings, but we use 5 for compatibility)
# - Only alphanumeric characters allowed
LS_ANSWER_CODE_MAX_LENGTH = 5


def _sanitize_answer_code(
    code: str, existing_codes: set, max_length: int = LS_ANSWER_CODE_MAX_LENGTH
) -> str:
    """
    Sanitize answer code for LimeSurvey compatibility.

    LimeSurvey answer codes have a 5-character limit by default.
    This function shortens long codes and ensures uniqueness within a question.

    Args:
        code: Original answer code (e.g., "corrected_glasses", "n/a")
        existing_codes: Set of already-used codes for this question (to avoid collisions)
        max_length: Maximum allowed length (default: 5)

    Returns:
        Sanitized unique code (e.g., "corgl", "na", "A1", "A2")
    """
    import re

    # Handle special cases
    if code == "n/a" or code == "N/A":
        result = "na"
        if result not in existing_codes:
            return result

    # Remove non-alphanumeric characters
    sanitized = re.sub(r"[^a-zA-Z0-9]", "", code)

    # If short enough and unique, use as-is
    if len(sanitized) <= max_length:
        if sanitized not in existing_codes:
            return sanitized
        # Need to make unique
        for i in range(1, 100):
            candidate = f"{sanitized[: max_length - 1]}{i}"[:max_length]
            if candidate not in existing_codes:
                return candidate

    # For long codes, create abbreviated version
    # Try to keep meaningful parts: first chars + last chars
    if len(sanitized) > max_length:
        # Take first 3 chars + last 2 chars (or adjusted based on max_length)
        prefix_len = max_length - 2
        suffix_len = 2
        abbreviated = sanitized[:prefix_len] + sanitized[-suffix_len:]

        if abbreviated not in existing_codes:
            return abbreviated

        # If collision, use incremental suffix
        for i in range(1, 100):
            candidate = f"{sanitized[: max_length - 1]}{i}"[:max_length]
            if candidate not in existing_codes:
                return candidate

    # Fallback: generate unique code A1, A2, etc.
    for i in range(1, 1000):
        candidate = f"A{i}"
        if candidate not in existing_codes:
            return candidate

    return sanitized[:max_length]  # Last resort


def _sanitize_question_code(
    code: str, max_length: int = LS_QUESTION_CODE_MAX_LENGTH
) -> str:
    """
    Sanitize and truncate question code for LimeSurvey compatibility.

    LimeSurvey restrictions:
    - Maximum 20 characters officially, but we use 15 to avoid edge-case issues
    - Must start with a letter (a-z, A-Z)
    - Only alphanumeric characters allowed (no underscores, hyphens, @, etc.)

    For long codes that need truncation, a 2-character hash suffix is added to
    ensure uniqueness (e.g., psychiatric_diagnosis vs psychiatric_diagnosis_details
    won't collide after truncation).

    Args:
        code: Question code (e.g., "neurological_diagnosis" or "LOT-R01" or "@context")
        max_length: Maximum allowed length (default: 15 for safe LS compatibility)

    Returns:
        Sanitized code that is valid for LimeSurvey
        Examples:
          "LOT-R_01" -> "LOTR01"
          "@context" -> "context"
          "_PRISM_META" -> "PRISMMETA"
          "123test" -> "Q123test"
          "psychiatric_diagnosis" -> "psychidiagab" (truncated + hash suffix)
    """
    import re
    import hashlib

    # Remove all non-alphanumeric characters (including @, _, -)
    sanitized = re.sub(r"[^a-zA-Z0-9]", "", code)

    # Ensure it starts with a letter (LimeSurvey requirement)
    if sanitized and not sanitized[0].isalpha():
        sanitized = "Q" + sanitized

    # Handle empty result
    if not sanitized:
        sanitized = "Q"

    # Truncate to max length, adding hash suffix for long codes to prevent collisions
    if len(sanitized) > max_length:
        # Reserve 2 characters for hash suffix to ensure uniqueness
        # Use hash of ORIGINAL code (before sanitization) to distinguish similar codes
        hash_suffix = hashlib.md5(code.encode()).hexdigest()[:2]
        prefix_len = max_length - 2
        sanitized = sanitized[:prefix_len] + hash_suffix

    return sanitized


def _apply_run_suffix(code: str, run: int | None) -> str:
    """
    Apply run suffix to question code for multi-run surveys.

    Args:
        code: Question code (e.g., "PANAS_1")
        run: Run number (1-based). If None or 1, no suffix is added.

    Returns:
        Code with run suffix if run > 1 (e.g., "PANAS1run02")
        Note: Uses no underscore to comply with LimeSurvey code restrictions.
    """
    if run is None or run <= 1:
        return _sanitize_question_code(code)

    # Build suffix without underscore (LimeSurvey doesn't allow underscores in codes)
    suffix = f"run{run:02d}"
    suffix_len = len(suffix)

    # If code + suffix would exceed max length, truncate code portion
    max_code_len = LS_QUESTION_CODE_MAX_LENGTH - suffix_len
    truncated_code = code[:max_code_len] if len(code) > max_code_len else code

    return _sanitize_question_code(f"{truncated_code}{suffix}")


def _apply_ls_styling(text):
    """
    Apply LimeSurvey HTML styling to question text.
    Creates professional, readable question formatting with proper sizing.
    Uses heading-like styling for clear visual hierarchy.
    """
    if not text:
        return text
    # Don't double-wrap if already has styling
    if "<span" in text or "<strong>" in text or "<div" in text or "<h" in text.lower():
        return text
    # Professional heading-like styling: 22px bold, dark text, proper spacing
    # Using inline styles to ensure they work across all LimeSurvey themes
    return f'<p style="font-size:22px; font-weight:700; color:#1a1a1a; margin:0 0 8px 0; line-height:1.3;">{text}</p>'


def _determine_ls_question_type(q_data, has_levels):
    """
    Determine the LimeSurvey question type based on PRISM metadata.

    Checks for LimeSurvey-specific settings first, then falls back to generic InputType.

    InputType mapping to LimeSurvey types:
    - numerical: N (Numerical input)
    - text: T (Long free text) or S (Short free text)
    - dropdown: ! (List dropdown) or L (List radio)
    - slider: 5 (5-point choice) or K (Multiple numerical) with slider settings
    - calculated: * (Equation) - hidden calculated field
    - radio (default for Levels): L (List radio)
    - array: F (Array/Matrix)

    Args:
        q_data: Question data dictionary from PRISM template
        has_levels: Whether the question has Levels defined

    Returns:
        Tuple of (ls_type, extra_attributes)
    """
    # Check for LimeSurvey-specific settings first
    ls_config = q_data.get("LimeSurvey", {})
    extra_attrs = {}

    # If LimeSurvey section has explicit questionType, use it
    if ls_config.get("questionType"):
        q_type = ls_config["questionType"]

        # Apply LimeSurvey-specific validation settings
        ls_validation = ls_config.get("validation", {})
        if ls_validation.get("min") is not None:
            extra_attrs["min_num_value_n"] = str(ls_validation["min"])
        if ls_validation.get("max") is not None:
            extra_attrs["max_num_value_n"] = str(ls_validation["max"])
        if ls_validation.get("integerOnly"):
            extra_attrs["num_value_int_only"] = "1"

        # Apply input width if specified
        if ls_config.get("inputWidth"):
            extra_attrs["text_input_width"] = ls_config["inputWidth"]

        # Apply hidden attribute
        if ls_config.get("hidden"):
            extra_attrs["hidden"] = "1"

        # Apply equation if specified
        if ls_config.get("equation"):
            extra_attrs["equation"] = ls_config["equation"]

        return q_type, extra_attrs

    # Fall back to generic InputType mapping
    input_type = q_data.get("InputType", "").lower()

    # Check for calculated field first
    if input_type == "calculated" or "Calculation" in q_data:
        calc_config = q_data.get("Calculation", {})

        # Use LimeSurvey-specific formula if provided, otherwise fall back to generic formula
        formula = calc_config.get("lsFormula", "") or calc_config.get("formula", "")

        # If using generic formula, try to convert to LimeSurvey syntax
        if not calc_config.get("lsFormula") and formula:
            import re

            depends_on = calc_config.get("dependsOn", [])

            # Replace variable references with LimeSurvey syntax
            for var in depends_on:
                sanitized_var = _sanitize_question_code(var)
                # Match whole word only
                formula = re.sub(
                    rf"\b{re.escape(var)}\b", f"{{{sanitized_var}.NAOK}}", formula
                )

            # Replace ** exponentiation with pow() function
            formula = re.sub(r"\(([^)]+)\)\s*\*\*\s*(\d+)", r"pow(\1, \2)", formula)

        extra_attrs["equation"] = formula
        if calc_config.get("hidden", False):
            extra_attrs["hidden"] = "1"
        return "*", extra_attrs

    # Numerical input - use generic MinValue/MaxValue
    if input_type == "numerical":
        min_val = q_data.get("MinValue", "")
        max_val = q_data.get("MaxValue", "")
        if min_val != "":
            extra_attrs["min_num_value_n"] = str(min_val)
        if max_val != "":
            extra_attrs["max_num_value_n"] = str(max_val)
        if q_data.get("DataType") == "integer":
            extra_attrs["num_value_int_only"] = "1"
        # Input width for numeric fields
        # LimeSurvey uses numeric scale: 1=smallest (~7%), 2=small, etc.
        input_width = ls_config.get("inputWidth", "1")  # Default to 1 (smallest)
        extra_attrs["text_input_width"] = str(input_width)
        return "N", extra_attrs

    # Slider input - map to Array (Numbers) with slider display or 5-point
    if input_type == "slider":
        slider_config = q_data.get("SliderConfig", {})
        extra_attrs["slider_min"] = str(slider_config.get("min", 1))
        extra_attrs["slider_max"] = str(slider_config.get("max", 5))
        extra_attrs["slider_step"] = str(slider_config.get("step", 1))
        extra_attrs["slider_showminmax"] = (
            "1" if slider_config.get("showLabels", True) else "0"
        )
        # Use K (Multiple numerical input) with slider appearance
        return "K", extra_attrs

    # Dropdown - use ! (List dropdown) for questions with many options
    if input_type == "dropdown":
        # Always use dropdown type for explicit dropdown InputType
        return "!", extra_attrs

    # Check if this has many Levels (>10) - use dropdown instead of radio
    levels = q_data.get("Levels", {})
    if len(levels) > 10:
        return "!", extra_attrs

    # Text input (multiline or single line)
    if input_type == "text":
        text_config = q_data.get("TextConfig", {})
        if text_config.get("multiline", False):
            extra_attrs["display_rows"] = str(text_config.get("rows", 3))
            return "T", extra_attrs  # Long free text
        return "S", extra_attrs  # Short free text

    # Default behavior based on Levels presence
    if has_levels:
        return "L", extra_attrs  # List (Radio)
    else:
        return "T", extra_attrs  # Long free text


def _build_relevance_equation(q_data, code_mapping=None):
    """
    Build LimeSurvey relevance equation from ConditionalDisplay metadata.

    Args:
        q_data: Question data dictionary
        code_mapping: Optional dict mapping original codes to sanitized codes

    Returns:
        Relevance equation string (e.g., "((sex.NAOK == 'F'))")
    """
    # Check for explicit Relevance first
    if "Relevance" in q_data:
        return q_data["Relevance"]
    if "LimeSurvey" in q_data and "Relevance" in q_data["LimeSurvey"]:
        return q_data["LimeSurvey"]["Relevance"]

    # Check for ConditionalDisplay
    conditional = q_data.get("ConditionalDisplay", {})
    if not conditional:
        return "1"  # Always shown

    show_when = conditional.get("showWhen", "")
    if not show_when:
        return "1"

    # Convert PRISM expression to LimeSurvey expression
    # Examples:
    #   "sex == 'F'" -> "((sex.NAOK == 'F'))"
    #   "medication_current == 'yes'" -> "((medicationcurrent.NAOK == 'yes'))"

    import re

    # Parse simple equality expressions
    # Pattern: variable == 'value' or variable != 'value'
    pattern = r"(\w+)\s*(==|!=)\s*['\"]([^'\"]+)['\"]"

    def replace_expr(match):
        var_name = match.group(1)
        operator = match.group(2)
        value = match.group(3)

        # Sanitize variable name to match LimeSurvey code
        sanitized_var = _sanitize_question_code(var_name)

        # Build LimeSurvey expression
        if operator == "==":
            return f"(({sanitized_var}.NAOK == '{value}'))"
        else:
            return f"(({sanitized_var}.NAOK != '{value}'))"

    result = re.sub(pattern, replace_expr, show_when)

    # Handle logical operators
    result = result.replace(" and ", " && ")
    result = result.replace(" or ", " || ")

    return result if result else "1"


def _extract_metadata_from_files(json_files, language="en"):
    """
    Extract metadata (Authors, DOI, Citation, Manual, License) from JSON files.

    Returns a structured metadata description that can be stored in surveyls_description.
    This metadata is preserved when exporting from LimeSurvey.
    """
    all_metadata = []

    for item in json_files:
        if isinstance(item, str):
            f_path = item
        else:
            f_path = item.get("path")

        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        study = data.get("Study", {})
        if not study:
            continue

        # Extract metadata fields
        meta = {}

        # Original name (with language support)
        orig_name = study.get("OriginalName", "")
        if isinstance(orig_name, dict):
            meta["Name"] = orig_name.get(language, orig_name.get("en", str(orig_name)))
        elif orig_name:
            meta["Name"] = str(orig_name)

        # Abbreviation
        if study.get("Abbreviation"):
            meta["Abbreviation"] = study["Abbreviation"]

        # Authors
        authors = study.get("Authors", [])
        if authors:
            if isinstance(authors, list):
                meta["Authors"] = ", ".join(str(a) for a in authors)
            else:
                meta["Authors"] = str(authors)

        # Year
        if study.get("Year"):
            meta["Year"] = str(study["Year"])

        # DOI
        if study.get("DOI"):
            meta["DOI"] = study["DOI"]

        # Citation
        if study.get("Citation"):
            meta["Citation"] = study["Citation"]

        # Source (Manual URL)
        if study.get("Source"):
            meta["Manual"] = study["Source"]

        # License (with language support)
        license_info = study.get("License", "")
        if isinstance(license_info, dict):
            meta["License"] = license_info.get(language, license_info.get("en", ""))
        elif license_info:
            meta["License"] = str(license_info)

        if meta:
            all_metadata.append(meta)

    return all_metadata


def _format_metadata_description(all_metadata, json_files):
    """
    Format extracted metadata into a description string for surveyls_description.

    The format is designed to be human-readable but also machine-parseable,
    so it can be preserved and extracted when the .lss/.lsa is re-exported.
    """
    lines = []

    # Add metadata for each questionnaire
    for idx, meta in enumerate(all_metadata, 1):
        if len(all_metadata) > 1:
            lines.append(f"=== Questionnaire {idx}: {meta.get('Name', 'Unknown')} ===")

        if meta.get("Abbreviation"):
            lines.append(f"Abbreviation: {meta['Abbreviation']}")
        if meta.get("Authors"):
            lines.append(f"Authors: {meta['Authors']}")
        if meta.get("Year"):
            lines.append(f"Year: {meta['Year']}")
        if meta.get("DOI"):
            lines.append(f"DOI: {meta['DOI']}")
        if meta.get("Manual"):
            lines.append(f"Manual/Source: {meta['Manual']}")
        if meta.get("Citation"):
            # Clean up citation (remove extra whitespace/newlines)
            citation = " ".join(meta["Citation"].split())
            lines.append(f"Citation: {citation}")
        if meta.get("License"):
            lines.append(f"License: {meta['License']}")

        if len(all_metadata) > 1:
            lines.append("")  # Blank line between questionnaires

    # Add generation info
    lines.append("")
    lines.append(
        f"--- Generated from {len(json_files)} PRISM template(s) on {datetime.now().strftime('%Y-%m-%d %H:%M')} ---"
    )

    return "\n".join(lines)


def _extract_single_file_metadata(file_path, language="en"):
    """
    Extract metadata from a single JSON file.
    Returns a dict with metadata fields, or None if extraction fails.
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None

    study = data.get("Study", {})
    if not study:
        return None

    meta = {}

    # Original name (with language support)
    orig_name = study.get("OriginalName", "")
    if isinstance(orig_name, dict):
        meta["Name"] = orig_name.get(language, orig_name.get("en", str(orig_name)))
    elif orig_name:
        meta["Name"] = str(orig_name)

    # Abbreviation
    if study.get("Abbreviation"):
        meta["Abbreviation"] = study["Abbreviation"]

    # Authors
    authors = study.get("Authors", [])
    if authors:
        if isinstance(authors, list):
            meta["Authors"] = ", ".join(str(a) for a in authors)
        else:
            meta["Authors"] = str(authors)

    # Year
    if study.get("Year"):
        meta["Year"] = str(study["Year"])

    # DOI
    if study.get("DOI"):
        meta["DOI"] = study["DOI"]

    # Citation
    if study.get("Citation"):
        meta["Citation"] = study["Citation"]

    # Source (Manual URL)
    if study.get("Source"):
        meta["Manual"] = study["Source"]

    # License (with language support)
    license_info = study.get("License", "")
    if isinstance(license_info, dict):
        meta["License"] = license_info.get(language, license_info.get("en", ""))
    elif license_info:
        meta["License"] = str(license_info)

    return meta if meta else None


def _format_single_metadata_html(meta):
    """
    Format metadata for a single questionnaire as HTML for the hidden question.
    Uses a structured format that can be parsed when re-importing.
    """
    if not meta:
        return ""

    lines = ['<div class="prism-metadata" style="display:none;">']
    lines.append("<p><strong>PRISM Template Metadata</strong></p>")

    if meta.get("Name"):
        lines.append(f'<p><span class="meta-name">{meta["Name"]}</span></p>')
    if meta.get("Abbreviation"):
        lines.append(
            f'<p>Abbreviation: <span class="meta-abbrev">{meta["Abbreviation"]}</span></p>'
        )
    if meta.get("Authors"):
        lines.append(
            f'<p>Authors: <span class="meta-authors">{meta["Authors"]}</span></p>'
        )
    if meta.get("Year"):
        lines.append(f'<p>Year: <span class="meta-year">{meta["Year"]}</span></p>')
    if meta.get("DOI"):
        lines.append(f'<p>DOI: <span class="meta-doi">{meta["DOI"]}</span></p>')
    if meta.get("Manual"):
        lines.append(
            f'<p>Source: <span class="meta-source">{meta["Manual"]}</span></p>'
        )
    if meta.get("Citation"):
        citation = " ".join(meta["Citation"].split())
        lines.append(f'<p>Citation: <span class="meta-citation">{citation}</span></p>')
    if meta.get("License"):
        lines.append(
            f'<p>License: <span class="meta-license">{meta["License"]}</span></p>'
        )

    lines.append(
        f'<p>Generated: <span class="meta-generated">{datetime.now().strftime("%Y-%m-%d %H:%M")}</span></p>'
    )
    lines.append("</div>")

    return "\n".join(lines)


def generate_lss(json_files, output_path=None, language="en", languages=None,
                 base_language=None, ls_version="6"):
    """
    Generate a LimeSurvey Structure (.lss) file from a list of Prism JSON sidecars.

    Args:
        json_files (list): List of paths to JSON files, or dicts with:
            - path (str): Path to JSON file
            - include (list, optional): Keys to include from the file
            - matrix (bool, optional): Enable matrix grouping
            - matrix_global (bool, optional): Group all questions with same levels
            - run (int, optional): Run number for multi-run surveys.
              If run > 1, appends "_run-NN" to question codes.
              Example: "PANAS_1" with run=2 becomes "PANAS_1_run-02"
        output_path (str, optional): Path to write the .lss file. If None, returns the XML string.
        language (str): The language to use for the export (backward compatible).
        languages (list, optional): List of language codes to include. If None, uses [language].
        base_language (str, optional): Base language code. If None, uses languages[0] or language.
        ls_version (str): Target LimeSurvey version ("3" or "6").

    Returns:
        str: The XML content if output_path is None, else None.
    """
    # Normalize language parameters
    if languages is None:
        languages = [language]
    if base_language is None:
        base_language = languages[0] if languages else language
    # Ensure base_language is first in the list
    if base_language in languages:
        languages = [base_language] + [l for l in languages if l != base_language]
    additional_languages = [l for l in languages if l != base_language]

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
    # DBVersion must match LimeSurvey's expected schema version
    # Use conservative versions for maximum compatibility
    # LS 5.x/6.x: 415 (widely compatible), LS 3.x: 350
    db_version = "415" if is_v6 else "350"

    # IDs
    sid = "123456"  # Dummy Survey ID

    # Root element
    root = ET.Element("document")
    ET.SubElement(root, "LimeSurveyDocType").text = "Survey"
    ET.SubElement(root, "DBVersion").text = db_version

    # Languages — one <language> per language
    langs_elem = ET.SubElement(root, "languages")
    for lang_code in languages:
        ET.SubElement(langs_elem, "language").text = lang_code

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

    # Question attributes section (for minimum, maximum, hidden, etc.)
    question_attributes_elem = ET.SubElement(root, "question_attributes")
    question_attributes_rows = ET.SubElement(question_attributes_elem, "rows")

    # Counters
    gid_counter = 10
    qid_counter = 100
    group_sort_order = 0
    qaid_counter = 1  # Question attribute ID counter
    l10n_id_counter = 1  # Localization row ID counter

    # --- Process Each JSON as a Group ---
    for item in json_files:
        # Determine path, filter, and run number
        if isinstance(item, str):
            json_path = item
            include_keys = None
            matrix_mode = False
            matrix_global = False
            run_number = None
        elif isinstance(item, dict):
            json_path = item.get("path")
            include_keys = item.get("include")
            matrix_mode = item.get("matrix", False)
            matrix_global = item.get("matrix_global", False)
            run_number = item.get("run")  # Run number for multi-run surveys
        else:
            continue

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                i18n_data = data.get("I18n", {})
        except Exception as e:
            print(f"Error reading {json_path}: {e}")
            continue

        # Filter out metadata keys to get questions
        # These are structural/metadata keys that should never appear as questions
        METADATA_KEYS = {
            "@context",
            "Technical",
            "Study",
            "Metadata",
            "Categories",
            "TaskName",
            "I18n",
            "Scoring",
            "Normative",
            "participant_id",  # Usually auto-assigned, not filled by participants
        }

        if "Questions" in data and isinstance(data["Questions"], dict):
            all_questions = data["Questions"]
        else:
            all_questions = {
                k: v
                for k, v in data.items()
                if k not in METADATA_KEYS
                and isinstance(v, dict)
                and "Description" in v
                and not v.get("_exclude", False)  # Respect _exclude flag
            }

        # Apply inclusion filter if provided
        if include_keys is not None:
            questions_data = {
                k: v for k, v in all_questions.items() if k in include_keys
            }
        else:
            questions_data = all_questions

        # Sort questions by DisplayOrder if available
        def get_display_order(item):
            return item[1].get("DisplayOrder", 999)

        questions_data = dict(sorted(questions_data.items(), key=get_display_order))

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

        # Add Group — emit per-language rows for v3, l10ns per language for v6
        if is_v6:
            group_data = {
                "gid": gid,
                "sid": sid,
                "group_order": str(group_sort_order),
                "randomization_group": "",
                "grelevance": "",
            }
            add_row(groups_rows, group_data)

            for lang in languages:
                g_name = get_text(
                    study_info.get(
                        "OriginalName",
                        data.get("TaskName", os.path.splitext(os.path.basename(json_path))[0]),
                    ),
                    lang, i18n_data, "Study.OriginalName",
                )
                g_desc = get_text(study_info.get("Description", ""), lang, i18n_data, "Study.Description")
                add_row(
                    group_l10ns_rows,
                    {
                        "id": str(l10n_id_counter),
                        "gid": gid,
                        "group_name": g_name,
                        "description": g_desc,
                        "language": lang,
                        "sid": sid,
                    },
                )
                l10n_id_counter += 1
        else:
            # v3: one group row per language
            for lang in languages:
                g_name = get_text(
                    study_info.get(
                        "OriginalName",
                        data.get("TaskName", os.path.splitext(os.path.basename(json_path))[0]),
                    ),
                    lang, i18n_data, "Study.OriginalName",
                )
                g_desc = get_text(study_info.get("Description", ""), lang, i18n_data, "Study.Description")
                group_data = {
                    "gid": gid,
                    "sid": sid,
                    "group_order": str(group_sort_order),
                    "randomization_group": "",
                    "grelevance": "",
                    "group_name": g_name,
                    "description": g_desc,
                    "language": lang,
                }
                add_row(groups_rows, group_data)

        # --- Add hidden metadata question for this questionnaire ---
        file_metadata = _extract_single_file_metadata(json_path, base_language)
        if file_metadata:
            meta_qid = str(qid_counter)
            qid_counter += 1
            # Unique code per group: PRISMMETAg1, PRISMMETAg2, etc.
            meta_q_code = f"PRISMMETAg{group_sort_order}"

            metadata_html = _format_single_metadata_html(file_metadata)

            if is_v6:
                meta_q_data = {
                    "qid": meta_qid,
                    "parent_qid": "0",
                    "sid": sid,
                    "gid": gid,
                    "type": "*",
                    "title": meta_q_code,
                    "preg": "",
                    "other": "N",
                    "mandatory": "N",
                    "encrypted": "N",
                    "question_order": "0",
                    "scale_id": "0",
                    "same_default": "0",
                    "relevance": "0",
                    "question_theme_name": "equation",
                    "modulename": "",
                }
                add_row(questions_rows, meta_q_data)

                # Store metadata HTML as equation value so it persists in response data
                add_row(question_attributes_rows, {
                    "qaid": str(qaid_counter),
                    "qid": meta_qid,
                    "attribute": "equation",
                    "value": metadata_html,
                    "language": "",
                })
                qaid_counter += 1

                for lang in languages:
                    add_row(
                        question_l10ns_rows,
                        {
                            "id": str(l10n_id_counter),
                            "qid": meta_qid,
                            "question": metadata_html,
                            "help": "",
                            "language": lang,
                        },
                    )
                    l10n_id_counter += 1
            else:
                for lang in languages:
                    meta_q_data = {
                        "qid": meta_qid,
                        "parent_qid": "0",
                        "sid": sid,
                        "gid": gid,
                        "type": "*",
                        "title": meta_q_code,
                        "preg": "",
                        "other": "N",
                        "mandatory": "N",
                        "encrypted": "N",
                        "question_order": "0",
                        "scale_id": "0",
                        "same_default": "0",
                        "relevance": "0",
                        "question_theme_name": "equation",
                        "modulename": "",
                        "question": metadata_html,
                        "help": "",
                        "language": lang,
                    }
                    add_row(questions_rows, meta_q_data)

                # Store metadata HTML as equation value so it persists in response data
                add_row(question_attributes_rows, {
                    "qaid": str(qaid_counter),
                    "qid": meta_qid,
                    "attribute": "equation",
                    "value": metadata_html,
                    "language": "",
                })
                qaid_counter += 1

        # Prepare Groups of Questions
        grouped_questions = []
        if matrix_mode:
            if matrix_global:
                # Global grouping: group all questions with identical levels
                # BUT skip grouping for dropdown questions or questions with many levels
                groups = []
                level_to_group_idx = {}

                for q_code, q_data in questions_data.items():
                    if not isinstance(q_data, dict):
                        continue

                    levels = q_data.get("Levels")
                    input_type = q_data.get("InputType", "").lower()

                    # Check for template-level MatrixGrouping flag
                    technical = data.get("Technical", {})
                    matrix_grouping_disabled = technical.get("MatrixGrouping") is False
                    has_other = "OtherOption" in q_data and q_data["OtherOption"].get(
                        "enabled", False
                    )

                    # Don't group: dropdown, numerical, text, calculated, questions with Other option,
                    # questions with 6+ options (likely demographics), or if template disables grouping
                    should_not_group = (
                        matrix_grouping_disabled
                        or input_type == "dropdown"
                        or input_type == "numerical"
                        or input_type == "text"
                        or input_type == "calculated"
                        or has_other
                        or (levels and len(levels) >= 6)
                    )

                    if should_not_group:
                        groups.append([(q_code, q_data)])
                    elif levels and isinstance(levels, dict) and len(levels) > 0:
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
                # BUT skip grouping for dropdown questions or questions with many levels
                current_group = []
                last_levels_str = None

                for q_code, q_data in questions_data.items():
                    if not isinstance(q_data, dict):
                        continue

                    levels = q_data.get("Levels")
                    input_type = q_data.get("InputType", "").lower()

                    # Check for template-level MatrixGrouping flag
                    technical = data.get("Technical", {})
                    matrix_grouping_disabled = technical.get("MatrixGrouping") is False
                    has_other = "OtherOption" in q_data and q_data["OtherOption"].get(
                        "enabled", False
                    )

                    # Don't group: dropdown, numerical, text, calculated, questions with Other option,
                    # questions with 6+ options (likely demographics), or if template disables grouping
                    should_not_group = (
                        matrix_grouping_disabled
                        or input_type == "dropdown"
                        or input_type == "numerical"
                        or input_type == "text"
                        or input_type == "calculated"
                        or has_other
                        or (levels and len(levels) >= 6)
                    )

                    levels_str = (
                        json.dumps(levels, sort_keys=True) if levels else "NO_LEVELS"
                    )

                    if should_not_group:
                        # Force this question to be standalone
                        if current_group:
                            grouped_questions.append(current_group)
                            current_group = []
                        grouped_questions.append([(q_code, q_data)])
                        last_levels_str = None
                    elif not current_group:
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

            # Logic / Relevance - use new helper function
            relevance = _build_relevance_equation(first_data)

            if is_matrix:
                # Matrix Question (Array)
                q_type = "F"

                matrix_title = _apply_run_suffix(f"M{first_code}", run_number)

                _matrix_texts = {"en": "Please answer the following questions:", "de": "Bitte beantworten Sie die folgenden Fragen:"}

                if is_v6:
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
                    add_row(questions_rows, q_data_row)

                    for lang in languages:
                        m_text = _matrix_texts.get(lang, _matrix_texts["en"])
                        add_row(question_l10ns_rows, {
                            "id": str(l10n_id_counter), "qid": qid,
                            "question": m_text, "help": "", "language": lang, "sid": sid,
                        })
                        l10n_id_counter += 1
                else:
                    for lang in languages:
                        m_text = _matrix_texts.get(lang, _matrix_texts["en"])
                        q_data_row = {
                            "qid": qid, "parent_qid": "0", "sid": sid, "gid": gid,
                            "type": q_type, "title": matrix_title, "other": "N",
                            "mandatory": "Y", "question_order": str(q_sort_order),
                            "scale_id": "0", "same_default": "0", "relevance": relevance,
                            "question": m_text, "language": lang,
                        }
                        add_row(questions_rows, q_data_row)

                # Add Subquestions
                sub_sort = 0
                for code, data_item in group:
                    sub_sort += 1
                    sub_qid = str(qid_counter)
                    qid_counter += 1

                    sub_q_code = _apply_run_suffix(code, run_number)

                    if is_v6:
                        sub_q_row = {
                            "qid": sub_qid, "parent_qid": qid, "sid": sid, "gid": gid,
                            "type": "T", "title": sub_q_code,
                            "question_order": str(sub_sort), "scale_id": "0",
                            "same_default": "0", "relevance": "1",
                        }
                        add_row(subquestions_rows, sub_q_row)

                        for lang in languages:
                            sq_text = get_text(data_item.get("Description", code), lang, i18n_data, f"{code}.Description")
                            add_row(question_l10ns_rows, {
                                "id": str(l10n_id_counter), "qid": sub_qid,
                                "question": sq_text, "help": "", "language": lang, "sid": sid,
                            })
                            l10n_id_counter += 1
                    else:
                        for lang in languages:
                            sq_text = get_text(data_item.get("Description", code), lang, i18n_data, f"{code}.Description")
                            sub_q_row = {
                                "qid": sub_qid, "parent_qid": qid, "sid": sid, "gid": gid,
                                "type": "T", "title": sub_q_code,
                                "question_order": str(sub_sort), "scale_id": "0",
                                "same_default": "0", "relevance": "1",
                                "question": sq_text, "language": lang,
                            }
                            add_row(subquestions_rows, sub_q_row)

                # Add Answers (only once per matrix parent)
                if levels:
                    sort_ans = 0
                    used_answer_codes = set()
                    for code, answer_text in levels.items():
                        sort_ans += 1
                        sanitized_code = _sanitize_answer_code(code, used_answer_codes)
                        used_answer_codes.add(sanitized_code)

                        if is_v6:
                            ans_row = {
                                "qid": qid, "code": sanitized_code,
                                "sortorder": str(sort_ans), "assessment_value": "0", "scale_id": "0",
                            }
                            add_row(answers_rows, ans_row)

                            for lang in languages:
                                a_text = get_text(answer_text, lang, i18n_data, f"{first_code}.Levels.{code}")
                                add_row(answer_l10ns_rows, {
                                    "id": str(l10n_id_counter), "qid": qid, "code": sanitized_code,
                                    "answer": a_text, "language": lang, "sid": sid,
                                })
                                l10n_id_counter += 1
                        else:
                            for lang in languages:
                                a_text = get_text(answer_text, lang, i18n_data, f"{first_code}.Levels.{code}")
                                ans_row = {
                                    "qid": qid, "code": sanitized_code,
                                    "sortorder": str(sort_ans), "assessment_value": "0", "scale_id": "0",
                                    "answer": a_text, "language": lang,
                                }
                                add_row(answers_rows, ans_row)

            else:
                # Single Question (with run suffix if applicable)
                q_code = _apply_run_suffix(first_code, run_number)
                q_data = first_data

                # Determine Type using helper function
                q_type, extra_attrs = _determine_ls_question_type(q_data, bool(levels))

                # Check for OtherOption
                has_other = "OtherOption" in q_data and q_data["OtherOption"].get(
                    "enabled", False
                )

                if is_v6:
                    q_data_row = {
                        "qid": qid, "parent_qid": "0", "sid": sid, "gid": gid,
                        "type": q_type, "title": q_code,
                        "other": "Y" if has_other else "N", "mandatory": "Y",
                        "question_order": str(q_sort_order), "scale_id": "0",
                        "same_default": "0", "relevance": relevance,
                    }
                    add_row(questions_rows, q_data_row)

                    for lang in languages:
                        desc = get_text(q_data.get("Description", first_code), lang, i18n_data, f"{first_code}.Description")
                        desc = _apply_ls_styling(desc)
                        h_text = get_text(q_data.get("Help", ""), lang, i18n_data, f"{first_code}.Help")
                        add_row(question_l10ns_rows, {
                            "id": str(l10n_id_counter), "qid": qid,
                            "question": desc, "help": h_text, "language": lang, "sid": sid,
                        })
                        l10n_id_counter += 1
                else:
                    for lang in languages:
                        desc = get_text(q_data.get("Description", first_code), lang, i18n_data, f"{first_code}.Description")
                        desc = _apply_ls_styling(desc)
                        h_text = get_text(q_data.get("Help", ""), lang, i18n_data, f"{first_code}.Help")
                        q_data_row = {
                            "qid": qid, "parent_qid": "0", "sid": sid, "gid": gid,
                            "type": q_type, "title": q_code,
                            "other": "Y" if has_other else "N", "mandatory": "Y",
                            "question_order": str(q_sort_order), "scale_id": "0",
                            "same_default": "0", "relevance": relevance,
                            "question": desc, "help": h_text, "language": lang,
                        }
                        add_row(questions_rows, q_data_row)

                # Add question attributes (minimum, maximum, hidden, etc.)
                for attr_key, attr_val in extra_attrs.items():
                    add_row(
                        question_attributes_rows,
                        {
                            "qaid": str(qaid_counter),
                            "qid": qid,
                            "attribute": attr_key,
                            "value": str(attr_val),
                            "language": "",
                        },
                    )
                    qaid_counter += 1

                # Add Answers (skip "other" if OtherOption is enabled to avoid duplicate)
                if levels:
                    sort_ans = 0
                    used_answer_codes = set()
                    for code, answer_text in levels.items():
                        if code.lower() == "other" and has_other:
                            continue
                        sort_ans += 1
                        sanitized_code = _sanitize_answer_code(code, used_answer_codes)
                        used_answer_codes.add(sanitized_code)

                        if is_v6:
                            ans_row = {
                                "qid": qid, "code": sanitized_code,
                                "sortorder": str(sort_ans), "assessment_value": "0", "scale_id": "0",
                            }
                            add_row(answers_rows, ans_row)

                            for lang in languages:
                                a_text = get_text(answer_text, lang, i18n_data, f"{first_code}.Levels.{code}")
                                add_row(answer_l10ns_rows, {
                                    "id": str(l10n_id_counter), "qid": qid, "code": sanitized_code,
                                    "answer": a_text, "language": lang, "sid": sid,
                                })
                                l10n_id_counter += 1
                        else:
                            for lang in languages:
                                a_text = get_text(answer_text, lang, i18n_data, f"{first_code}.Levels.{code}")
                                ans_row = {
                                    "qid": qid, "code": sanitized_code,
                                    "sortorder": str(sort_ans), "assessment_value": "0", "scale_id": "0",
                                    "answer": a_text, "language": lang,
                                }
                                add_row(answers_rows, ans_row)

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
        "language": base_language,
    }
    if additional_languages:
        survey_settings["additional_languages"] = " ".join(additional_languages)
    add_row(surveys_rows, survey_settings)

    # --- Survey Language Settings ---
    survey_title_base = "Combined Survey"
    if len(json_files) == 1:
        try:
            f_item = json_files[0]
            f_path = f_item if isinstance(f_item, str) else f_item.get("path")
            with open(f_path, "r", encoding="utf-8") as f:
                d = json.load(f)
                s_info = d.get("Study", {})
                i_data = d.get("I18n", {})
                survey_title_base = get_text(
                    s_info.get("OriginalName", d.get("TaskName", "Combined Survey")),
                    base_language, i_data, "Study.OriginalName",
                )
        except Exception:
            pass

    # One language settings row per language
    for lang in languages:
        title_for_lang = survey_title_base
        if len(json_files) == 1:
            try:
                f_item = json_files[0]
                f_path = f_item if isinstance(f_item, str) else f_item.get("path")
                with open(f_path, "r", encoding="utf-8") as f:
                    d = json.load(f)
                    s_info = d.get("Study", {})
                    i_data = d.get("I18n", {})
                    title_for_lang = get_text(
                        s_info.get("OriginalName", d.get("TaskName", "Combined Survey")),
                        lang, i_data, "Study.OriginalName",
                    )
            except Exception:
                pass

        add_row(
            surveys_lang_rows,
            {
                "surveyls_survey_id": sid,
                "surveyls_language": lang,
                "surveyls_title": title_for_lang,
                "surveyls_description": "",
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


def generate_lss_from_customization(
    groups,
    output_path=None,
    language="en",
    languages=None,
    base_language=None,
    ls_version="6",
    matrix_mode=True,
    matrix_global=True,
    survey_title=None,
):
    """
    Generate a LimeSurvey Structure (.lss) file from a CustomizationState.

    This function accepts the output from the Survey Customizer, which allows
    users to reorder questions, create custom groups, and set mandatory flags.

    Args:
        groups (list): List of group dicts from CustomizationState.
        output_path (str, optional): Path to write the .lss file.
        language (str): The language to use for the export (backward compatible).
        languages (list, optional): List of language codes to include.
        base_language (str, optional): Base language code.
        ls_version (str): Target LimeSurvey version ("3" or "6").
        matrix_mode (bool): Group questions with identical options into matrices.
        matrix_global (bool): Group all identical options, not just consecutive.
        survey_title (str, optional): Custom title for the survey.

    Returns:
        str: The XML content if output_path is None, else None.
    """
    # Normalize language parameters
    if languages is None:
        languages = [language]
    if base_language is None:
        base_language = languages[0] if languages else language
    if base_language in languages:
        languages = [base_language] + [l for l in languages if l != base_language]
    additional_languages = [l for l in languages if l != base_language]

    is_v6 = str(ls_version) == "6"
    db_version = "415" if is_v6 else "350"

    # IDs
    sid = "123456"

    # Root element
    root = ET.Element("document")
    ET.SubElement(root, "LimeSurveyDocType").text = "Survey"
    ET.SubElement(root, "DBVersion").text = db_version

    # Languages — one per language
    langs_elem = ET.SubElement(root, "languages")
    for lang_code in languages:
        ET.SubElement(langs_elem, "language").text = lang_code

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

    question_attributes_elem = ET.SubElement(root, "question_attributes")
    question_attributes_rows = ET.SubElement(question_attributes_elem, "rows")

    # Counters
    gid_counter = 10
    qid_counter = 100
    group_sort_order = 0
    qaid_counter = 1
    l10n_id_counter = 1

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
        return str(obj) if obj else ""

    # Sort groups by order
    sorted_groups = sorted(groups, key=lambda g: g.get("order", 0))

    for group in sorted_groups:
        # Skip groups with no enabled questions
        enabled_questions = [
            q for q in group.get("questions", []) if q.get("enabled", True)
        ]
        if not enabled_questions:
            continue

        gid = str(gid_counter)
        gid_counter += 1
        group_sort_order += 1

        group_name = group.get("name", f"Group {group_sort_order}")
        group_desc = ""

        # Add Group — per-language rows
        if is_v6:
            group_data = {
                "gid": gid, "sid": sid,
                "group_order": str(group_sort_order),
                "randomization_group": "", "grelevance": "",
            }
            add_row(groups_rows, group_data)

            for lang in languages:
                add_row(group_l10ns_rows, {
                    "id": str(l10n_id_counter), "gid": gid,
                    "group_name": group_name, "description": group_desc,
                    "language": lang, "sid": sid,
                })
                l10n_id_counter += 1
        else:
            for lang in languages:
                group_data = {
                    "gid": gid, "sid": sid,
                    "group_order": str(group_sort_order),
                    "randomization_group": "", "grelevance": "",
                    "group_name": group_name, "description": group_desc,
                    "language": lang,
                }
                add_row(groups_rows, group_data)

        # --- Add hidden metadata question for this questionnaire ---
        source_file = None
        if enabled_questions:
            source_file = enabled_questions[0].get("sourceFile")

        if source_file:
            file_metadata = _extract_single_file_metadata(source_file, base_language)
            if file_metadata:
                meta_qid = str(qid_counter)
                qid_counter += 1
                meta_q_code = f"PRISMMETAg{group_sort_order}"
                metadata_html = _format_single_metadata_html(file_metadata)

                if is_v6:
                    meta_q_data = {
                        "qid": meta_qid, "parent_qid": "0", "sid": sid, "gid": gid,
                        "type": "*", "title": meta_q_code, "preg": "", "other": "N",
                        "mandatory": "N", "encrypted": "N", "question_order": "0",
                        "scale_id": "0", "same_default": "0", "relevance": "0",
                        "question_theme_name": "equation", "modulename": "",
                    }
                    add_row(questions_rows, meta_q_data)

                    # Store metadata HTML as equation value so it persists in response data
                    add_row(question_attributes_rows, {
                        "qaid": str(qaid_counter), "qid": meta_qid,
                        "attribute": "equation", "value": metadata_html, "language": "",
                    })
                    qaid_counter += 1

                    for lang in languages:
                        add_row(question_l10ns_rows, {
                            "id": str(l10n_id_counter), "qid": meta_qid,
                            "question": metadata_html, "help": "", "language": lang,
                        })
                        l10n_id_counter += 1
                else:
                    for lang in languages:
                        meta_q_data = {
                            "qid": meta_qid, "parent_qid": "0", "sid": sid, "gid": gid,
                            "type": "*", "title": meta_q_code, "preg": "", "other": "N",
                            "mandatory": "N", "encrypted": "N", "question_order": "0",
                            "scale_id": "0", "same_default": "0", "relevance": "0",
                            "question_theme_name": "equation", "modulename": "",
                            "question": metadata_html, "help": "", "language": lang,
                        }
                        add_row(questions_rows, meta_q_data)

                    # Store metadata HTML as equation value so it persists in response data
                    add_row(question_attributes_rows, {
                        "qaid": str(qaid_counter), "qid": meta_qid,
                        "attribute": "equation", "value": metadata_html, "language": "",
                    })
                    qaid_counter += 1

        # Sort questions by displayOrder
        sorted_questions = sorted(
            enabled_questions, key=lambda q: q.get("displayOrder", 0)
        )

        # Prepare question grouping for matrices
        grouped_questions = []

        def _should_not_group(q):
            """Check if a question should NOT be grouped into a matrix."""
            orig = q.get("originalData", {})
            input_type = orig.get("InputType", "").lower()
            levels = q.get("levels") or orig.get("Levels", {})
            has_other = "OtherOption" in orig and orig["OtherOption"].get(
                "enabled", False
            )

            # Check for template-level MatrixGrouping flag (passed from loader)
            # This is more reliable than re-reading the file
            matrix_grouping_disabled = q.get("matrixGroupingDisabled", False)

            # Additional check: if the source file is participants.json, never group
            source_file = q.get("sourceFile", "")
            is_participants = "participants" in source_file.lower()

            num_levels = len(levels) if levels else 0

            return (
                matrix_grouping_disabled  # Template explicitly disables matrix grouping
                or is_participants  # Participants/demographics should never be grouped
                or input_type == "dropdown"
                or input_type == "numerical"
                or input_type == "text"
                or input_type == "calculated"
                or has_other  # Questions with "Other" option shouldn't be grouped
                or num_levels >= 6  # 6+ options = likely demographic, not Likert scale
            )

        if matrix_mode:
            if matrix_global:
                # Global grouping: group all questions with identical levels
                level_groups = []
                level_to_idx = {}

                for q in sorted_questions:
                    # Skip grouping for certain question types
                    if _should_not_group(q):
                        level_groups.append([q])
                        continue

                    levels = q.get("levels") or q.get("originalData", {}).get(
                        "Levels", {}
                    )
                    if levels and isinstance(levels, dict) and len(levels) > 0:
                        l_str = json.dumps(levels, sort_keys=True)
                        if l_str in level_to_idx:
                            level_groups[level_to_idx[l_str]].append(q)
                        else:
                            level_to_idx[l_str] = len(level_groups)
                            level_groups.append([q])
                    else:
                        level_groups.append([q])
                grouped_questions = level_groups
            else:
                # Consecutive grouping only
                current_group = []
                last_levels_str = None

                for q in sorted_questions:
                    # Skip grouping for certain question types
                    if _should_not_group(q):
                        if current_group:
                            grouped_questions.append(current_group)
                            current_group = []
                        grouped_questions.append([q])
                        last_levels_str = None
                        continue

                    levels = q.get("levels") or q.get("originalData", {}).get(
                        "Levels", {}
                    )
                    levels_str = (
                        json.dumps(levels, sort_keys=True) if levels else "NO_LEVELS"
                    )

                    if not current_group:
                        current_group.append(q)
                        last_levels_str = levels_str
                    else:
                        if levels and levels_str == last_levels_str:
                            current_group.append(q)
                        else:
                            grouped_questions.append(current_group)
                            current_group = [q]
                            last_levels_str = levels_str

                if current_group:
                    grouped_questions.append(current_group)
        else:
            # No grouping - each question is its own group
            grouped_questions = [[q] for q in sorted_questions]

        # Cache for source file data to avoid re-reading
        _source_file_cache = {}

        def _get_question_from_source(q):
            """Get full question data from source file (most reliable)."""
            source_file = q.get("sourceFile")
            q_code = q.get("questionCode")
            if not source_file or not q_code:
                logger.warning(
                    "Missing sourceFile or questionCode for question"
                )
                return None

            if source_file not in _source_file_cache:
                try:
                    with open(source_file, "r", encoding="utf-8") as f:
                        _source_file_cache[source_file] = json.load(f)
                    logger.debug("Loaded source file: %s", source_file)
                except Exception as e:
                    logger.error("Error loading source file %s: %s", source_file, e)
                    _source_file_cache[source_file] = None

            template_data = _source_file_cache.get(source_file)
            if not template_data:
                logger.warning("No template data for %s", source_file)
                return None

            # Check Questions section first, then top-level
            questions_section = template_data.get("Questions", {})
            if q_code in questions_section:
                return questions_section[q_code]
            if q_code in template_data:
                return template_data[q_code]

            logger.warning("Question '%s' not found in %s", q_code, source_file)
            return None

        def _get_i18n_from_source(q):
            """Get I18n data from cached source file."""
            source_file = q.get("sourceFile")
            if not source_file:
                return {}
            template_data = _source_file_cache.get(source_file)
            if not template_data:
                return {}
            return template_data.get("I18n", {})

        # Process question groups
        q_sort_order = 0
        logger.debug("Processing %d question groups", len(grouped_questions))
        for q_group in grouped_questions:
            first_q = q_group[0]

            # Get levels - try multiple sources for reliability
            # Priority: 1) Source file (most reliable), 2) originalData, 3) levels field
            q_code = first_q.get("questionCode", "unknown")
            source_file = first_q.get("sourceFile", "")
            source_q_data = _get_question_from_source(first_q)

            logger.debug(
                "Question: %s (sourceFile=%s, source_q_data=%s)",
                q_code, source_file, source_q_data is not None,
            )

            if source_q_data and source_q_data.get("Levels"):
                levels = source_q_data.get("Levels", {})
            else:
                orig_levels = first_q.get("originalData", {}).get("Levels", {})
                q_levels = first_q.get("levels", {})
                levels = orig_levels or q_levels

            is_matrix = len(q_group) > 1

            qid = str(qid_counter)
            qid_counter += 1
            q_sort_order += 1

            # Relevance - use new helper function with originalData
            # Prefer source file data if available
            original_data = (
                source_q_data if source_q_data else first_q.get("originalData", {})
            )
            relevance = _build_relevance_equation(original_data)

            if is_matrix:
                q_type = "F"

                first_code = first_q.get("questionCode", "Q")
                run_number = first_q.get("runNumber")
                matrix_title = _apply_run_suffix(f"M{first_code}", run_number)

                _matrix_texts = {"en": "Please answer the following questions:", "de": "Bitte beantworten Sie die folgenden Fragen:"}
                any_mandatory = any(q.get("mandatory", True) for q in q_group)

                if is_v6:
                    q_data_row = {
                        "qid": qid, "parent_qid": "0", "sid": sid, "gid": gid,
                        "type": q_type, "title": matrix_title, "other": "N",
                        "mandatory": "Y" if any_mandatory else "N",
                        "question_order": str(q_sort_order), "scale_id": "0",
                        "same_default": "0", "relevance": relevance,
                    }
                    add_row(questions_rows, q_data_row)

                    for lang in languages:
                        m_text = _matrix_texts.get(lang, _matrix_texts["en"])
                        add_row(question_l10ns_rows, {
                            "id": str(l10n_id_counter), "qid": qid,
                            "question": m_text, "help": "", "language": lang, "sid": sid,
                        })
                        l10n_id_counter += 1
                else:
                    for lang in languages:
                        m_text = _matrix_texts.get(lang, _matrix_texts["en"])
                        q_data_row = {
                            "qid": qid, "parent_qid": "0", "sid": sid, "gid": gid,
                            "type": q_type, "title": matrix_title, "other": "N",
                            "mandatory": "Y" if any_mandatory else "N",
                            "question_order": str(q_sort_order), "scale_id": "0",
                            "same_default": "0", "relevance": relevance,
                            "question": m_text, "language": lang,
                        }
                        add_row(questions_rows, q_data_row)

                # Add Subquestions
                sub_sort = 0
                for q in q_group:
                    sub_sort += 1
                    sub_qid = str(qid_counter)
                    qid_counter += 1

                    q_code = q.get("questionCode", f"SQ{sub_sort}")
                    run_num = q.get("runNumber")
                    sub_q_code = _apply_run_suffix(q_code, run_num)

                    sub_source_data = _get_question_from_source(q)
                    sub_orig = sub_source_data if sub_source_data else q.get("originalData", {})
                    sub_i18n = _get_i18n_from_source(q)

                    if is_v6:
                        sub_q_row = {
                            "qid": sub_qid, "parent_qid": qid, "sid": sid, "gid": gid,
                            "type": "T", "title": sub_q_code,
                            "question_order": str(sub_sort), "scale_id": "0",
                            "same_default": "0", "relevance": "1",
                        }
                        add_row(subquestions_rows, sub_q_row)

                        for lang in languages:
                            sq_desc = get_text(sub_orig.get("Description", q_code), lang, sub_i18n, f"{q_code}.Description")
                            if not sq_desc:
                                sq_desc = q.get("description", q_code)
                            add_row(question_l10ns_rows, {
                                "id": str(l10n_id_counter), "qid": sub_qid,
                                "question": sq_desc, "help": "", "language": lang,
                            })
                            l10n_id_counter += 1
                    else:
                        for lang in languages:
                            sq_desc = get_text(sub_orig.get("Description", q_code), lang, sub_i18n, f"{q_code}.Description")
                            if not sq_desc:
                                sq_desc = q.get("description", q_code)
                            sub_q_row = {
                                "qid": sub_qid, "parent_qid": qid, "sid": sid, "gid": gid,
                                "type": "T", "title": sub_q_code,
                                "question_order": str(sub_sort), "scale_id": "0",
                                "same_default": "0", "relevance": "1",
                                "question": sq_desc, "language": lang,
                            }
                            add_row(subquestions_rows, sub_q_row)

                # Add Answers for the matrix (only once)
                if levels:
                    first_q_code = first_q.get("questionCode", "")
                    matrix_i18n = _get_i18n_from_source(first_q)
                    sort_ans = 0
                    used_answer_codes = set()
                    for code, answer_text in levels.items():
                        sort_ans += 1
                        sanitized_code = _sanitize_answer_code(code, used_answer_codes)
                        used_answer_codes.add(sanitized_code)

                        if is_v6:
                            ans_row = {
                                "qid": qid, "code": sanitized_code,
                                "sortorder": str(sort_ans), "assessment_value": "0", "scale_id": "0",
                            }
                            add_row(answers_rows, ans_row)

                            for lang in languages:
                                a_text = get_text(answer_text, lang, matrix_i18n, f"{first_q_code}.Levels.{code}")
                                add_row(answer_l10ns_rows, {
                                    "id": str(l10n_id_counter), "qid": qid, "code": sanitized_code,
                                    "answer": a_text, "language": lang, "sid": sid,
                                })
                                l10n_id_counter += 1
                        else:
                            for lang in languages:
                                a_text = get_text(answer_text, lang, matrix_i18n, f"{first_q_code}.Levels.{code}")
                                ans_row = {
                                    "qid": qid, "code": sanitized_code,
                                    "sortorder": str(sort_ans), "assessment_value": "0", "scale_id": "0",
                                    "answer": a_text, "language": lang,
                                }
                                add_row(answers_rows, ans_row)
            else:
                # Single Question
                q = first_q
                q_code = q.get("questionCode", f"Q{q_sort_order}")
                run_num = q.get("runNumber")
                final_code = _apply_run_suffix(q_code, run_num)

                orig = source_q_data if source_q_data else q.get("originalData", {})
                i18n_data = _get_i18n_from_source(q)
                is_mandatory = q.get("mandatory", True)

                # Apply toolOverrides if present
                tool_ov = q.get("toolOverrides", {})

                # Determine Type — use toolOverride first, then auto-detect
                if tool_ov.get("questionType"):
                    q_type = tool_ov["questionType"]
                    extra_attrs = {}
                else:
                    q_type, extra_attrs = _determine_ls_question_type(orig, bool(levels))

                # Apply toolOverride attributes
                if tool_ov.get("inputWidth"):
                    extra_attrs["text_input_width"] = str(tool_ov["inputWidth"])
                if tool_ov.get("displayRows"):
                    extra_attrs["display_rows"] = str(tool_ov["displayRows"])
                if tool_ov.get("validationMin") is not None:
                    extra_attrs["min_num_value_n"] = str(tool_ov["validationMin"])
                if tool_ov.get("validationMax") is not None:
                    extra_attrs["max_num_value_n"] = str(tool_ov["validationMax"])
                if tool_ov.get("integerOnly"):
                    extra_attrs["num_value_int_only"] = "1"
                if tool_ov.get("hidden"):
                    extra_attrs["hidden"] = "1"
                if tool_ov.get("equation"):
                    extra_attrs["equation"] = tool_ov["equation"]

                # Additional toolOverride → LS attribute mappings
                _ov_to_ls = {
                    "cssClass": "cssclass",
                    "pageBreak": "page_break",
                    "maximumChars": "maximum_chars",
                    "numbersOnly": "numbers_only",
                    "inputSize": "input_size",
                    "prefix": "prefix",
                    "suffix": "suffix",
                    "placeholder": "placeholder",
                    "displayColumns": "display_columns",
                    "alphasort": "alphasort",
                    "dropdownSize": "dropdown_size",
                    "dropdownPrefix": "dropdown_prefix",
                    "categorySeparator": "category_separator",
                    "answerWidth": "answer_width",
                    "repeatHeadings": "repeat_headings",
                    "useDropdown": "use_dropdown",
                }
                for ov_key, ls_attr in _ov_to_ls.items():
                    val = tool_ov.get(ov_key)
                    if val is not None and val != "" and val is not False:
                        # Boolean True → "1" for LS attributes
                        if isinstance(val, bool):
                            extra_attrs[ls_attr] = "1"
                        else:
                            extra_attrs[ls_attr] = str(val)

                # Relevance — toolOverride takes precedence
                if tool_ov.get("relevance"):
                    relevance = tool_ov["relevance"]

                # Check for OtherOption
                has_other = "OtherOption" in orig and orig["OtherOption"].get("enabled", False)

                if is_v6:
                    q_data_row = {
                        "qid": qid, "parent_qid": "0", "sid": sid, "gid": gid,
                        "type": q_type, "title": final_code,
                        "other": "Y" if has_other else "N",
                        "mandatory": "Y" if is_mandatory else "N",
                        "question_order": str(q_sort_order), "scale_id": "0",
                        "same_default": "0", "relevance": relevance,
                    }
                    add_row(questions_rows, q_data_row)

                    for lang in languages:
                        desc = tool_ov.get("questionText") or get_text(orig.get("Description", q_code), lang, i18n_data, f"{q_code}.Description")
                        if not desc:
                            desc = q.get("description", q_code)
                        desc = _apply_ls_styling(desc)
                        h_text = tool_ov.get("helpText") or get_text(orig.get("Help", ""), lang, i18n_data, f"{q_code}.Help")
                        add_row(question_l10ns_rows, {
                            "id": str(l10n_id_counter), "qid": qid,
                            "question": desc, "help": h_text, "language": lang, "sid": sid,
                        })
                        l10n_id_counter += 1
                else:
                    for lang in languages:
                        desc = tool_ov.get("questionText") or get_text(orig.get("Description", q_code), lang, i18n_data, f"{q_code}.Description")
                        if not desc:
                            desc = q.get("description", q_code)
                        desc = _apply_ls_styling(desc)
                        h_text = tool_ov.get("helpText") or get_text(orig.get("Help", ""), lang, i18n_data, f"{q_code}.Help")
                        q_data_row = {
                            "qid": qid, "parent_qid": "0", "sid": sid, "gid": gid,
                            "type": q_type, "title": final_code,
                            "other": "Y" if has_other else "N",
                            "mandatory": "Y" if is_mandatory else "N",
                            "question_order": str(q_sort_order), "scale_id": "0",
                            "same_default": "0", "relevance": relevance,
                            "question": desc, "help": h_text, "language": lang,
                        }
                        add_row(questions_rows, q_data_row)

                # Add question attributes
                for attr_key, attr_val in extra_attrs.items():
                    add_row(question_attributes_rows, {
                        "qaid": str(qaid_counter), "qid": qid,
                        "attribute": attr_key, "value": str(attr_val), "language": "",
                    })
                    qaid_counter += 1

                # Add Answers
                if levels:
                    sort_ans = 0
                    used_answer_codes = set()
                    for code, answer_text in levels.items():
                        if code.lower() == "other" and has_other:
                            continue
                        sort_ans += 1
                        sanitized_code = _sanitize_answer_code(code, used_answer_codes)
                        used_answer_codes.add(sanitized_code)

                        if is_v6:
                            ans_row = {
                                "qid": qid, "code": sanitized_code,
                                "sortorder": str(sort_ans), "assessment_value": "0", "scale_id": "0",
                            }
                            add_row(answers_rows, ans_row)

                            for lang in languages:
                                a_text = get_text(answer_text, lang, i18n_data, f"{q_code}.Levels.{code}")
                                add_row(answer_l10ns_rows, {
                                    "id": str(l10n_id_counter), "qid": qid, "code": sanitized_code,
                                    "answer": a_text, "language": lang, "sid": sid,
                                })
                                l10n_id_counter += 1
                        else:
                            for lang in languages:
                                a_text = get_text(answer_text, lang, i18n_data, f"{q_code}.Levels.{code}")
                                ans_row = {
                                    "qid": qid, "code": sanitized_code,
                                    "sortorder": str(sort_ans), "assessment_value": "0", "scale_id": "0",
                                    "answer": a_text, "language": lang,
                                }
                                add_row(answers_rows, ans_row)
                else:
                    logger.warning("No levels for %s", final_code)

    # --- Survey Settings ---
    survey_settings = {
        "sid": sid,
        "owner_id": "1",
        "admin": "Administrator",
        "active": "N",
        "anonymized": "N",
        "format": "G",
        "savetimings": "Y",
        "template": "vanilla",
        "language": base_language,
    }
    if additional_languages:
        survey_settings["additional_languages"] = " ".join(additional_languages)
    add_row(surveys_rows, survey_settings)

    # --- Survey Language Settings ---
    if not survey_title:
        survey_title = "Custom Survey"
        if sorted_groups:
            survey_title = sorted_groups[0].get("name", "Custom Survey")

    for lang in languages:
        add_row(
            surveys_lang_rows,
            {
                "surveyls_survey_id": sid,
                "surveyls_language": lang,
                "surveyls_title": survey_title,
                "surveyls_description": "",
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
