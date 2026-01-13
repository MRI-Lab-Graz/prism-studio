import json
import os
from pathlib import Path


def sync_biometrics_keys(library_dir=None):
    if library_dir is None:
        library_dir = (
            Path(__file__).resolve().parent.parent.parent / "library" / "biometrics"
        )
    else:
        library_dir = Path(library_dir)

    if not library_dir.exists():
        print(f"Error: Library directory {library_dir} does not exist.")
        return

    files = [f for f in os.listdir(library_dir) if f.endswith(".json")]
    if not files:
        print(f"No JSON files found in {library_dir}")
        return

    # Use cmj as template if it exists, else first file
    template_file = (
        "biometrics-cmj.json" if "biometrics-cmj.json" in files else files[0]
    )

    with open(os.path.join(library_dir, template_file), "r") as f:
        template = json.load(f)

    template_keys = set(template.keys())
    template_study_keys = set(template.get("Study", {}).keys())
    template_tech_keys = set(template.get("Technical", {}).keys())

    for filename in files:
        if filename == template_file:
            continue

        filepath = os.path.join(library_dir, filename)
        with open(filepath, "r") as f:
            data = json.load(f)

        changed = False

        # Check top level
        for k in template_keys:
            if k not in data:
                if k in [
                    "Technical",
                    "Study",
                    "I18n",
                    "Metadata",
                    "Scoring",
                    "Normative",
                ]:
                    data[k] = template[k].copy()
                    changed = True
                # DO NOT copy measurement keys (like pre_cmj_1) to other tasks!

        # Check Study
        if "Study" in data:
            for k in template_study_keys:
                if k not in data["Study"]:
                    data["Study"][k] = ""
                    changed = True

        # Check Technical
        if "Technical" in data:
            for k in template_tech_keys:
                if k not in data["Technical"]:
                    data["Technical"][k] = ""
                    changed = True

        if changed:
            with open(filepath, "w") as f:
                json.dump(data, f, indent=2)
            print(f"✅ Synchronized keys for {filename}")
        else:
            print(f"ℹ️ {filename} is already synchronized")


if __name__ == "__main__":
    sync_biometrics_keys()
