#!/usr/bin/env python3
"""
Convert a LimeSurvey .lsa archive to TSV/CSV without LimeSurvey.
Extracts the *_responses.lsr XML inside the archive and flattens <row> elements
into a table. Useful for quick inspection or downstream conversions.
"""

import argparse
import sys
import defusedxml.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List

import pandas as pd


def _find_responses_member(zf: zipfile.ZipFile) -> str:
    matches = [name for name in zf.namelist() if name.endswith("_responses.lsr")]
    if not matches:
        raise FileNotFoundError("No *_responses.lsr found inside the .lsa archive")
    if len(matches) > 1:
        # Pick the first deterministically to avoid surprises.
        matches.sort()
    return matches[0]


def _parse_rows(xml_bytes: bytes) -> List[dict]:
    root = ET.fromstring(xml_bytes)
    rows: List[dict] = []
    for row in root.findall(".//row"):
        record = {}
        for child in row:
            tag = child.tag
            if "}" in tag:  # strip namespace if present
                tag = tag.split("}", 1)[1]
            record[tag] = child.text or ""
        rows.append(record)
    return rows


def lsa_to_dataframe(lsa_path: Path) -> pd.DataFrame:
    with zipfile.ZipFile(lsa_path) as zf:
        member = _find_responses_member(zf)
        data = zf.read(member)
    rows = _parse_rows(data)
    return pd.DataFrame(rows)


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Convert LimeSurvey .lsa responses to TSV/CSV"
    )
    parser.add_argument("lsa", type=Path, help="Path to .lsa archive")
    parser.add_argument(
        "output",
        type=Path,
        nargs="?",
        help="Output file (default: <lsa-stem>.tsv in cwd)",
    )
    parser.add_argument(
        "--format",
        choices=["tsv", "csv"],
        default="tsv",
        help="Output format",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Encoding for the output file",
    )
    args = parser.parse_args(argv)

    out_path = args.output
    if out_path is None:
        suffix = ".tsv" if args.format == "tsv" else ".csv"
        out_path = Path(f"{Path(args.lsa).stem}{suffix}")

    df = lsa_to_dataframe(args.lsa)

    if args.format == "tsv":
        df.to_csv(out_path, sep="\t", index=False, encoding=args.encoding)
    else:
        df.to_csv(out_path, index=False, encoding=args.encoding)

    print(f"Wrote {len(df)} rows to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
