import os
import json
import pandas as pd


def generate_index(library_path, output_file):
    print(f"Scanning library: {library_path}")

    records = []

    if not os.path.exists(library_path):
        print("Library path not found.")
        return

    files = sorted(
        [
            f
            for f in os.listdir(library_path)
            if f.endswith(".json") and f.startswith("survey-")
        ]
    )

    for filename in files:
        filepath = os.path.join(library_path, filename)
        try:
            with open(filepath, "r") as f:
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

    # Create DataFrame
    df = pd.DataFrame(records)

    # Generate Markdown
    md_content = "# Survey Library Catalog\n\n"
    md_content += f"**Total Instruments:** {len(records)}\n\n"
    md_content += df.to_markdown(index=False)

    with open(output_file, "w") as f:
        f.write(md_content)

    print(f"Catalog generated at: {output_file}")


if __name__ == "__main__":
    generate_index("survey_library", "survey_library/CATALOG.md")
