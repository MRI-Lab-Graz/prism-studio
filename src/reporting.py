"""
Output formatting and reporting utilities
"""

import os
import json


def get_entity_description(dataset_path, prefix, name, stats=None):
    """Try to fetch OriginalName from sidecar or stats"""
    # Try stats first
    if stats:
        desc = stats.get_description(prefix, name)
        if desc:
            return desc

    # Try root level first: prefix-name.json (e.g. survey-ads.json)
    candidates = [
        os.path.join(dataset_path, f"{prefix}-{name}.json"),
        os.path.join(dataset_path, f"{prefix}s", f"{prefix}-{name}.json"),
        os.path.join(dataset_path, f"{name}.json"),  # Fallback
    ]

    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "Study" in data and "OriginalName" in data["Study"]:
                        return data["Study"]["OriginalName"]
            except Exception:
                continue
    return None


def print_dataset_summary(dataset_path, stats):
    """Print a comprehensive dataset summary"""
    print("\n" + "=" * 60)
    print("🗂️  DATASET SUMMARY")
    print("=" * 60)

    # Dataset info
    dataset_name = os.path.basename(os.path.abspath(dataset_path))
    print(f"📁 Dataset: {dataset_name}")

    # Subject and session counts
    num_subjects = len(stats.subjects)
    has_sessions = len(stats.sessions) > 0

    print(f"👥 Subjects: {num_subjects}")

    if has_sessions:
        # stats.sessions is a list of subject/session combinations like "sub-01/ses-01".
        # For the summary, report the number of unique session *labels* (e.g., ses-01),
        # not the number of subject-session folders.
        sessions_per_subject: dict[str, set[str]] = {}
        unique_session_labels: set[str] = set()
        for session in stats.sessions:
            parts = session.split("/")
            subj = parts[0] if parts else session
            ses = parts[1] if len(parts) > 1 else session
            sessions_per_subject.setdefault(subj, set()).add(ses)
            unique_session_labels.add(ses)

        print(f"📋 Sessions: {len(unique_session_labels)} (unique labels)")

        avg_sessions = (
            sum(len(v) for v in sessions_per_subject.values())
            / len(sessions_per_subject)
            if sessions_per_subject
            else 0
        )
        print(f"📊 Sessions per subject: {avg_sessions:.1f} (avg)")
    else:
        print("📋 Sessions: No session structure detected")

    # Modality breakdown
    print(f"\n🎯 MODALITIES ({len(stats.modalities)} found):")
    if stats.modalities:
        for modality, count in sorted(stats.modalities.items()):
            print(f"  • {modality}: {count} files")
    else:
        print("  No modality data found")

    # Task breakdown (exclude items that are surveys or biometrics)
    pure_tasks = {
        t for t in stats.tasks if t not in stats.surveys and t not in stats.biometrics
    }
    print(f"\n📝 TASKS ({len(pure_tasks)} found):")
    if pure_tasks:
        for task in sorted(pure_tasks):
            desc = get_entity_description(dataset_path, "task", task, stats)
            if desc:
                print(f"  • {task} - {desc}")
            else:
                print(f"  • {task}")
    else:
        print("  No tasks detected")

    # Survey breakdown
    print(f"\n📋 SURVEYS ({len(stats.surveys)} found):")
    if stats.surveys:
        for survey in sorted(stats.surveys):
            desc = get_entity_description(dataset_path, "survey", survey, stats)
            if desc:
                print(f"  • {survey} - {desc}")
            else:
                print(f"  • {survey}")
    else:
        print("  No surveys detected")

    # Biometrics breakdown
    print(f"\n🧬 BIOMETRICS ({len(stats.biometrics)} found):")
    if stats.biometrics:
        for biometric in sorted(stats.biometrics):
            desc = get_entity_description(dataset_path, "biometrics", biometric, stats)
            if desc:
                print(f"  • {biometric} - {desc}")
            else:
                print(f"  • {biometric}")
    else:
        print("  No biometrics detected")

    # File statistics intentionally omitted (counts often exclude inherited sidecars and can be misleading)


def get_i18n_text(field, lang="en"):
    """Extract text from an i18n field (string or dict)."""
    if isinstance(field, str):
        return field
    if isinstance(field, dict):
        # Try requested language
        val = field.get(lang)
        if val:
            return val
        # Try English
        val = field.get("en")
        if val:
            return val
        # Try German
        val = field.get("de")
        if val:
            return val
        # Try anything else
        for v in field.values():
            if v:
                return v
    return ""


