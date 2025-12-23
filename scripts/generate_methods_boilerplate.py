#!/usr/bin/env python3
import json
import argparse
from pathlib import Path

def get_i18n_text(field, lang='en'):
    """Extract text from an i18n field (string or dict)."""
    if isinstance(field, str):
        return field
    if isinstance(field, dict):
        # Try requested language
        val = field.get(lang)
        if val:
            return val
        # Try English
        val = field.get('en')
        if val:
            return val
        # Try German
        val = field.get('de')
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
    out = {"primary": None, "manual": None, "translation": None, "validation": None, "norms": None}
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

def generate_methods_text(library_dirs_or_files, output_file, lang='en', github_url=None, schema_version=None):
    """
    Generates a formal methods section boilerplate based on PRISM library templates.
    library_dirs_or_files can be a list of directories or a list of specific JSON files.
    """
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
        path = Path(item)
        if not path.exists():
            continue
        
        if path.is_dir():
            all_files.extend(sorted(path.glob("*.json")))
        else:
            all_files.append(path)
            
    for json_file in all_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            study = data.get("Study", {})
            tech = data.get("Technical", {})
            scoring = data.get("Scoring", {})
            name = get_i18n_text(study.get("OriginalName", json_file.stem), lang)
            short_name = get_i18n_text(study.get("ShortName", ""), lang)
            version = get_i18n_text(study.get("Version", ""), lang)
            desc = get_i18n_text(study.get("Description", ""), lang)
            license_id = study.get("LicenseID") or study.get("License")
            license_url = study.get("LicenseURL")
            access = get_i18n_text(study.get("Access", ""), lang)
            permissions_note = get_i18n_text(study.get("PermissionsNote", ""), lang)
            permissions_url = study.get("PermissionsURL")
            authors = study.get("Authors", [])
            citation = study.get("Citation") or study.get("DOI")
            doi = study.get("DOI")
            refs = _pick_references(study, lang=lang)

            instrument_lang = tech.get("Language")
            respondent = tech.get("Respondent")
            admin_method = tech.get("AdministrationMethod")
            platform = tech.get("SoftwarePlatform")
            response_type = tech.get("ResponseType")
            if isinstance(response_type, list):
                response_type = ", ".join([str(x) for x in response_type if str(x).strip()])
            else:
                response_type = str(response_type or "").strip() or None

            item_count = study.get("ItemCount")
            administration_time = get_i18n_text(study.get("AdministrationTime", ""), lang)
            scoring_time = get_i18n_text(study.get("ScoringTime", ""), lang)

            translation = study.get("Translation") or {}
            translation_src = translation.get("SourceLanguage")
            translation_tgt = translation.get("TargetLanguage")
            translation_validated = translation.get("Validated")
            translation_method = get_i18n_text(translation.get("Method", ""), lang)
            translation_ref = get_i18n_text(translation.get("Reference", ""), lang)
            
            if "survey-" in json_file.name:
                surveys.append({
                    "name": name,
                    "short": short_name,
                    "version": version,
                    "desc": desc,
                    "license": license_id,
                    "license_url": license_url,
                    "access": access,
                    "permissions_note": permissions_note,
                    "permissions_url": permissions_url,
                    "authors": authors,
                    "citation": citation,
                    "doi": doi,
                    "refs": refs,
                    "instrument_lang": instrument_lang,
                    "respondent": respondent,
                    "admin_method": admin_method,
                    "platform": platform,
                    "response_type": response_type,
                    "item_count": item_count,
                    "administration_time": administration_time,
                    "scoring_time": scoring_time,
                    "translation": {
                        "src": translation_src,
                        "tgt": translation_tgt,
                        "validated": translation_validated,
                        "method": translation_method,
                        "ref": translation_ref,
                        "ref_struct": refs.get("translation"),
                    },
                    "scoring": {
                        "method": get_i18n_text(scoring.get("ScoringMethod", ""), lang),
                        "range": scoring.get("ScoreRange"),
                        "reverse_items": scoring.get("ReverseCodedItems"),
                        "reverse_scale": scoring.get("ReverseCodingScale"),
                        "cutoffs": scoring.get("Cutoffs"),
                        "cutoffs_source": get_i18n_text(scoring.get("CutoffsSource", ""), lang),
                        "norms_source": get_i18n_text(scoring.get("NormsSource", ""), lang),
                    },
                })
            elif "biometrics-" in json_file.name:
                equip = tech.get("Equipment", "standard equipment")
                biometrics.append({
                    "name": name,
                    "desc": desc,
                    "equip": equip,
                    "license": license_id
                })
        except Exception:
            continue

    # 3. Surveys Section
    if surveys:
        sections.append("\n## Psychological Assessments\n")
        sections.append(
            "Psychological assessments were administered and stored as tab-separated value (.tsv) files with "
            "corresponding JSON metadata sidecars. The following standardized instruments were included:\n"
        )
        for s in surveys:
            display_name = s["name"]
            if s.get("short"):
                display_name += f" ({s['short']})"
            if s.get("version"):
                display_name += f", version {s['version']}"

            line = f"- **{display_name}**"
            if s['authors']:
                line += f" ({', '.join(s['authors'][:3])}{' et al.' if len(s['authors']) > 3 else ''})"

            if s.get("desc"):
                line += f": {s['desc']}"

            details = []
            if s.get("instrument_lang"):
                details.append(f"language={s['instrument_lang']}")
            if s.get("respondent"):
                details.append(f"respondent={s['respondent']}")
            if s.get("admin_method"):
                details.append(f"administration={s['admin_method']}")
            if s.get("platform"):
                details.append(f"platform={s['platform']}")
            if s.get("response_type"):
                details.append(f"response_type={s['response_type']}")
            if isinstance(s.get("item_count"), int):
                details.append(f"items={s['item_count']}")
            if s.get("administration_time"):
                details.append(f"completion_time≈{s['administration_time']}")
            if s.get("scoring_time"):
                details.append(f"scoring_time≈{s['scoring_time']}")
            if details:
                line += f" ({'; '.join(details)})"

            # Rights/licensing transparency
            rights_bits = []
            if s.get("access"):
                rights_bits.append(f"access={s['access']}")
            if s.get("license"):
                rights_bits.append(f"license={s['license']}")
            if s.get("permissions_note"):
                rights_bits.append(f"permissions={s['permissions_note']}")
            if rights_bits:
                line += f" [Rights: {', '.join(rights_bits)}]"
            if s.get("license_url"):
                line += f" (license URL: {s['license_url']})"
            if s.get("permissions_url"):
                line += f" (permissions URL: {s['permissions_url']})"

            # References (prefer structured refs when available)
            ref_parts = []
            if s.get("refs") and s["refs"].get("primary"):
                ref_parts.append(f"primary: {s['refs']['primary']}")
            if s.get("refs") and s["refs"].get("manual"):
                ref_parts.append(f"manual: {s['refs']['manual']}")
            if not ref_parts:
                if s.get("citation"):
                    ref_parts.append(str(s["citation"]))
                elif s.get("doi"):
                    ref_parts.append(f"DOI: {s['doi']}")
            if ref_parts:
                line += f" (see {"; ".join(ref_parts)})"

            # Translation/adaptation provenance (only if present)
            tr = s.get("translation") or {}
            tr_bits = []
            if tr.get("src") or tr.get("tgt"):
                tr_bits.append(f"{tr.get('src','?')}→{tr.get('tgt','?')}")
            if tr.get("validated") is True:
                tr_bits.append("validated")
            elif tr.get("validated") is False:
                tr_bits.append("not validated")
            if tr.get("method"):
                tr_bits.append(f"method={tr['method']}")
            tr_ref = tr.get("ref_struct") or tr.get("ref")
            if tr_ref:
                tr_bits.append(f"ref={tr_ref}")
            if tr_bits:
                line += f" [Translation: {', '.join(tr_bits)}]"

            sections.append(line)

    # 4. Biometrics Section
    if biometrics:
        sections.append("\n## Biometric and Physical Performance Measures\n")
        sections.append(
            "Physical performance and biometric data were recorded following standardized protocols. "
            "Metadata for each test includes technical specifications such as equipment used and supervisor roles. "
            "The following measures were obtained:\n"
        )
        for b in biometrics:
            line = f"- **{b['name']}**: {b['desc']} (Equipment: {b['equip']})"
            if b['license']:
                line += f" [License: {b['license']}]"
            sections.append(line)

    # 5. Metadata and Reproducibility
    sections.append("\n## Metadata and Reproducibility\n")
    
    # Check for participants.json in library
    participants_vars = []
    checked_dirs = set()
    for item in library_dirs_or_files:
        path = Path(item)
        if not path.exists():
            continue
        
        search_dir = path if path.is_dir() else path.parent
        if search_dir in checked_dirs:
            continue
        checked_dirs.add(search_dir)
        
        p_json = search_dir / "participants.json"
        if p_json.exists():
            try:
                with open(p_json, 'r', encoding='utf-8') as f:
                    p_data = json.load(f)
                reserved = {"Technical", "I18n", "Study", "Metadata"}
                participants_vars.extend([k for k in p_data.keys() if k not in reserved])
            except Exception:
                continue
    
    repro_text = (
        "To facilitate reproducibility, each data file is accompanied by a JSON sidecar containing "
        "variable-level metadata, including descriptions, units, and measurement levels. "
        "The dataset supports multi-language metadata (i18n), with primary documentation provided in "
        f"{'English' if lang == 'en' else 'German' if lang == 'de' else lang}. "
        "Participant-level metadata is stored in a centralized participants.tsv file in the dataset root."
    )
    if participants_vars:
        repro_text += f" This file includes variables such as: {', '.join(sorted(list(set(participants_vars))))}."
    
    sections.append(repro_text)

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n\n".join(sections))
    
    print(f"✅ Methods boilerplate generated: {output_file}")

def main():
    parser = argparse.ArgumentParser(description="Generate a scientific methods boilerplate from PRISM library.")
    parser.add_argument("--survey-lib", default="library/survey", help="Path to survey library")
    parser.add_argument("--biometrics-lib", default="library/biometrics", help="Path to biometrics library")
    parser.add_argument("--output", default="methods_boilerplate.md", help="Output markdown file")
    parser.add_argument("--lang", default="en", choices=["en", "de"], help="Language for the text")
    parser.add_argument("--github-url", help="GitHub URL for the project")
    parser.add_argument("--schema-version", help="PRISM schema version")
    
    args = parser.parse_args()
    
    generate_methods_text(
        [args.survey_lib, args.biometrics_lib], 
        args.output, 
        lang=args.lang,
        github_url=args.github_url,
        schema_version=args.schema_version
    )

if __name__ == "__main__":
    main()
