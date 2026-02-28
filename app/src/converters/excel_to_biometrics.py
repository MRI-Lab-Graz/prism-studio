"""Compatibility shim for biometrics Excel conversion.

Delegates runtime symbols to canonical backend module:
`src/converters/excel_to_biometrics.py`.
"""

from __future__ import annotations

import argparse

from src._compat import load_canonical_module

_src_excel_to_biometrics = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="converters/excel_to_biometrics.py",
    alias="prism_backend_converters_excel_to_biometrics",
)

for _name in dir(_src_excel_to_biometrics):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_excel_to_biometrics, _name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert Excel data dictionary to PRISM biometrics JSON library."
    )
    parser.add_argument(
        "--excel", required=True, help="Path to the Excel metadata file."
    )
    parser.add_argument(
        "--output",
        default="biometrics_library",
        help="Output directory for JSON files.",
    )
    parser.add_argument(
        "--sheet",
        default=0,
        help="Sheet name or index containing the data dictionary (default: 0). For sport.xlsx use: --sheet Description",
    )
    parser.add_argument(
        "--equipment",
        default="Legacy/Imported",
        help="Default Equipment value written to Technical.Equipment (required by schema).",
    )
    parser.add_argument(
        "--supervisor",
        default="investigator",
        choices=["investigator", "physician", "trainer", "self"],
        help="Default Supervisor value written to Technical.Supervisor.",
    )

    args = parser.parse_args()
    sheet = (
        int(args.sheet)
        if isinstance(args.sheet, str) and args.sheet.isdigit()
        else args.sheet
    )
    process_excel_biometrics(
        args.excel,
        args.output,
        sheet_name=sheet,
        equipment=args.equipment,
        supervisor=args.supervisor,
    )