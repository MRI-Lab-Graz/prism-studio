#!/usr/bin/env python3
"""Utility to redact or hash sensitive survey sidecar fields for public releases."""

import argparse
import json
import hashlib
import sys
from pathlib import Path


SENSITIVE_TOP_LEVEL = {"Technical", "Study", "Metadata"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create a sanitized copy of a survey sidecar by replacing question text "
            "and optional fields with placeholders or hashes."
        )
    )
    parser.add_argument("input", type=Path, help="Path to the source sidecar JSON")
    parser.add_argument(
        "output",
        type=Path,
        help="Where to write the redacted JSON (use - for stdout)",
    )
    parser.add_argument(
        "--fields",
        nargs="+",
        default=["Description"],
        help="Item-level fields to redact (default: Description)",
    )
    parser.add_argument(
        "--placeholder",
        default="[REDACTED]",
        help="String that replaces sensitive fields (default: [REDACTED])",
    )
    parser.add_argument(
        "--hash",
        action="store_true",
        help="Store a SHA256 hash instead of the placeholder (useful for audits)",
    )
    parser.add_argument(
        "--drop-levels",
        action="store_true",
        help="Remove Levels objects entirely (prevents disclosure of choice labels)",
    )
    parser.add_argument(
        "--keep-empty",
        action="store_true",
        help="Keep questions even if every specified field is removed (default drops)",
    )
    return parser.parse_args()


def redact_value(value, placeholder, use_hash):
    if not use_hash:
        return placeholder
    digest = hashlib.sha256(str(value).encode("utf-8")).hexdigest()
    return f"HASH:{digest}"


def redact_sidecar(data, fields, placeholder, use_hash, drop_levels, keep_empty):
    sanitized = {}
    for key, value in data.items():
        if key in SENSITIVE_TOP_LEVEL:
            sanitized[key] = value
            continue

        if not isinstance(value, dict):
            # Preserve as-is (unexpected metadata block)
            sanitized[key] = value
            continue

        item = dict(value)
        removed_fields = 0

        for field in fields:
            if field in item:
                item[field] = redact_value(item[field], placeholder, use_hash)
                removed_fields += 1

        if drop_levels and "Levels" in item:
            item.pop("Levels")
            removed_fields += 1

        # Drop item if everything was removed and keep_empty is False
        meaningful_content = any(k not in fields for k in item.keys())
        if not keep_empty and not meaningful_content:
            continue

        sanitized[key] = item

    return sanitized


def main():
    args = parse_args()
    try:
        content = json.loads(args.input.read_text())
    except Exception as exc:  # noqa: BLE001 - provide context
        print(f"Failed to read {args.input}: {exc}", file=sys.stderr)
        sys.exit(1)

    redacted = redact_sidecar(
        content,
        fields=args.fields,
        placeholder=args.placeholder,
        use_hash=args.hash,
        drop_levels=args.drop_levels,
        keep_empty=args.keep_empty,
    )

    serialized = json.dumps(redacted, indent=2, ensure_ascii=False) + "\n"
    if args.output == Path("-"):
        sys.stdout.write(serialized)
    else:
        args.output.write_text(serialized)


if __name__ == "__main__":
    main()
