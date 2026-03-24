"""Conversion-related prism_tools command handlers."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from helpers.physio.convert_varioport import convert_varioport
from src.converters.wide_to_long import (
    convert_wide_to_long_dataframe,
    detect_wide_session_prefixes,
    inspect_wide_to_long_columns,
)
from src.cross_platform import normalize_path


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
            try:
                convert_varioport(
                    str(raw_file),
                    str(out_edf),
                    str(out_root_json),
                    task_name=args.task,
                    base_freq=args.sampling_rate,
                )
            except ValueError as e:
                if "Unsupported Varioport header type" in str(e):
                    print(
                        "⚠️ Type-7 RAW detected. Retrying with experimental multiplexed decoder (QC required)."
                    )
                    convert_varioport(
                        str(raw_file),
                        str(out_edf),
                        str(out_root_json),
                        task_name=args.task,
                        base_freq=args.sampling_rate,
                        allow_raw_multiplexed=True,
                    )
                else:
                    raise

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


def _parse_session_indicators(raw_value: str | None) -> list[str]:
    return [item.strip() for item in str(raw_value or "").split(",") if item.strip()]


def _parse_session_value_map(raw_value: str | None) -> dict[str, str]:
    mapping_text = str(raw_value or "").strip()
    if not mapping_text:
        return {}

    session_value_map: dict[str, str] = {}
    entries = [
        item.strip()
        for item in mapping_text.replace(";", ",").split(",")
        if item.strip()
    ]
    for entry in entries:
        if ":" in entry:
            left, right = entry.split(":", 1)
        elif "=" in entry:
            left, right = entry.split("=", 1)
        else:
            raise ValueError(
                "Invalid session map format. Use entries like T1_:pre,T2_:post or T1_=1,T2_=2."
            )

        source = left.strip()
        target = right.strip()
        if not source or not target:
            raise ValueError(
                "Invalid session map format. Empty source/target values are not allowed."
            )
        session_value_map[source] = target

    return session_value_map


def _read_wide_to_long_input(input_path: Path, sheet: str | int = 0) -> pd.DataFrame:
    suffix = input_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(input_path, dtype=str)
    if suffix == ".tsv":
        return pd.read_csv(input_path, sep="\t", dtype=str)
    if suffix == ".xlsx":
        return pd.read_excel(input_path, sheet_name=sheet, dtype=str)
    raise ValueError("Supported formats: .csv, .tsv, .xlsx")


def _write_wide_to_long_output(long_df: pd.DataFrame, output_path: Path) -> None:
    suffix = output_path.suffix.lower()
    if suffix == ".csv":
        long_df.to_csv(output_path, index=False)
        return
    if suffix == ".tsv":
        long_df.to_csv(output_path, sep="\t", index=False)
        return
    if suffix == ".xlsx":
        long_df.to_excel(output_path, index=False)
        return
    raise ValueError("Output format must be .csv, .tsv, or .xlsx")


def _default_wide_to_long_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_long.csv")


def _wide_to_long_indicator_counts(
    plan: dict[str, Any], indicators: list[str]
) -> dict[str, int]:
    indicator_upper_to_cols = plan.get("indicator_upper_to_cols") or {}
    return {
        indicator: len(indicator_upper_to_cols.get(str(indicator).upper(), []))
        for indicator in indicators
    }


def _wide_to_long_json_payload(
    *,
    input_path: Path,
    indicators: list[str],
    plan: dict[str, Any],
    preview_limit: int,
    long_df: pd.DataFrame | None = None,
    output_path: Path | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "filename": input_path.name,
        "input_path": normalize_path(input_path),
        "detected_indicators": indicators,
        "detected_prefixes": indicators,
        "indicator_counts": _wide_to_long_indicator_counts(plan, indicators),
        "matched_columns": len(plan.get("matched_columns") or []),
        "ambiguous_columns": plan.get("ambiguous_columns") or [],
        "shared_columns": len(plan.get("shared_columns") or []),
        "can_convert": not bool(plan.get("ambiguous_columns")),
        "column_rename_preview": list(plan.get("matched_columns") or [])[
            :preview_limit
        ],
        "rows_total": 0,
        "rows_shown": 0,
        "columns": [],
        "rows": [],
    }

    if long_df is not None:
        preview_df = long_df.head(preview_limit).fillna("").astype(str)
        payload.update(
            {
                "rows_total": int(len(long_df)),
                "rows_shown": int(len(preview_df)),
                "columns": list(preview_df.columns),
                "rows": preview_df.to_dict(orient="records"),
            }
        )

    if output_path is not None:
        payload["output_path"] = normalize_path(output_path)

    if error:
        payload["error"] = error

    return payload


def _print_wide_to_long_plan(plan: dict[str, Any], preview_limit: int) -> None:
    indicators = plan.get("indicators") or []
    indicator_upper_to_cols = plan.get("indicator_upper_to_cols") or {}
    matched_columns = plan.get("matched_columns") or []
    ambiguous_columns = plan.get("ambiguous_columns") or []
    shared_columns = plan.get("shared_columns") or []

    print("Wide-to-long inspection")
    print("=" * 50)
    print(f"Indicators: {', '.join(str(item) for item in indicators) or '<none>'}")
    print(f"Matched columns: {len(matched_columns)}")
    print(f"Ambiguous columns: {len(ambiguous_columns)}")
    print(f"Shared columns: {len(shared_columns)}")

    if indicator_upper_to_cols:
        print("\nIndicator counts:")
        for indicator in indicators:
            matched = indicator_upper_to_cols.get(str(indicator).upper(), [])
            print(f"  {indicator}: {len(matched)}")

    if matched_columns:
        print("\nRename preview:")
        for item in list(matched_columns)[:preview_limit]:
            print(
                "  "
                + f"{item.get('column')} -> {item.get('output_column')} "
                + f"({item.get('indicator')})"
            )

    if ambiguous_columns:
        print("\nAmbiguous columns:")
        for item in list(ambiguous_columns)[:preview_limit]:
            details = item.get("details") or []
            if item.get("reason") == "indicator-occurs-multiple-times":
                detail_text = ", ".join(
                    f"{detail.get('indicator')} x{detail.get('match_count')}"
                    for detail in details
                )
            else:
                detail_text = ", ".join(
                    str(detail.get("indicator"))
                    for detail in details
                    if detail.get("indicator")
                )
            print(f"  {item.get('column')}: {detail_text}")


def cmd_convert_wide_to_long(args) -> None:
    """Handle the 'wide-to-long' command."""
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file '{normalize_path(input_path)}' does not exist.")
        sys.exit(1)

    try:
        sheet_arg: str | int
        preview_limit = max(1, int(args.preview_limit))
        sheet_arg = int(args.sheet) if str(args.sheet).isdigit() else args.sheet
        df = _read_wide_to_long_input(input_path, sheet=sheet_arg)
        indicators = _parse_session_indicators(args.session_indicators)
        indicators = indicators or detect_wide_session_prefixes(
            list(df.columns), min_count=2
        )
        if not indicators:
            raise ValueError(
                "No session-coded columns detected. Provide --session-indicators like T1_,T2_,T3_ "
                "or leave it empty only when the file uses detectable prefixes."
            )

        session_value_map = _parse_session_value_map(args.session_map)
        plan = inspect_wide_to_long_columns(
            list(df.columns), session_indicators=indicators
        )
        can_convert = not bool(plan["ambiguous_columns"])

        if args.inspect_only:
            long_df = None
            if can_convert:
                long_df = convert_wide_to_long_dataframe(
                    df,
                    session_indicators=indicators,
                    session_column_name=args.session_column,
                    session_value_map=session_value_map,
                )

            if args.json:
                print(
                    json.dumps(
                        _wide_to_long_json_payload(
                            input_path=input_path,
                            indicators=indicators,
                            plan=plan,
                            preview_limit=preview_limit,
                            long_df=long_df,
                        ),
                        ensure_ascii=True,
                    )
                )
                return

            _print_wide_to_long_plan(plan, preview_limit=preview_limit)
            if not can_convert:
                sys.exit(2)
            print("\nInspect-only mode: no output file written.")
            return

        if not can_convert:
            if args.json:
                print(
                    json.dumps(
                        _wide_to_long_json_payload(
                            input_path=input_path,
                            indicators=indicators,
                            plan=plan,
                            preview_limit=preview_limit,
                            error=(
                                "Ambiguous session indicator matches found. Use a more specific indicator."
                            ),
                        ),
                        ensure_ascii=True,
                    )
                )
            else:
                _print_wide_to_long_plan(plan, preview_limit=preview_limit)
            sys.exit(2)

        output_path = (
            Path(args.output)
            if args.output
            else _default_wide_to_long_output_path(input_path)
        )
        if output_path.exists() and not args.force:
            message = (
                f"Output file '{normalize_path(output_path)}' already exists. "
                "Use --force to overwrite."
            )
            if args.json:
                print(
                    json.dumps(
                        _wide_to_long_json_payload(
                            input_path=input_path,
                            indicators=indicators,
                            plan=plan,
                            preview_limit=preview_limit,
                            error=message,
                        ),
                        ensure_ascii=True,
                    )
                )
            else:
                print(f"Error: {message}")
            sys.exit(1)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        long_df = convert_wide_to_long_dataframe(
            df,
            session_indicators=indicators,
            session_column_name=args.session_column,
            session_value_map=session_value_map,
        )
        _write_wide_to_long_output(long_df, output_path)

        if args.json:
            print(
                json.dumps(
                    _wide_to_long_json_payload(
                        input_path=input_path,
                        indicators=indicators,
                        plan=plan,
                        preview_limit=preview_limit,
                        long_df=long_df,
                        output_path=output_path,
                    ),
                    ensure_ascii=True,
                )
            )
            return

        _print_wide_to_long_plan(plan, preview_limit=preview_limit)

        print("\nConversion complete")
        print("=" * 50)
        print(f"Input rows: {len(df)}")
        print(f"Output rows: {len(long_df)}")
        print(f"Output columns: {len(long_df.columns)}")
        print(f"Wrote: {normalize_path(output_path)}")
    except ValueError as exc:
        if args.json:
            print(json.dumps({"error": str(exc)}, ensure_ascii=True))
        else:
            print(f"Error: {exc}")
        sys.exit(2)
    except Exception as exc:
        message = f"Wide-to-long conversion failed: {exc}"
        if args.json:
            print(json.dumps({"error": message}, ensure_ascii=True))
        else:
            print(f"Error: {message}")
        sys.exit(2)
