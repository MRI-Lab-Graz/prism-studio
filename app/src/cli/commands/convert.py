"""Conversion-related prism_tools command handlers."""

from __future__ import annotations

from src.physio_varioport import run_varioport_conversion
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from helpers.physio.convert_varioport import convert_varioport
from src.converters.wide_to_long import (
    convert_wide_to_long_dataframe,
    detect_wide_session_prefixes,
    find_empty_data_rows,
    inspect_wide_to_long_columns,
    resolve_wide_to_long_id_uniqueness,
)
from src.batch_convert import (
    PhysioDestinationError,
    _build_physio_base_name,
    physio_target_folder,
)
from src.cross_platform import normalize_path
from src.safe_excel import to_excel_safe
from src.entity_rules import load_entity_rules
from src.utils.naming import sanitize_id


def _normalize_physio_suffix(raw_suffix: str | None) -> str:
    """Normalize CLI physio suffixes to canonical recording-<label>_physio."""
    rules = load_entity_rules()
    physio_suffix = rules.primary_suffix("physio")
    recording_rule = dict(rules.modalities["physio"].optional_entity_values)["recording"]
    default_recording = recording_rule.enum[0]

    suffix = str(raw_suffix or "").strip()
    if not suffix:
        return f"recording-{default_recording}_{physio_suffix}"
    if suffix == physio_suffix:
        return f"recording-{default_recording}_{physio_suffix}"
    if suffix.startswith("recording-"):
        return suffix if suffix.endswith(f"_{physio_suffix}") else f"{suffix}_{physio_suffix}"
    if suffix.endswith(f"_{physio_suffix}"):
        return suffix
    return f"recording-{suffix}_{physio_suffix}"


