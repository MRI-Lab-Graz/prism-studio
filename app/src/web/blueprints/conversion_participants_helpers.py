import json
import re
import warnings
from pathlib import Path

from src.web.blueprints.conversion_utils import participant_json_candidates

try:
    from src.converters.survey import _NON_ITEM_TOPLEVEL_KEYS as _SURVEY_NON_ITEM_KEYS
except Exception:
    _SURVEY_NON_ITEM_KEYS = set()

_PARTICIPANT_RELEVANT_KEYWORDS = {
    "age",
    "sex",
    "gender",
    "education",
    "handedness",
    "group",
    "diagnosis",
    "ethnicity",
    "site",
    "center",
    "cohort",
    "language",
    "country",
    "state",
    "city",
    "race",
    "income",
    "occupation",
    "marital",
    "status",
    "session",
    "session_id",
    "visit",
    "timepoint",
    "completion_date",
    "date",
}

_DEFAULT_NEUROBAGEL_KEYS = {
    "participant_id",
    "subject",
    "sub",
    "age",
    "sex",
    "gender",
    "handedness",
    "group",
    "diagnosis",
    "education",
    "ethnicity",
    "session",
    "session_id",
    "visit",
    "timepoint",
    "completion_date",
    "date",
}

_DEFAULT_PARTICIPANT_STANDARD_ALIASES = {
    "age": {"age"},
    "sex": {"sex", "biologicalsex"},
    "gender": {"gender", "genderidentity"},
    "education": {"education", "educationlevel"},
    "handedness": {"handedness", "hand"},
    "group": {"group"},
    "diagnosis": {"diagnosis", "diagnosticgroup", "diagnosisgroup"},
    "ethnicity": {"ethnicity", "race"},
}

_PARTICIPANT_FILTER_CONFIG = {
    "min_repeated_prefix_count": 3,
    "participant_keywords": _PARTICIPANT_RELEVANT_KEYWORDS,
}


def _merge_participant_filter_config(overrides: dict | None) -> dict:
    merged = {
        "min_repeated_prefix_count": int(
            _PARTICIPANT_FILTER_CONFIG.get("min_repeated_prefix_count", 3)
        ),
        "participant_keywords": {
            str(key).lower()
            for key in _PARTICIPANT_FILTER_CONFIG.get(
                "participant_keywords", _PARTICIPANT_RELEVANT_KEYWORDS
            )
        },
    }

    if not isinstance(overrides, dict):
        return merged

    min_count = overrides.get(
        "minRepeatedPrefixCount",
        overrides.get("min_repeated_prefix_count"),
    )
    if isinstance(min_count, int) and min_count > 0:
        merged["min_repeated_prefix_count"] = min_count

    keywords = overrides.get("participantKeywords", overrides.get("participant_keywords"))
    if isinstance(keywords, (list, tuple, set)):
        cleaned = {str(key).lower().strip() for key in keywords if str(key).strip()}
        if cleaned:
            merged["participant_keywords"] = cleaned

    return merged


def _load_project_participant_filter_config(project_path: str | Path | None) -> dict:
    default_config = _merge_participant_filter_config(None)
    if not project_path:
        return default_config

    try:
        from src.config import load_config

        project_root = Path(project_path).expanduser().resolve()
        if project_root.is_file():
            project_root = project_root.parent

        prism_config = load_config(str(project_root))
        overrides = getattr(prism_config, "neurobagel_participant_filter", {})
        return _merge_participant_filter_config(overrides)
    except Exception:
        return default_config


def _normalize_column_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(name).lower().strip())


def _load_participant_template_columns(library_path: Path | str | None) -> set[str]:
    if not library_path:
        return set()

    root = Path(library_path)
    for candidate in participant_json_candidates(root):
        if not candidate.exists() or not candidate.is_file():
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as handle:
                template = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(template, dict) and isinstance(template.get("Columns"), dict):
            template = template["Columns"]
        if not isinstance(template, dict):
            continue

        return {
            _normalize_column_name(key)
            for key in template.keys()
            if isinstance(key, str)
        }

    return set()


