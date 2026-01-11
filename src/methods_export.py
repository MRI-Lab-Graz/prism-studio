"""
APA-style Methods Section Generator for PRISM datasets.

Generates publication-ready methods sections from dataset metadata.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict, List, Any


def generate_apa_methods(project_path: str, lang: str = "en") -> str:
    """
    Generate an APA-style methods section for a PRISM dataset.

    Args:
        project_path: Path to the PRISM project root
        lang: Language code for i18n text (default: "en")

    Returns:
        Markdown string with APA-formatted methods section
    """
    sections = []

    # Load dataset_description.json
    dataset_desc = _load_dataset_description(project_path)

    # Load participants data
    participants_data = _load_participants_data(project_path)

    # Load survey templates from library
    survey_templates = _load_survey_templates(project_path)

    # Generate Method header
    sections.append("# Method\n")

    # 1. Participants Section
    sections.append(_generate_participants_section(dataset_desc, participants_data, lang))

    # 2. Measures Section
    if survey_templates:
        sections.append(_generate_measures_section(survey_templates, lang))

    # 3. Procedure Section
    sections.append(_generate_procedure_section(dataset_desc, survey_templates, lang))

    # 4. Data Processing Section
    sections.append(_generate_data_processing_section(dataset_desc))

    return "\n".join(sections)


def _load_dataset_description(project_path: str) -> Dict[str, Any]:
    """Load dataset_description.json from project."""
    desc_path = os.path.join(project_path, "dataset_description.json")
    if os.path.exists(desc_path):
        try:
            with open(desc_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _load_participants_data(project_path: str) -> Dict[str, Any]:
    """Load participants.tsv and participants.json data."""
    result = {"count": 0, "demographics": {}}

    # Try to read participants.tsv for count
    tsv_path = os.path.join(project_path, "participants.tsv")
    if os.path.exists(tsv_path):
        try:
            with open(tsv_path, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                if len(lines) > 1:  # Header + data rows
                    result["count"] = len(lines) - 1

                    # Parse demographics
                    header = lines[0].split("\t")
                    data_rows = [l.split("\t") for l in lines[1:]]

                    # Try to extract age and sex statistics
                    if "age" in header:
                        age_idx = header.index("age")
                        ages = []
                        for row in data_rows:
                            if len(row) > age_idx and row[age_idx]:
                                try:
                                    ages.append(float(row[age_idx]))
                                except ValueError:
                                    pass
                        if ages:
                            result["demographics"]["age"] = {
                                "mean": round(sum(ages) / len(ages), 1),
                                "min": min(ages),
                                "max": max(ages)
                            }

                    if "sex" in header:
                        sex_idx = header.index("sex")
                        sex_counts = {}
                        for row in data_rows:
                            if len(row) > sex_idx and row[sex_idx]:
                                sex = row[sex_idx].upper()
                                sex_counts[sex] = sex_counts.get(sex, 0) + 1
                        if sex_counts:
                            result["demographics"]["sex"] = sex_counts
        except Exception:
            pass

    # Count subjects from directory structure if tsv not available
    if result["count"] == 0:
        try:
            for item in os.listdir(project_path):
                if item.startswith("sub-") and os.path.isdir(os.path.join(project_path, item)):
                    result["count"] += 1
        except Exception:
            pass

    return result


def _load_survey_templates(project_path: str) -> List[Dict[str, Any]]:
    """Load all survey templates from library."""
    templates = []
    library_path = os.path.join(project_path, "library", "survey")

    if os.path.isdir(library_path):
        for fname in sorted(os.listdir(library_path)):
            if fname.startswith("survey-") and fname.endswith(".json"):
                template_path = os.path.join(library_path, fname)
                try:
                    with open(template_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data["_filename"] = fname
                        templates.append(data)
                except Exception:
                    pass

    return templates


def _get_i18n_text(value: Any, lang: str = "en") -> str:
    """Extract text from i18n object or return string directly."""
    if isinstance(value, dict):
        return value.get(lang) or value.get("en") or list(value.values())[0] if value else ""
    return str(value) if value else ""


def _generate_participants_section(
    dataset_desc: Dict[str, Any],
    participants_data: Dict[str, Any],
    lang: str
) -> str:
    """Generate APA Participants subsection."""
    lines = ["## Participants\n"]

    n = participants_data.get("count", 0)
    demographics = participants_data.get("demographics", {})

    # Build participants sentence
    parts = []

    if n > 0:
        # Basic count
        if demographics.get("sex"):
            sex_counts = demographics["sex"]
            sex_parts = []
            for sex, count in sorted(sex_counts.items()):
                label = {"M": "male", "F": "female", "O": "other"}.get(sex, sex.lower())
                sex_parts.append(f"{count} {label}")
            parts.append(f"*N* = {n} participants ({', '.join(sex_parts)})")
        else:
            parts.append(f"*N* = {n} participants")

        # Age info
        if demographics.get("age"):
            age = demographics["age"]
            parts.append(f"aged {age['min']:.0f}-{age['max']:.0f} years (*M* = {age['mean']:.1f})")

        parts.append("participated in this study")
    else:
        parts.append("[Sample size and demographics to be added]")

    lines.append(". ".join(parts) + ".")

    # Ethics approval
    ethics = dataset_desc.get("EthicsApprovals", [])
    if ethics:
        if isinstance(ethics[0], dict):
            committee = ethics[0].get("committee", "the institutional ethics committee")
            approval = ethics[0].get("approval_number", "")
            if approval:
                lines.append(f" The study was approved by {committee} (approval number: {approval}).")
            else:
                lines.append(f" The study was approved by {committee}.")
        else:
            lines.append(f" The study was approved by {ethics[0]}.")
    else:
        lines.append(" [Ethics approval information to be added].")

    lines.append("")
    return "\n".join(lines)


def _generate_measures_section(templates: List[Dict[str, Any]], lang: str) -> str:
    """Generate APA Measures/Materials subsection."""
    lines = ["## Measures\n"]

    for template in templates:
        study = template.get("Study", {})

        # Get instrument name
        original_name = _get_i18n_text(study.get("OriginalName"), lang)
        short_name = _get_i18n_text(study.get("ShortName"), lang)
        task_name = study.get("TaskName", "")

        if original_name:
            name = original_name
        elif short_name:
            name = short_name
        else:
            name = task_name.upper() if task_name else template.get("_filename", "Unknown")

        lines.append(f"### {name}\n")

        # Build instrument description
        paragraphs = []

        # First sentence: What it is
        item_count = study.get("ItemCount")
        construct = _get_i18n_text(study.get("Construct"), lang)

        # Get citation
        citation = _get_citation(study)

        intro_parts = []
        if short_name and short_name != name:
            intro_parts.append(f"The {name} ({short_name})")
        else:
            intro_parts.append(f"The {name}")

        if citation:
            intro_parts.append(f"({citation})")

        if item_count:
            intro_parts.append(f"is a {item_count}-item")
        else:
            intro_parts.append("is a")

        # Determine respondent type
        technical = template.get("Technical", {})
        respondent = technical.get("Respondent", "self")
        if respondent == "self":
            intro_parts.append("self-report measure")
        elif respondent == "clinician":
            intro_parts.append("clinician-administered measure")
        else:
            intro_parts.append("measure")

        if construct:
            intro_parts.append(f"of {construct}")

        paragraphs.append(" ".join(intro_parts) + ".")

        # Description
        description = _get_i18n_text(study.get("Description"), lang)
        if description and len(description) > 30:
            paragraphs.append(description)

        # Reliability
        reliability = _get_i18n_text(study.get("Reliability"), lang)
        if reliability:
            paragraphs.append(f"The instrument has demonstrated {reliability}.")

        # Administration time
        admin_time = study.get("AdministrationTime")
        if admin_time:
            if isinstance(admin_time, dict):
                min_t = admin_time.get("min", 0)
                max_t = admin_time.get("max", 0)
                if min_t == max_t:
                    paragraphs.append(f"Administration time is approximately {min_t} minutes.")
                else:
                    paragraphs.append(f"Administration time is approximately {min_t}-{max_t} minutes.")
            else:
                paragraphs.append(f"Administration time is approximately {admin_time} minutes.")

        # Translation info
        translation = study.get("Translation", {})
        if translation.get("Validated"):
            source_lang = translation.get("SourceLanguage", "")
            target_lang = translation.get("TargetLanguage", "")
            trans_ref = translation.get("Reference", "")
            if source_lang and target_lang:
                trans_sentence = f"A validated {target_lang} translation"
                if trans_ref:
                    trans_sentence += f" ({trans_ref})"
                trans_sentence += " was used."
                paragraphs.append(trans_sentence)

        lines.append(" ".join(paragraphs))
        lines.append("")

    return "\n".join(lines)


def _get_citation(study: Dict[str, Any]) -> str:
    """Extract citation from study metadata."""
    # Try References array first
    refs = study.get("References", [])
    for ref in refs:
        if isinstance(ref, dict) and ref.get("Type") == "primary":
            return ref.get("Citation", "")

    # Fall back to Citation field
    if study.get("Citation"):
        return study["Citation"]

    # Fall back to DOI
    if study.get("DOI"):
        return f"https://doi.org/{study['DOI']}"

    return ""


def _generate_procedure_section(
    dataset_desc: Dict[str, Any],
    templates: List[Dict[str, Any]],
    lang: str
) -> str:
    """Generate APA Procedure subsection."""
    lines = ["## Procedure\n"]

    paragraphs = []

    # List measures administered
    if templates:
        measure_names = []
        for t in templates:
            study = t.get("Study", {})
            name = _get_i18n_text(study.get("ShortName"), lang) or \
                   _get_i18n_text(study.get("OriginalName"), lang) or \
                   study.get("TaskName", "")
            if name:
                measure_names.append(name)

        if measure_names:
            if len(measure_names) == 1:
                paragraphs.append(f"Participants completed the {measure_names[0]}.")
            elif len(measure_names) == 2:
                paragraphs.append(f"Participants completed the {measure_names[0]} and {measure_names[1]}.")
            else:
                listed = ", ".join(measure_names[:-1]) + f", and {measure_names[-1]}"
                paragraphs.append(f"Participants completed the following measures: {listed}.")

    # Data collection info
    data_collection = dataset_desc.get("DataCollection", {})
    if data_collection:
        collection_parts = []

        start_date = data_collection.get("start_date", "")
        end_date = data_collection.get("end_date", "")
        location = data_collection.get("location", "")

        if start_date and end_date:
            collection_parts.append(f"Data were collected between {start_date} and {end_date}")
        elif start_date:
            collection_parts.append(f"Data collection began in {start_date}")

        if location:
            if collection_parts:
                collection_parts.append(f"at {location}")
            else:
                collection_parts.append(f"Data were collected at {location}")

        if collection_parts:
            paragraphs.append(" ".join(collection_parts) + ".")

    # Administration method
    if templates:
        tech = templates[0].get("Technical", {})
        method = tech.get("AdministrationMethod", "") or tech.get("ResponseType", "")
        if isinstance(method, list):
            method = method[0] if method else ""

        platform = tech.get("SoftwarePlatform", "")

        if method == "online" and platform:
            paragraphs.append(f"All measures were administered online via {platform}.")
        elif method == "online":
            paragraphs.append("All measures were administered online.")
        elif method and platform:
            paragraphs.append(f"Measures were administered using {platform}.")

    if paragraphs:
        lines.append(" ".join(paragraphs))
    else:
        lines.append("[Procedure details to be added]")

    lines.append("")
    return "\n".join(lines)


def _generate_data_processing_section(dataset_desc: Dict[str, Any]) -> str:
    """Generate Data Processing subsection."""
    lines = ["## Data Processing\n"]

    prism_desc = (
        "Data were organized according to the PRISM (Psychological Research Information "
        "System & Metadata) standard, which extends the Brain Imaging Data Structure "
        "(BIDS; Gorgolewski et al., 2016) to psychological and behavioral research. "
        "This framework ensures machine-readable metadata and standardized filename "
        "patterns for all measures. Data quality was validated using PRISM Studio."
    )

    lines.append(prism_desc)
    lines.append("")

    # References
    lines.append("### References\n")
    lines.append(
        "Gorgolewski, K. J., Auer, T., Calhoun, V. D., Craddock, R. C., Das, S., Duff, E. P., ... & Poldrack, R. A. (2016). "
        "The brain imaging data structure, a format for organizing and describing outputs of neuroimaging experiments. "
        "*Scientific Data, 3*, 160044. https://doi.org/10.1038/sdata.2016.44"
    )
    lines.append("")

    return "\n".join(lines)
