import os
import json
import argparse
import pandas as pd


def generate_index(library_path, output_file):
    print(f"Scanning library: {library_path}")

    records = []

    if not os.path.exists(library_path):
        print(f"Error: Library path '{library_path}' not found.")
        return

    files = sorted(
        [
            f
            for f in os.listdir(library_path)
            if f.endswith(".json") and f.startswith("survey-")
        ]
    )

    if not files:
        print(f"No survey JSON files found in '{library_path}'.")
        return

    for filename in files:
        filepath = os.path.join(library_path, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            study = data.get("Study", {})

            # Extract fields
            name = study.get(
                "TaskName", filename.replace("survey-", "").replace(".json", "")
            )
            full_name = study.get("OriginalName", "n/a")
            domain = study.get("Domain", "-")
            keywords = ", ".join(study.get("Keywords", []))
            citation = study.get("Citation", "")

            # Truncate citation for table
            short_citation = (citation[:50] + "...") if len(citation) > 50 else citation

            records.append(
                {
                    "ID": name,
                    "Domain": domain,
                    "Full Name": full_name,
                    "Keywords": keywords,
                    "Citation": short_citation,
                    "Filename": filename,
                }
            )

        except Exception as e:
            print(f"Error reading {filename}: {e}")

    if not records:
        print("No valid survey records found.")
        return

    # Create DataFrame
    df = pd.DataFrame(records)

    # Generate Markdown
    md_content = "# Survey Library Catalog\n\n"
    md_content += f"**Total Instruments:** {len(records)}\n\n"
    
    try:
        md_content += df.to_markdown(index=False)
    except ImportError:
        # Fallback if tabulate is not installed
        md_content += df.to_string(index=False)

    # Ensure output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Catalog generated at: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a catalog of the survey library.")
    parser.add_argument(
        "--library", 
        default="survey_library", 
        help="Path to the survey library folder (default: survey_library)"
    )
    parser.add_argument(
        "--output", 
        default="survey_library/CATALOG.md", 
        help="Path to the output Markdown file (default: survey_library/CATALOG.md)"
    )
    
    args = parser.parse_args()
    generate_index(args.library, args.output)