def _format_reference(ref: dict, lang: str = "en") -> str:
    if not isinstance(ref, dict):
        return ""
    citation = (ref.get("Citation") or "").strip()
    doi = (ref.get("DOI") or "").strip()
    url = (ref.get("URL") or "").strip()
    year = ref.get("Year")

    parts = []
    if citation:
        parts.append(citation)
    elif doi:
        parts.append(f"DOI: {doi}")
    elif url:
        parts.append(url)

    if isinstance(year, int):
        parts.append(str(year))
    if doi and (not citation):
        parts.append(f"DOI: {doi}")
    if url and (not citation) and (url not in parts):
        parts.append(url)
    return "; ".join([p for p in parts if p])


def _pick_references(study: dict, lang: str = "en") -> dict:
    """Return a small structured set of references for reporting."""
    out = {
        "primary": None,
        "manual": None,
        "translation": None,
        "validation": None,
        "norms": None,
    }
    refs = study.get("References") or []
    if not isinstance(refs, list):
        refs = []
    for r in refs:
        if not isinstance(r, dict):
            continue
        t = str(r.get("Type") or "other").strip().lower()
        if t in out and out[t] is None:
            out[t] = _format_reference(r, lang=lang)
    return out


def _instrument_additional_metadata(study: dict) -> list[str]:
    if not isinstance(study, dict):
        return []

    extras: list[str] = []
    doi = (study.get("DOI") or "").strip()
    if doi:
        extras.append(f"Canonical DOI: {doi}.")

    license_id = (study.get("LicenseID") or study.get("License") or "").strip()
    if license_id:
        extras.append(f"License: {license_id}.")

    age_range = study.get("AgeRange")
    if isinstance(age_range, dict):
        min_age = age_range.get("min")
        max_age = age_range.get("max")
        if min_age is not None and max_age is not None:
            extras.append(f"Target age range: {min_age}–{max_age} years.")

    def _format_time_block(block, label):
        if not isinstance(block, dict):
            return None
        min_val = block.get("min")
        max_val = block.get("max")
        if min_val is None or max_val is None:
            return None
        return f"{label} {min_val}–{max_val} minutes."

    admin_time = _format_time_block(study.get("AdministrationTime"), "Administration time:")
    if admin_time:
        extras.append(admin_time)

    scoring_time = _format_time_block(study.get("ScoringTime"), "Scoring time:")
    if scoring_time:
        extras.append(scoring_time)

    item_count = study.get("ItemCount")
    if isinstance(item_count, int):
        extras.append(f"Item count: {item_count}.")

    access = (study.get("Access") or "").strip()
    if access:
        extras.append(f"Access level: {access}.")

    return extras


