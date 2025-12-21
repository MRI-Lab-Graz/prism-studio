#!/usr/bin/env python3
"""
Excel to JSON Library Converter
-------------------------------
Converts a data dictionary (Excel) into a library of PRISM-compliant JSON sidecars.

Usage:
    python scripts/excel_to_library.py --excel metadata.xlsx --output survey_library

Excel Format Requirements:
    - Column 1: Variable Name (e.g., ADS1, BDI_1)
    - Column 2: Question/Description (e.g., "I feel sad")
    - Column 3: Scale/Levels (e.g., "1=Not at all; 2=Very much")

The script groups variables into surveys based on their prefix (e.g., ADS1 -> ads).
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd

# Add project root to path to import from src
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from src.converters.excel_base import (
        find_column_idx,
        clean_variable_name,
        parse_levels,
        detect_language,
    )
except ImportError:
    # Fallback for different execution contexts
    sys.path.append(os.path.join(os.getcwd(), "src"))
    from converters.excel_base import (
        find_column_idx,
        clean_variable_name,
        parse_levels,
        detect_language,
    )

# Standard metadata for known instruments
# You can extend this dictionary or load it from an external file
SURVEY_METADATA = {
    "ads": {
        "OriginalName": "Allgemeine Depressionsskala (ADS)",
        "Citation": "Hautzinger, M., & Bailer, M. (1993). Allgemeine Depressionsskala (ADS). Göttingen: Hogrefe.",
    },
    "bdi": {
        "OriginalName": "Beck Depression Inventory (BDI-II)",
        "Citation": "Beck, A. T., Steer, R. A., & Brown, G. K. (1996). Manual for the Beck Depression Inventory-II. San Antonio, TX: Psychological Corporation.",
    },
    # Add more here...
}


ID_ALIASES = {"item_id", "id", "code", "variable", "var", "name", "variablename", "itemname"}
QUESTION_ALIASES = {"item", "question", "description", "text", "itemdescription"}
SCALE_ALIASES = {"scale", "scaling", "levels", "options", "answers"}
GROUP_ALIASES = {"group", "survey", "section", "domain", "category"}
ALIAS_ALIASES = {"alias_of", "alias", "canonical", "duplicate_of", "merge_into"}
SESSION_ALIASES = {"session", "visit", "wave", "timepoint"}
RUN_ALIASES = {"run", "repeat"}

# Item-level optional schema fields
QUESTION_EN_ALIASES = {"question_en", "description_en", "text_en", "label_en"}
QUESTION_DE_ALIASES = {"question_de", "description_de", "text_de", "label_de"}
SCALE_EN_ALIASES = {"scale_en", "levels_en", "options_en", "answers_en"}
SCALE_DE_ALIASES = {"scale_de", "levels_de", "options_de", "answers_de"}
UNITS_ALIASES = {"units", "unit"}
DTYPE_ALIASES = {"datatype", "data_type", "type"}
MIN_ALIASES = {"minvalue", "min", "minimum"}
MAX_ALIASES = {"maxvalue", "max", "maximum"}
WARN_MIN_ALIASES = {"warnminvalue", "warn_min", "warnminimum"}
WARN_MAX_ALIASES = {"warnmaxvalue", "warn_max", "warnmaximum"}
ALLOWED_ALIASES = {"allowedvalues", "allowed_values", "allowed"}
TERMURL_ALIASES = {"termurl", "term_url"}
RELEVANCE_ALIASES = {"relevance", "logic", "condition", "equation"}

# Instrument/task-level metadata (repeatable per row; first non-empty per group wins)
ORIGINAL_NAME_ALIASES = {
    "originalname",
    "original_name",
    "instrument_name",
    "survey_name",
    "task_original_name",
}
ORIGINAL_NAME_EN_ALIASES = {"originalname_en", "original_name_en"}
ORIGINAL_NAME_DE_ALIASES = {"originalname_de", "original_name_de"}
SHORT_NAME_ALIASES = {"shortname", "short_name", "abbrev", "abbreviation"}
VERSION_ALIASES = {"version", "instrumentversion", "instrument_version"}
VERSION_EN_ALIASES = {"version_en"}
VERSION_DE_ALIASES = {"version_de"}
CITATION_ALIASES = {"citation", "reference", "doi"}
CONSTRUCT_ALIASES = {"construct", "domain", "measure"}
INSTRUCTIONS_ALIASES = {"instructions", "instruction", "taskinstructions", "task_instructions"}
INSTRUCTIONS_EN_ALIASES = {"instructions_en", "taskinstructions_en"}
INSTRUCTIONS_DE_ALIASES = {"instructions_de", "taskinstructions_de"}
STUDY_DESC_EN_ALIASES = {"study_description_en", "studydescription_en", "description_en"}
STUDY_DESC_DE_ALIASES = {"study_description_de", "studydescription_de", "description_de"}
KEYWORDS_ALIASES = {"keywords", "tags"}

# Technical/I18n settings
RESPONDENT_ALIASES = {"respondent"}
ADMIN_METHOD_ALIASES = {
    "administrationmethod",
    "administration_method",
    "administration",
}
SOFTWARE_PLATFORM_ALIASES = {"softwareplatform", "software_platform", "platform", "software"}
SOFTWARE_VERSION_ALIASES = {"softwareversion", "software_version"}
I18N_LANGUAGES_ALIASES = {"languages", "i18n_languages", "i18nlanguages"}
I18N_DEFAULT_LANGUAGE_ALIASES = {"defaultlanguage", "default_language"}
I18N_TRANSLATION_METHOD_ALIASES = {"translationmethod", "translation_method"}


def extract_prefix(var_name):
    """
    Extract prefix from variable name to group surveys.
    Example: ADS1 -> ADS, BDI_1 -> BDI
    """
    match = re.match(r"([a-zA-Z]+)", str(var_name))
    if match:
        return match.group(1)
    return "unknown"


def _clean_cell(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    return s if s else None


def _parse_float(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _parse_allowed_values(cell):
    """Parse AllowedValues: supports '1-5', '1;2;3', '1,2,3', or '1=Never;2=Often'."""
    s = _clean_cell(cell)
    if s is None:
        return None

    # Range shorthand: "1-10" -> [1..10] (guard against huge expansions)
    m_range = re.match(r"^\s*([-+]?\d+)\s*-\s*([-+]?\d+)\s*$", s)
    if m_range:
        a = int(m_range.group(1))
        b = int(m_range.group(2))
        if b >= a and (b - a) <= 200:
            return list(range(a, b + 1))

    # "1=foo; 2=bar" -> allowed [1,2]
    if "=" in s:
        keys = []
        for part in re.split(r"[;,]\s*", s):
            if "=" not in part:
                continue
            k, _ = part.split("=", 1)
            k = k.strip()
            if not k:
                continue
            n = _parse_float(k)
            if n is None:
                keys.append(k)
            else:
                keys.append(int(n) if n.is_integer() else n)
        return keys or None

    parts = [p.strip() for p in re.split(r"[;,]\s*", s) if p.strip()]
    if not parts:
        return None

    out = []
    for p in parts:
        n = _parse_float(p)
        if n is None:
            out.append(p)
        else:
            out.append(int(n) if n.is_integer() else n)
    return out or None


def process_excel(
    excel_file, output_dir, participants_prefix=None, participants_output=None
):
    print(f"Loading metadata from {excel_file}...")
    try:
        df_meta = pd.read_excel(excel_file, header=None)
    except Exception as e:
        print(f"Error reading Excel file: {e}")
        sys.exit(1)

    # Detect header row and column indices
    header_row = [str(v) for v in df_meta.iloc[0].tolist()]

    id_idx = find_column_idx(header_row, ID_ALIASES)
    question_idx = find_column_idx(header_row, QUESTION_ALIASES)
    scale_idx = find_column_idx(header_row, SCALE_ALIASES)
    group_idx = find_column_idx(header_row, GROUP_ALIASES)
    alias_idx = find_column_idx(header_row, ALIAS_ALIASES)
    session_idx = find_column_idx(header_row, SESSION_ALIASES)
    run_idx = find_column_idx(header_row, RUN_ALIASES)

    # Optional item-level and i18n columns
    question_en_idx = find_column_idx(header_row, QUESTION_EN_ALIASES)
    question_de_idx = find_column_idx(header_row, QUESTION_DE_ALIASES)
    scale_en_idx = find_column_idx(header_row, SCALE_EN_ALIASES)
    scale_de_idx = find_column_idx(header_row, SCALE_DE_ALIASES)
    units_idx = find_column_idx(header_row, UNITS_ALIASES)
    dtype_idx = find_column_idx(header_row, DTYPE_ALIASES)
    min_idx = find_column_idx(header_row, MIN_ALIASES)
    max_idx = find_column_idx(header_row, MAX_ALIASES)
    warn_min_idx = find_column_idx(header_row, WARN_MIN_ALIASES)
    warn_max_idx = find_column_idx(header_row, WARN_MAX_ALIASES)
    allowed_idx = find_column_idx(header_row, ALLOWED_ALIASES)
    termurl_idx = find_column_idx(header_row, TERMURL_ALIASES)
    relevance_idx = find_column_idx(header_row, RELEVANCE_ALIASES)

    # Optional instrument/task-level metadata
    original_name_idx = find_column_idx(header_row, ORIGINAL_NAME_ALIASES)
    original_name_en_idx = find_column_idx(header_row, ORIGINAL_NAME_EN_ALIASES)
    original_name_de_idx = find_column_idx(header_row, ORIGINAL_NAME_DE_ALIASES)
    short_name_idx = find_column_idx(header_row, SHORT_NAME_ALIASES)
    version_idx = find_column_idx(header_row, VERSION_ALIASES)
    version_en_idx = find_column_idx(header_row, VERSION_EN_ALIASES)
    version_de_idx = find_column_idx(header_row, VERSION_DE_ALIASES)
    citation_idx = find_column_idx(header_row, CITATION_ALIASES)
    construct_idx = find_column_idx(header_row, CONSTRUCT_ALIASES)
    instructions_idx = find_column_idx(header_row, INSTRUCTIONS_ALIASES)
    instructions_en_idx = find_column_idx(header_row, INSTRUCTIONS_EN_ALIASES)
    instructions_de_idx = find_column_idx(header_row, INSTRUCTIONS_DE_ALIASES)
    study_desc_en_idx = find_column_idx(header_row, STUDY_DESC_EN_ALIASES)
    study_desc_de_idx = find_column_idx(header_row, STUDY_DESC_DE_ALIASES)
    keywords_idx = find_column_idx(header_row, KEYWORDS_ALIASES)
    respondent_idx = find_column_idx(header_row, RESPONDENT_ALIASES)
    admin_method_idx = find_column_idx(header_row, ADMIN_METHOD_ALIASES)
    platform_idx = find_column_idx(header_row, SOFTWARE_PLATFORM_ALIASES)
    platform_version_idx = find_column_idx(header_row, SOFTWARE_VERSION_ALIASES)
    i18n_languages_idx = find_column_idx(header_row, I18N_LANGUAGES_ALIASES)
    i18n_default_lang_idx = find_column_idx(header_row, I18N_DEFAULT_LANGUAGE_ALIASES)
    i18n_translation_method_idx = find_column_idx(
        header_row, I18N_TRANSLATION_METHOD_ALIASES
    )

    header_detected = any(
        idx is not None
        for idx in [
            id_idx,
            question_idx,
            scale_idx,
            group_idx,
            alias_idx,
            session_idx,
            run_idx,
            question_en_idx,
            question_de_idx,
            scale_en_idx,
            scale_de_idx,
            units_idx,
            dtype_idx,
            min_idx,
            max_idx,
            warn_min_idx,
            warn_max_idx,
            allowed_idx,
            termurl_idx,
            relevance_idx,
            original_name_idx,
            original_name_en_idx,
            original_name_de_idx,
            short_name_idx,
            version_idx,
            version_en_idx,
            version_de_idx,
            citation_idx,
            construct_idx,
            instructions_idx,
            instructions_en_idx,
            instructions_de_idx,
            study_desc_en_idx,
            study_desc_de_idx,
            keywords_idx,
            respondent_idx,
            admin_method_idx,
            platform_idx,
            platform_version_idx,
            i18n_languages_idx,
            i18n_default_lang_idx,
            i18n_translation_method_idx,
        ]
    )
    if header_detected:
        print("Detected header row (named columns). Using column names.")
        data_rows = df_meta.iloc[1:]
    else:
        data_rows = df_meta
        # Fallback to positional columns
        id_idx = 0
        question_idx = 1
        scale_idx = 2
        group_idx = 3
        alias_idx = 4
        session_idx = 5
        run_idx = 6

    surveys = {}
    surveys_meta = {}

    def get_val(row, idx):
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    print("Processing metadata...")
    for _, row in data_rows.iterrows():
        var_name = clean_variable_name(get_val(row, id_idx))
        question = get_val(row, question_idx)
        scale = get_val(row, scale_idx)
        question_en = get_val(row, question_en_idx)
        question_de = get_val(row, question_de_idx)
        scale_en = get_val(row, scale_en_idx)
        scale_de = get_val(row, scale_de_idx)
        manual_group = get_val(row, group_idx)
        alias_of = get_val(row, alias_idx)
        session_hint = get_val(row, session_idx)
        run_hint = get_val(row, run_idx)

        units = get_val(row, units_idx)
        dtype = get_val(row, dtype_idx)
        min_v = get_val(row, min_idx)
        max_v = get_val(row, max_idx)
        warn_min_v = get_val(row, warn_min_idx)
        warn_max_v = get_val(row, warn_max_idx)
        allowed_v = get_val(row, allowed_idx)
        term_url = get_val(row, termurl_idx)
        relevance = get_val(row, relevance_idx)

        original_name = get_val(row, original_name_idx)
        original_name_en = get_val(row, original_name_en_idx)
        original_name_de = get_val(row, original_name_de_idx)
        short_name = get_val(row, short_name_idx)
        version = get_val(row, version_idx)
        version_en = get_val(row, version_en_idx)
        version_de = get_val(row, version_de_idx)
        citation = get_val(row, citation_idx)
        construct = get_val(row, construct_idx)
        instructions = get_val(row, instructions_idx)
        instructions_en = get_val(row, instructions_en_idx)
        instructions_de = get_val(row, instructions_de_idx)
        study_desc_en = get_val(row, study_desc_en_idx)
        study_desc_de = get_val(row, study_desc_de_idx)
        keywords = get_val(row, keywords_idx)
        respondent = get_val(row, respondent_idx)
        admin_method = get_val(row, admin_method_idx)
        platform = get_val(row, platform_idx)
        platform_version = get_val(row, platform_version_idx)
        i18n_languages = get_val(row, i18n_languages_idx)
        i18n_default_lang = get_val(row, i18n_default_lang_idx)
        i18n_translation_method = get_val(row, i18n_translation_method_idx)

        if var_name.lower() == "nan" or not var_name:
            continue

        if pd.notna(manual_group) and str(manual_group).strip():
            manual_clean = clean_variable_name(manual_group).lower()
            if manual_clean in {"disable", "skip", "omit", "ignore"}:
                continue  # Explicitly skip this item
            prefix = manual_clean
        else:
            prefix = extract_prefix(var_name).lower()

        if prefix not in surveys:
            surveys[prefix] = {}
        if prefix not in surveys_meta:
            surveys_meta[prefix] = {}

        # Capture per-instrument metadata (first non-empty value per group wins)
        meta = surveys_meta[prefix]
        if _clean_cell(original_name) and "OriginalName" not in meta:
            meta["OriginalName"] = _clean_cell(original_name)
        if _clean_cell(original_name_en) and "OriginalName_en" not in meta:
            meta["OriginalName_en"] = _clean_cell(original_name_en)
        if _clean_cell(original_name_de) and "OriginalName_de" not in meta:
            meta["OriginalName_de"] = _clean_cell(original_name_de)
        if _clean_cell(short_name) and "ShortName" not in meta:
            meta["ShortName"] = _clean_cell(short_name)
        if _clean_cell(version) and "Version" not in meta:
            meta["Version"] = _clean_cell(version)
        if _clean_cell(version_en) and "Version_en" not in meta:
            meta["Version_en"] = _clean_cell(version_en)
        if _clean_cell(version_de) and "Version_de" not in meta:
            meta["Version_de"] = _clean_cell(version_de)
        if _clean_cell(citation) and "Citation" not in meta:
            meta["Citation"] = _clean_cell(citation)
        if _clean_cell(construct) and "Construct" not in meta:
            meta["Construct"] = _clean_cell(construct)

        if _clean_cell(study_desc_en) and "StudyDescription_en" not in meta:
            meta["StudyDescription_en"] = _clean_cell(study_desc_en)
        if _clean_cell(study_desc_de) and "StudyDescription_de" not in meta:
            meta["StudyDescription_de"] = _clean_cell(study_desc_de)

        # Subject-facing instructions (support one-language or EN/DE columns)
        if _clean_cell(instructions) and "Instructions" not in meta:
            meta["Instructions"] = _clean_cell(instructions)
        if _clean_cell(instructions_en) and "Instructions_en" not in meta:
            meta["Instructions_en"] = _clean_cell(instructions_en)
        if _clean_cell(instructions_de) and "Instructions_de" not in meta:
            meta["Instructions_de"] = _clean_cell(instructions_de)

        if _clean_cell(keywords) and "Keywords" not in meta:
            meta["Keywords"] = [k.strip() for k in re.split(r"[;,]", str(keywords)) if k.strip()]

        if _clean_cell(respondent) and "Respondent" not in meta:
            meta["Respondent"] = _clean_cell(respondent)
        if _clean_cell(admin_method) and "AdministrationMethod" not in meta:
            meta["AdministrationMethod"] = _clean_cell(admin_method)
        if _clean_cell(platform) and "SoftwarePlatform" not in meta:
            meta["SoftwarePlatform"] = _clean_cell(platform)
        if _clean_cell(platform_version) and "SoftwareVersion" not in meta:
            meta["SoftwareVersion"] = _clean_cell(platform_version)

        if _clean_cell(i18n_languages) and "I18nLanguages" not in meta:
            # Accept: "en,de" or "['en','de']" (keep it simple)
            langs = [k.strip() for k in re.split(r"[;,]", str(i18n_languages)) if k.strip()]
            meta["I18nLanguages"] = langs
        if _clean_cell(i18n_default_lang) and "I18nDefaultLanguage" not in meta:
            meta["I18nDefaultLanguage"] = _clean_cell(i18n_default_lang)
        if _clean_cell(i18n_translation_method) and "I18nTranslationMethod" not in meta:
            meta["I18nTranslationMethod"] = _clean_cell(i18n_translation_method)

        description_default = str(question).strip() if pd.notna(question) else var_name
        description_default = re.sub(r"\[.*?\]", "", description_default).strip()

        q_en = _clean_cell(question_en)
        q_de = _clean_cell(question_de)
        q_en = re.sub(r"\[.*?\]", "", q_en).strip() if q_en else None
        q_de = re.sub(r"\[.*?\]", "", q_de).strip() if q_de else None

        # i18n template format: Description as {de,en}
        entry = {
            "Description": {
                "de": q_de or (description_default if detect_language([description_default]) == "de" else ""),
                "en": q_en or (description_default if detect_language([description_default]) == "en" else ""),
            }
        }

        if pd.notna(alias_of) and str(alias_of).strip():
            entry["AliasOf"] = clean_variable_name(alias_of)

        if pd.notna(session_hint) and str(session_hint).strip():
            session_clean = str(session_hint).strip().lower().replace(" ", "")
            session_clean = session_clean.replace("session", "ses-")
            session_clean = session_clean.replace("visit", "ses-")
            if session_clean in {"t1", "wave1", "visit1"}:
                session_clean = "ses-1"
            elif session_clean in {"t2", "wave2", "visit2"}:
                session_clean = "ses-2"
            elif session_clean in {"t3", "wave3", "visit3"}:
                session_clean = "ses-3"
            if not session_clean.startswith("ses-"):
                session_clean = f"ses-{session_clean}"
            entry["SessionHint"] = session_clean

        if pd.notna(run_hint) and str(run_hint).strip():
            run_clean = str(run_hint).strip().lower().replace(" ", "")
            if not run_clean.startswith("run-"):
                run_clean = f"run-{run_clean}"
            entry["RunHint"] = run_clean

        levels_default = parse_levels(scale)
        levels_en = parse_levels(scale_en)
        levels_de = parse_levels(scale_de)

        if levels_default or levels_en or levels_de:
            combined: dict[str, dict[str, str]] = {}
            # Merge by value code
            keys = set()
            for d in [levels_default, levels_en, levels_de]:
                if isinstance(d, dict):
                    keys.update([str(k) for k in d.keys()])
            default_guess = detect_language([description_default])
            for k in sorted(keys, key=lambda x: (len(x), x)):
                de_label = ""
                en_label = ""
                if levels_de and k in levels_de:
                    de_label = str(levels_de[k])
                if levels_en and k in levels_en:
                    en_label = str(levels_en[k])
                if levels_default and k in levels_default:
                    if default_guess == "de" and not de_label:
                        de_label = str(levels_default[k])
                    elif default_guess == "en" and not en_label:
                        en_label = str(levels_default[k])
                combined[str(k)] = {"de": de_label, "en": en_label}
            entry["Levels"] = combined

        if _clean_cell(units):
            entry["Units"] = _clean_cell(units)

        if _clean_cell(dtype):
            dt = str(dtype).strip().lower()
            if dt in {"string", "integer", "float"}:
                entry["DataType"] = dt

        min_num = _parse_float(min_v)
        max_num = _parse_float(max_v)
        warn_min_num = _parse_float(warn_min_v)
        warn_max_num = _parse_float(warn_max_v)
        if min_num is not None:
            entry["MinValue"] = min_num
        if max_num is not None:
            entry["MaxValue"] = max_num
        if warn_min_num is not None:
            entry["WarnMinValue"] = warn_min_num
        if warn_max_num is not None:
            entry["WarnMaxValue"] = warn_max_num

        allowed_vals = _parse_allowed_values(allowed_v)
        if allowed_vals:
            entry["AllowedValues"] = allowed_vals

        if _clean_cell(term_url):
            entry["TermURL"] = _clean_cell(term_url)

        if _clean_cell(relevance):
            entry["Relevance"] = _clean_cell(relevance)

        surveys[prefix][var_name] = entry

    # Generate JSON Sidecars
    print(f"Generating JSON sidecars in {output_dir}...")
    os.makedirs(output_dir, exist_ok=True)
    if participants_output and participants_output != output_dir:
        os.makedirs(participants_output, exist_ok=True)

    for prefix, variables in surveys.items():
        is_participants = (
            participants_prefix is not None and prefix == participants_prefix
        )

        meta = surveys_meta.get(prefix, {})

        # Decide default language and i18n settings.
        languages = []
        texts_for_lang: list[str] = []

        # Infer from template items and instructions
        for item in variables.values():
            if not isinstance(item, dict):
                continue
            desc = item.get("Description")
            if isinstance(desc, dict):
                for vv in desc.values():
                    if isinstance(vv, str) and vv.strip():
                        texts_for_lang.append(vv)
            levels = item.get("Levels")
            if isinstance(levels, dict):
                for vv in levels.values():
                    if isinstance(vv, dict):
                        for vvv in vv.values():
                            if isinstance(vvv, str) and vvv.strip():
                                texts_for_lang.append(vvv)

        if isinstance(meta.get("Instructions_en"), str) and meta.get("Instructions_en").strip():
            languages.append("en")
            texts_for_lang.append(meta["Instructions_en"])
        if isinstance(meta.get("Instructions_de"), str) and meta.get("Instructions_de").strip():
            languages.append("de")
            texts_for_lang.append(meta["Instructions_de"])

        # Respect explicit I18n columns if present
        if isinstance(meta.get("I18nLanguages"), list) and meta.get("I18nLanguages"):
            languages = list(
                dict.fromkeys(
                    [str(x).strip() for x in meta["I18nLanguages"] if str(x).strip()]
                )
            )
        else:
            # Default to bilingual template layout
            languages = list(dict.fromkeys(languages))
            if not languages:
                languages = ["de", "en"]

        default_language = None
        if isinstance(meta.get("I18nDefaultLanguage"), str) and meta.get("I18nDefaultLanguage").strip():
            default_language = meta["I18nDefaultLanguage"].strip()
        if not default_language:
            default_language = detect_language(texts_for_lang)

        if is_participants:
            sidecar = {}
        else:
            fallback_meta = SURVEY_METADATA.get(prefix, {})
            citation = meta.get("Citation") or fallback_meta.get("Citation", "")
            construct = meta.get("Construct") or fallback_meta.get("Domain", "")
            keywords = meta.get("Keywords") or fallback_meta.get("Keywords", [])

            # i18n-aware study fields
            original_name_de = meta.get("OriginalName_de") or ""
            original_name_en = meta.get("OriginalName_en") or ""
            if not original_name_de and not original_name_en:
                raw = meta.get("OriginalName") or fallback_meta.get(
                    "OriginalName", f"{prefix} Questionnaire"
                )
                if default_language == "de":
                    original_name_de = raw
                else:
                    original_name_en = raw

            version_de = meta.get("Version_de") or ""
            version_en = meta.get("Version_en") or ""
            if not version_de and not version_en:
                raw_version = meta.get("Version") or "1.0"
                if default_language == "de":
                    version_de = raw_version
                else:
                    version_en = raw_version

            study_desc_de = meta.get("StudyDescription_de") or ""
            study_desc_en = meta.get("StudyDescription_en") or ""
            if not study_desc_de and not study_desc_en:
                raw_desc = f"Imported {prefix} survey data"
                if default_language == "de":
                    study_desc_de = raw_desc
                else:
                    study_desc_en = raw_desc

            sidecar = {
                "Technical": {
                    "StimulusType": "Questionnaire",
                    "FileFormat": "tsv",
                    "SoftwarePlatform": meta.get("SoftwarePlatform", "Legacy/Imported"),
                    "SoftwareVersion": meta.get("SoftwareVersion", ""),
                    "Language": default_language,
                    "Respondent": meta.get("Respondent", "self"),
                    "AdministrationMethod": meta.get("AdministrationMethod", "paper"),
                    "ResponseType": ["paper-pencil"],
                },
                "I18n": {
                    "Languages": languages,
                    "DefaultLanguage": default_language,
                    "TranslationMethod": meta.get("I18nTranslationMethod", ""),
                },
                "Study": {
                    "TaskName": prefix,
                    "OriginalName": {"de": original_name_de, "en": original_name_en},
                    "ShortName": meta.get("ShortName", ""),
                    "Version": {"de": version_de, "en": version_en},
                    "Citation": "",
                    "Construct": construct,
                    "Description": {"de": study_desc_de, "en": study_desc_en},
                },
                "Metadata": {
                    "SchemaVersion": "1.1.0",
                    "CreationDate": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "Creator": "excel_to_library.py",
                },
            }

            if citation:
                sidecar["Study"]["Citation"] = citation
            if keywords:
                sidecar["Study"]["Keywords"] = keywords

            # Subject-facing instructions (template stores i18n dict)
            instr_de = meta.get("Instructions_de") or ""
            instr_en = meta.get("Instructions_en") or ""
            if not instr_de and not instr_en:
                raw_instr = meta.get("Instructions") or ""
                if default_language == "de":
                    instr_de = raw_instr
                else:
                    instr_en = raw_instr
            if instr_de or instr_en:
                sidecar["Study"]["Instructions"] = {"de": instr_de, "en": instr_en}

            # Drop empty TranslationMethod
            if not sidecar["I18n"].get("TranslationMethod"):
                sidecar["I18n"].pop("TranslationMethod", None)

            # Drop empty SoftwareVersion/ShortName for tidier output
            if not sidecar["Technical"].get("SoftwareVersion"):
                sidecar["Technical"].pop("SoftwareVersion", None)
            if not sidecar["Study"].get("ShortName"):
                sidecar["Study"].pop("ShortName", None)

        sidecar.update(variables)

        if is_participants:
            json_filename = "participants.json"
            target_dir = participants_output or output_dir
        else:
            json_filename = f"survey-{prefix}.json"
            target_dir = output_dir

        json_path = os.path.join(target_dir, json_filename)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(sidecar, f, indent=2, ensure_ascii=False)
            print(f"  - Created {json_path}")

    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Excel data dictionary to PRISM JSON library."
    )
    parser.add_argument(
        "--excel", required=True, help="Path to the Excel metadata file."
    )
    parser.add_argument(
        "--output", default="survey_library", help="Output directory for JSON files."
    )
    parser.add_argument(
        "--participants-prefix",
        default=None,
        help="Prefix to treat as participants.json (e.g., 'demo').",
    )
    parser.add_argument(
        "--participants-output",
        default=None,
        help="Directory where participants.json should be written (defaults to --output).",
    )

    args = parser.parse_args()
    process_excel(
        args.excel,
        args.output,
        participants_prefix=args.participants_prefix,
        participants_output=args.participants_output,
    )
