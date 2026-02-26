"""Anonymization-related prism_tools command handlers."""

from __future__ import annotations

import csv
import json
import shutil
import sys
from pathlib import Path

from src.anonymizer import anonymize_tsv_file, create_participant_mapping


def cmd_anonymize(args):
    """Anonymize a dataset for sharing."""
    dataset_path = Path(args.dataset).resolve()
    output_path = (
        Path(args.output).resolve()
        if args.output
        else dataset_path.parent / f"{dataset_path.name}_anonymized"
    )
    mapping_file = (
        Path(args.mapping).resolve()
        if args.mapping
        else output_path / "code" / "anonymization_map.json"
    )

    if not dataset_path.exists() or not dataset_path.is_dir():
        print(f"Error: Dataset path not found: {dataset_path}")
        sys.exit(1)

    print(f"Anonymizing dataset: {dataset_path}")
    print(f"Output will be saved to: {output_path}")
    print()

    participant_ids = set()
    participants_tsv = dataset_path / "rawdata" / "participants.tsv"
    if not participants_tsv.exists():
        participants_tsv = dataset_path / "participants.tsv"

    if participants_tsv.exists():
        with open(participants_tsv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                pid = row.get("participant_id", "")
                if pid:
                    participant_ids.add(pid)
    else:
        for sub_dir in dataset_path.glob("sub-*"):
            if sub_dir.is_dir():
                participant_ids.add(sub_dir.name)

    if not participant_ids:
        print("Error: No participants found in dataset")
        sys.exit(1)

    print(f"Found {len(participant_ids)} participants")

    if mapping_file.exists() and not args.force:
        print(f"Loading existing mapping from: {mapping_file}")
        with open(mapping_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            participant_mapping = data.get("mapping", {})
    else:
        print("Creating new participant ID mapping...")
        participant_mapping = create_participant_mapping(
            list(participant_ids),
            mapping_file,
            id_length=args.id_length,
            deterministic=not args.random,
        )
        print(f"✓ Mapping saved to: {mapping_file}")
        print("  ⚠️  KEEP THIS FILE SECURE! It allows re-identification.")

    print()
    print("Sample mappings:")
    for _, (orig, anon) in enumerate(list(participant_mapping.items())[:3]):
        print(f"  {orig} → {anon}")
    print()

    output_path.mkdir(parents=True, exist_ok=True)

    if participants_tsv.exists():
        print("Anonymizing participants.tsv...")
        output_participants = output_path / "participants.tsv"
        anonymize_tsv_file(participants_tsv, output_participants, participant_mapping)
        print(f"  ✓ {output_participants}")

    print("Anonymizing data files...")
    for tsv_file in dataset_path.rglob("*.tsv"):
        if tsv_file.name == "participants.tsv":
            continue

        rel_path = tsv_file.relative_to(dataset_path)
        new_rel_path_str = str(rel_path)

        for orig_id, anon_id in participant_mapping.items():
            new_rel_path_str = new_rel_path_str.replace(orig_id, anon_id)

        output_file = output_path / new_rel_path_str
        anonymize_tsv_file(tsv_file, output_file, participant_mapping)
        print(f"  ✓ {rel_path} → {new_rel_path_str}")

    print("Copying metadata files...")
    for json_file in dataset_path.rglob("*.json"):
        rel_path = json_file.relative_to(dataset_path)

        if json_file == mapping_file:
            continue

        new_rel_path_str = str(rel_path)
        for orig_id, anon_id in participant_mapping.items():
            new_rel_path_str = new_rel_path_str.replace(orig_id, anon_id)

        output_file = output_path / new_rel_path_str
        output_file.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(json_file, output_file)

    print()
    print("=" * 70)
    print("✅ Anonymization complete!")
    print(f"   Anonymized dataset: {output_path}")
    print(f"   Mapping file: {mapping_file}")
    print()
    print("⚠️  IMPORTANT:")
    print("   - Keep the mapping file secure and separate from shared data")
    print("   - The mapping allows re-identification of participants")
    print("   - Review the output before sharing to ensure anonymization")
    print("=" * 70)