def get_json_hash(json_path):
    """Calculate hash of a JSON file's semantic content."""
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        canonical = json.dumps(
            obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        return hashlib.md5(
            canonical.encode("utf-8"), usedforsecurity=False
        ).hexdigest()
    except Exception:
        # Fallback: raw bytes hash
        with open(json_path, "rb") as f:
            return hashlib.md5(f.read(), usedforsecurity=False).hexdigest()


def _iter_physio_input_files(input_path: Path) -> list[Path]:
    supported_suffixes = {".raw", ".vpd"}
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in supported_suffixes else []

    files: list[Path] = []
    for candidate in input_path.rglob("*"):
        if candidate.is_file() and candidate.suffix.lower() in supported_suffixes:
            files.append(candidate)
    return files


def cmd_convert_physio(args):
    """Handle the 'convert physio' command."""
    input_path = Path(args.input)
    output_dir = Path(args.output)
    canonical_suffix = _normalize_physio_suffix(getattr(args, "suffix", "physio"))
    task = (getattr(args, "task", None) or "").strip().removeprefix("task-")

    if not input_path.exists():
        print(f"Error: Input path '{input_path}' does not exist.")
        sys.exit(1)

    files = _iter_physio_input_files(input_path)

    if not files:
        if input_path.is_file():
            print("No supported Varioport file found. Supported formats: .raw, .vpd")
        else:
            print("No .raw or .vpd files found in input directory.")
        return

    if input_path.is_file():
        raw_file = files[0]
        output_dir.mkdir(parents=True, exist_ok=True)

        out_edf = output_dir / f"{raw_file.stem}.edf"
        out_json = output_dir / f"{raw_file.stem}.json"

        print(f"Converting {raw_file.name} -> {out_edf.name}")

        try:
            run_varioport_conversion(
                convert_varioport,
                raw_file,
                out_edf,
                out_json,
                task=task,
                sampling_rate=args.sampling_rate,
            )
        except Exception as e:
            print(f"Error converting {raw_file.name}: {e}")
            sys.exit(1)

        print(f"\nConversion finished. Success: 1, Errors: 0")
        return

    if not task and getattr(args, "destination", None):
        print("--destination is ignored without --task: files go to physio/", file=sys.stderr)
    try:
        folder = physio_target_folder(task, getattr(args, "destination", None))
    except PhysioDestinationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)

    print(f"Scanning {input_path} for raw physio files...")

    print(f"Found {len(files)} files to process.")
    if canonical_suffix != getattr(args, "suffix", "physio"):
        print(
            "ℹ️  Using canonical physio suffix "
            f"'{canonical_suffix}' for BIDS-like naming."
        )

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

        target_dir = output_dir / sub_id / ses_id / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        recording = canonical_suffix.removeprefix("recording-").removesuffix("_physio")
        out_base = _build_physio_base_name(
            sub_id, ses_id, f"task-{task}" if task else None, recording
        )
        bids = bool(task)
        out_edf = target_dir / f"{out_base}.{'tsv.gz' if bids else 'edf'}"

        print(f"Converting {filename} -> {out_edf.name}")

        try:
            run_varioport_conversion(
                convert_varioport,
                raw_file,
                out_edf,
                target_dir / f"{out_base}.json",
                task=task,
                sampling_rate=args.sampling_rate,
                bids_base=target_dir / out_base if bids else None,
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
    if success_count:
        from src.modality_versions import pin_after_import

        pin_after_import(output_dir)


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
    from src.converters.file_reader import read_tabular_file

    if suffix in {".csv", ".tsv", ".xlsx"}:
        kind = "xlsx" if suffix == ".xlsx" else suffix.lstrip(".")
        return read_tabular_file(input_path, kind=kind, sheet=sheet).df
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
        to_excel_safe(long_df, output_path, index=False)
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
    id_column_checked: str | None = None,
    id_uniqueness: dict[str, Any] | None = None,
    empty_data_rows: list[dict[str, Any]] | None = None,
    empty_data_rows_dropped: bool = False,
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
        "id_column_checked": id_column_checked,
        "id_uniqueness": id_uniqueness or {},
        "empty_data_rows": empty_data_rows or [],
        "empty_data_rows_dropped": empty_data_rows_dropped,
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


def _print_empty_data_rows(
    empty_data_rows: list[dict[str, Any]], *, dropped: bool
) -> None:
    if not empty_data_rows:
        return
    ids = [
        str(row.get("id_value") or f"row {row.get('row_index')}")
        for row in empty_data_rows
    ]
    action = "Dropped" if dropped else "Found"
    print(
        f"\n{action} {len(empty_data_rows)} participant(s) with no session-coded "
        f"data (only ID/shared columns filled in): {', '.join(ids)}"
    )
    if not dropped:
        print("Pass --drop-empty-rows to exclude them from the long output.")


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
        id_check = resolve_wide_to_long_id_uniqueness(
            df,
            source_format=input_path.suffix.lower(),
            explicit_id_column=getattr(args, "id_column", None),
        )
        id_column_checked = str(id_check.get("id_column") or "")
        id_uniqueness = id_check.get("id_uniqueness") or {}

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

        data_columns = list(plan.get("rename_map") or {})
        empty_data_rows = find_empty_data_rows(
            df, id_column=id_column_checked, data_columns=data_columns
        )
        drop_empty_rows = bool(getattr(args, "drop_empty_rows", False))
        if drop_empty_rows and empty_data_rows:
            df = df.drop(
                index=[row["row_index"] for row in empty_data_rows], errors="ignore"
            )

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
                            id_column_checked=id_column_checked,
                            id_uniqueness=id_uniqueness,
                            empty_data_rows=empty_data_rows,
                            empty_data_rows_dropped=drop_empty_rows,
                        ),
                        ensure_ascii=True,
                    )
                )
                return

            _print_wide_to_long_plan(plan, preview_limit=preview_limit)
            print(f"ID uniqueness check passed for column: {id_column_checked}")
            _print_empty_data_rows(empty_data_rows, dropped=drop_empty_rows)
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
                            id_column_checked=id_column_checked,
                            id_uniqueness=id_uniqueness,
                        ),
                        ensure_ascii=True,
                    )
                )
            else:
                _print_wide_to_long_plan(plan, preview_limit=preview_limit)
                print(f"ID uniqueness check passed for column: {id_column_checked}")
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
                            id_column_checked=id_column_checked,
                            id_uniqueness=id_uniqueness,
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
                        id_column_checked=id_column_checked,
                        id_uniqueness=id_uniqueness,
                        empty_data_rows=empty_data_rows,
                        empty_data_rows_dropped=drop_empty_rows,
                    ),
                    ensure_ascii=True,
                )
            )
            return

        _print_wide_to_long_plan(plan, preview_limit=preview_limit)
        print(f"ID uniqueness check passed for column: {id_column_checked}")
        _print_empty_data_rows(empty_data_rows, dropped=drop_empty_rows)

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


