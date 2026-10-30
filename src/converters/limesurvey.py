import io
import os
import re
import sys
import unicodedata
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
import defusedxml.ElementTree as ET
import pandas as pd

from src.cross_platform import describe_case_insensitive_id_collisions
from src.limesurvey_attributes import LS_ARRAY_TYPES, LS_DESIGN_ATTRIBUTES, LS_ROW_TYPES
from src.modality_versions import current_survey_schema_version
from src.survey_export_settings import strip_export_settings
from src.text_sanitizer import html_to_text
from src.converters.survey_templates import _METADATA_CODE_RE as _PRISMMETA_RE
from src.converters.template_import import TEMPLATE_SECTIONS, match_questionnaire_to_library


def _get_text(element, tag):
    """Text of a child element, "" when the child or its text is missing."""
    child = element.find(tag)
    return (child.text if child is not None else "") or ""


def _utc_creation_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _bootstrap_import_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    app_root = repo_root / "app"

    for candidate in (repo_root, app_root):
        candidate_str = str(candidate)
        if candidate_str not in sys.path:
            sys.path.insert(0, candidate_str)


def _import_with_bootstrap(import_fn, *, catch=(ImportError,)):
    """Run `import_fn`; on failure, add repo/app roots to sys.path and retry once.

    If the retry also fails, the exception propagates to the caller — callers
    that want a silent fallback (leaving names as their pre-declared default)
    must wrap the call in their own try/except.
    """
    try:
        return import_fn()
    except catch:
        _bootstrap_import_path()
        return import_fn()


# Import item registry for collision detection
ItemRegistry: Any = None
ItemCollisionError: Any = None
merge_survey_versions: Callable[..., Any] | None = None
save_merged_template: Callable[..., Any] | None = None
detect_version_name_from_import: Callable[..., Any] | None = None


def _import_item_registry_and_merger():
    from src.converters.item_registry import (
        ItemRegistry as item_registry_cls,
        ItemCollisionError as item_collision_error_cls,
    )
    from src.converters.version_merger import (
        merge_survey_versions as merge_survey_versions_fn,
        save_merged_template as save_merged_template_fn,
        detect_version_name_from_import as detect_version_name_from_import_fn,
    )

    return (
        item_registry_cls,
        item_collision_error_cls,
        merge_survey_versions_fn,
        save_merged_template_fn,
        detect_version_name_from_import_fn,
    )


try:
    (
        ItemRegistry,
        ItemCollisionError,
        merge_survey_versions,
        save_merged_template,
        detect_version_name_from_import,
    ) = _import_with_bootstrap(_import_item_registry_and_merger)
except ImportError:
    pass


def _import_survey_base_and_naming():
    from src.converters.survey_base import load_survey_library
    from src.utils.naming import sanitize_task_name

    return load_survey_library, sanitize_task_name


load_schemas, sanitize_task_name = _import_with_bootstrap(
    _import_survey_base_and_naming, catch=(ImportError, ValueError)
)


def _import_csv_process_dataframe():
    from src.converters.csv import process_dataframe  # noqa: E402

    return process_dataframe


process_dataframe = _import_with_bootstrap(_import_csv_process_dataframe)

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
    "5": "5 Point Choice",
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


def parse_lsa_responses(lsa_path):
    """Return (dataframe, qid->title mapping, groups_map) extracted from a LimeSurvey .lsa file."""
    with zipfile.ZipFile(lsa_path, "r") as z:
        xml_resp = z.read(next(n for n in z.namelist() if n.endswith("_responses.lsr")))
        xml_lss = z.read(next(n for n in z.namelist() if n.endswith(".lss")))

    lss_root = ET.fromstring(xml_lss)


    questions_map, groups_map = _parse_lss_structure(lss_root, _get_text)

    # Parse once; both the fieldname list and the row data come from this tree.
    resp_root = ET.fromstring(xml_resp)
    fieldnames = [el.text or "" for el in resp_root.findall(".//fieldname")]
    rows = resp_root.findall("./responses/rows/row")
    records = []
    for row in rows:
        rec = {}
        for child in row:
            tag = child.tag.lstrip("_")
            rec[tag] = child.text
        records.append(rec)

    if not records:
        raise ValueError("The .lsa archive contains no responses (only the survey structure).")
    df = pd.DataFrame(records)

    rename_map = dict(zip(fieldnames, lsa_column_names(fieldnames, xml_lss)))
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
    clean_text = html_to_text(html_content)
    # Clean up whitespace
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    return clean_text, media_urls


