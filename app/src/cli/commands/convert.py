"""Conversion-related prism_tools command handlers."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

from helpers.physio.convert_varioport import convert_varioport


def sanitize_id(id_str):
    """Sanitize subject/session IDs by replacing German umlauts and special characters."""
    if not id_str:
        return id_str
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "Ä": "Ae",
        "Ö": "Oe",
        "Ü": "Ue",
        "ß": "ss",
    }
    for char, repl in replacements.items():
        id_str = id_str.replace(char, repl)
    return id_str


def get_json_hash(json_path):
    """Calculate hash of a JSON file's semantic content."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        canonical = json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.md5(
            usedforsecurity=(
                False
                if hasattr(hashlib, "md5")
                and "usedforsecurity" in hashlib.md5.__code__.co_varnames
                else canonical.encode("utf-8")
            )
        ).hexdigest()
    except Exception:
        # Fallback: raw bytes hash
        with open(json_path, "rb") as f:
            return hashlib.md5(
                usedforsecurity=(
                    False
                    if hasattr(hashlib, "md5")
                    and "usedforsecurity" in hashlib.md5.__code__.co_varnames
                    else f.read()
                )
            ).hexdigest()


def consolidate_sidecars(output_dir, task, suffix):
    """Consolidate identical JSON sidecars into a single file in the root directory."""
    print("\nConsolidating JSON sidecars...")
    pattern = f"sub-*/ses-*/physio/*_task-{task}_{suffix}.json"
    json_files = list(output_dir.glob(pattern))

    if not json_files:
        print("No sidecars found to consolidate.")
        return

    first_json = json_files[0]
    first_hash = get_json_hash(first_json)

    all_identical = True
    for jf in json_files[1:]:
        if get_json_hash(jf) != first_hash:
            all_identical = False
            break

    if all_identical:
        print(f"All {len(json_files)} sidecars are identical. Consolidating to root.")
        root_json_name = f"task-{task}_{suffix}.json"
        root_json_path = output_dir / root_json_name
        shutil.copy(first_json, root_json_path)
        print(f"Created root sidecar: {root_json_path}")

        for jf in json_files:
            jf.unlink()
        print("Deleted individual sidecars.")
    else:
        print("Sidecars differ. Keeping individual files.")


def cmd_convert_physio(args):
    """Handle the 'convert physio' command."""
    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    print(f"Scanning {input_dir} for raw physio files...")

    files = list(input_dir.rglob("*.[rR][aA][wW]"))

    if not files:
        print("No .raw files found in input directory.")
        return

    print(f"Found {len(files)} files to process.")

    success_count = 0
    error_count = 0

    for raw_file in files:
        filename = raw_file.name

        parts = raw_file.stem.split("_")
        sub_id = None
        ses_id = None

        for part in parts:
            if part.startswith("sub-"):
                sub_id = part
            elif part.startswith("ses-"):
                ses_id = part

        if not sub_id:
            for parent in raw_file.parents:
                if parent.name.startswith("sub-"):
                    sub_id = parent.name
                    break

        if not ses_id:
            for parent in raw_file.parents:
                if parent.name.startswith("ses-"):
                    ses_id = parent.name
                    break

        if not sub_id or not ses_id:
            print(f"Skipping {filename}: Could not determine subject or session ID.")
            continue

        sub_id = sanitize_id(sub_id)
        ses_id = sanitize_id(ses_id)

        target_dir = output_dir / sub_id / ses_id / "physio"
        target_dir.mkdir(parents=True, exist_ok=True)

        out_base = f"{sub_id}_{ses_id}_task-{args.task}_{args.suffix}"
        out_edf = target_dir / f"{out_base}.edf"

        out_root_json = output_dir / f"task-{args.task}_{args.suffix}.json"

        print(f"Converting {filename} -> {out_base}.edf")

        try:
            convert_varioport(
                str(raw_file),
                str(out_edf),
                str(out_root_json),
                task_name=args.task,
                base_freq=args.sampling_rate,
            )

            if out_edf.exists():
                size_kb = out_edf.stat().st_size / 1024
                if size_kb < 10:
                    print(
                        f"⚠️  WARNING: Output file is suspiciously small ({size_kb:.2f} KB): {out_edf}"
                    )
                else:
                    print(f"✅ Created {out_edf.name} ({size_kb:.2f} KB)")
            else:
                print(f"❌ Error: Output file was not created: {out_edf}")
                error_count += 1
                continue

            success_count += 1
        except Exception as e:
            print(f"Error converting {filename}: {e}")
            error_count += 1

    print(f"\nConversion finished. Success: {success_count}, Errors: {error_count}")