def cmd_physio_batch_convert(args) -> None:
    """Handle 'physio batch-convert' command: what Studio's batch convert does, including 'save to project'."""
    import tempfile

    from src.batch_convert import (
        PhysioDestinationError,
        batch_convert_folder,
        create_dataset_description,
        describe_conflicts,
    )
    from src.conversion_to_project import save_physio_batch_to_project
    from src.physio_renamer import normalize_project_dest_root, normalize_subject_rewrite_mode

    source_folder = Path(args.input)
    project = getattr(args, "project", None)
    dry_run = bool(getattr(args, "dry_run", False))
    if not project and not getattr(args, "output", None):
        print("Error: give --output (a folder to write the PRISM dataset to) or --project.", file=sys.stderr)
        sys.exit(2)

    if not source_folder.exists():
        print(f"Error: Input folder '{source_folder}' does not exist.", file=sys.stderr)
        sys.exit(1)

    def _log(msg: str, level: str = "info") -> None:
        prefix = {
            "success": "✅",
            "warning": "⚠️ ",
            "error": "❌",
            "step": "→ ",
        }.get(level, "")
        print(f"{prefix}{msg}")

    # With --project, like Studio: convert into a staging folder, then save into the project
    staging = tempfile.TemporaryDirectory(prefix="prism_batch_convert_") if project else None
    output_folder = Path(staging.name) / "output" if staging else Path(args.output)
    dataset_name = getattr(args, "dataset_name", None) or "Converted Dataset"
    try:
        result = batch_convert_folder(
            source_folder=source_folder,
            output_folder=output_folder,
            physio_sampling_rate=getattr(args, "sampling_rate", None),
            generate_physio_reports=bool(getattr(args, "generate_physio_reports", False)),
            modality_filter=getattr(args, "modality", "all"),
            log_callback=_log,
            dry_run=dry_run,
            physio_destination=getattr(args, "destination", None),
        )
        conflicts = None if dry_run else describe_conflicts(result, output_folder)
        if conflicts:  # as Studio: two different files for one place, nothing is saved
            print(f"Error: {conflicts[0]}", file=sys.stderr)
            sys.exit(1)
        if not dry_run:  # Studio writes it after every real conversion
            create_dataset_description(output_folder, name=dataset_name)
        if project and not dry_run:
            saved = save_physio_batch_to_project(
                project_root=Path(project).resolve(),
                staged_root=output_folder,
                converted=result.converted,
                dataset_name=dataset_name,
                dest_root=normalize_project_dest_root(getattr(args, "dest_root", None) or "root"),
                flat_structure=bool(getattr(args, "flat_structure", False)),
                modality_filter=getattr(args, "modality", "all"),
                subject_rewrite_mode=normalize_subject_rewrite_mode(getattr(args, "subject_rewrite_mode", None)),
                log_fn=_log,
            )
            for warning in saved.warnings:
                _log(warning, "warning")
    except PhysioDestinationError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(2)
    finally:
        if staging is not None:
            staging.cleanup()

    print(
        f"\n{'DRY-RUN ' if dry_run else ''}Batch convert complete: "
        f"{result.success_count} converted, {result.error_count} errors, "
        f"{len(result.skipped)} skipped."
    )
    if result.error_count:
        sys.exit(1)