def _parse_survey_metadata(root, get_text):
    """Extract survey-level metadata from surveys and surveys_languagesettings sections."""
    metadata = {
        "title": "",
        "admin": "",
        "admin_email": "",
        "language": "",
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
                metadata["language"] = get_text(row, "language")
                metadata["anonymized"] = get_text(row, "anonymized") == "Y"
                metadata["format"] = get_text(row, "format") or "G"
                metadata["template"] = get_text(row, "template")
                metadata["datestamp"] = get_text(row, "datestamp") == "Y"
                break  # Only first survey row

    # Title and messages: the base language's settings row (else the first one)
    rows = root.findall("surveys_languagesettings/rows/row")
    base = _base_language(root)
    row = next((r for r in rows if get_text(r, "surveyls_language").strip() == base), rows[0] if rows else None)
    if row is not None:
        for key, tag in (("title", "surveyls_title"), ("welcome_message", "surveyls_welcometext"),
                         ("end_message", "surveyls_endtext"), ("description", "surveyls_description")):
            if get_text(row, tag):
                metadata[key] = html_to_text(get_text(row, tag))

    return metadata


def _parse_answers_into_questions(root, questions_map, get_text):
    """Parse <answers> section and attach levels to questions_map entries.

    Args:
        root: XML root element containing <answers> section
        questions_map: Dict mapping qid -> question data (modified in place)
        get_text: Helper to extract text from XML elements
    """
    answers_section = root.find("answers")
    if answers_section is None:
        return

    rows = answers_section.find("rows")
    if rows is None:
        return

    # LS 6.x: answer text lives in <answer_l10ns> (one row per language), keyed by aid.
    answer_l10ns = {}
    for l10n in root.findall("answer_l10ns/rows/row"):
        answer_l10ns.setdefault(get_text(l10n, "aid"), []).append(
            (get_text(l10n, "language"), html_to_text(get_text(l10n, "answer")))
        )

    for row in rows.findall("row"):
        qid = get_text(row, "qid")
        code = get_text(row, "code")
        answer = html_to_text(get_text(row, "answer"))
        lang = get_text(row, "language")

        if qid not in questions_map:
            continue

        pairs = [(lang, answer)]
        if not answer and get_text(row, "aid") in answer_l10ns:
            pairs = answer_l10ns[get_text(row, "aid")]

        # all scales together, and apart (the two scales of a dual-scale array share their codes)
        scale_levels = questions_map[qid]["levels_by_scale"].setdefault(get_text(row, "scale_id") or "0", {})
        for levels in (questions_map[qid]["levels"], scale_levels):
            for lang, answer in pairs:
                # code -> answer text (possibly multilingual)
                if lang and lang.strip():
                    if not isinstance(levels.get(code), dict):
                        levels[code] = {}
                    levels[code][lang] = answer
                else:
                    levels[code] = answer


# Answer options LimeSurvey defines itself (no <answers> rows): stored code -> label in
# LimeSurvey's wording, en and its German translation. Codes as in its question renderers.
_YES, _NO = {"en": "Yes", "de": "Ja"}, {"en": "No", "de": "Nein"}
_ONE_TO_FIVE = {str(i): {} for i in range(1, 6)}
_FIXED_ANSWERS = {
    "Y": {"Y": _YES, "N": _NO},
    "G": {"F": {"en": "Female", "de": "weiblich"}, "M": {"en": "Male", "de": "männlich"}},
    "C": {"Y": _YES, "U": {"en": "Uncertain", "de": "Unsicher"}, "N": _NO},
    "E": {
        "I": {"en": "Increase", "de": "Zunahme"},
        "S": {"en": "Same", "de": "Unverändert"},
        "D": {"en": "Decrease", "de": "Abnahme"},
    },
    "5": _ONE_TO_FIVE,
    "A": _ONE_TO_FIVE,
    "B": {str(i): {} for i in range(1, 11)},  # numbers label themselves
}


def _builtin_levels(options, languages):
    """``options`` (code -> labels per language) as levels in each of ``languages``."""
    # ponytail: en/de labels only; other languages are left out, and with none of the two
    # the English label goes under "en", never under another language's key. Add languages
    # from LimeSurvey's locale/<lang>.mo when needed.
    keys = {lang: lang.split("-")[0] for lang in languages if lang.split("-")[0] in ("en", "de")} or {"en": "en"}
    return {
        code: {key: labels.get(base, labels.get("en", code)) for key, base in keys.items()}
        for code, labels in options.items()
    }


def _add_fixed_answer_levels(questions_map, languages):
    """Give the fixed-option types their LimeSurvey answer options as levels, labelled in
    each of ``languages`` (German variants like de-informal included); numbers label themselves."""
    for q in questions_map.values():
        options = _FIXED_ANSWERS.get(q["type"])
        if options and not q["levels"]:
            q["levels"] = _builtin_levels(options, languages)


def _base_language(root):
    """The survey's base language: <surveys> row, else the first of <languages>, else the
    first language any row names, else "" (.lsq/.lsg files may name none: never invented)."""
    for path in ("surveys/rows/row/language", "languages/language"):
        value = (root.findtext(path) or "").strip()
        if value:
            return value
    return next(((el.text or "").strip() for el in root.iter("language") if (el.text or "").strip()), "")


def _detect_languages(root, get_text):
    """(all languages of the survey, sorted; the base language)."""
    base = _base_language(root)
    languages = {base} | {(el.text or "").strip() for el in root.iter("language")}
    for row in root.findall("surveys/rows/row"):
        languages.update(get_text(row, "additional_languages").split())
    return sorted(lang for lang in languages if lang), base

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

    # Every language's texts, from LS 6 *_l10ns tables and LS 3 per-language rows alike:
    # ("g", gid) / ("q", qid) -> {language: {field: text}}. Rows without a language
    # (single-language exports) count as the base language.
    base = _base_language(root)
    texts = {}

    def collect(rows, kind, id_tag, fields):
        for row in rows:
            values = {f: get_text(row, f) for f in fields if get_text(row, f)}
            if values:
                lang = get_text(row, "language").strip() or base
                texts.setdefault((kind, get_text(row, id_tag)), {}).setdefault(lang, {}).update(values)

    collect(root.findall("groups/rows/row") + root.findall(".//group_l10ns/rows/row"),
            "g", "gid", ("group_name", "description"))
    collect(root.findall("questions/rows/row") + root.findall("subquestions/rows/row")
            + root.findall(".//question_l10ns/rows/row"), "q", "qid", ("question", "help"))

    def text_by_language(kind, key, field, clean=html_to_text):
        """{language: plain text} of one field, the base language first."""
        found = {lang: clean(v[field]) for lang, v in texts.get((kind, key), {}).items() if v.get(field)}
        return dict(sorted(((lang, t) for lang, t in found.items() if t), key=lambda kv: kv[0] != base))

    def other_language(row):  # LS 3 repeats each row once per language
        lang = get_text(row, "language").strip()
        return bool(lang) and lang != base

    # Temporary map for question attributes: qid -> {attribute_name: value}
    attributes_map = {}

    # 1. Parse Groups
    groups_section = root.find("groups")
    if groups_section is not None:
        rows = groups_section.find("rows")
        if rows is not None:
            for row in rows.findall("row"):
                if other_language(row):
                    continue
                gid = get_text(row, "gid")
                name = next(iter(text_by_language("g", gid, "group_name").values()), "")
                group_order = get_text(row, "group_order")
                description = next(iter(text_by_language("g", gid, "description").values()), "")
                randomization_group = get_text(row, "randomization_group")
                grelevance = get_text(row, "grelevance")  # Group relevance equation

                try:
                    order_int = int(group_order) if group_order else 0
                except ValueError:
                    order_int = 0

                groups_map[gid] = {
                    "name": name if name else "",
                    "order": order_int,
                    "description": description,
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
                if other_language(row):
                    continue
                qid = get_text(row, "qid")
                parent_qid = get_text(row, "parent_qid")
                title = get_text(row, "title")  # Subquestion code (e.g., SQ001)
                question_text = next(iter(text_by_language("q", qid, "question", str).values()), "")
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
                    "text_i18n": text_by_language("q", qid, "question"),
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
                if other_language(row):
                    continue
                qid = get_text(row, "qid")
                gid = get_text(row, "gid")
                title = get_text(row, "title")  # Variable name (e.g. 'ADS01')
                question_i18n = text_by_language("q", qid, "question")
                help_i18n = text_by_language("q", qid, "help")
                q_type = get_text(row, "type")
                parent_qid = get_text(row, "parent_qid")
                mandatory = get_text(row, "mandatory")  # Y or N
                question_order = get_text(row, "question_order")
                other = get_text(row, "other")  # Y or N - has "Other" option
                preg = get_text(row, "preg")  # Validation regex
                relevance = get_text(row, "relevance")  # Relevance equation

                try:
                    q_order_int = int(question_order) if question_order else 0
                except ValueError:
                    q_order_int = 0

                clean_question = next(iter(question_i18n.values()), "")
                clean_help = next(iter(help_i18n.values()), "")

                questions_map[qid] = {
                    "title": title,
                    "question": clean_question,
                    "question_i18n": question_i18n,
                    "help_i18n": help_i18n,
                    "type": q_type,
                    "type_name": _get_question_type_name(q_type),
                    "mandatory": mandatory.upper() == "Y" if mandatory else False,
                    "question_order": q_order_int,
                    "parent_qid": parent_qid,
                    "gid": gid,
                    "levels": {},
                    "levels_by_scale": {},
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


_ITEM_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _array_item_id(parent_code, row_code, taken):
    """Row code as item ID when it is a usable, unused identifier; otherwise
    prefixed with its array's code (ADS1 + "1" -> "ADS1_1")."""
    if _ITEM_ID_RE.match(row_code) and row_code not in taken:
        return row_code
    return f"{parent_code}_{row_code}"


def _unkeyed(value):
    """``{"": text}`` (texts of a file that names no language) as plain ``text``, everywhere in ``value``."""
    if isinstance(value, dict):
        return value[""] if set(value) == {""} else {k: _unkeyed(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_unkeyed(v) for v in value]
    return value


def _multilingual(levels, language):
    """Levels with plain strings turned into {language: text}."""
    return {
        code: text if isinstance(text, dict) else {language: str(text) if text else ""}
        for code, text in levels.items()
    }


def _texts(sq, fallback_language):
    """{language: text} of a subquestion."""
    return dict(sq.get("text_i18n") or {fallback_language: sq.get("text", "")})


def _join_texts(first, second, template):
    """Per language ``template`` filled with both texts; a language one side lacks uses that side's first text."""
    def pick(texts, lang):
        return texts.get(lang) or next(iter(texts.values()), "")

    return {lang: template.format(pick(first, lang), pick(second, lang)) for lang in dict.fromkeys([*first, *second])}


def _row_items(q_data, ls_props, languages, language):
    """The items of a question that is several response columns, as (LimeSurvey column suffix,
    item ID hint, item): matrix rows, checkbox options (with comments), ranking positions,
    row x column cells of the text/number arrays, row x scale of the dual-scale array.
    Empty when the question has no rows, so it stays one item."""
    q_type, subs = q_data["type"], q_data.get("subquestions", [])
    stem = dict(q_data.get("question_i18n") or {language: q_data.get("question", "")})
    levels = _multilingual(q_data.get("levels", {}), language)

    def item(texts, extra_levels=None, **props):
        entry = {"Description": texts, "LimeSurvey": {**ls_props, **props}}
        if extra_levels:
            entry["Levels"] = extra_levels
        return entry

    def as_type(code):  # a cell of the array is a plain text/number item for LimeSurvey
        return {"questionType": code, "questionTypeName": _get_question_type_name(code)}

    rows = [sq for sq in subs if sq["scale_id"] == 0]
    if q_type == "R":
        return [
            (str(n), str(n), item({lang: f"{text} ({n})" for lang, text in stem.items()}, levels))
            for n in range(1, len(levels) + 1)
        ]
    if not subs:
        return []
    if q_type in ("M", "P"):
        checked = _builtin_levels({"Y": _YES}, languages)
        out = []
        for sq in subs:
            out.append((sq["code"], sq["code"], item(_texts(sq, language), checked)))
            if q_type == "P":
                comment = item(_join_texts(_texts(sq, language), {}, "{0} (comment)"), mandatory=False, **as_type("T"))
                out.append((f"{sq['code']}comment", f"{sq['code']}_comment", comment))
        return out
    if q_type in (";", ":"):
        columns = [sq for sq in subs if sq["scale_id"] == 1]
        cell = as_type("S" if q_type == ";" else "N")
        return [
            (f"{r['code']}_{c['code']}", f"{r['code']}_{c['code']}",
             {**item(_join_texts(_texts(r, language), _texts(c, language), "{0} / {1}"), **cell),
              "DataType": "string" if q_type == ";" else "float"})
            for r in rows for c in columns
        ]
    if q_type == "1":
        by_scale = q_data.get("levels_by_scale", {})
        return [
            (f"{r['code']}-{scale}", f"{r['code']}_scale{scale + 1}",
             item(_join_texts(_texts(r, language), {}, "{0} (" + str(scale + 1) + ")"),
                  _multilingual(by_scale.get(str(scale), {}), language)))
            for r in rows for scale in (0, 1)
        ]
    # matrix rows (F, A, B, C, E, H): all rows share the question's answer options
    return [(sq["code"], sq["code"], item(_texts(sq, language) if sq.get("text") else stem, levels)) for sq in subs]


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
            ls_props["helpText"] = dict(q_data.get("help_i18n") or {default_language: help_text})
        # Check for language-specific help in attributes
        for attr_key, attr_val in attributes.items():
            if attr_key.startswith("help_"):
                lang = attr_key[5:]
                if lang and isinstance(attr_val, str):
                    ls_props["helpText"][lang] = attr_val

        # Equation type: the equation attribute (LimeSurvey 5+), else the question text
        if q_type == "*":
            ls_props["equation"] = str(attributes.get("equation") or question_text)

        # Design options (maximum characters, prefix/suffix, ...): the base language's value,
        # defaults (0, empty) left out
        for name in LS_DESIGN_ATTRIBUTES:
            value = attributes.get(f"{name}_{default_language}", attributes.get(name))
            if value not in (None, "", 0, False):
                ls_props[name] = value

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

        columns = _row_items(q_data, ls_props, languages, default_language) if q_type in LS_ROW_TYPES else []
        if columns:
            # Several response columns: one item per column, named after LimeSurvey's column
            for suffix, id_hint, entry in columns:
                entry["LimeSurvey"]["columnName"] = f"{title}[{suffix}]"
                prism_questions[_array_item_id(title, id_hint, prism_questions)] = entry
        else:
            # Non-matrix question: single entry
            entry = {
                "Description": dict(q_data.get("question_i18n") or {default_language: question_text}),
                "LimeSurvey": ls_props,
            }

            if levels:
                entry["Levels"] = _multilingual(levels, default_language)

            prism_questions[title] = entry

    # Infer DataType from question type for each item
    numeric_types = {"N", "K", "A", "B", "5"}
    text_types = {"S", "T", "U", "Q"}
    for key, entry in prism_questions.items():
        ls = entry.get("LimeSurvey", {})
        qt = ls.get("questionType", "")
        if qt in numeric_types:
            entry.setdefault("DataType", "integer")
        elif qt in text_types:
            entry.setdefault("DataType", "string")

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
            "ResponseType": ["online"],
            **({"Language": default_language} if default_language else {}),
        },
        "Study": {
            "TaskName": normalized_task,
            "OriginalName": task_name,
            "Version": "1.0",
            "Description": f"Imported from LimeSurvey .{source_type}: {task_name}",
            "ItemCount": len(prism_questions),
        },
        "Metadata": {
            "SchemaVersion": current_survey_schema_version(),
            "CreationDate": _utc_creation_date(),
            "Creator": "limesurvey_to_prism.py",
        },
    }

    if languages:  # none named: no I18n, and the texts stay plain strings (the editor asks for the language)
        template["I18n"] = {
            "Languages": languages,
            "DefaultLanguage": default_language,
        }

    template.update(prism_questions)
    return _unkeyed(strip_export_settings(template)[0])  # export settings are derived at export time, not kept


def _parse_lsq_lsg_xml(xml_content, source_type):
    """Parse a .lsq (one question: <questions>, <subquestions>, <answers>,
    <question_attributes>) or .lsg (the same plus <groups>) export into a PRISM
    template dict with per-item LimeSurvey properties, or None on invalid XML."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"Error parsing .{source_type} XML: {e}")
        return None

    questions_map, groups_map = _parse_lss_structure(root, _get_text)
    _parse_answers_into_questions(root, questions_map, _get_text)
    languages, default_language = _detect_languages(root, _get_text)
    _add_fixed_answer_levels(questions_map, languages)
    return _build_prism_template_from_parsed(
        questions_map, groups_map, languages, default_language, source_type=source_type
    )


def parse_lsq_xml(xml_content):
    return _parse_lsq_lsg_xml(xml_content, "lsq")


def parse_lsg_xml(xml_content):
    return _parse_lsq_lsg_xml(xml_content, "lsg")


SPLIT_MODES = ("group", "question", "survey")
# Text, equation and display questions: no answer options of their own.
_HELPER_TYPES = {"S", "T", "U", "Q", "*", "X"}


def read_lss_xml(data, filename):
    """Return the .lss XML from an uploaded .lss file or .lsa archive."""
    name = filename.lower()
    if name.endswith(".lss"):
        return data
    if not name.endswith(".lsa"):
        raise ValueError("Unsupported file type. Use .lss or .lsa")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            lss_names = [n for n in archive.namelist() if n.endswith(".lss")]
            if not lss_names:
                raise ValueError(f"No .lss file found inside {filename}")
            return archive.read(lss_names[0])
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{filename} is not a valid .lsa archive") from exc


def _task_name(name):
    # Transliterate first: sanitize_task_name drops non-ASCII ("Händigkeit" -> "hndigkeit").
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return sanitize_task_name(ascii_name) or "imported"


def _parse_lss_for_questionnaires(xml_content):
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid LimeSurvey XML: {exc}") from exc


    languages, default_language = _detect_languages(root, _get_text)
    questions_map, groups_map = _parse_lss_structure(root, _get_text)
    _parse_answers_into_questions(root, questions_map, _get_text)
    _add_fixed_answer_levels(questions_map, languages)
    return {
        "questions": questions_map,
        "groups": groups_map,
        "languages": languages,
        "default_language": default_language,
        "title": _parse_survey_metadata(root, _get_text).get("title") or "survey",
        "db_version": _get_text(root, "DBVersion"),
    }


def _split_questionnaires(parsed, split, keep_prismmeta=False):
    if split not in SPLIT_MODES:
        raise ValueError(f"Unknown split mode '{split}'. Use one of: {', '.join(SPLIT_MODES)}")
    groups = parsed["groups"]
    top = sorted(
        (
            (qid, q)
            for qid, q in parsed["questions"].items()
            if q.get("parent_qid") in (None, "", "0")
        ),
        key=lambda item: (groups.get(item[1]["gid"], {}).get("order", 0), item[1]["question_order"]),
    )
    prismmeta = {
        q["gid"]: str(q["attributes"].get("equation", ""))
        for _qid, q in top
        if _PRISMMETA_RE.match(q["title"])
    }
    if not keep_prismmeta:
        top = [(qid, q) for qid, q in top if not _PRISMMETA_RE.match(q["title"])]

    if split == "survey":
        if not top:
            return []
        return [{"key": "survey", "name": parsed["title"], "description": "",
                 "qids": [qid for qid, _ in top], "prismmeta": ""}]
    if split == "question":
        return [{"key": f"q{qid}", "name": q["title"], "description": "",
                 "qids": [qid], "prismmeta": ""} for qid, q in top]
    parts = []
    for gid, group in sorted(groups.items(), key=lambda g: g[1]["order"]):
        qids = [qid for qid, q in top if q["gid"] == gid]
        if qids:
            parts.append({"key": f"g{gid}", "name": group["name"] or f"group {gid}",
                          "description": group["description"], "qids": qids,
                          "prismmeta": prismmeta.get(gid, "")})
    return parts


def _apply_prismmeta(template, html):
    """Restore what the exporter stored in a group's hidden PRISMMETA question.
    Returns the names of the restored fields."""
    if not html:
        return []
    from src.converters.survey_templates import _extract_prismmeta, parse_prismmeta_codemap

    fields = _extract_prismmeta({"PRISMMETA": {"Attributes": {"equation": html}}})
    study = template["Study"]
    restored = []
    for field, target in (("name", "OriginalName"), ("abbrev", "ShortName"),
                          ("doi", "DOI"), ("citation", "Citation"), ("license", "License")):
        if fields.get(field):
            study[target] = fields[field]
            restored.append(target)
    if fields.get("authors"):
        # ponytail: the exporter joins authors with ", ", which also appears inside
        # "Doe, J." names; kept as one entry rather than guessing the split.
        study["Authors"] = [fields["authors"]]
        restored.append("Authors")
    codemap = parse_prismmeta_codemap(fields)

    def column(key, entry):  # a matrix row's CodeMap entry names its column, MPHQ901[PHQ01]
        return (entry.get("LimeSurvey") or {}).get("columnName", key) if isinstance(entry, dict) else key

    if any(column(k, v) in codemap for k, v in template.items()):
        renamed = {codemap.get(column(k, v), k): v for k, v in template.items()}
        template.clear()
        template.update(renamed)
        restored.append("CodeMap")
    return restored


def _questionnaire_template(parsed, part):
    questions = {qid: parsed["questions"][qid] for qid in part["qids"]}
    lang = parsed["default_language"]
    template = _build_prism_template_from_parsed(
        questions, parsed["groups"], parsed["languages"], lang, source_type="lss"
    )
    study = template["Study"]
    study["OriginalName"] = part["name"]
    study["TaskName"] = _task_name(part["name"])
    study["Description"] = part["description"] or f"Imported from LimeSurvey: {part['name']}"
    stems = [
        q.get("question_i18n") or {lang: q["question"]}
        for q in questions.values()
        if q["type"] in LS_ARRAY_TYPES and q["subquestions"] and q["question"]
    ]
    instructions = {
        language: "\n\n".join(stem[language] for stem in stems if stem.get(language))
        for language in dict.fromkeys(language for stem in stems for language in stem)
    }
    if instructions:
        study["Instructions"] = instructions
    template["Technical"]["AdministrationMethod"] = "online"
    template = _unkeyed(template)
    return template, _apply_prismmeta(template, part["prismmeta"])


def _import_notes(part_name, questions, languages):
    """What the import of these questions cannot represent, one readable line each."""
    from src.survey_answer_codes import _is_number

    notes = []
    for q in questions:
        where = f"{part_name} / {q['title']}"
        if q["type"] in ("M", "P") and q["subquestions"]:
            notes.append(f"{where}: unchecked options are empty in LimeSurvey's data and import as missing (n/a), "
                         "not as \"not selected\"")
        if q["type_name"].startswith("Unknown"):
            notes.append(f"{where}: question type {q['type']} is not known, imported as a single item")
        if q["other"]:
            notes.append(f"{where}: has an \"Other\" text field; it is not imported as an item")
        if q["type"] == "O":
            notes.append(f"{where}: has a comment field; it is not imported as an item")
        codes = [c for c in q["levels"] if c != "n/a"]
        if q["type"] not in _FIXED_ANSWERS and codes and not all(_is_number(c) for c in codes):
            notes.append(f"{where}: answer codes {', '.join(codes)} are not numbers; give them numbers in the "
                         "Template Editor (Answer codes) or with 'prism_tools.py survey answer-codes'")
    builtin = [q for q in questions if any(_FIXED_ANSWERS.get(q["type"], {}).values())]
    if builtin and not any(lang.split("-")[0] in ("en", "de") for lang in languages):
        notes.append(f"{part_name}: the built-in answer labels (Yes/No, Gender, ...) exist in English and German only; "
                     f"this survey ({', '.join(languages)}) got the English labels, check them")
    return notes


def _major_release(db_version):
    """Major LimeSurvey release for a DBVersion ('' if unknown); the file stores no release number."""
    # ponytail: only 6.x (DBVersion 600+) is known for sure; extend when older ranges are confirmed
    return "6" if str(db_version).isdigit() and int(db_version) >= 600 else ""


def _build_questionnaires(xml_content, split, keep_prismmeta=False):
    """keep_prismmeta: leave the hidden PRISMMETA question in each template as a
    pseudo-item (Survey Generator readers parse it) instead of restoring it into Study."""
    parsed = _parse_lss_for_questionnaires(xml_content)
    results = []
    for part in _split_questionnaires(parsed, split, keep_prismmeta):
        if keep_prismmeta:
            part["prismmeta"] = ""
        template, restored = _questionnaire_template(parsed, part)
        major = _major_release(parsed["db_version"])
        if major:
            template["Technical"].setdefault("SoftwareVersion", major)
        if keep_prismmeta:
            # old by-groups shape: string Description + Attributes.equation (what _extract_prismmeta reads)
            for qid in part["qids"]:
                q = parsed["questions"][qid]
                if _PRISMMETA_RE.match(q["title"]) and q["title"] in template:
                    template[q["title"]] = {
                        "Description": q["question"],
                        "Attributes": {"equation": str(q["attributes"].get("equation", ""))},
                    }
        questions = [parsed["questions"][qid] for qid in part["qids"]]
        results.append((
            {
                "key": part["key"],
                "name": part["name"],
                "item_count": len([k for k in template if k not in TEMPLATE_SECTIONS]),
                "helper": all(
                    q["type"] in _HELPER_TYPES and not q["levels"] and not q["subquestions"]
                    for q in questions
                ),
                "arrays": [q["title"] for q in questions if q["type"] in LS_ARRAY_TYPES and q["subquestions"]],
                "restored": restored,
                "notes": _import_notes(part["name"], questions, parsed["languages"]),
            },
            template,
        ))
    used = set()
    for _info, template in results:  # groups whose names sanitize alike get base-2, base-3, ...
        study = template["Study"]
        base = name = study["TaskName"]
        n = 1
        while name in used:
            n += 1
            name = f"{base}-{n}"
        used.add(name)
        study["TaskName"] = name
    return parsed, results


def lsa_column_names(fieldnames, lss_xml):
    """Name each LimeSurvey response field (``{sid}X{gid}X{qid}{code}``) after the item the
    template import makes for it, so every answer reaches its own item.

    The question id is looked up among the survey's questions, never read off the digits
    (qid 38486 + row "1" is the field ``...X384861``). A field without an item of its own
    (an "Other" text, or a row whose item ID two arrays share) keeps LimeSurvey's notation
    ``title[code]`` and so shows up as an unconverted column instead of feeding another item.
    """
    parsed, results = _build_questionnaires(lss_xml, "group", keep_prismmeta=True)
    item_of = {}  # LimeSurvey column -> item ID
    for _info, template in results:
        for key, entry in template.items():
            if key not in TEMPLATE_SECTIONS and isinstance(entry, dict):
                item_of[entry.get("LimeSurvey", {}).get("columnName", key)] = key
    shared = {item for item, n in Counter(item_of.values()).items() if n > 1}
    questions = [
        (qid, q) for qid, q in parsed["questions"].items() if q.get("parent_qid") in (None, "", "0")
    ]

    def column(field):
        m = re.fullmatch(r"_?\d+X(\d+)X(\d+.*)", field)
        if not m:
            return field
        gid, rest = m.groups()
        found = set()
        for qid, q in questions:
            if q["gid"] != gid or not rest.startswith(qid):
                continue
            suffix = re.sub(r"#([01])$", r"-\1", rest[len(qid):])  # dual scale: LimeSurvey 6 writes -0/-1, older #0/#1
            name = f"{q['title']}[{suffix}]" if suffix else q["title"]
            # a column of an item, an "Other" text, a comment (of the question or of a checkbox row)
            if name in item_of or suffix in ("other", "comment") or (
                suffix.endswith("comment") and f"{q['title']}[{suffix[:-7]}]" in item_of
            ):
                found.add(name)
        if len(found) != 1:
            return field  # no question (or more than one) fits: leave it as LimeSurvey named it
        name = found.pop()
        item = item_of.get(name)
        return item if item and item not in shared else name

    return [column(f) for f in fieldnames]


def list_limesurvey_questionnaires(
    xml_content, split="group", source_name="LimeSurvey file", project_path=None, match_library=False
):
    """List the questionnaires in a LimeSurvey survey, split by group, question or whole survey.

    With ``match_library`` each entry also gets ``library_match`` (the best global/project
    library template by wording, or None) and the terminal shows one line per questionnaire.
    """
    parsed, results = _build_questionnaires(xml_content, split)
    print(
        f"[PRISM] LimeSurvey import: {source_name} (DBVersion {parsed['db_version'] or '?'}, "
        f"languages: {', '.join(parsed['languages'])})"
    )
    print(f"[PRISM] Split by {split} -> {len(results)} questionnaire(s):")
    for info, _template in results:
        _print_notes(info["notes"])
        line = f"[PRISM]   {info['key']:<8} {info['name']}  {info['item_count']} item(s)"
        if info["arrays"]:
            line += f"  (array {', '.join(info['arrays'])})"
        if info["helper"]:
            line += "  [helper: no answer options]"
        print(line)
    listing = [{k: info[k] for k in ("key", "name", "item_count", "helper")} for info, _ in results]
    if match_library:
        from src.converters.library_wording_match import public_library_match

        for entry, (info, template) in zip(listing, results):
            entry["library_match"] = public_library_match(
                match_questionnaire_to_library(template, info["name"], project_path)
            )
    return listing


def _print_notes(notes):
    for note in notes:
        print(f"[PRISM] WARNING {note}")


def limesurvey_questionnaire_template(xml_content, key, split="group"):
    """Build the PRISM template for one questionnaire (key from list_limesurvey_questionnaires)."""
    return limesurvey_questionnaire(xml_content, key, split)[0]


def limesurvey_questionnaire(xml_content, key, split="group"):
    """(PRISM template, notes) for one questionnaire; the notes list what the import could not
    represent and are printed to the terminal as well."""
    _parsed, results = _build_questionnaires(xml_content, split)
    for info, template in results:
        if info["key"] == key:
            stem = "stem -> Study.Instructions" if "Instructions" in template["Study"] else "no array stem"
            meta = (
                f"PRISMMETA restored: {', '.join(info['restored'])}"
                if info["restored"]
                else "no PRISMMETA (fill in Citation, Category, SoftwareVersion by hand)"
            )
            print(f"[PRISM] Loading {key} '{info['name']}': {info['item_count']} item(s), {stem}, {meta}")
            return template, info["notes"]
    valid = ", ".join(info["key"] for info, _ in results) or "none"
    raise ValueError(f"No questionnaire '{key}' (split by {split}). Valid keys: {valid}")


def parse_lss_xml(
    xml_content,
    task_name=None,
    check_collisions=True,
    local_library=None,
    official_library=None,
):
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


    # Get survey-level metadata
    survey_meta = _parse_survey_metadata(root, _get_text)

    questions_map, groups_map = _parse_lss_structure(root, _get_text)

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
                official_library=Path(official_library) if official_library else None,
            )
            print(
                f"[PRISM] Item collision checking enabled ({item_registry.get_item_count()} existing items)"
            )
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
                qid = _get_text(row, "qid")
                code = _get_text(row, "code")
                answer = html_to_text(_get_text(row, "answer"))

                if qid in questions_map:
                    questions_map[qid]["levels"][code] = answer
    _add_fixed_answer_levels(questions_map, [survey_meta.get("language") or "en"])

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
                    item_data=entry,
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
        print(
            f"\n[PRISM] Processing {len(version_collisions)} version candidate collision(s)..."
        )

        # Group by existing template
        collisions_by_template = {}
        for key, entry, error in version_collisions:
            existing_template = error.existing_meta.get("source_template")
            if existing_template not in collisions_by_template:
                collisions_by_template[existing_template] = {
                    "items": {},
                    "error": error,
                }
            collisions_by_template[existing_template]["items"][key] = entry

        for existing_template_name, collision_info in collisions_by_template.items():
            new_items = collision_info["items"]

            # Find existing template file
            existing_template_path = None
            if local_library:
                lib_path = (
                    Path(local_library)
                    if isinstance(local_library, str)
                    else local_library
                )
                if lib_path.exists():
                    candidate = lib_path / f"{existing_template_name}.json"
                    if candidate.exists():
                        existing_template_path = candidate

            if official_library and not existing_template_path:
                lib_path = (
                    Path(official_library)
                    if isinstance(official_library, str)
                    else official_library
                )
                if lib_path.exists():
                    candidate = lib_path / f"{existing_template_name}.json"
                    if candidate.exists():
                        existing_template_path = candidate

            if not existing_template_path:
                print(
                    f"[PRISM WARNING] Could not find existing template {existing_template_name}, skipping merge"
                )
                # Add items normally
                for item_id, item_data in new_items.items():
                    prism_json[item_id] = item_data
                continue

            # Prompt for version name
            print(f"\n{'=' * 60}")
            print(
                f"Survey '{normalized_task}' appears to be a version of '{existing_template_name}'"
            )
            print(f"  Existing template: {existing_template_path.name}")
            print(f"  Colliding items: {len(new_items)}")

            suggested_new, suggested_existing = detect_version_name_from_import(
                new_items, existing_template_path
            )
            print(f"  Suggested new version name: '{suggested_new}'")
            version_name = input(
                f"Enter version name for this import (or press Enter for '{suggested_new}'): "
            ).strip()
            if not version_name:
                version_name = suggested_new

            print(f"[PRISM] Merging as version: '{version_name}'")

            # Perform merge
            merged_template = merge_survey_versions(
                existing_template_path=existing_template_path,
                new_items=new_items,
                new_version_name=version_name,
            )

            # Save merged template
            save_merged_template(merged_template, existing_template_path)

            # Add new items to prism_json
            for item_id, item_data in new_items.items():
                prism_json[item_id] = item_data

            print("[PRISM] ✓ Version merge complete\n")

    # Build description from survey metadata
    description = (
        survey_meta.get("description") or f"Imported from LimeSurvey: {survey_title}"
    )

    metadata = {
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "tsv",
            "SoftwarePlatform": "LimeSurvey",
            "ResponseType": ["online"],
            **({"Language": survey_meta["language"]} if survey_meta["language"] else {}),
        },
        "Study": {
            "TaskName": normalized_task,
            "OriginalName": survey_title,
            "Version": "1.0",
            "Description": description,
            "ItemCount": len(prism_json),
        },
        "Metadata": {
            "SchemaVersion": current_survey_schema_version(),
            "CreationDate": _utc_creation_date(),
            "Creator": "limesurvey_to_prism.py",
        },
    }

    # this converter keeps the base language's texts only
    if survey_meta["language"]:
        metadata["I18n"] = {"Languages": [survey_meta["language"]]}

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

    Same builder as the Template Editor import: one flattened PRISM template
    per question group, keyed by its task name.
    """
    try:
        _parsed, results = _build_questionnaires(xml_content, "group", keep_prismmeta=True)
    except ValueError as e:
        print(f"Error parsing XML: {e}")
        return None
    out = {}
    for _info, template in results:
        out[template["Study"]["TaskName"]] = template
    return out


def add_survey_time_columns(df) -> None:
    """Add SurveyDuration (min), SurveyStartTime (HH:MM:SS) and SurveyStartDate (YYYY-MM-DD) in place.

    Duration and time need ``startdate`` and ``submitdate``. The date also falls back to
    ``datestamp`` (exports without "Save start time"); unparsable dates become empty cells.
    The date identifies people: ``src.survey_dates`` removes it from every shared export.
    """
    if "startdate" in df.columns and "submitdate" in df.columns:
        try:
            start = pd.to_datetime(df["startdate"], errors="coerce")
            submit = pd.to_datetime(df["submitdate"], errors="coerce")
            df["SurveyDuration"] = ((submit - start).dt.total_seconds() / 60.0).round(2)
            df["SurveyStartTime"] = start.dt.strftime("%H:%M:%S")
        except Exception as e:
            print(f"Warning: Could not calculate duration/time: {e}")
    source = "startdate" if "startdate" in df.columns else "datestamp"
    if source in df.columns:
        df["SurveyStartDate"] = (
            pd.to_datetime(df[source], errors="coerce").dt.strftime("%Y-%m-%d").fillna("")
        )


SURVEY_START_DATE_SCHEMA = {
    "Description": "Start date of the LimeSurvey session (YYYY-MM-DD)",
    "Units": "date",
}


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

    def _normalize_participant_id(value):
        if pd.isna(value):
            return value

        text = str(value).strip()
        if not text or text.lower() == "nan":
            return ""
        # Normalize to NFC before stripping non-ASCII chars so a name like
        # "José" sanitizes the same way regardless of which Unicode
        # normalization form the source system used (see
        # ParticipantsConverter._normalize_participant_id for the full
        # rationale).
        text = unicodedata.normalize("NFC", text)
        label = text[4:] if text[:4].lower() == "sub-" else text
        label = re.sub(r"[^A-Za-z0-9]+", "", label)
        if not label:
            return ""
        return f"sub-{label}"

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

    df["participant_id"] = df["participant_id"].apply(_normalize_participant_id)

    # Two participant ids differing only by case (e.g. 'sub-Ab'/'sub-ab')
    # resolve to the identical on-disk directory on a case-insensitive
    # filesystem (default macOS/Windows): the second one written would
    # silently overwrite the first's survey files with no error. Fail
    # fast, before any output is written, rather than allow that.
    collision_message = describe_case_insensitive_id_collisions(
        [pid for pid in df["participant_id"] if pid]
    )
    if collision_message:
        raise ValueError(collision_message)

    df["session"] = session_label

    add_survey_time_columns(df)

    # --- Merge Group Timings ---
    group_duration_fields = {}
    try:
        timings_df = parse_lsa_timings(lsa_path)

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
        "SurveyStartDate": SURVEY_START_DATE_SCHEMA,
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

        t_schema.setdefault("SurveyStartDate", dict(SURVEY_START_DATE_SCHEMA))

        # 3. Overwrite SurveyDuration with granular data if available
        if granular_col:
            # Granular is in seconds, convert to minutes to match schema unit
            # or update schema unit to seconds.
            # Let's update schema to seconds for precision.
            t_schema["SurveyDuration"]["Units"] = "seconds"
            t_schema["SurveyDuration"][
                "Description"
            ] = f"Duration for task {t_name} (derived from group timing)"
            task_df["SurveyDuration"] = task_df[granular_col]


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
