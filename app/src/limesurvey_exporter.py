import json
import logging
import xml.etree.ElementTree as ET

from datetime import datetime
import os
import io

from src.limesurvey_attributes import LS_DESIGN_ATTRIBUTES, LS_ROW_TYPES
from src.text_sanitizer import sanitize_answer_text, strip_invalid_xml_chars
from src.survey_template_metadata import get_study_short_name

logger = logging.getLogger(__name__)


def add_row(parent, data):
    """Add a <row> element with child tags based on dictionary"""
    row = ET.SubElement(parent, "row")
    for key, value in data.items():
        child = ET.SubElement(row, key)
        child.text = str(value)
    return row


def _fill_metadata_cells(cells, metadata_kwargs, code_map):
    """Write the PRISMMETA HTML once the group's questions are laid out, so its
    CodeMap holds the LimeSurvey column each item was really written to."""
    if cells:
        html = _format_single_metadata_html(**metadata_kwargs, code_map=code_map)
        for cell in cells:
            cell.text = html


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

# LimeSurvey subquestion code limits:
# - Default limit is 5 characters (same as answer codes)
# - Must start with a letter (a-z, A-Z)
# - Only alphanumeric characters allowed
# - Must be unique within the parent question
# See: https://www.limesurvey.org/manual/Adding_answers_or_subquestions
LS_SUBQUESTION_CODE_MAX_LENGTH = 5

# Types whose answer options LimeSurvey defines itself: an <answers> row would not be used.
LS_FIXED_ANSWER_TYPES = {"Y", "G", "5"}


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


def _sanitize_subquestion_code(
    code: str,
    existing_codes: set,
    run_number: int | None = None,
    subquestion_index: int = 1,
    max_length: int = LS_SUBQUESTION_CODE_MAX_LENGTH,
) -> str:
    """
    Sanitize subquestion code for LimeSurvey compatibility.

    LimeSurvey subquestion codes have a 5-character limit (same as answer codes).
    This function creates short, unique codes that preserve as much meaning as possible.

    Strategy:
    - For short codes (<=5 chars): use as-is if valid
    - For longer codes: create abbreviated version with run suffix if needed
    - Ensure uniqueness within the parent question

    Args:
        code: Original question code (e.g., "BFAS01", "LOT_R_01")
        existing_codes: Set of already-used codes within this parent question
        run_number: Run number for multi-run surveys (None or 1 = no suffix, 2+ = add suffix)
        subquestion_index: 1-based index of this subquestion (used as fallback)
        max_length: Maximum allowed length (default: 5)

    Returns:
        Sanitized unique code (e.g., "BFA01", "SQ01", "B1R2")

    Examples:
        "BFAS01" -> "BFA01" or "SQ001"
        "BFAS01" with run=2 -> "B1R02" or "S1R02"
        "LOT_R_01" -> "LOT01"
    """
    import re

    # Remove non-alphanumeric characters
    sanitized = re.sub(r"[^a-zA-Z0-9]", "", code)

    # Ensure it starts with a letter
    if sanitized and not sanitized[0].isalpha():
        sanitized = "S" + sanitized

    if not sanitized:
        sanitized = "SQ"

    # For multi-run surveys, we need to encode run info in a very short code
    if run_number and run_number > 1:
        # Strategy: Use format like "X1R2" where X=first letter, 1=item number, R2=run 2
        # This gives us meaningful codes that fit in 5 chars

        # Extract any numbers from the original code
        numbers = re.findall(r"\d+", code)
        item_num = numbers[0] if numbers else str(subquestion_index)

        # Keep item number short (1-2 digits)
        item_num = item_num[-2:] if len(item_num) > 2 else item_num

        # Format: FirstLetter + ItemNum + R + RunNum
        # e.g., "B01R2" for BFAS01 run 2
        first_letter = sanitized[0].upper()
        run_suffix = f"R{run_number}"

        # Calculate available space for item number
        available = max_length - len(first_letter) - len(run_suffix)
        item_num = item_num[:available] if available > 0 else ""

        candidate = f"{first_letter}{item_num}{run_suffix}"

        if candidate not in existing_codes:
            return candidate

        # If collision, try with subquestion index
        candidate = f"S{subquestion_index}R{run_number}"[:max_length]
        if candidate not in existing_codes:
            return candidate
    else:
        # No run suffix needed - try to preserve meaningful part of code
        if len(sanitized) <= max_length:
            if sanitized not in existing_codes:
                return sanitized
        else:
            # Abbreviate: take first 3 chars + last 2 digits (if any)
            numbers = re.findall(r"\d+", sanitized)
            if numbers:
                last_num = numbers[-1][-2:]  # Last 2 digits of last number
                prefix_len = max_length - len(last_num)
                candidate = sanitized[:prefix_len] + last_num
            else:
                candidate = sanitized[:max_length]

            if candidate not in existing_codes:
                return candidate

    # Fallback: generate sequential code SQ001, SQ002, etc.
    for i in range(1, 1000):
        if run_number and run_number > 1:
            # Include run number in fallback
            candidate = f"S{i}R{run_number}"[:max_length]
        else:
            candidate = f"SQ{i:03d}"[:max_length]

        if candidate not in existing_codes:
            return candidate

    return f"SQ{subquestion_index}"[:max_length]


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
        # Hash used for generating short suffixes, not for security
        hash_suffix = hashlib.md5(code.encode(), usedforsecurity=False).hexdigest()[:2]
        prefix_len = max_length - 2
        sanitized = sanitized[:prefix_len] + hash_suffix

    return sanitized


