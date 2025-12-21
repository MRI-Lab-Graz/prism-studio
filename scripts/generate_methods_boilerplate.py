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

def generate_methods_text(library_dirs, output_file, lang='en'):
    """
    Generates a formal methods section boilerplate based on PRISM library templates.
    """
    sections = []
    
    # 1. General PRISM/BIDS Section
    sections.append("## Data Standardization and Validation\n")
    sections.append(
        "Data were organized and validated according to the PRISM (Psychological Research Information System & Metadata) "
        "standard, which extends the Brain Imaging Data Structure (BIDS; Gorgolewski et al., 2016) to psychological "
        "and behavioral research. This framework ensures high interoperability and machine-readability by enforcing "
        "standardized filename patterns and comprehensive metadata sidecars in JSON format. All datasets were "
        "automatically validated for structural integrity and schema compliance using the PRISM validator."
    )

    # 2. Modalities
    surveys = []
    biometrics = []
    
    for lib_dir in library_dirs:
        lib_path = Path(lib_dir)
        if not lib_path.exists():
            continue
            
        for json_file in sorted(lib_path.glob("*.json")):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                study = data.get("Study", {})
                name = get_i18n_text(study.get("OriginalName", json_file.stem), lang)
                desc = get_i18n_text(study.get("Description", ""), lang)
                
                if "survey-" in json_file.name:
                    surveys.append((name, desc))
                elif "biometrics-" in json_file.name:
                    tech = data.get("Technical", {})
                    equip = tech.get("Equipment", "standard equipment")
                    biometrics.append((name, desc, equip))
            except Exception:
                continue

    # 3. Surveys Section
    if surveys:
        sections.append("\n## Psychological Assessments\n")
        sections.append(
            "Psychological assessments were administered and stored as tab-separated value (.tsv) files with "
            "corresponding JSON metadata sidecars. The following standardized instruments were included:\n"
        )
        for name, desc in surveys:
            sections.append(f"- **{name}**: {desc}")

    # 4. Biometrics Section
    if biometrics:
        sections.append("\n## Biometric and Physical Performance Measures\n")
        sections.append(
            "Physical performance and biometric data were recorded following standardized protocols. "
            "Metadata for each test includes technical specifications such as equipment used and supervisor roles. "
            "The following measures were obtained:\n"
        )
        for name, desc, equip in biometrics:
            sections.append(f"- **{name}**: {desc} (Equipment: {equip})")

    # 5. Metadata and Reproducibility
    sections.append("\n## Metadata and Reproducibility\n")
    
    # Check for participants.json in library
    participants_vars = []
    for lib_dir in library_dirs:
        p_json = Path(lib_dir) / "participants.json"
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
    
    args = parser.parse_args()
    
    generate_methods_text([args.survey_lib, args.biometrics_lib], args.output, args.lang)

if __name__ == "__main__":
    main()
