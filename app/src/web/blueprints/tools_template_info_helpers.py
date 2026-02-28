import json


def detect_languages_from_template(data):
    """Detect all languages available in a PRISM template.

    Checks:
    1. Explicit I18n.Languages list
    2. Keys of I18n translation blocks (I18n.de, I18n.en, etc.)
    3. Inline lang-map dicts on question Descriptions and Levels
    """
    langs = set()

    i18n = data.get("I18n", {})
    if isinstance(i18n, dict):
        explicit = i18n.get("Languages", [])
        if isinstance(explicit, list):
            langs.update(explicit)
        for key in i18n:
            if key == "Languages":
                continue
            if isinstance(key, str) and (
                len(key) == 2 or (len(key) == 5 and key[2] == "-")
            ):
                langs.add(key)

    tech = data.get("Technical", {})
    if isinstance(tech, dict):
        tech_lang = tech.get("Language", "")
        if isinstance(tech_lang, str) and len(tech_lang) >= 2:
            langs.add(tech_lang[:2].lower())

    questions_section = data.get("Questions", {})
    items = questions_section if isinstance(questions_section, dict) else {}
    if not items:
        reserved = {
            "@context",
            "Technical",
            "Study",
            "Metadata",
            "Categories",
            "TaskName",
            "I18n",
            "Scoring",
            "Normative",
            "Name",
            "BIDSVersion",
            "Description",
            "URL",
            "License",
            "Authors",
            "Acknowledgements",
            "References",
            "Funding",
        }
        items = {
            k: v for k, v in data.items() if k not in reserved and isinstance(v, dict)
        }

    for _q_code, q_data in items.items():
        if not isinstance(q_data, dict):
            continue
        desc = q_data.get("Description")
        if isinstance(desc, dict):
            langs.update(k for k in desc if isinstance(k, str) and len(k) <= 5)
        levels = q_data.get("Levels", {})
        if isinstance(levels, dict):
            for _lk, lv in levels.items():
                if isinstance(lv, dict):
                    langs.update(k for k in lv if isinstance(k, str) and len(k) <= 5)

    tech_lang_code = ""
    tech_sec = data.get("Technical", {})
    if isinstance(tech_sec, dict):
        tl = tech_sec.get("Language", "")
        if isinstance(tl, str) and len(tl) >= 2:
            tech_lang_code = tl[:2].lower()

    if len(langs) > 1:
        texts_by_lang = {l: [] for l in langs}
        for _q_code, q_data in items.items():
            if not isinstance(q_data, dict):
                continue
            desc = q_data.get("Description")
            if isinstance(desc, dict):
                for l in langs:
                    texts_by_lang[l].append(desc.get(l, ""))

        ref_lang = None
        if tech_lang_code in langs and any(
            t for t in texts_by_lang.get(tech_lang_code, [])
        ):
            ref_lang = tech_lang_code
        elif "en" in langs and any(t for t in texts_by_lang.get("en", [])):
            ref_lang = "en"
        else:
            for l in sorted(langs):
                if any(t for t in texts_by_lang.get(l, [])):
                    ref_lang = l
                    break

        if ref_lang:
            for l in list(langs):
                if l == ref_lang:
                    continue
                l_texts = texts_by_lang.get(l, [])
                ref_texts = texts_by_lang.get(ref_lang, [])
                if l_texts and l_texts == ref_texts:
                    langs.discard(l)

        if tech_lang_code and tech_lang_code in langs and len(langs) > 1:
            for l in list(langs):
                if l == tech_lang_code:
                    continue
                overlap = 0
                for _q_code, q_data in items.items():
                    if not isinstance(q_data, dict):
                        continue
                    desc = q_data.get("Description")
                    if isinstance(desc, dict):
                        if desc.get(tech_lang_code, "") and desc.get(l, ""):
                            overlap += 1
                if overlap == 0:
                    langs.discard(l)

    if not langs:
        tech = data.get("Technical", {})
        tech_lang = tech.get("Language", "") if isinstance(tech, dict) else ""
        langs.add(
            tech_lang[:2].lower()
            if isinstance(tech_lang, str) and len(tech_lang) >= 2
            else "en"
        )

    return sorted(langs)


def extract_template_info(full_path, filename, source="global"):
    """Helper to extract metadata and questions from a PRISM JSON template."""
    desc = ""
    original_name = ""
    questions = []
    i18n = {}
    study_info = {}
    detected_languages = ["en"]
    try:
        with open(full_path, "r", encoding="utf-8") as jf:
            data = json.load(jf)
            study = data.get("Study", {})
            desc = study.get("Description", "")
            original_name = study.get("OriginalName", "")
            i18n = data.get("I18n", {})

            study_info = {
                "Authors": study.get("Authors", []),
                "Citation": study.get("Citation", ""),
                "DOI": study.get("DOI", ""),
                "License": study.get("License", ""),
                "LicenseID": study.get("LicenseID", ""),
                "LicenseURL": study.get("LicenseURL", ""),
                "ItemCount": study.get("ItemCount"),
                "AgeRange": study.get("AgeRange", ""),
                "AdministrationTime": study.get("AdministrationTime", ""),
                "ScoringTime": study.get("ScoringTime", ""),
                "Norming": study.get("Norming", ""),
                "Reliability": study.get("Reliability", ""),
                "Validity": study.get("Validity", ""),
            }

            if not desc:
                desc = data.get("TaskName", "")

            detected_languages = detect_languages_from_template(data)

            def _get_q_info(k, v):
                if not isinstance(v, dict):
                    return {"id": k, "description": str(v)}
                return {
                    "id": k,
                    "description": v.get("Description", ""),
                    "levels": v.get("Levels", {}),
                    "scale": v.get("Scale", ""),
                    "units": v.get("Unit", ""),
                    "min_value": v.get("MinValue"),
                    "max_value": v.get("MaxValue"),
                }

            if "Questions" in data and isinstance(data["Questions"], dict):
                for k, v in data["Questions"].items():
                    if isinstance(v, dict) and not v.get("_exclude", False):
                        questions.append(_get_q_info(k, v))
            else:
                reserved = [
                    "@context",
                    "Technical",
                    "Study",
                    "Metadata",
                    "Categories",
                    "TaskName",
                    "Name",
                    "BIDSVersion",
                    "Description",
                    "URL",
                    "License",
                    "Authors",
                    "Acknowledgements",
                    "References",
                    "Funding",
                    "I18n",
                    "Scoring",
                    "Normative",
                ]
                for k, v in data.items():
                    if (
                        k not in reserved
                        and isinstance(v, dict)
                        and "Description" in v
                        and not v.get("_exclude", False)
                    ):
                        questions.append(_get_q_info(k, v))
    except Exception:
        pass

    return {
        "filename": filename,
        "path": str(full_path),
        "description": desc,
        "original_name": original_name,
        "questions": questions,
        "question_count": len(questions),
        "i18n": i18n,
        "study": study_info,
        "source": source,
        "detected_languages": detected_languages,
    }