"""prism_tools merge-versions: merge a new questionnaire version into an existing survey template.

Thin adapter over src.converters.version_merger (the merge itself); this module only loads the
new items (JSON template or Excel) and prints the result.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def cmd_merge_versions(args) -> None:
    template_path = os.path.abspath(args.template)
    new_items_path = os.path.abspath(args.new_items)

    if not os.path.exists(template_path):
        print(f"❌ Template not found: {template_path}")
        sys.exit(1)
    if not os.path.exists(new_items_path):
        print(f"❌ New items file not found: {new_items_path}")
        sys.exit(1)

    try:
        from src.converters.version_merger import (
            merge_survey_versions,
            save_merged_template,
            detect_version_name_from_import,
        )
    except ImportError as e:
        print(f"❌ Could not import version merger: {e}")
        sys.exit(1)

    # Load new items from JSON or Excel
    ext = os.path.splitext(new_items_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        try:
            from src.converters.excel_to_survey import _extract_items_from_excel

            new_items = _extract_items_from_excel(new_items_path)
        except Exception as e:
            print(f"❌ Failed to read Excel file: {e}")
            sys.exit(1)
    elif ext == ".json":
        try:
            with open(new_items_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            _NON_ITEM_KEYS = {
                "Technical",
                "Study",
                "Metadata",
                "Normative",
                "Scoring",
                "I18n",
            }
            new_items = {
                k: v
                for k, v in raw.items()
                if k not in _NON_ITEM_KEYS and isinstance(v, dict)
            }
        except Exception as e:
            print(f"❌ Failed to read JSON file: {e}")
            sys.exit(1)
    else:
        print(f"❌ Unsupported file format: {ext} (expected .json or .xlsx)")
        sys.exit(1)

    if not new_items:
        print("❌ No items found in the new items file.")
        sys.exit(1)

    # Auto-detect version names if not provided
    new_version = args.new_version
    existing_version = args.existing_version
    if not new_version or not existing_version:
        suggested_new, suggested_existing = detect_version_name_from_import(
            new_items, Path(template_path)
        )
        if not new_version:
            new_version = suggested_new
            print(f"  Auto-detected new version name: '{new_version}'")
        if not existing_version:
            existing_version = suggested_existing
            print(f"  Auto-detected existing version name: '{existing_version}'")

    print(f"\n🔀 Merging '{existing_version}' + '{new_version}'")
    print(f"  Template : {template_path}")
    print(f"  New items: {new_items_path} ({len(new_items)} items)")

    merged = merge_survey_versions(
        existing_template_path=Path(template_path),
        new_items=new_items,
        new_version_name=new_version,
        existing_version_name=existing_version,
    )

    if args.dry_run:
        print("\n📋 Dry run — merged template preview (Study section):")
        print(json.dumps(merged.get("Study", {}), indent=2, ensure_ascii=False))
        print("\n(No files were written. Remove --dry-run to apply.)")
        return

    output_path = Path(args.output) if args.output else Path(template_path)
    save_merged_template(merged, output_path)
    print(f"\n✅ Merged template saved to: {output_path}")
    versions = merged.get("Study", {}).get("Versions", [])
    print(f"   Versions: {versions}")