def _text_in_language(texts: dict, lang, path=None):
    """``texts[lang]``; a missing translation falls back to English (else the first
    language) and is logged, so the survey shows it instead of an empty question."""
    if lang in texts:
        return texts[lang]
    fallback_lang = "en" if "en" in texts else next(iter(texts), None)
    if fallback_lang is None:
        return ""
    logger.warning("No %r text for %s: exported the %r text instead", lang, path or "an item", fallback_lang)
    return texts[fallback_lang]


def _text_in(obj, lang, i18n_data=None, path=None):
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
        return _text_in_language(obj, lang, path)
    return str(obj) if obj else ""


def _ls_settings(q_data) -> dict:
    """The item's LimeSurvey settings (what the Template Editor and a LimeSurvey import write)."""
    ls = q_data.get("LimeSurvey") if isinstance(q_data, dict) else None
    return ls if isinstance(ls, dict) else {}


def item_is_mandatory(q_data) -> bool:
    """Required in LimeSurvey: LimeSurvey.mandatory wins over the generic Mandatory; required if neither is set."""
    ls = _ls_settings(q_data)
    return bool(ls["mandatory"]) if "mandatory" in ls else bool(q_data.get("Mandatory", True))


def item_has_other(q_data) -> bool:
    """An "Other" answer field: LimeSurvey.other or the generic OtherOption.enabled."""
    other_option = q_data.get("OtherOption")
    return bool(_ls_settings(q_data).get("other")) or (
        isinstance(other_option, dict) and bool(other_option.get("enabled"))
    )


def item_help(q_data):
    """Help text (a string or one per language): the generic Help, else LimeSurvey.helpText."""
    return q_data.get("Help") or _ls_settings(q_data).get("helpText") or ""


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
        if q_type in LS_ROW_TYPES:
            q_type = "L"  # a lone matrix row, checkbox option or ranking position: a list keeps its options

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

        if ls_config.get("displayRows"):
            extra_attrs["display_rows"] = str(ls_config["displayRows"])

        for name in LS_DESIGN_ATTRIBUTES:
            if ls_config.get(name) not in (None, "", 0, False):
                extra_attrs[name] = "1" if ls_config[name] is True else str(ls_config[name])

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
    ls = _ls_settings(q_data)
    ls_relevance = ls.get("relevance") or ls.get("Relevance")
    if ls_relevance and ls_relevance != "1":  # "1" (always shown) leaves room for ConditionalDisplay
        return ls_relevance

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

    # ShortName / Abbreviation
    short_name = get_study_short_name(study)
    if short_name:
        meta["Abbreviation"] = short_name

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


