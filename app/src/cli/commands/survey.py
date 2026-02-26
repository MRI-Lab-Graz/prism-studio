"""Survey-related prism_tools command handlers (safe extraction batch)."""

from __future__ import annotations

import sys
from pathlib import Path

from src.converters.excel_to_survey import process_excel
from src.converters.limesurvey import batch_convert_lsa, convert_lsa_to_prism
from src.library_i18n import compile_survey_template, migrate_survey_template_to_i18n
from src.library_validator import check_uniqueness
from src.utils.io import ensure_dir as _ensure_dir
from src.utils.io import read_json as _read_json
from src.utils.io import write_json as _write_json


def cmd_survey_import_excel(args):
    """Import survey library from Excel."""
    print(f"Importing survey library from {args.excel}...")
    try:
        if getattr(args, "library_root", None):
            output_dir = Path(args.library_root) / "survey"
        else:
            output_dir = Path(args.output)
            if output_dir.name != "survey":
                output_dir = output_dir / "survey"

        output_dir_str = str(_ensure_dir(output_dir))
        process_excel(args.excel, output_dir_str)

        print("\nValidating imported files...")
        check_uniqueness(output_dir_str)
    except Exception as e:
        print(f"Error importing Excel: {e}")
        sys.exit(1)


def cmd_survey_validate(args):
    """Validate survey library."""
    print(f"Validating survey library at {args.library}...")
    if check_uniqueness(args.library):
        sys.exit(0)
    else:
        sys.exit(1)


def cmd_survey_import_limesurvey(args):
    """Import LimeSurvey structure."""
    print(f"Importing LimeSurvey structure from {args.input}...")
    try:
        convert_lsa_to_prism(args.input, args.output, task_name=args.task)

        print("\nValidating imported files...")
        check_uniqueness(args.output)
    except Exception as e:
        print(f"Error importing LimeSurvey: {e}")
        sys.exit(1)


def parse_session_map(map_str):
    mapping = {}
    for item in map_str.split(","):
        token = item.strip()
        if not token:
            continue
        sep = ":" if ":" in token else ("=" if "=" in token else None)
        if not sep:
            if "_" in token:
                raw, mapped = token.split("_", 1)
            else:
                continue
        else:
            raw, mapped = token.split(sep, 1)
        mapping[raw.strip().lower()] = mapped.strip()
    return mapping


def cmd_survey_import_limesurvey_batch(args):
    """Batch convert LimeSurvey archives with session mapping (t1/t2/t3 -> ses-1/2/3)."""
    session_map = parse_session_map(args.session_map)
    if not session_map:
        print("No valid session mapping provided. Example: t1:ses-1,t2:ses-2,t3:ses-3")
        sys.exit(1)
    try:
        batch_convert_lsa(
            args.input_dir,
            args.output_dir,
            session_map,
            library_path=args.library,
            task_fallback=args.task,
            id_column=args.subject_id_col,
            id_map_file=args.id_map,
        )

        print("\nValidating imported files...")
        check_uniqueness(args.output_dir)
    except Exception as e:
        print(f"Error importing LimeSurvey: {e}")
        sys.exit(1)


def cmd_survey_i18n_migrate(args):
    """Create i18n-capable source files from single-language survey templates."""
    src_dir = Path(args.src).resolve()
    dst_dir = _ensure_dir(Path(args.dst).resolve())
    languages = [p.strip() for p in str(args.languages).replace(";", ",").split(",")]
    languages = [p for p in languages if p]
    if not languages:
        languages = ["de", "en"]

    if not src_dir.exists() or not src_dir.is_dir():
        print(f"Error: --src is not a directory: {src_dir}")
        sys.exit(1)

    files = sorted(src_dir.glob("survey-*.json"))
    if not files:
        print(f"Error: No survey-*.json files found in: {src_dir}")
        sys.exit(1)

    written = 0
    for p in files:
        try:
            data = _read_json(p)
        except Exception as e:
            print(f"Warning: Skipping unreadable JSON {p.name}: {e}")
            continue

        migrated = migrate_survey_template_to_i18n(data, languages=languages)
        out_path = dst_dir / p.name
        _write_json(out_path, migrated)
        written += 1

    print(f"✅ Migrated {written} template(s) into i18n source format")
    print(f"   Output: {dst_dir}")


def cmd_survey_i18n_build(args):
    """Compile i18n-capable survey templates into PRISM schema-compatible templates."""
    src_dir = Path(args.src).resolve()
    out_dir = _ensure_dir(Path(args.out).resolve())
    lang = str(args.lang).strip()
    fallback = str(args.fallback).strip() if getattr(args, "fallback", None) else ""
    fallback_langs = [fallback] if fallback else []

    if not src_dir.exists() or not src_dir.is_dir():
        print(f"Error: --src is not a directory: {src_dir}")
        sys.exit(1)

    files = sorted(src_dir.glob("survey-*.json"))
    if not files:
        print(f"Error: No survey-*.json files found in: {src_dir}")
        sys.exit(1)

    written = 0
    for p in files:
        try:
            data = _read_json(p)
        except Exception as e:
            print(f"Warning: Skipping unreadable JSON {p.name}: {e}")
            continue

        compiled = compile_survey_template(data, lang=lang, fallback_langs=fallback_langs)
        out_path = out_dir / p.name
        _write_json(out_path, compiled)
        written += 1

    print(f"✅ Built {written} template(s) for lang='{lang}'")
    print(f"   Output: {out_dir}")
