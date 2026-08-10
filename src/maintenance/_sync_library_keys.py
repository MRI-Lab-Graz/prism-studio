"""Shared key-synchronization logic for the survey/biometrics library maintenance scripts."""

import json
import os
from pathlib import Path


def _sync_library_keys(
    library_dir,
    *,
    default_relative_path: tuple,
    preferred_template_name: str,
    reset_study_values: bool,
    skip_item_prefix: bool,
    mark_changed_for_skipped_keys: bool,
) -> None:
    if library_dir is None:
        library_dir = Path(__file__).resolve().parent.parent.parent
        for part in default_relative_path:
            library_dir = library_dir / part
    else:
        library_dir = Path(library_dir)

    if not library_dir.exists():
        print(f"Error: Library directory {library_dir} does not exist.")
        return

    files = [f for f in os.listdir(library_dir) if f.endswith(".json")]
    if not files:
        print(f"No JSON files found in {library_dir}")
        return

    template_file = preferred_template_name if preferred_template_name in files else files[0]

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
            if skip_item_prefix and k.startswith("item_"):
                continue
            if k not in data:
                if k in ["Technical", "Study", "I18n", "Metadata", "Scoring", "Normative"]:
                    data[k] = template[k].copy()
                    if reset_study_values and k == "Study":
                        for sk in data[k]:
                            data[k][sk] = ""
                    changed = True
                elif mark_changed_for_skipped_keys:
                    # Not a recognized block (e.g. a per-item top-level key like
                    # "AAI01" that isn't `item_`-prefixed) — nothing is copied,
                    # but the survey variant still flags the file as touched so
                    # it gets rewritten. Preserves original sync_survey_keys.py
                    # behavior; sync_biometrics_keys.py never set this flag here.
                    changed = True
                # else: likely an item or something else, skip

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