def _load_survey_template_item_ids(library_path: Path | str | None) -> set[str]:
    if not library_path:
        return set()

    root = Path(library_path)
    item_ids: set[str] = set()

    roots_to_scan: list[tuple[Path, str]] = []
    survey_root = root / "survey" if (root / "survey").is_dir() else root
    if survey_root.exists() and survey_root.is_dir():
        roots_to_scan.append((survey_root, "survey-*.json"))

    biometrics_root = root / "biometrics" if (root / "biometrics").is_dir() else root
    if biometrics_root.exists() and biometrics_root.is_dir():
        roots_to_scan.append((biometrics_root, "biometrics-*.json"))

    biometrics_non_item_top_keys = {
        "Technical",
        "Study",
        "I18n",
        "Metadata",
    }

    for template_root, pattern in roots_to_scan:
        for template_json in template_root.glob(pattern):
            try:
                with open(template_json, "r", encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue

            if not isinstance(payload, dict):
                continue

            for key, value in payload.items():
                if (
                    key in _SURVEY_NON_ITEM_KEYS
                    or key in biometrics_non_item_top_keys
                    or key.startswith("_")
                ):
                    continue
                if isinstance(value, dict):
                    item_ids.add(_normalize_column_name(key))

    return item_ids


def _detect_repeated_questionnaire_prefixes(
    columns: list[str], participant_filter_config: dict | None = None
) -> set[str]:
    counts: dict[str, int] = {}
    effective_config = _merge_participant_filter_config(participant_filter_config)
    min_count = int(effective_config.get("min_repeated_prefix_count", 3))

    for col in columns:
        match = re.match(r"^([A-Za-z]{2,})[_-]?\d{1,4}$", str(col).strip())
        if not match:
            continue
        prefix = match.group(1).lower()
        counts[prefix] = counts.get(prefix, 0) + 1

    return {prefix for prefix, count in counts.items() if count >= min_count}


def _is_likely_questionnaire_column(
    col_name: str,
    normalized_name: str,
    survey_item_ids: set[str],
    repeated_prefixes: set[str],
) -> bool:
    if normalized_name in survey_item_ids:
        return True

    match = re.match(r"^([A-Za-z]{2,})[_-]?\d{1,4}$", str(col_name).strip())
    if match and match.group(1).lower() in repeated_prefixes:
        return True

    return False


def _filter_participant_relevant_columns(
    df,
    id_column: str,
    library_path: Path | str | None,
    neurobagel_keys: set[str] | None = None,
    participant_filter_config: dict | None = None,
) -> list[str]:
    if df is None or getattr(df, "empty", True):
        return []

    template_columns = _load_participant_template_columns(library_path)
    survey_item_ids = _load_survey_template_item_ids(library_path)
    repeated_prefixes = _detect_repeated_questionnaire_prefixes(
        [str(col) for col in df.columns],
        participant_filter_config=participant_filter_config,
    )

    effective_config = _merge_participant_filter_config(participant_filter_config)
    participant_keywords = {
        str(key).lower().strip()
        for key in effective_config.get(
            "participant_keywords", _PARTICIPANT_RELEVANT_KEYWORDS
        )
        if str(key).strip()
    }
    normalized_nb_keys = {
        _normalize_column_name(key)
        for key in (neurobagel_keys or _DEFAULT_NEUROBAGEL_KEYS)
    }

    selected: list[str] = []
    for col in df.columns:
        col_str = str(col)
        normalized = _normalize_column_name(col_str)

        if col_str == id_column:
            selected.append(col_str)
            continue

        in_template = normalized in template_columns
        nb_match = any(
            nb_key in normalized or normalized in nb_key
            for nb_key in normalized_nb_keys
            if nb_key and normalized
        )
        keyword_match = any(keyword in normalized for keyword in participant_keywords)

        if not (in_template or nb_match or keyword_match):
            continue

        if not in_template and _is_likely_questionnaire_column(
            col_str, normalized, survey_item_ids, repeated_prefixes
        ):
            continue

        selected.append(col_str)

    if id_column in df.columns and id_column not in selected:
        selected.insert(0, id_column)

    if len(selected) <= 1:
        fallback = [id_column] if id_column in df.columns else []
        for col in df.columns:
            col_str = str(col)
            if col_str == id_column:
                continue
            normalized = _normalize_column_name(col_str)
            if _is_likely_questionnaire_column(
                col_str, normalized, survey_item_ids, repeated_prefixes
            ):
                continue
            fallback.append(col_str)
        return fallback if fallback else list(df.columns)

    return selected


def _collect_default_participant_columns(df, id_column: str | None) -> list[str]:
    if df is None or getattr(df, "empty", True):
        return []

    selected: list[str] = []
    if id_column and id_column in df.columns:
        selected.append(str(id_column))

    alias_values = {
        _normalize_column_name(alias)
        for aliases in _DEFAULT_PARTICIPANT_STANDARD_ALIASES.values()
        for alias in aliases
    }

    for col in df.columns:
        col_str = str(col)
        if id_column and col_str == id_column:
            continue

        normalized = _normalize_column_name(col_str)
        if normalized in alias_values and col_str not in selected:
            selected.append(col_str)

    return selected


def _generate_neurobagel_schema(
    df,
    id_column,
    library_path=None,
    participant_filter_config: dict | None = None,
):
    import pandas as pd

    neurobagel_vocab = {
        "age": {
            "term": "nb:Age",
            "label": "Age",
            "type": "continuous",
            "unit": "years",
        },
        "sex": {
            "term": "nb:Sex",
            "label": "Sex",
            "type": "categorical",
            "levels": {
                "M": {"label": "Male", "uri": "nb:BiologicalSex/Male"},
                "F": {"label": "Female", "uri": "nb:BiologicalSex/Female"},
                "O": {"label": "Other", "uri": "nb:BiologicalSex/Other"},
                "1": {"label": "Male", "uri": "nb:BiologicalSex/Male"},
                "2": {"label": "Female", "uri": "nb:BiologicalSex/Female"},
            },
        },
        "gender": {
            "term": "nb:Gender",
            "label": "Gender",
            "type": "categorical",
            "levels": {
                "M": {"label": "Male", "uri": "nb:Gender/Male"},
                "F": {"label": "Female", "uri": "nb:Gender/Female"},
                "NB": {"label": "Non-binary", "uri": "nb:Gender/NonBinary"},
            },
        },
        "handedness": {
            "term": "nb:Handedness",
            "label": "Handedness",
            "type": "categorical",
            "levels": {
                "R": {"label": "Right", "uri": "nb:Handedness/Right"},
                "L": {"label": "Left", "uri": "nb:Handedness/Left"},
                "A": {"label": "Ambidextrous", "uri": "nb:Handedness/Ambidextrous"},
                "1": {"label": "Right", "uri": "nb:Handedness/Right"},
                "2": {"label": "Left", "uri": "nb:Handedness/Left"},
                "3": {"label": "Ambidextrous", "uri": "nb:Handedness/Ambidextrous"},
            },
        },
        "group": {"term": "nb:Group", "label": "Group", "type": "categorical"},
        "diagnosis": {
            "term": "nb:Diagnosis",
            "label": "Diagnosis",
            "type": "categorical",
        },
        "education": {
            "term": "nb:EducationLevel",
            "label": "Education Level",
            "type": "categorical",
            "levels": {
                "1": {"label": "Primary education", "uri": "nb:EducationLevel/Primary"},
                "2": {"label": "Secondary education", "uri": "nb:EducationLevel/Secondary"},
                "3": {"label": "Vocational training", "uri": "nb:EducationLevel/Vocational"},
                "4": {"label": "Bachelor level", "uri": "nb:EducationLevel/Bachelor"},
                "5": {"label": "Master level", "uri": "nb:EducationLevel/Master"},
                "6": {"label": "Doctoral level", "uri": "nb:EducationLevel/Doctoral"},
            },
        },
        "ethnicity": {
            "term": "nb:Ethnicity",
            "label": "Ethnicity",
            "type": "categorical",
        },
        "participant_id": {
            "term": "nb:ParticipantID",
            "label": "Participant ID",
            "type": "string",
        },
        "subject": {
            "term": "nb:ParticipantID",
            "label": "Subject ID",
            "type": "string",
        },
        "sub": {"term": "nb:ParticipantID", "label": "Subject ID", "type": "string"},
    }

    normalized_vocab = {
        _normalize_column_name(key): vocab for key, vocab in neurobagel_vocab.items()
    }

    selected_columns = _filter_participant_relevant_columns(
        df,
        id_column=id_column,
        library_path=library_path,
        neurobagel_keys=set(neurobagel_vocab.keys()),
        participant_filter_config=participant_filter_config,
    )

    if selected_columns:
        df = df[selected_columns]

    schema = {}

    for col in df.columns:
        col_normalized = _normalize_column_name(col)
        col_data = df[col].dropna()
        field = {"Description": "", "Annotations": {}}

        neurobagel_match = None
        for key_normalized, vocab in normalized_vocab.items():
            if key_normalized in col_normalized or col_normalized in key_normalized:
                neurobagel_match = vocab
                break

        if col == id_column:
            data_type = "string"
            is_categorical = False
        else:
            date_name_hint = any(
                token in col_normalized for token in ["date", "time", "timestamp", "datetime"]
            )
            col_text = col_data.astype(str).str.strip()
            if len(col_text) > 0:
                date_like_pattern = r"^(\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{4}[./-]\d{1,2}[./-]\d{1,2})(\s+\d{1,2}:\d{2}(:\d{2})?)?$"
                date_like_ratio = float(col_text.str.match(date_like_pattern, na=False).mean())
                should_try_date_parse = date_name_hint or date_like_ratio >= 0.3
                if should_try_date_parse:
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        parsed_dates = pd.to_datetime(col_text, errors="coerce", dayfirst=True)
                    date_parse_ratio = float(parsed_dates.notna().mean())
                else:
                    date_parse_ratio = 0.0
            else:
                date_parse_ratio = 0.0

            if date_name_hint or date_parse_ratio >= 0.8:
                data_type = "string"
                is_categorical = False
            else:
                try:
                    pd.to_numeric(col_data, errors="raise")
                    unique_count = col_data.nunique()
                    is_categorical = unique_count < 10
                    data_type = "categorical" if is_categorical else "continuous"
                except (ValueError, TypeError):
                    unique_count = col_data.nunique()
                    is_categorical = unique_count < 20
                    data_type = "categorical" if is_categorical else "string"

        if neurobagel_match:
            field["Description"] = neurobagel_match.get("label", col)
            field["Annotations"]["IsAbout"] = {
                "TermURL": neurobagel_match["term"],
                "Label": neurobagel_match["label"],
            }
            field["Annotations"]["VariableType"] = neurobagel_match["type"].capitalize()

            if "unit" in neurobagel_match:
                field["Unit"] = neurobagel_match["unit"]
                if data_type == "continuous":
                    field["Annotations"]["Format"] = {
                        "TermURL": "nb:FromFloat",
                        "Label": "Float",
                    }
        else:
            field["Description"] = f"{col} (auto-detected)"
            field["Annotations"]["VariableType"] = data_type.capitalize()

        if is_categorical and len(col_data) > 0:
            levels = {}
            level_annotations = {}
            unique_vals = col_data.unique()[:50]

            if neurobagel_match and "levels" in neurobagel_match:
                nb_levels = neurobagel_match["levels"]
                for val in unique_vals:
                    val_str = str(val)
                    if val_str in nb_levels:
                        nb_info = nb_levels[val_str]
                        if isinstance(nb_info, dict):
                            levels[val_str] = nb_info.get("label", val_str)
                            level_annotations[val_str] = {
                                "TermURL": nb_info.get("uri"),
                                "Label": nb_info.get("label", val_str),
                            }
                        else:
                            levels[val_str] = nb_info
                    else:
                        levels[val_str] = val_str
            else:
                for val in unique_vals:
                    levels[str(val)] = str(val)

            field["Levels"] = levels
            if level_annotations:
                if "Annotations" not in field:
                    field["Annotations"] = {}
                field["Annotations"]["Levels"] = level_annotations

        schema[col] = field

    return schema
