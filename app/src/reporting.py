"""
Output formatting and reporting utilities
"""

from __future__ import annotations

import os
import json

from src import __version__ as prism_version


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
            parts = session.split(os.sep)
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

    tasks_to_show = set(pure_tasks)
    if hasattr(stats, "func_tasks"):
        tasks_to_show.update(stats.func_tasks)
    if hasattr(stats, "eeg_tasks"):
        tasks_to_show.update(stats.eeg_tasks)

    print(f"\n📝 TASKS ({len(tasks_to_show)} found):")
    if tasks_to_show:
        for task in sorted(tasks_to_show):
            # Badge or prefix for modality
            prefix = ""
            if hasattr(stats, "func_tasks") and task in stats.func_tasks:
                prefix = "[func] "
            elif hasattr(stats, "eeg_tasks") and task in stats.eeg_tasks:
                prefix = "[eeg] "

            desc = get_entity_description(dataset_path, "task", task, stats)
            if desc:
                print(f"  • {prefix}{task} - {desc}")
            else:
                print(f"  • {prefix}{task}")
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

    admin_time = _format_time_block(
        study.get("AdministrationTime"), "Administration time:"
    )
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


def _md_inline(text: str) -> str:
    """Convert markdown inline formatting to HTML (bold, italic)."""
    import re

    # Bold (**text**)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Italic (*text*)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    return text


def _md_to_html(md_text: str) -> str:
    """Convert simple markdown to standalone HTML with embedded styles."""
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        '<meta charset="utf-8">',
        "<style>",
        "body { font-family: 'Times New Roman', Times, serif; line-height: 1.8; max-width: 800px; margin: 40px auto; padding: 0 20px; color: #333; font-size: 12pt; }",
        "h2 { color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; margin-top: 40px; }",
        "h3 { color: #34495e; margin-top: 30px; }",
        "p { margin: 10px 0; text-align: justify; }",
        "ul { padding-left: 20px; }",
        "li { margin-bottom: 5px; }",
        "</style>",
        "</head>",
        "<body>",
    ]
    in_list = False
    for line in md_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            continue
        if stripped.startswith("- "):
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"  <li>{_md_inline(stripped[2:])}</li>")
            continue
        if in_list:
            html_parts.append("</ul>")
            in_list = False
        if stripped.startswith("## "):
            html_parts.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("### "):
            html_parts.append(f"<h3>{stripped[4:]}</h3>")
        else:
            html_parts.append(f"<p>{_md_inline(stripped)}</p>")
    if in_list:
        html_parts.append("</ul>")
    html_parts.append("</body></html>")
    return "\n".join(html_parts)


def _get_apa_citation(study: dict) -> str:
    """Extract a clean APA-style citation string from a template's Study block.

    Handles both the flat legacy format (Study.Citation) and the newer
    Study.References array format.  Returns an empty string when nothing
    usable is found.
    """
    # 1. Try structured References array (preferred)
    refs = study.get("References") or []
    if isinstance(refs, list):
        for r in refs:
            if not isinstance(r, dict):
                continue
            if str(r.get("Type", "")).strip().lower() == "primary":
                cit = (r.get("Citation") or "").strip()
                if cit:
                    return cit.replace("\n", " ")

    # 2. Flat legacy format
    cit = (study.get("Citation") or "").strip()
    if cit:
        return cit.replace("\n", " ")

    # 3. Build a minimal reference from Authors + Year
    authors = study.get("Authors") or []
    year = study.get("Year")
    if isinstance(authors, list) and authors and year:
        author_str = ", ".join(a for a in authors if a)
        return f"{author_str} ({year})"
    return ""


def _get_translation_citation(study: dict) -> str:
    """Extract APA citation for a translation reference, if available."""
    refs = study.get("References") or []
    if isinstance(refs, list):
        for r in refs:
            if not isinstance(r, dict):
                continue
            if str(r.get("Type", "")).strip().lower() == "translation":
                cit = (r.get("Citation") or "").strip()
                if cit:
                    return cit.replace("\n", " ")
    return ""


