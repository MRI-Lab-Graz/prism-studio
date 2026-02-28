"""Compatibility shim for LimeSurvey conversion.

Delegates runtime symbols to canonical backend module:
`src/converters/limesurvey.py`.
"""

from __future__ import annotations

import argparse

from src._compat import load_canonical_module

_src_limesurvey = load_canonical_module(
    current_file=__file__,
    canonical_rel_path="converters/limesurvey.py",
    alias="prism_backend_converters_limesurvey",
)

for _name in dir(_src_limesurvey):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_src_limesurvey, _name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert LimeSurvey .lsa/.lss to Prism JSON sidecar."
    )
    parser.add_argument("input_file", help="Path to .lsa or .lss file")
    parser.add_argument("-o", "--output", help="Path to output .json file")

    args = parser.parse_args()
    convert_lsa_to_prism(args.input_file, args.output)