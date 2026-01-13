#!/usr/bin/env python3
"""
Restructure Varioport files into PRISM/BIDS-style sourcedata folders by
matching the trailing 3-digit code in filenames to participant IDs in a
participants TSV.

Usage:
  python scripts/restructure_varioport.py --src /path/to/VPDATA \
        --participants /path/to/participants.tsv --dst /path/to/output_root

The script will:
 - read `participants.tsv` and build a map from last-3-digit suffix -> subject_id
 - scan files in `--src` (non-recursive by default, can use --recursive)
 - for each file, extract trailing 3 digits and map to subject(s)
 - create `sourcedata/sub-<participant_id>/ses-<index>/` and copy the file there
 - rename the copied file to a safer name: `sub-<id>_ses-<ses>_varioport.RAW`
 - produce a CSV log `restructure_map.csv` in the destination root with mapping details

Notes:
 - If multiple files map to a subject, sessions are assigned incrementally
 - If multiple participants share the same 3-digit suffix (rare), the script
   picks the first and records a warning in the log; it also writes an
   `ambiguous_matches.csv` file for manual fixing
 - The script does not modify file contents
"""

import argparse
import csv
import os
import re
import shutil
from collections import defaultdict


def load_participants(participants_tsv):
    mapping = defaultdict(list)  # suffix -> [participant_id,...]
    # Allow passing either a file path or a directory containing participants.tsv
    if os.path.isdir(participants_tsv):
        # look for participants.tsv (case-insensitive)
        found = None
        for fn in os.listdir(participants_tsv):
            if fn.lower() == "participants.tsv":
                found = os.path.join(participants_tsv, fn)
                break
        if not found:
            raise ValueError(
                f"No participants.tsv found in directory: {participants_tsv}"
            )
        participants_tsv = found

    if not os.path.exists(participants_tsv):
        raise ValueError(f"participants.tsv file not found: {participants_tsv}")

    with open(participants_tsv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        if "participant_id" not in reader.fieldnames:
            raise ValueError("participants.tsv must have a participant_id column")
        for row in reader:
            pid = row["participant_id"].strip()
            if not pid:
                continue
            # Extract last 3 digits from participant id
            m = re.search(r"(\d{3})\s*$", pid)
            if m:
                suffix = m.group(1)
                mapping[suffix].append(pid)
    return mapping


def find_files(src_dir, recursive=False):
    files = []
    if recursive:
        for root, _, filenames in os.walk(src_dir):
            for fn in filenames:
                files.append(os.path.join(root, fn))
    else:
        for fn in os.listdir(src_dir):
            p = os.path.join(src_dir, fn)
            if os.path.isfile(p):
                files.append(p)
    return sorted(files)


def extract_suffix(file_path):
    # 1. Check filename first
    bn = os.path.basename(file_path)
    # Examples: subj_001.RAW, 1292001.RAW -> take last 3 digits
    m = re.search(r"(\d{3})(?:[^\d]*$)", bn)
    if m:
        return m.group(1)

    # 2. Check path components (directories)
    # Split path and look for a component that is exactly 3 digits
    # This handles structures like /path/to/001/t1/VPDATA.RAW
    parts = file_path.split(os.sep)
    for part in reversed(parts[:-1]):  # Check parents, starting from immediate parent
        if re.match(r"^\d{3}$", part):
            return part

    return None


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def determine_session(file_path, suffix):
    """
    Determine session number from file path or filename.
    Returns integer session number (1, 2, 3) or None if not determined.
    """
    # 1. Check for t1/t2/t3 folders in path (case-insensitive)
    parts = file_path.split(os.sep)
    for part in parts:
        lower_part = part.lower()
        if lower_part == "t1":
            return 1
        elif lower_part == "t2":
            return 2
        elif lower_part == "t3":
            return 3

    # 2. Check filename pattern: 1xxx.vpd, 2xxx.vpd, 3xxx.vpd
    # where xxx matches the suffix.
    # We handle cases where there might be extra zeros or digits, e.g. 10106.vpd (suffix 106) -> Session 1
    bn = os.path.basename(file_path)
    name_no_ext = os.path.splitext(bn)[0]

    # Check if the name ends with the suffix
    if name_no_ext.endswith(suffix):
        prefix = name_no_ext[: -len(suffix)]
        # If prefix is numeric and starts with 1, 2, or 3
        # This handles 1003 (prefix 1), 10106 (prefix 10), 2003 (prefix 2), etc.
        if prefix.isdigit() and len(prefix) > 0:
            first_digit = int(prefix[0])
            if first_digit in [1, 2, 3]:
                return first_digit

    return None


def main():
    p = argparse.ArgumentParser(
        description="Restructure Varioport RAW files into sourcedata folders"
    )
    p.add_argument("--src", required=True, help="Source folder containing VPDATA files")
    p.add_argument("--participants", required=True, help="Path to participants.tsv")
    p.add_argument(
        "--dst",
        required=True,
        help="Destination root (where sourcedata/ will be created)",
    )
    p.add_argument(
        "--recursive", action="store_true", help="Scan source folder recursively"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="Show actions but do not copy files"
    )
    args = p.parse_args()

    src = args.src
    dst = args.dst
    participants = args.participants

    print(f"Loading participants from {participants}...")
    suffix_map = load_participants(participants)
    print(
        f"Loaded {sum(len(v) for v in suffix_map.values())} participants across {len(suffix_map)} suffix keys"
    )

    files = find_files(src, recursive=args.recursive)
    print(f"Found {len(files)} files in {src}")

    # Prepare counters for session numbering per participant
    sess_counters = defaultdict(int)

    map_log_path = os.path.join(dst, "restructure_map.csv")
    ambiguous_log = os.path.join(dst, "ambiguous_matches.csv")
    ensure_dir(dst)

    with (
        open(map_log_path, "w", newline="", encoding="utf-8") as mapf,
        open(ambiguous_log, "w", newline="", encoding="utf-8") as ambf,
    ):
        map_writer = csv.writer(mapf)
        amb_writer = csv.writer(ambf)
        map_writer.writerow(
            [
                "src_path",
                "basename",
                "suffix",
                "participant_id",
                "session",
                "dst_path",
                "note",
            ]
        )
        amb_writer.writerow(["src_path", "basename", "suffix", "candidates"])

        for fp in files:
            bn = os.path.basename(fp)
            suffix = extract_suffix(fp)
            if not suffix:
                print(
                    f"Warning: no 3-digit suffix found for {bn} in path {fp}; skipping"
                )
                map_writer.writerow([fp, bn, "", "", "", "", "no-suffix"])
                continue

            candidates = suffix_map.get(suffix, [])
            if not candidates:
                print(
                    f"No participant matches suffix {suffix} for file {bn}; logging as unmatched"
                )
                map_writer.writerow([fp, bn, suffix, "", "", "", "no-match"])
                continue

            if len(candidates) > 1:
                # Ambiguous; pick first but record
                chosen = candidates[0]
                amb_writer.writerow([fp, bn, suffix, ";".join(candidates)])
                note = "ambiguous-picked-first"
            else:
                chosen = candidates[0]
                note = ""

            # Determine session from file path or name; prefer explicit session folders (t1/t2/t3)
            fixed_ses = determine_session(fp, suffix)
            if fixed_ses:
                ses_idx = fixed_ses
                note += f";fixed-session-{ses_idx}"
            else:
                # Fallback: assign new session index
                sess_counters[chosen] += 1
                ses_idx = sess_counters[chosen]
                note += ";incremental-session"

            ses_label = f"ses-{ses_idx:02d}"

            # Create destination path
            subdir = os.path.join(dst, "sourcedata", chosen, ses_label, "physio")
            ensure_dir(subdir)

            # Destination file name: sub-<id>_ses-<n>_varioport + original extension
            orig_ext = os.path.splitext(bn)[1] or ".RAW"
            new_bn = f"{chosen}_{ses_label}_varioport{orig_ext}"
            dst_path = os.path.join(subdir, new_bn)

            map_writer.writerow([fp, bn, suffix, chosen, ses_label, dst_path, note])

            if args.dry_run:
                print(f"[DRY] Would copy {fp} -> {dst_path}")
            else:
                print(f"Copying {fp} -> {dst_path}")
                shutil.copy2(fp, dst_path)

    print("\nDone. Mapping log:", map_log_path)
    print("Ambiguous matches log:", ambiguous_log)


if __name__ == "__main__":
    main()