def _count_items(template: dict) -> int | None:
    """Count the number of items in a template.

    Tries NumberOfItems → ItemCount → counting item keys (non-metadata).
    Returns None if unknown.
    """
    study = template.get("Study") or {}
    n = study.get("NumberOfItems") or study.get("ItemCount")
    if isinstance(n, int) and n > 0:
        return n
    # Count item keys: everything that's not a metadata section
    reserved = {"Study", "Technical", "I18n", "Scoring"}
    item_keys = [k for k in template if k not in reserved]
    return len(item_keys) if item_keys else None


def _get_response_format(template: dict) -> str | None:
    """Extract the response scale description from the first item's Levels."""
    reserved = {"Study", "Technical", "I18n", "Scoring"}
    for key, val in template.items():
        if key in reserved or not isinstance(val, dict):
            continue
        levels = val.get("Levels")
        if not isinstance(levels, dict) or not levels:
            continue
        n_levels = len(levels)
        # Get first and last level labels
        sorted_keys = sorted(
            levels.keys(), key=lambda x: (int(x) if x.isdigit() else 0, x)
        )
        first_label = ""
        last_label = ""
        if sorted_keys:
            first_val = levels[sorted_keys[0]]
            last_val = levels[sorted_keys[-1]]
            first_label = (
                get_i18n_text(first_val)
                if isinstance(first_val, (str, dict))
                else str(first_val)
            )
            last_label = (
                get_i18n_text(last_val)
                if isinstance(last_val, (str, dict))
                else str(last_val)
            )
            # Strip score prefixes like "{score=0} "
            import re

            first_label = re.sub(r"\{score=\d+\}\s*", "", first_label).strip()
            last_label = re.sub(r"\{score=\d+\}\s*", "", last_label).strip()
        if first_label and last_label and n_levels > 1:
            return f'{n_levels}-point Likert scale (from "{first_label}" to "{last_label}")'
        return f"{n_levels}-point scale"
    return None


def _session_display_label(sess: dict, index: int) -> str:
    """Return a human-readable session label for use in prose.

    Strips the 'ses-' prefix and capitalises, e.g. 'ses-01' -> 'Session 01',
    'ses-baseline' -> 'Baseline'.  Falls back to 'Session N'.
    """
    raw = sess.get("label", "")
    if not raw:
        raw = sess.get("id", "")
    if not raw:
        return f"Session {index + 1}"
    # Strip ses- prefix for display
    if raw.lower().startswith("ses-"):
        stripped = raw[4:]
        # If purely numeric, keep as "Session <num>"
        if stripped.isdigit():
            return f"Session {stripped}"
        return stripped.capitalize()
    return raw