def generate_methods_text(
    library_dirs_or_files,
    output_file,
    lang="en",
    github_url=None,
    schema_version=None,
):
    """
    Generates a formal methods section boilerplate based on PRISM library templates.
    library_dirs_or_files can be a list of directories or a list of specific JSON files.
    """
    from pathlib import Path

    sections = []

    # 1. General PRISM/BIDS Section
    sections.append("## Data Standardization and Validation\n")

    prism_desc = (
        "Data were organized and validated according to the PRISM (Psychological Research Information System & Metadata) "
        "standard, which extends the Brain Imaging Data Structure (BIDS; Gorgolewski et al., 2016) to psychological "
        "and behavioral research. This framework ensures high interoperability and machine-readability by enforcing "
        "standardized filename patterns and comprehensive metadata sidecars in JSON format. All datasets were "
        "automatically validated for structural integrity and schema compliance using the PRISM validator."
    )

    if schema_version:
        prism_desc += f" The dataset follows PRISM schema version {schema_version}."

    if github_url:
        prism_desc += f" More information about the PRISM standard and tools can be found at {github_url}."

    sections.append(prism_desc)

    # 2. Modalities
    surveys = []
    biometrics = []

    all_files = []
    for item in library_dirs_or_files:
        p = Path(item)
        if p.is_dir():
            all_files.extend(list(p.glob("*.json")))
        else:
            all_files.append(p)

    for file_path in all_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if file_path.name.startswith("survey-"):
                surveys.append(data)
            elif file_path.name.startswith("biometrics-"):
                biometrics.append(data)
        except Exception:
            continue

    # 3. Surveys Section
    if surveys:
        sections.append("\n## Psychological Assessments\n")
        sections.append(
            f"A total of {len(surveys)} psychological instruments were administered. "
            "For each instrument, metadata including item descriptions, response scales, "
            "and scoring procedures were documented in machine-readable JSON sidecars."
        )

        for s in surveys:
            study = s.get("Study", {})
            name = get_i18n_text(study.get("OriginalName") or study.get("TaskName"), lang)
            desc = get_i18n_text(study.get("Description"), lang)
            refs = _pick_references(study, lang)

            text = f"\n### {name}\n\n"
            sentences = []
            if desc:
                sentences.append(desc)
            if refs["primary"]:
                sentences.append(f"The instrument is based on {refs['primary']}.")
            if refs["translation"]:
                sentences.append(f"The translation used is {refs['translation']}.")
            sentences.extend(_instrument_additional_metadata(study))
            if sentences:
                paragraph = " ".join(sentences).strip()
                text += f"{paragraph}\n"

            sections.append(text)

    # 4. Biometrics Section
    if biometrics:
        sections.append("\n## Biometric and Physiological Measures\n")
        for b in biometrics:
            study = b.get("Study", {})
            name = get_i18n_text(study.get("OriginalName") or study.get("TaskName"), lang)
            tech = b.get("Technical", {})
            device = tech.get("Manufacturer") or tech.get("SoftwarePlatform")

            text = f"\n### {name}\n\n"
            sentences = []
            if device:
                sentences.append(f"Data were recorded using {device}.")
            sentences.extend(_instrument_additional_metadata(study))
            if sentences:
                paragraph = " ".join(sentences).strip()
                text += f"{paragraph}\n"
            sections.append(text)

    # Write to file
    content = "\n".join(sections)
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"✅ Methods boilerplate written to {output_file}")
        
        # Also generate HTML version
        try:
            html_path = Path(output_file).with_suffix(".html")
            html_content = [
                "<!DOCTYPE html>",
                "<html>",
                "<head>",
                '<meta charset="utf-8">',
                "<style>",
                "body { font-family: sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; }",
                "h2 { color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 40px; }",
                "h3 { color: #34495e; margin-top: 30px; }",
                "p { margin: 15px 0; }",
                "ul { padding-left: 20px; }",
                "li { margin-bottom: 5px; }",
                "code { background: #f8f9fa; padding: 2px 4px; border-radius: 3px; font-family: monospace; }",
                "strong { color: #2c3e50; }",
                "</style>",
                "</head>",
                "<body>"
            ]
            
            in_list = False
            for line in sections:
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith("- "):
                    if not in_list:
                        html_content.append("<ul>")
                        in_list = True
                    
                    li_text = line[2:]
                    while "`" in li_text:
                        li_text = li_text.replace("`", "<code>", 1).replace("`", "</code>", 1)
                    html_content.append(f"  <li>{li_text}</li>")
                    continue
                
                # If we were in a list and the line doesn't start with "- ", close the list
                if in_list:
                    html_content.append("</ul>")
                    in_list = False

                if line.startswith("## "):
                    html_content.append(f"<h2>{line[3:]}</h2>")
                elif line.startswith("### "):
                    html_content.append(f"<h3>{line[4:]}</h3>")
                elif line.startswith("**"):
                    # Handle bold headers like **Scoring**:
                    bold_text = line.replace("**", "").strip().strip(":")
                    html_content.append(f"<p><strong>{bold_text}:</strong></p>")
                else:
                    # Handle backticks in paragraphs
                    p_text = line
                    while "`" in p_text:
                        p_text = p_text.replace("`", "<code>", 1).replace("`", "</code>", 1)
                    html_content.append(f"<p>{p_text}</p>")
            
            if in_list:
                html_content.append("</ul>")
            
            html_content.append("</body></html>")
            
            with open(html_path, "w", encoding="utf-8") as f:
                f.write("\n".join(html_content))
            print(f"✅ Methods boilerplate (HTML) written to {html_path}")
        except Exception as e:
            print(f"⚠️ Could not generate HTML boilerplate: {e}")
    else:
        print(content)

    return content


