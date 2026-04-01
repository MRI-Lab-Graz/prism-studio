"""One-off migration: rename legacy Study keys to canonical names in all official templates.

Renames:
  Study.Abbreviation  -> Study.ShortName
  Study.NumberOfItems -> Study.ItemCount
"""

import json
import glob
import os

SURVEY_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "official",
    "library",
    "survey",
)

RENAMES = {
    "Abbreviation": "ShortName",
    "NumberOfItems": "ItemCount",
}


def normalize_file(fpath: str) -> bool:
    with open(fpath, encoding="utf-8") as fh:
        data = json.load(fh)

    study = data.get("Study")
    if not isinstance(study, dict):
        return False

    modified = False
    new_study = {}
    for k, v in study.items():
        canonical = RENAMES.get(k)
        if canonical and canonical not in study:
            # replace legacy key with canonical key, preserving position
            new_study[canonical] = v
            modified = True
        else:
            new_study[k] = v

    if not modified:
        return False

    data["Study"] = new_study
    with open(fpath, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=4)
        fh.write("\n")
    return True


def main():
    files = sorted(glob.glob(os.path.join(SURVEY_DIR, "*.json")))
    changed = [f for f in files if normalize_file(f)]
    unchanged = len(files) - len(changed)
    print(f"Normalized {len(changed)} files, {unchanged} already canonical.")
    for f in changed:
        print(f"  {os.path.basename(f)}")


if __name__ == "__main__":
    main()