def generate_full_methods(
    project_data: dict,
    dataset_desc: dict | None,
    template_data: dict[str, dict],
    participant_stats: dict | None = None,
    lang: str = "en",
    detail_level: str = "standard",
    continuous: bool = False,
) -> tuple[str, list[str]]:
    """Generate a publication-ready methods section from project.json metadata.

    Args:
        project_data: Parsed project.json contents.
        dataset_desc: Parsed dataset_description.json contents (or None).
        template_data: Mapping of task_name -> loaded template JSON.
        participant_stats: Demographics summary from participants.tsv (or None).
        lang: Language code for i18n fields.
        detail_level: "brief", "standard", or "detailed".
        continuous: If True, omit section headings for a single flowing text.

    Returns:
        Tuple of (markdown_text, list_of_section_names_used).
    """
    import re as _re

    sections: list[str] = []
    sections_used: list[str] = []
    pstats = participant_stats or {}
    is_detailed = detail_level == "detailed"
    is_brief = detail_level == "brief"

    def _heading(level: int, text: str) -> str:
        if continuous:
            return ""
        prefix = "#" * level
        return f"{prefix} {text}\n"

    dd = dataset_desc or {}

    # --- Study Design ---
    sd = project_data.get("StudyDesign") or {}
    if sd:
        parts: list[str] = []
        sd_type = sd.get("Type", "")
        sd_desc = sd.get("TypeDescription", "")
        if sd_type:
            label = sd_type.replace("-", " ")
            parts.append(f"The present study employed a {label} design.")
        if sd_desc:
            parts.append(sd_desc.rstrip(".") + ".")
        if not is_brief:
            blinding = sd.get("Blinding", "")
            if blinding and blinding != "none":
                parts.append(f"A {blinding.replace('-', ' ')} procedure was used.")
            randomization = sd.get("Randomization", "")
            if randomization:
                parts.append(randomization.rstrip(".") + ".")
            control = sd.get("ControlCondition", "")
            if control:
                parts.append(
                    f"The control condition consisted of {control.rstrip('.')}."
                )
        if parts:
            h = _heading(2, "Study Design")
            if h:
                sections.append(h)
            sections.append(" ".join(parts))
            sections_used.append("StudyDesign")

    # --- Participants ---
    recruitment = project_data.get("Recruitment") or {}
    eligibility = project_data.get("Eligibility") or {}
    has_pstats = bool(pstats.get("n"))
    if recruitment or eligibility or has_pstats:
        parts: list[str] = []

        if has_pstats:
            n = pstats["n"]
            age_mean = pstats.get("age_mean")
            age_sd = pstats.get("age_sd")
            age_min = pstats.get("age_min")
            age_max = pstats.get("age_max")
            sex_counts = pstats.get("sex_counts") or {}

            sample_sent = f"The final sample consisted of *N* = {n} participants"
            sex_parts = []
            for label, count in sex_counts.items():
                pct = (count / n * 100) if n else 0
                sex_parts.append(f"{count} {label} ({pct:.1f}%)")
            if sex_parts:
                sample_sent += f" ({', '.join(sex_parts)})"
            sample_sent += "."
            parts.append(sample_sent)

            if age_mean is not None and age_sd is not None:
                if age_min is not None and age_max is not None:
                    parts.append(
                        f"Participants were aged between {age_min} and {age_max} years "
                        f"(*M* = {age_mean:.1f}, *SD* = {age_sd:.1f})."
                    )
                else:
                    parts.append(
                        f"The mean age was {age_mean:.1f} years (*SD* = {age_sd:.1f})."
                    )
            elif age_mean is not None:
                parts.append(f"The mean age was {age_mean:.1f} years.")

            # Additional demographic columns — only if detailed or standard
            if not is_brief:
                for col_info in pstats.get("additional_columns") or []:
                    col_name = col_info.get("name", "")
                    col_values = col_info.get("distribution") or {}
                    if col_name and col_values:
                        # Count total valid responses for this column
                        col_total = sum(col_values.values())
                        dist_parts = []
                        for val, count in col_values.items():
                            pct = (count / col_total * 100) if col_total else 0
                            dist_parts.append(f"{val}: *n* = {count} ({pct:.1f}%)")
                        parts.append(
                            f"Regarding {col_name.lower()}: {'; '.join(dist_parts)}."
                        )
            sections_used.append("SampleDescription")

        method = recruitment.get("Method", "")
        if method:
            parts.append(f"Participants were recruited via {method.rstrip('.')}.")
        location = recruitment.get("Location", "")
        if location:
            parts.append(f"Recruitment took place in {location.rstrip('.')}.")
        period = recruitment.get("Period") or {}
        period_start = period.get("Start", "")
        period_end = period.get("End", "")
        if period_start and period_end:
            parts.append(
                f"Data collection occurred between {period_start} and {period_end}."
            )
        elif period_start:
            parts.append(f"Data collection began in {period_start}.")
        if not is_brief:
            platform = recruitment.get("Platform", "")
            if platform:
                parts.append(f"Participants were recruited through {platform}.")
        compensation = recruitment.get("Compensation", "")
        if compensation:
            parts.append(f"Compensation was {compensation.rstrip('.')}.")

        target = eligibility.get("TargetSampleSize")
        if isinstance(target, int) and not is_brief:
            parts.append(f"The target sample size was *N* = {target}.")
        power = eligibility.get("PowerAnalysis", "")
        if power and is_detailed:
            parts.append(power.rstrip(".") + ".")

        inclusion = eligibility.get("InclusionCriteria") or []
        exclusion = eligibility.get("ExclusionCriteria") or []
        if not is_brief:
            if inclusion:
                joined = "; ".join(c.rstrip(".") for c in inclusion)
                parts.append(f"Inclusion criteria were: {joined}.")
            if exclusion:
                joined = "; ".join(c.rstrip(".") for c in exclusion)
                parts.append(f"Exclusion criteria were: {joined}.")

        if parts:
            h = _heading(2, "Participants")
            if h:
                sections.append("\n" + h)
            sections.append(" ".join(parts))
            if "Participants" not in sections_used:
                sections_used.append("Participants")

    # --- Experimental Conditions ---
    conditions = project_data.get("Conditions") or {}
    cond_type = conditions.get("Type", "")
    groups = conditions.get("Groups") or []
    if cond_type and groups and not is_brief:
        parts: list[str] = []
        parts.append(
            f"The study used a {cond_type.replace('-', ' ')} design with {len(groups)} conditions:"
        )
        group_labels = [g.get("label", g.get("id", "?")) for g in groups]
        parts.append(", ".join(group_labels) + ".")
        if is_detailed:
            for g in groups:
                desc = g.get("description", "")
                if desc:
                    parts.append(
                        f"The {g.get('label', g.get('id', '?'))} condition: {desc.rstrip('.')}."
                    )
        h = _heading(2, "Experimental Conditions")
        if h:
            sections.append("\n" + h)
        sections.append(" ".join(parts))
        sections_used.append("Conditions")

    # --- Procedure ---
    procedure = project_data.get("Procedure") or {}
    sessions = project_data.get("Sessions") or []
    task_defs = project_data.get("TaskDefinitions") or {}
    if procedure or sessions:
        parts: list[str] = []
        overview = procedure.get("Overview", "")
        if overview:
            parts.append(overview.rstrip(".") + ".")

        informed_consent = procedure.get("InformedConsent", "")
        if informed_consent and not is_brief:
            parts.append(informed_consent.rstrip(".") + ".")

        if sessions:
            n_sessions = len(sessions)
            if n_sessions == 1:
                parts.append("The study comprised a single measurement time point.")
            else:
                parts.append(
                    f"The study comprised {n_sessions} measurement time points."
                )

            for i, sess in enumerate(sessions):
                sess_label = _session_display_label(sess, i)
                timing = sess.get("timingRelativeToBaseline") or {}
                timing_val = timing.get("Value")
                timing_unit = timing.get("Unit", "days")

                if i == 0:
                    sess_intro = f'In the first session ("{sess_label}"), administered at study enrollment,'
                elif isinstance(timing_val, (int, float)) and timing_val > 0:
                    sess_intro = (
                        f'In session {i + 1} ("{sess_label}"), administered approximately '
                        f"{int(timing_val)} {timing_unit} after baseline,"
                    )
                else:
                    sess_intro = f'In session {i + 1} ("{sess_label}"),'

                tasks = sess.get("tasks") or []
                if tasks:
                    grouped: dict[int, list[str]] = {}
                    for t in tasks:
                        eg = t.get("executionGroup", 1)
                        task_name = t.get("task", "")
                        display_name = task_name
                        if task_name in template_data:
                            tpl_study = template_data[task_name].get("Study", {})
                            abbr = tpl_study.get("Abbreviation", "")
                            orig = get_i18n_text(
                                tpl_study.get("OriginalName")
                                or tpl_study.get("TaskName"),
                                lang,
                            )
                            if abbr:
                                display_name = abbr
                            elif orig:
                                display_name = orig
                        elif task_name in task_defs:
                            td_desc = task_defs[task_name].get("description", "")
                            if td_desc:
                                display_name = td_desc
                        grouped.setdefault(eg, []).append(display_name)

                    all_task_names = []
                    for eg_key in sorted(grouped.keys()):
                        all_task_names.extend(grouped[eg_key])

                    if len(all_task_names) == 1:
                        parts.append(
                            f"{sess_intro} participants completed the {all_task_names[0]}."
                        )
                    elif len(all_task_names) == 2:
                        parts.append(
                            f"{sess_intro} participants completed the {all_task_names[0]} and the {all_task_names[1]}."
                        )
                    else:
                        joined = (
                            ", the ".join(all_task_names[:-1])
                            + f", and the {all_task_names[-1]}"
                        )
                        parts.append(
                            f"{sess_intro} participants completed the {joined}."
                        )

        debriefing = procedure.get("Debriefing", "")
        if debriefing and is_detailed:
            parts.append(debriefing.rstrip(".") + ".")

        if parts:
            h = _heading(2, "Procedure")
            if h:
                sections.append("\n" + h)
            sections.append(" ".join(parts))
            sections_used.append("Procedure")

    # --- Measures ---
    if task_defs:
        modality_groups: dict[str, list[tuple[str, dict, dict | None]]] = {}
        for task_name, td in task_defs.items():
            modality = td.get("modality", "other")
            tpl = template_data.get(task_name)
            modality_groups.setdefault(modality, []).append((task_name, td, tpl))

        modality_labels = {
            "survey": "Psychological Assessments",
            "biometrics": "Biometric Measures",
            "physio": "Physiological Measures",
            "eeg": "Electroencephalography (EEG)",
            "eyetracking": "Eye Tracking",
            "func": "Functional Neuroimaging",
            "anat": "Structural Neuroimaging",
            "other": "Other Measures",
        }

        measures_parts: list[str] = []
        total = len(task_defs)

        # Intro sentence with correct grammar
        if total == 1:
            measures_parts.append("A single instrument was administered.")
        else:
            survey_count = len(modality_groups.get("survey", []))
            bio_count = len(modality_groups.get("biometrics", []))
            intro_detail = []
            if survey_count:
                intro_detail.append(
                    f"{survey_count} psychological questionnaire{'s' if survey_count != 1 else ''}"
                )
            if bio_count:
                intro_detail.append(
                    f"{bio_count} biometric measure{'s' if bio_count != 1 else ''}"
                )
            other_count = total - survey_count - bio_count
            if other_count > 0:
                intro_detail.append(
                    f"{other_count} additional measure{'s' if other_count != 1 else ''}"
                )
            if intro_detail:
                measures_parts.append(
                    f"A total of {total} instruments were administered, including {', '.join(intro_detail)}."
                )
            else:
                measures_parts.append(
                    f"A total of {total} instruments were administered."
                )

        for modality in [
            "survey",
            "biometrics",
            "physio",
            "eeg",
            "eyetracking",
            "func",
            "anat",
            "other",
        ]:
            group = modality_groups.get(modality)
            if not group:
                continue

            if not continuous:
                label = modality_labels.get(modality, modality.title())
                measures_parts.append(f"\n### {label}\n")

            for task_name, td, tpl in group:
                study = (tpl or {}).get("Study", {}) if tpl else {}
                name = (
                    get_i18n_text(
                        study.get("OriginalName") or study.get("TaskName"), lang
                    )
                    if study
                    else ""
                )
                if not name:
                    name = td.get("description", "")
                if not name:
                    # Use task_name as last resort but make it presentable
                    name = (
                        _re.sub(r"([a-z])([A-Z])", r"\1 \2", task_name)
                        .replace("-", " ")
                        .replace("_", " ")
                    )
                abbr = study.get("Abbreviation", "") if study else ""

                sentences: list[str] = []
                apa = _get_apa_citation(study) if study else ""
                item_count = _count_items(tpl) if tpl else None
                resp_format = _get_response_format(tpl) if tpl else None

                # Opening sentence
                opening = f"The {name}"
                if abbr and abbr not in name:
                    opening += f" ({abbr})"
                if apa:
                    opening += f" ({apa})"
                details = []
                if item_count:
                    details.append(f"{item_count} items")
                if resp_format and not is_brief:
                    details.append(f"a {resp_format}")
                if details:
                    opening += f" comprises {' and '.join(details)}"
                opening += "."
                sentences.append(opening)

                if not is_brief:
                    desc = (
                        get_i18n_text(study.get("Description"), lang) if study else ""
                    )
                    if desc:
                        sentences.append(desc.rstrip(".") + ".")

                    if study:
                        trans_cit = _get_translation_citation(study)
                        if trans_cit:
                            sentences.append(
                                f"The translation used in this study was validated by {trans_cit}."
                            )

                if is_detailed:
                    subscales = study.get("Subscales") or [] if study else []
                    if subscales:
                        sentences.append(
                            f"The instrument contains the following subscales: {', '.join(subscales)}."
                        )
                    reliability = (
                        get_i18n_text(study.get("Reliability"), lang) if study else ""
                    )
                    if reliability:
                        sentences.append(reliability.rstrip(".") + ".")
                    validity = (
                        get_i18n_text(study.get("Validity"), lang) if study else ""
                    )
                    if validity:
                        sentences.append(validity.rstrip(".") + ".")

                duration = td.get("duration") or {}
                dur_val = duration.get("Value")
                dur_unit = duration.get("Unit", "minutes")
                if isinstance(dur_val, (int, float)) and not is_brief:
                    sentences.append(
                        f"The estimated completion time is {dur_val} {dur_unit}."
                    )

                measures_parts.append(" ".join(sentences))

        if len(measures_parts) > 1:
            h = _heading(2, "Measures")
            if h:
                sections.append("\n" + h)
            sections.append("\n\n".join(measures_parts))
            sections_used.append("Measures")

    # --- Data Collection ---
    dc = project_data.get("DataCollection") or {}
    if dc:
        parts: list[str] = []
        platform = dc.get("Platform", "")
        platform_ver = dc.get("PlatformVersion", "")
        method = dc.get("Method", "")
        setting = dc.get("Setting", "")
        supervision = dc.get("SupervisionLevel", "")

        if platform and method:
            ver_str = f" (version {platform_ver})" if platform_ver else ""
            parts.append(f"Data were collected {method} using {platform}{ver_str}.")
        elif platform:
            ver_str = f" (version {platform_ver})" if platform_ver else ""
            parts.append(f"Data were collected using {platform}{ver_str}.")
        elif method:
            parts.append(f"Data were collected {method}.")

        if setting and not is_brief:
            parts.append(setting.rstrip(".") + ".")
        if supervision and not is_brief:
            parts.append(f"Participation was {supervision.replace('-', ' ')}.")
        avg_dur = dc.get("AverageDuration") or {}
        dur_val = avg_dur.get("Value")
        dur_unit = avg_dur.get("Unit", "minutes")
        if isinstance(dur_val, (int, float)):
            parts.append(
                f"The average completion time was approximately {dur_val} {dur_unit}."
            )
        if parts:
            h = _heading(2, "Data Collection")
            if h:
                sections.append("\n" + h)
            sections.append(" ".join(parts))
            sections_used.append("DataCollection")

    # --- Data Standardization (PRISM/BIDS boilerplate) ---
    if not is_brief:
        meta = project_data.get("Metadata") or {}
        schema_ver = meta.get("SchemaVersion", "")
        ver_suffix = f" (schema version {schema_ver})" if schema_ver else ""
        boilerplate = (
            "Data were organized and validated according to the PRISM "
            "(Psychological Research Information System & Metadata) standard"
            f"{ver_suffix}, which extends the Brain Imaging Data Structure "
            "(BIDS; Gorgolewski et al., 2016) to psychological and behavioral research. "
            "This framework ensures high interoperability and machine-readability by "
            "enforcing standardized filename patterns and comprehensive metadata sidecars "
            "in JSON format. All datasets were automatically validated for structural "
            f"integrity and schema compliance using PRISM Studio v{prism_version}."
        )
        h = _heading(2, "Data Standardization and Validation")
        if h:
            sections.append("\n" + h)
        sections.append(boilerplate)
        sections_used.append("DataStandardization")

    # --- Quality Control ---
    qc = (procedure.get("QualityControl") or []) if procedure else []
    missing_data = (procedure.get("MissingDataHandling") or "") if procedure else ""
    if (qc or missing_data) and not is_brief:
        parts: list[str] = []
        if qc:
            joined = "; ".join(item.rstrip(".") for item in qc)
            parts.append(f"Quality control measures included: {joined}.")
        if missing_data:
            parts.append(missing_data.rstrip(".") + ".")
        h = _heading(2, "Quality Control")
        if h:
            sections.append("\n" + h)
        sections.append(" ".join(parts))
        sections_used.append("QualityControl")

    # --- Ethics Statement ---
    ethics = dd.get("EthicsApprovals") or []
    if isinstance(ethics, str):
        ethics = [e.strip() for e in ethics.split(",") if e.strip()]
    if ethics:
        parts_eth: list[str] = []
        if len(ethics) == 1:
            parts_eth.append(f"The study was approved by {ethics[0]}.")
        else:
            joined = "; ".join(ethics)
            parts_eth.append(
                f"The study was approved by the following bodies: {joined}."
            )
        informed = procedure.get("InformedConsent", "") if procedure else ""
        if informed and "Ethics" not in "".join(sections):
            # Only add if not already mentioned in Procedure
            pass
        h = _heading(2, "Ethics Statement")
        if h:
            sections.append("\n" + h)
        sections.append(" ".join(parts_eth))
        sections_used.append("EthicsStatement")

    # --- Data Availability ---
    dd_license = dd.get("License", "")
    dd_doi = dd.get("DatasetDOI", "")
    dd_name = dd.get("Name", "")
    dd_desc = dd.get("Description", "")
    dd_refs = dd.get("ReferencesAndLinks") or []
    if isinstance(dd_refs, str):
        dd_refs = [r.strip() for r in dd_refs.split(",") if r.strip()]
    if (dd_license or dd_doi or dd_desc) and not is_brief:
        parts_da: list[str] = []
        if dd_name and dd_desc:
            parts_da.append(
                f'The dataset "{dd_name}" is described as: {dd_desc.rstrip(".")}.'
            )
        elif dd_desc:
            parts_da.append(dd_desc.rstrip(".") + ".")
        if dd_license:
            parts_da.append(
                f"The dataset is made available under the {dd_license} license."
            )
        if dd_doi:
            parts_da.append(f"The dataset can be accessed via DOI: {dd_doi}.")
        if dd_refs:
            parts_da.append("Related references: " + "; ".join(dd_refs) + ".")
        if parts_da:
            h = _heading(2, "Data Availability")
            if h:
                sections.append("\n" + h)
            sections.append(" ".join(parts_da))
            sections_used.append("DataAvailability")

    # --- Funding ---
    funding = dd.get("Funding") or []
    if isinstance(funding, str):
        funding = [f.strip() for f in funding.split(",") if f.strip()]
    ack = dd.get("Acknowledgements", "")
    how_to_ack = dd.get("HowToAcknowledge", "")
    if (funding or ack or how_to_ack) and not is_brief:
        parts_fund: list[str] = []
        if funding:
            if len(funding) == 1:
                parts_fund.append(f"This work was supported by {funding[0]}.")
            else:
                parts_fund.append(f"This work was supported by: {'; '.join(funding)}.")
        if ack:
            parts_fund.append(ack.rstrip(".") + ".")
        if how_to_ack and is_detailed:
            parts_fund.append(how_to_ack.rstrip(".") + ".")
        if parts_fund:
            h = _heading(2, "Funding and Acknowledgements")
            if h:
                sections.append("\n" + h)
            sections.append(" ".join(parts_fund))
            sections_used.append("Funding")

    md_text = "\n".join(sections)
    return md_text, sections_used


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
        f"automatically validated for structural integrity and schema compliance using PRISM Studio (v{prism_version})."
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
            name = get_i18n_text(
                study.get("OriginalName") or study.get("TaskName"), lang
            )
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
            name = get_i18n_text(
                study.get("OriginalName") or study.get("TaskName"), lang
            )
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
                "<body>",
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
                        li_text = li_text.replace("`", "<code>", 1).replace(
                            "`", "</code>", 1
                        )
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
                        p_text = p_text.replace("`", "<code>", 1).replace(
                            "`", "</code>", 1
                        )
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
