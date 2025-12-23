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
            name = get_i18n_text(study.get("OriginalName", json_file.stem), lang)
            desc = get_i18n_text(study.get("Description", ""), lang)
            license_id = study.get("LicenseID") or study.get("License")
            authors = study.get("Authors", [])
            citation = study.get("Citation") or study.get("DOI")
            
            if "survey-" in json_file.name:
                surveys.append({
                    "name": name,
                    "desc": desc,
                    "license": license_id,
                    "authors": authors,
                    "citation": citation
                })
            elif "biometrics-" in json_file.name:
                tech = data.get("Technical", {})
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
            line = f"- **{s['name']}**"
            if s['authors']:
                line += f" ({', '.join(s['authors'][:3])}{' et al.' if len(s['authors']) > 3 else ''})"
            line += f": {s['desc']}"
            if s['license']:
                line += f" [License: {s['license']}]"
            if s['citation']:
                line += f" (see {s['citation']})"
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