def _format_single_metadata_html(
    meta, is_participants=False, participant_variables=None, code_map=None
):
    """
    Format metadata for a single questionnaire as HTML for the hidden question.
    Uses a structured format that can be parsed when re-importing.

    Args:
        meta: Metadata dict extracted from the JSON template.
        is_participants: If True, mark this group as participants data.
        participant_variables: List of variable codes for participants groups.
        code_map: Optional dict mapping original PRISM codes to sanitized LS codes.
            Used during re-import to reverse the code sanitization.
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

    if is_participants:
        lines.append('<p>Type: <span class="meta-type">participants</span></p>')
        if participant_variables:
            vars_str = ",".join(sorted(participant_variables))
            lines.append(
                f'<p>Variables: <span class="meta-variables">{vars_str}</span></p>'
            )

    # Embed code mapping so re-import can reverse sanitization.
    # Format: "original=sanitized,original2=sanitized2,..."
    if code_map:
        # Only include entries where original != sanitized (i.e., codes that changed)
        changed = {orig: san for orig, san in code_map.items() if orig != san}
        if changed:
            map_str = ",".join(f"{orig}={san}" for orig, san in sorted(changed.items()))
            lines.append(f'<p>CodeMap: <span class="meta-codemap">{map_str}</span></p>')

    lines.append(
        f'<p>Generated: <span class="meta-generated">{datetime.now().strftime("%Y-%m-%d %H:%M")}</span></p>'
    )
    lines.append("</div>")

    return "\n".join(lines)


# Columns LimeSurvey 6 writes on every row of these sections (section -> column -> value).
_LS6_ROW_COLUMNS = {
    "questions": {"same_script": "0"},
    "subquestions": {"other": "N", "mandatory": "N", "encrypted": "N", "same_script": "0"},
    "question_l10ns": {"script": ""},
}


def _add_ls6_columns(root) -> None:
    """Give the rows the structural columns of a LimeSurvey 6 export (DBVersion 636); a value
    a row already has is kept."""
    for section, columns in _LS6_ROW_COLUMNS.items():
        for row in root.findall(f"{section}/rows/row"):
            for name, value in columns.items():
                if row.find(name) is None:
                    ET.SubElement(row, name).text = value


def _strip_invalid_xml_chars(root) -> None:
    """Drop characters XML 1.0 forbids (pasted Word/PDF text has them); the .lss would not import otherwise."""
    for element in root.iter():
        element.text = strip_invalid_xml_chars(element.text)
        element.tail = strip_invalid_xml_chars(element.tail)
        for key, value in element.attrib.items():
            element.attrib[key] = strip_invalid_xml_chars(value)


def _group_texts(template_path, languages):
    """Group name and description of a template file in each language (Study.OriginalName /
    Study.Description, translations from I18n); {} when the file cannot be read."""
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    study, i18n = data.get("Study", {}), data.get("I18n", {})
    fallback_name = data.get("TaskName", os.path.splitext(os.path.basename(template_path))[0])
    return {
        lang: {
            "name": _text_in(study.get("OriginalName", fallback_name), lang, i18n, "Study.OriginalName"),
            "description": _text_in(study.get("Description", ""), lang, i18n, "Study.Description"),
        }
        for lang in languages
    }


def generate_lss(
    json_files,
    output_path=None,
    language="en",
    languages=None,
    base_language=None,
    matrix_mode=True,
    matrix_global=True,
):
    """Generate a LimeSurvey Structure (.lss) file from PRISM template files (Quick Export).

    The same builder as the Survey Customizer's export (generate_lss_from_customization), fed
    from the files by the Customizer's own loader, so both give the same structure for the
    same data.

    Args:
        json_files (list): Paths, or dicts with:
            - path (str): the template file
            - include (list, optional): the keys to export (default: all)
            - matrix / matrix_global (bool, optional): override the function-level values for this file
            - run (int, optional): run number for multi-run surveys; codes get a "run02"
              style suffix from run 2 on
            Unreadable files are skipped. Several files get the survey title "Combined Survey".
        output_path (str, optional): Path to write the .lss file. If None, returns the XML string.
        language, languages, base_language: as in generate_lss_from_customization.
        matrix_mode, matrix_global (bool): matrix grouping defaults (Customizer defaults: on).

    Returns:
        str: The XML content if output_path is None, else the output path.
    """
    from src.survey_customizer import build_customizer_groups

    if languages is None:
        languages = [language]
    groups = []
    for item in json_files:
        entry = {"path": item} if isinstance(item, str) else item
        if not isinstance(entry, dict) or not entry.get("path"):
            continue
        include = entry.get("include")
        if include is not None and not include:
            continue  # nothing ticked for this file: nothing to export
        for group in build_customizer_groups(
            [{"path": entry["path"], "includeQuestions": include or []}], language
        ):
            group["order"] = len(groups)
            group["matrix"] = entry.get("matrix", matrix_mode)
            group["matrixGlobal"] = entry.get("matrix_global", matrix_global)
            if entry.get("run"):
                for question in group["questions"]:
                    question["runNumber"] = entry["run"]
            group["texts"] = _group_texts(entry["path"], languages)
            groups.append(group)
    return generate_lss_from_customization(
        groups,
        output_path,
        language=language,
        languages=languages,
        base_language=base_language,
        matrix_mode=matrix_mode,
        matrix_global=matrix_global,
        survey_title="Combined Survey" if len(json_files) > 1 else None,
    )


def generate_lss_from_customization(
    groups,
    output_path=None,
    language="en",
    languages=None,
    base_language=None,
    matrix_mode=True,
    matrix_global=True,
    survey_title=None,
    ls_settings=None,
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
        matrix_mode (bool): Group questions with identical options into matrices.
        matrix_global (bool): Group all identical options, not just consecutive.
        survey_title (str, optional): Custom title for the survey.
        ls_settings (dict, optional): LimeSurvey survey-level settings from the UI.

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

    db_version = "636"

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

    # Localization tables
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
    aid_counter = 1

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
        group_data = {
            "gid": gid,
            "sid": sid,
            "group_order": str(group_sort_order),
            "randomization_group": "",
            "grelevance": "",
        }
        add_row(groups_rows, group_data)

        for lang in languages:
            add_row(
                group_l10ns_rows,
                {
                    "id": str(l10n_id_counter),
                    "gid": gid,
                    "group_name": group.get("texts", {}).get(lang, {}).get("name", group_name),
                    "description": group.get("texts", {}).get(lang, {}).get("description", group_desc),
                    "language": lang,
                    "sid": sid,
                },
            )
            l10n_id_counter += 1
        # --- Add hidden metadata question for this questionnaire ---
        meta_cells = []  # filled by _fill_metadata_cells after the questions
        code_map = {}  # original PRISM code -> LimeSurvey column it is written to
        metadata_kwargs = {}
        source_file = None
        if enabled_questions:
            source_file = enabled_questions[0].get("sourceFile")

        if source_file:
            file_metadata = _extract_single_file_metadata(source_file, base_language)
            if file_metadata:
                meta_qid = str(qid_counter)
                qid_counter += 1
                meta_q_code = f"PRISMMETAg{group_sort_order}"

                # Detect participants group for authoritative PRISMMETA signal
                is_participants_group = (
                    source_file and "participants" in source_file.lower()
                )
                participant_var_codes = (
                    [
                        q.get("questionCode", "")
                        for q in enabled_questions
                        if q.get("questionCode")
                    ]
                    if is_participants_group
                    else None
                )

                metadata_kwargs = {
                    "meta": file_metadata,
                    "is_participants": is_participants_group,
                    "participant_variables": participant_var_codes,
                }

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
                meta_cells.append(add_row(
                    question_attributes_rows,
                    {
                        "qaid": str(qaid_counter),
                        "qid": meta_qid,
                        "attribute": "equation",
                        "value": "",
                        "language": "",
                    },
                ).find("value"))
                qaid_counter += 1

                for lang in languages:
                    meta_cells.append(add_row(
                        question_l10ns_rows,
                        {
                            "id": str(l10n_id_counter),
                            "qid": meta_qid,
                            "question": "",
                            "help": "",
                            "language": lang,
                        },
                    ).find("question"))
                    l10n_id_counter += 1
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
            has_other = item_has_other(orig)

            # Check for template-level MatrixGrouping flag (passed from loader)
            # This is more reliable than re-reading the file
            matrix_grouping_disabled = q.get("matrixGroupingDisabled", False)

            # Additional check: if the source file is participants.json, never group
            source_file = q.get("sourceFile", "")
            is_participants = "participants" in source_file.lower()

            return (
                matrix_grouping_disabled  # Template explicitly disables matrix grouping
                or is_participants  # Participants/demographics should never be grouped
                or input_type == "dropdown"
                or input_type == "numerical"
                or input_type == "text"
                or input_type == "calculated"
                or has_other  # Questions with "Other" option shouldn't be grouped
            )

        if group.get("matrix", matrix_mode):
            if group.get("matrixGlobal", matrix_global):
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
                logger.warning("Missing sourceFile or questionCode for question")
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
                q_code,
                source_file,
                source_q_data is not None,
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

                # Matrix parent question text: toolOverrides > Study.Instructions > fallback
                _fallback_texts = {
                    "en": "Please answer the following questions:",
                    "de": "Bitte beantworten Sie die folgenden Fragen:",
                }
                source_file = first_q.get("sourceFile")
                template_data = (
                    _source_file_cache.get(source_file) if source_file else None
                )
                study_instructions = (
                    (template_data or {}).get("Study", {}).get("Instructions", {})
                )
                source_i18n = (template_data or {}).get("I18n", {})
                custom_matrix_text = first_q.get("toolOverrides", {}).get(
                    "matrixQuestionText"
                )

                def _get_matrix_text(lang):
                    if custom_matrix_text:
                        return str(custom_matrix_text)
                    if isinstance(study_instructions, dict) and study_instructions:
                        text = _text_in(
                            study_instructions, lang, source_i18n, "Study.Instructions"
                        )
                        if text:
                            return text
                    elif isinstance(study_instructions, str) and study_instructions:
                        return study_instructions
                    return _fallback_texts.get(lang, _fallback_texts["en"])

                any_mandatory = any(q.get("mandatory", True) for q in q_group)

                q_data_row = {
                    "qid": qid,
                    "parent_qid": "0",
                    "sid": sid,
                    "gid": gid,
                    "type": q_type,
                    "title": matrix_title,
                    "other": "N",
                    "mandatory": "Y" if any_mandatory else "N",
                    "question_order": str(q_sort_order),
                    "scale_id": "0",
                    "same_default": "0",
                    "relevance": relevance,
                }
                add_row(questions_rows, q_data_row)

                for lang in languages:
                    m_text = _get_matrix_text(lang)
                    add_row(
                        question_l10ns_rows,
                        {
                            "id": str(l10n_id_counter),
                            "qid": qid,
                            "question": m_text,
                            "help": "",
                            "language": lang,
                            "sid": sid,
                        },
                    )
                    l10n_id_counter += 1
                # Add Subquestions
                sub_sort = 0
                used_subq_codes = set()  # Track codes within this matrix
                for q in q_group:
                    sub_sort += 1
                    sub_qid = str(qid_counter)
                    qid_counter += 1

                    q_code = q.get("questionCode", f"SQ{sub_sort}")
                    run_num = q.get("runNumber")
                    # Sanitize subquestion code to fit 5-char limit
                    sub_q_code = _sanitize_subquestion_code(
                        q_code, used_subq_codes, run_num, sub_sort
                    )
                    used_subq_codes.add(sub_q_code)
                    code_map[q_code] = f"{matrix_title}[{sub_q_code}]"

                    sub_source_data = _get_question_from_source(q)
                    sub_orig = (
                        sub_source_data
                        if sub_source_data
                        else q.get("originalData", {})
                    )
                    sub_i18n = _get_i18n_from_source(q)

                    sub_q_row = {
                        "qid": sub_qid,
                        "parent_qid": qid,
                        "sid": sid,
                        "gid": gid,
                        "type": "T",
                        "title": sub_q_code,
                        "question_order": str(sub_sort),
                        "scale_id": "0",
                        "same_default": "0",
                        "relevance": "1",
                    }
                    add_row(subquestions_rows, sub_q_row)

                    for lang in languages:
                        sq_desc = _text_in(
                            sub_orig.get("Description", q_code),
                            lang,
                            sub_i18n,
                            f"{q_code}.Description",
                        )
                        if not sq_desc:
                            sq_desc = q.get("description", q_code)
                        add_row(
                            question_l10ns_rows,
                            {
                                "id": str(l10n_id_counter),
                                "qid": sub_qid,
                                "question": sq_desc,
                                "help": "",
                                "language": lang,
                            },
                        )
                        l10n_id_counter += 1
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

                        ans_row = {
                            "aid": str(aid_counter),
                            "qid": qid,
                            "code": sanitized_code,
                            "sortorder": str(sort_ans),
                            "assessment_value": "0",
                            "scale_id": "0",
                        }
                        add_row(answers_rows, ans_row)

                        for lang in languages:
                            a_text = sanitize_answer_text(
                                _text_in(
                                    answer_text,
                                    lang,
                                    matrix_i18n,
                                    f"{first_q_code}.Levels.{code}",
                                )
                            )
                            add_row(
                                answer_l10ns_rows,
                                {
                                    "id": str(l10n_id_counter),
                                    "aid": str(aid_counter),
                                    "answer": a_text,
                                    "language": lang,
                                },
                            )
                            l10n_id_counter += 1
                        aid_counter += 1
            else:
                # Single Question
                q = first_q
                q_code = q.get("questionCode", f"Q{q_sort_order}")
                run_num = q.get("runNumber")
                final_code = _apply_run_suffix(q_code, run_num)
                code_map[q_code] = final_code

                orig = source_q_data if source_q_data else q.get("originalData", {})
                i18n_data = _get_i18n_from_source(q)
                is_mandatory = q.get("mandatory", True)

                # Apply toolOverrides if present
                tool_ov = q.get("toolOverrides", {})

                # Determine Type — use toolOverride first, then auto-detect
                if tool_ov.get("questionType"):
                    q_type = "L" if tool_ov["questionType"] in LS_ROW_TYPES else tool_ov["questionType"]
                    extra_attrs = {}
                else:
                    q_type, extra_attrs = _determine_ls_question_type(
                        orig, bool(levels)
                    )

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
                _ov_to_ls = {override: attribute for attribute, override in LS_DESIGN_ATTRIBUTES.items()}
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
                has_other = item_has_other(orig)

                q_data_row = {
                    "qid": qid,
                    "parent_qid": "0",
                    "sid": sid,
                    "gid": gid,
                    "type": q_type,
                    "title": final_code,
                    "other": "Y" if has_other else "N",
                    "mandatory": "Y" if is_mandatory else "N",
                    "question_order": str(q_sort_order),
                    "scale_id": "0",
                    "same_default": "0",
                    "relevance": relevance,
                }
                add_row(questions_rows, q_data_row)

                for lang in languages:
                    desc = tool_ov.get("questionText") or _text_in(
                        orig.get("Description", q_code),
                        lang,
                        i18n_data,
                        f"{q_code}.Description",
                    )
                    if not desc:
                        desc = q.get("description", q_code)
                    desc = _apply_ls_styling(desc)
                    h_text = tool_ov.get("helpText") or _text_in(
                        item_help(orig), lang, i18n_data, f"{q_code}.Help"
                    )
                    add_row(
                        question_l10ns_rows,
                        {
                            "id": str(l10n_id_counter),
                            "qid": qid,
                            "question": desc,
                            "help": h_text,
                            "language": lang,
                            "sid": sid,
                        },
                    )
                    l10n_id_counter += 1
                # Add question attributes
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

                # Add Answers
                if q_type in LS_FIXED_ANSWER_TYPES:
                    pass  # LimeSurvey defines these options itself
                elif levels:
                    sort_ans = 0
                    used_answer_codes = set()
                    for code, answer_text in levels.items():
                        if code.lower() == "other" and has_other:
                            continue
                        sort_ans += 1
                        sanitized_code = _sanitize_answer_code(code, used_answer_codes)
                        used_answer_codes.add(sanitized_code)

                        ans_row = {
                            "aid": str(aid_counter),
                            "qid": qid,
                            "code": sanitized_code,
                            "sortorder": str(sort_ans),
                            "assessment_value": "0",
                            "scale_id": "0",
                        }
                        add_row(answers_rows, ans_row)

                        for lang in languages:
                            a_text = sanitize_answer_text(
                                _text_in(
                                    answer_text,
                                    lang,
                                    i18n_data,
                                    f"{q_code}.Levels.{code}",
                                )
                            )
                            add_row(
                                answer_l10ns_rows,
                                {
                                    "id": str(l10n_id_counter),
                                    "aid": str(aid_counter),
                                    "answer": a_text,
                                    "language": lang,
                                },
                            )
                            l10n_id_counter += 1
                        aid_counter += 1
                else:
                    logger.warning("No levels for %s", final_code)

        _fill_metadata_cells(meta_cells, metadata_kwargs, code_map)

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
        "assessments": "N",  # Disable assessment mode to avoid {score=N} badges on answers
    }
    if additional_languages:
        survey_settings["additional_languages"] = " ".join(additional_languages)

    # Merge LimeSurvey survey-level settings from the UI
    if ls_settings:
        survey_level_fields = {
            "showsurveypolicynotice": ls_settings.get("showDataPolicy", "0"),
            "navigationdelay": ls_settings.get("navigationDelay", "0"),
            "questionindex": ls_settings.get("questionIndex", "0"),
            "showgroupinfo": ls_settings.get("showGroupInfo", "B"),
            "showqnumcode": ls_settings.get("showQnumCode", "X"),
            "shownoanswer": ls_settings.get("showNoAnswer", "Y"),
            "showxquestions": ls_settings.get("showXQuestions", "Y"),
            "showwelcome": ls_settings.get("showWelcome", "Y"),
            "allowprev": ls_settings.get("allowPrev", "N"),
            "nokeyboard": ls_settings.get("noKeyboard", "N"),
            "showprogress": ls_settings.get("showProgress", "Y"),
            "printanswers": ls_settings.get("printAnswers", "N"),
            "publicstatistics": ls_settings.get("publicStatistics", "N"),
            "publicgraphs": ls_settings.get("publicGraphs", "N"),
            "autoredirect": ls_settings.get("autoRedirect", "N"),
        }
        survey_settings.update(survey_level_fields)

    add_row(surveys_rows, survey_settings)

    # --- Survey Language Settings ---
    first_group = sorted_groups[0] if sorted_groups else {}

    def title_in(lang):
        return survey_title or first_group.get("texts", {}).get(lang, {}).get("name") \
            or first_group.get("name", "Custom Survey")

    for lang in languages:
        lang_row = {
            "surveyls_survey_id": sid,
            "surveyls_language": lang,
            "surveyls_title": title_in(lang),
            "surveyls_description": "",
            "surveyls_welcometext": (
                ls_settings.get("welcomeText", "") if ls_settings else ""
            ),
            "surveyls_endtext": ls_settings.get("endText", "") if ls_settings else "",
            "surveyls_url": ls_settings.get("endUrl", "") if ls_settings else "",
            "surveyls_urldescription": (
                ls_settings.get("endUrlDescription", "") if ls_settings else ""
            ),
            "surveyls_policy_notice": (
                ls_settings.get("policyNotice", "") if ls_settings else ""
            ),
            "surveyls_policy_error": (
                ls_settings.get("policyError", "") if ls_settings else ""
            ),
            "surveyls_policy_notice_label": (
                ls_settings.get("policyCheckboxLabel", "") if ls_settings else ""
            ),
        }
        add_row(surveys_lang_rows, lang_row)

    # --- Themes (required by LimeSurvey) ---
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

    # --- Themes Inherited (required by LimeSurvey) ---
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
    _add_ls6_columns(root)
    _strip_invalid_xml_chars(root)
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