def print_validation_results(problems, show_bids_warnings=True):
    """Print validation results with proper categorization"""
    if not problems:
        print("\n" + "=" * 60)
        print("✅ VALIDATION RESULTS")
        print("=" * 60)
        print("🎉 No issues found! Dataset is valid.")
        return

    # Normalize problems to (level, message) pairs.
    normalized: list[tuple[str, str]] = []
    for problem in problems:
        # Structured Issue object
        if hasattr(problem, "severity") and hasattr(problem, "message"):
            try:
                level = problem.severity.value  # type: ignore[attr-defined]
            except Exception:
                level = str(problem.severity)  # type: ignore[attr-defined]
            normalized.append((level, str(problem.message)))  # type: ignore[attr-defined]
            continue

        # Legacy tuple format: (level, message) or (level, message, file_path)
        if isinstance(problem, tuple) and len(problem) >= 2:
            level = str(problem[0])
            message = str(problem[1])
            if len(problem) >= 3 and problem[2]:
                message = f"{message} (File: {problem[2]})"
            normalized.append((level, message))
            continue

        # Fallback: stringify unknown structures
        normalized.append(("INFO", str(problem)))

    # Categorize problems
    errors = [msg for level, msg in normalized if level == "ERROR"]
    warnings = [msg for level, msg in normalized if level == "WARNING"]
    infos = [msg for level, msg in normalized if level == "INFO"]

    # Split BIDS vs PRISM
    bids_errors = [e for e in errors if e.startswith("[BIDS]")]
    prism_errors = [e for e in errors if not e.startswith("[BIDS]")]

    bids_warnings = [w for w in warnings if w.startswith("[BIDS]")]
    prism_warnings = [w for w in warnings if not w.startswith("[BIDS]")]

    bids_infos = [i for i in infos if i.startswith("[BIDS]")]
    prism_infos = [i for i in infos if not i.startswith("[BIDS]")]

    print("\n" + "=" * 60)
    print("🔍 VALIDATION RESULTS")
    print("=" * 60)

    # --- PRISM ISSUES ---
    if prism_errors or prism_warnings or prism_infos:
        print("\n🔸 PRISM VALIDATOR REPORT:")

        if prism_errors:
            print(f"\n\033[31m  🔴 ERRORS ({len(prism_errors)}):\033[0m")
            for i, error in enumerate(prism_errors, 1):
                print(f"    \033[31m{i:2d}. {error}\033[0m")

        if prism_warnings:
            print(f"\n\033[33m  🟡 WARNINGS ({len(prism_warnings)}):\033[0m")
            for i, warning in enumerate(prism_warnings, 1):
                print(f"    \033[33m{i:2d}. {warning}\033[0m")

        if prism_infos:
            print(f"\n\033[34m  🔵 INFO ({len(prism_infos)}):\033[0m")
            for i, info in enumerate(prism_infos, 1):
                print(f"    \033[34m{i:2d}. {info}\033[0m")

    # --- BIDS ISSUES ---
    if bids_errors or bids_warnings or bids_infos:
        print("\n🔹 BIDS VALIDATOR REPORT:")

        if bids_errors:
            print(f"\n\033[31m  🔴 ERRORS ({len(bids_errors)}):\033[0m")
            for i, error in enumerate(bids_errors, 1):
                # Strip [BIDS] prefix for cleaner output since we are in BIDS section
                clean_error = error.replace("[BIDS] ", "", 1)
                print(f"    \033[31m{i:2d}. {clean_error}\033[0m")

        if bids_warnings:
            if show_bids_warnings:
                print(f"\n\033[33m  🟡 WARNINGS ({len(bids_warnings)}):\033[0m")
                for i, warning in enumerate(bids_warnings, 1):
                    clean_warning = warning.replace("[BIDS] ", "", 1)
                    print(f"    \033[33m{i:2d}. {clean_warning}\033[0m")
            else:
                print(
                    f"\n\033[33m  🟡 WARNINGS ({len(bids_warnings)}): [Hidden] Use --bids-warnings to view\033[0m"
                )

        if bids_infos:
            print(f"\n\033[34m  🔵 INFO ({len(bids_infos)}):\033[0m")
            for i, info in enumerate(bids_infos, 1):
                clean_info = info.replace("[BIDS] ", "", 1)
                print(f"    \033[34m{i:2d}. {clean_info}\033[0m")

    # Summary line
    print(
        f"\n📊 SUMMARY: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} info"
    )

    if errors:
        print("❌ Dataset validation failed due to errors.")
    else:
        print("⚠️  Dataset has warnings but no critical errors.")
