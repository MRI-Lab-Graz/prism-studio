#!/usr/bin/env python3
import argparse
import sys
import os
import shutil
import json
import hashlib
from pathlib import Path

# Enforce running from the repo-local virtual environment (skip for frozen/packaged apps)
# Since this script moved to app/, venv is one level up
current_dir = os.path.dirname(os.path.abspath(__file__))
venv_path = os.path.join(os.path.dirname(current_dir), ".venv")
if not getattr(sys, "frozen", False) and not sys.prefix.startswith(venv_path):
    print("❌ Error: You are not running inside the prism virtual environment!")
    print("   Please activate the venv first:")
    if os.name == "nt":
        print(f"     {venv_path}\\Scripts\\activate")
    else:
        print(f"     source {venv_path}/bin/activate")
    print("   Then run this script again.")
    sys.exit(1)

# Add project root to path to import helpers
project_root = Path(__file__).resolve().parent
sys.path.append(str(project_root))

from src.utils.io import (
    ensure_dir as _ensure_dir,
    read_json as _read_json,
    write_json as _write_json,
)  # noqa: E402

from helpers.physio.convert_varioport import convert_varioport  # noqa: E402
from src.library_validator import check_uniqueness  # noqa: E402
from src.converters.limesurvey import (
    convert_lsa_to_prism,
    batch_convert_lsa,
)  # noqa: E402
from src.converters.excel_to_survey import process_excel  # noqa: E402
from src.converters.excel_to_biometrics import process_excel_biometrics  # noqa: E402
from src.reporting import generate_methods_text  # noqa: E402
from src.library_i18n import (
    compile_survey_template,
    migrate_survey_template_to_i18n,
)  # noqa: E402
from src.recipes_surveys import compute_survey_recipes  # noqa: E402
from src.config import get_effective_library_paths  # noqa: E402
from src.cli.commands.dataset import (  # noqa: E402
    cmd_dataset_build_biometrics_smoketest as _cmd_dataset_build_biometrics_smoketest,
)
from src.cli.commands.library import (  # noqa: E402
    cmd_library_generate_methods_text as _cmd_library_generate_methods_text,
    cmd_library_sync as _cmd_library_sync,
    cmd_library_catalog as _cmd_library_catalog,
    cmd_library_fill as _cmd_library_fill,
)


def _normalize_survey_key(raw: str) -> str:
    s = str(raw or "").strip().lower()
    if not s:
        return s
    for prefix in ("survey-", "task-"):
        if s.startswith(prefix):
            s = s[len(prefix) :]
    return s


def _extract_task_from_survey_filename(path: Path) -> str | None:
    stem = path.stem
    # Examples:
    # sub-001_ses-1_task-ads_beh.tsv
    # sub-001_ses-1_survey-ads_beh.tsv
    for token in stem.split("_"):
        if token.startswith("task-"):
            return token.replace("task-", "", 1).strip().lower() or None
        if token.startswith("survey-"):
            return token.replace("survey-", "", 1).strip().lower() or None
    return None


def _infer_sub_ses_from_path(path: Path) -> tuple[str | None, str | None]:
    sub_id = None
    ses_id = None
    for part in path.parts:
        if sub_id is None and part.startswith("sub-"):
            sub_id = part
        if ses_id is None and part.startswith("ses-"):
            ses_id = part
    return sub_id, ses_id


def _parse_numeric_cell(val: str | None) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "n/a":
        return None
    try:
        # Support both periods and commas as decimal separators (EU locales use commas)
        return float(s.replace(",", "."))
    except ValueError:
        return None


def _format_numeric_cell(val: float | None) -> str:
    if val is None:
        return "n/a"
    if float(val).is_integer():
        return str(int(val))
    return str(val)


def cmd_recipes_surveys(args):
    prism_root = Path(args.prism).resolve()
    if not prism_root.exists() or not prism_root.is_dir():
        print(f"Error: --prism is not a directory: {prism_root}")
        sys.exit(1)

    # Use global library paths if --repo not specified
    if hasattr(args, "repo") and args.repo:
        repo_root = Path(args.repo).resolve()
    else:
        # Get global recipe path from configuration
        lib_paths = get_effective_library_paths(app_root=str(project_root))
        if lib_paths["global_library_root"]:
            repo_root = Path(lib_paths["global_library_root"]).resolve()
            print(f"ℹ️  Using global library: {repo_root}")
        else:
            # Fallback to current directory
            repo_root = Path(project_root).resolve()
            print(f"ℹ️  Using default repository root: {repo_root}")

    if not repo_root.exists() or not repo_root.is_dir():
        print(f"Error: --repo is not a directory: {repo_root}")
        sys.exit(1)

    out_format = str(getattr(args, "format", "flat") or "flat").strip().lower()
    recipe_dir = (
        str(args.recipes).strip() if getattr(args, "recipes", None) else ""
    ) or None
    survey_filter = (
        str(args.survey).strip() if getattr(args, "survey", None) else ""
    ) or None
    sessions_filter = (
        str(args.sessions).strip() if getattr(args, "sessions", None) else ""
    ) or None
    lang = str(getattr(args, "lang", "en") or "en").strip().lower()
    layout = str(getattr(args, "layout", "long") or "long").strip().lower()
    include_raw = bool(getattr(args, "include_raw", False))
    boilerplate = bool(getattr(args, "boilerplate", False))

    try:
        result = compute_survey_recipes(
            prism_root=prism_root,
            repo_root=repo_root,
            recipe_dir=recipe_dir,
            survey=survey_filter,
            sessions=sessions_filter,
            out_format=out_format,
            modality="survey",
            lang=lang,
            layout=layout,
            include_raw=include_raw,
            boilerplate=boilerplate,
        )
        print(f"Survey recipe scoring complete: {result.written_files} file(s) written")
        if result.flat_out_path:
            print(f"   Flat output: {result.flat_out_path}")
        if result.boilerplate_path:
            print(f"   Methods boilerplate (MD):   {result.boilerplate_path}")
        if result.boilerplate_html_path:
            print(f"   Methods boilerplate (HTML): {result.boilerplate_html_path}")
        if result.fallback_note:
            print(f"   Note: {result.fallback_note}")
        if result.nan_report:
            print("   Columns with all n/a:")
            for key, cols in result.nan_report.items():
                joined = ", ".join(sorted(cols))
                print(f"     - {key}: {joined}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_recipes_biometrics(args):
    prism_root = Path(args.prism).resolve()
    if not prism_root.exists() or not prism_root.is_dir():
        print(f"Error: --prism is not a directory: {prism_root}")
        sys.exit(1)

    # Use global library paths if --repo not specified
    if hasattr(args, "repo") and args.repo:
        repo_root = Path(args.repo).resolve()
    else:
        # Get global recipe path from configuration
        lib_paths = get_effective_library_paths(app_root=str(project_root))
        if lib_paths["global_library_root"]:
            repo_root = Path(lib_paths["global_library_root"]).resolve()
            print(f"ℹ️  Using global library: {repo_root}")
        else:
            # Fallback to current directory
            repo_root = Path(project_root).resolve()
            print(f"ℹ️  Using default repository root: {repo_root}")

    if not repo_root.exists() or not repo_root.is_dir():
        print(f"Error: --repo is not a directory: {repo_root}")
        sys.exit(1)

    out_format = str(getattr(args, "format", "flat") or "flat").strip().lower()
    recipe_dir = (
        str(args.recipes).strip() if getattr(args, "recipes", None) else ""
    ) or None
    biometric_filter = (
        str(args.biometric).strip() if getattr(args, "biometric", None) else ""
    ) or None
    sessions_filter = (
        str(args.sessions).strip() if getattr(args, "sessions", None) else ""
    ) or None
    lang = str(getattr(args, "lang", "en") or "en").strip().lower()
    layout = str(getattr(args, "layout", "long") or "long").strip().lower()

    try:
        result = compute_survey_recipes(
            prism_root=prism_root,
            repo_root=repo_root,
            recipe_dir=recipe_dir,
            survey=biometric_filter,
            sessions=sessions_filter,
            out_format=out_format,
            modality="biometrics",
            lang=lang,
            layout=layout,
        )
        print(
            f"✅ Biometric recipe scoring complete: {result.written_files} file(s) written"
        )
        if result.flat_out_path:
            print(f"   Flat output: {result.flat_out_path}")
        if result.fallback_note:
            print(f"   Note: {result.fallback_note}")
        if result.nan_report:
            print("   Columns with all n/a:")
            for key, cols in result.nan_report.items():
                joined = ", ".join(sorted(cols))
                print(f"     - {key}: {joined}")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def sanitize_id(id_str):
    """
    Sanitizes subject/session IDs by replacing German umlauts and special characters.
    """
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
    """Calculates hash of a JSON file's semantic content."""
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
    """
    Consolidates identical JSON sidecars into a single file in the root directory.
    """
    print("\nConsolidating JSON sidecars...")
    # Find all generated JSONs for this task/suffix
    # Pattern: sub-*/ses-*/physio/*_task-<task>_<suffix>.json
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
        # Create root sidecar name: task-<task>_<suffix>.json
        root_json_name = f"task-{task}_{suffix}.json"
        root_json_path = output_dir / root_json_name

        # Copy first json to root
        shutil.copy(first_json, root_json_path)
        print(f"Created root sidecar: {root_json_path}")

        # Delete individual sidecars
        for jf in json_files:
            jf.unlink()
        print("Deleted individual sidecars.")
    else:
        print("Sidecars differ. Keeping individual files.")


def cmd_convert_physio(args):
    """
    Handles the 'convert physio' command.
    """
    input_dir = Path(args.input)
    output_dir = Path(args.output)

    if not input_dir.exists():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        sys.exit(1)

    print(f"Scanning {input_dir} for raw physio files...")

    # Expected structure: sourcedata/sub-XXX/ses-YYY/physio/filename.raw
    # We search recursively for the raw files
    # The pattern should be flexible but ideally match the BIDS-like structure

    # Find all files matching the pattern
    # We assume files end with .raw or .RAW (case insensitive check later if needed)
    # But glob is case sensitive on Linux.
    files = list(input_dir.rglob("*.[rR][aA][wW]"))

    if not files:
        print("No .raw files found in input directory.")
        return

    print(f"Found {len(files)} files to process.")

    success_count = 0
    error_count = 0

    for raw_file in files:
        # Infer subject and session from path or filename
        # Expected filename: sub-<id>_ses-<id>_physio.raw
        filename = raw_file.name

        # Simple parsing logic
        parts = raw_file.stem.split("_")
        sub_id = None
        ses_id = None

        for part in parts:
            if part.startswith("sub-"):
                sub_id = part
            elif part.startswith("ses-"):
                ses_id = part

        # Fallback: try to get from parent folders if not in filename
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

        # Sanitize IDs
        sub_id = sanitize_id(sub_id)
        ses_id = sanitize_id(ses_id)

        # Construct output path
        # rawdata/sub-XXX/ses-YYY/physio/
        target_dir = output_dir / sub_id / ses_id / "physio"
        target_dir.mkdir(parents=True, exist_ok=True)

        # Construct output filename
        # sub-XXX_ses-YYY_task-<task>_<suffix>.edf
        out_base = f"{sub_id}_{ses_id}_task-{args.task}_{args.suffix}"
        out_edf = target_dir / f"{out_base}.edf"

        # Root sidecar for BIDS inheritance
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

            # Check file size
            if out_edf.exists():
                size_kb = out_edf.stat().st_size / 1024
                if size_kb < 10:  # Warn if smaller than 10KB
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

    # BIDS inheritance is now handled directly by writing to root during conversion
    # consolidate_sidecars(output_dir, args.task, args.suffix)

    print(f"\nConversion finished. Success: {success_count}, Errors: {error_count}")


def cmd_demo_create(args):
    """
    Creates a demo dataset.
    """
    output_path = Path(args.output)
    demo_source = project_root / "demo" / "prism_demo"

    if output_path.exists():
        print(f"Error: Output path '{output_path}' already exists.")
        sys.exit(1)

    print(f"Creating demo dataset at {output_path}...")
    try:
        shutil.copytree(demo_source, output_path)
        print("✅ Demo dataset created successfully.")
    except Exception as e:
        print(f"Error creating demo dataset: {e}")
        sys.exit(1)


def cmd_survey_import_excel(args):
    """
    Imports survey library from Excel.
    """
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


def cmd_survey_convert(args):
    """Convert a wide survey table (currently .xlsx) into a PRISM/BIDS survey dataset."""
    try:
        from src.converters.survey import convert_survey_xlsx_to_prism_dataset
    except Exception as e:
        print(f"Error: Could not import survey conversion module: {e}")
        sys.exit(1)

    import tempfile

    def _has_survey_templates(dir_path: Path) -> bool:
        try:
            return any(dir_path.glob("survey-*.json"))
        except Exception:
            return False

    def _library_needs_i18n_compile(dir_path: Path) -> bool:
        """Return True if templates in dir_path appear to contain language maps."""
        try:
            files = sorted(dir_path.glob("survey-*.json"))
        except Exception:
            return False
        for p in files[:3]:
            try:
                data = _read_json(p)
            except Exception:
                continue
            if isinstance(data, dict) and "I18n" in data:
                return True
            reserved = {
                "Technical",
                "Study",
                "Metadata",
                "I18n",
                "Scoring",
                "Normative",
            }
            for item_id, item_def in (data or {}).items():
                if item_id in reserved or not isinstance(item_def, dict):
                    continue
                d = item_def.get("Description")
                if isinstance(d, dict):
                    return True
                levels = item_def.get("Levels")
                if isinstance(levels, dict) and any(
                    isinstance(v, dict) for v in levels.values()
                ):
                    return True
        return False

    def _compile_i18n_library(
        src_dir: Path, lang: str
    ) -> tuple[Path, tempfile.TemporaryDirectory]:
        tmp = tempfile.TemporaryDirectory(prefix=f"prism_survey_library_{lang}_")
        out_dir = Path(tmp.name)
        _ensure_dir(out_dir)
        fallback_langs = [lang_code for lang_code in ["de", "en"] if lang_code != lang]

        for p in sorted(src_dir.glob("survey-*.json")):
            compiled = compile_survey_template(
                _read_json(p), lang=lang, fallback_langs=fallback_langs
            )
            _write_json(out_dir / p.name, compiled)

        return out_dir, tmp

    lang = str(getattr(args, "lang", "de") or "de").strip().lower()
    if not lang:
        lang = "de"

    library_tmp: tempfile.TemporaryDirectory | None = None
    library_label: str | None = None

    # If --library is explicitly provided, respect it, but auto-compile if it looks like i18n.
    if hasattr(args, "library") and args.library:
        candidate = Path(args.library)
        if _library_needs_i18n_compile(candidate):
            lib_dir, library_tmp = _compile_i18n_library(candidate, lang=lang)
            library_label = f"{candidate.resolve()} (i18n compiled to {lang})"
        else:
            lib_dir = candidate
            library_label = str(candidate.resolve())
    else:
        # Auto-pick best available library:
        # 1) precompiled per-language library (library/survey_de, library/survey_en)
        # 2) i18n source library compiled on the fly (library/survey_i18n)
        # 3) legacy single-language library (library/survey)
        compiled_candidate = project_root / f"library/survey_{lang}"
        i18n_candidate = project_root / "library/survey_i18n"
        legacy_candidate = project_root / "library/survey"

        if compiled_candidate.exists() and _has_survey_templates(compiled_candidate):
            lib_dir = compiled_candidate
            library_label = str(compiled_candidate.resolve())
        elif i18n_candidate.exists() and _has_survey_templates(i18n_candidate):
            lib_dir, library_tmp = _compile_i18n_library(i18n_candidate, lang=lang)
            library_label = f"{i18n_candidate.resolve()} (i18n compiled to {lang})"
        elif legacy_candidate.exists() and _has_survey_templates(legacy_candidate):
            lib_dir = legacy_candidate
            library_label = str(legacy_candidate.resolve())
        else:
            print("Error: Could not find a survey template library.")
            print(
                "       Looked for: library/survey_<lang>, library/survey_i18n, library/survey"
            )
            print("       Or provide --library /path/to/library")
            sys.exit(1)

    try:
        result = convert_survey_xlsx_to_prism_dataset(
            input_path=args.input,
            library_dir=str(lib_dir),
            output_root=args.output,
            survey=args.survey,
            id_column=args.id_column,
            session_column=args.session_column,
            sheet=args.sheet,
            unknown=args.unknown,
            dry_run=bool(args.dry_run),
            force=bool(args.force),
            name=args.name,
            authors=args.authors,
            alias_file=getattr(args, "alias", None),
            skip_participants=True,
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Keep CLI output similar to previous behavior
    print("Survey convert mapping report")
    print("-----------------------------")
    print(f"Input:   {Path(args.input).resolve()}")
    print(f"Library: {library_label or str(lib_dir.resolve())}")
    print(f"Output:  {Path(args.output).resolve()}")
    print(f"ID col:  {result.id_column}")
    if result.session_column:
        print(f"Session: {result.session_column}")
    else:
        print("Session: (default ses-1)")

    for task in result.tasks_included:
        missing = result.missing_items_by_task.get(task, 0)
        print(f"\nSurvey: {task}")
        if missing:
            print(
                f"  - missing items:   {missing} (will be written as '{result.missing_value_token}')"
            )

    if result.missing_cells_by_subject:
        total_missing = sum(result.missing_cells_by_subject.values())
        missing_subjects = sorted(
            result.missing_cells_by_subject.items(), key=lambda kv: kv[1], reverse=True
        )
        worst = ", ".join([f"{sid} ({cnt})" for sid, cnt in missing_subjects[:5]])
        print(
            f"\nWARNING: Normalized {total_missing} missing cells to '{result.missing_value_token}' "
            f"across {len(result.missing_cells_by_subject)} subjects. Top: {worst}"
        )

    if result.unknown_columns and args.unknown != "ignore":
        msg = "WARNING" if args.unknown == "warn" else "ERROR"
        print(f"\n{msg}: Unmapped columns (not found in any survey template):")
        for c in result.unknown_columns:
            print(f"  - {c}")

    if args.dry_run:
        print("\n" + "=" * 80)
        print("DRY-RUN MODE: Conversion Preview")
        print("=" * 80)

        if result.dry_run_preview:
            preview = result.dry_run_preview

            # Summary
            print("\n📊 SUMMARY")
            print(
                f"   Total participants in file: {preview['summary']['total_participants']}"
            )
            print(
                f"   Unique participants: {preview['summary']['unique_participants']}"
            )
            print(f"   Tasks detected: {', '.join(preview['summary']['tasks'])}")
            print(f"   Total files to create: {preview['summary']['total_files']}")

            # Data issues
            if preview["data_issues"]:
                print(f"\n⚠️  DATA ISSUES FOUND ({len(preview['data_issues'])})")
                print(
                    "   These issues should be fixed in your input data BEFORE conversion:\n"
                )

                for issue in preview["data_issues"][:10]:  # Show first 10
                    severity = issue["severity"].upper()
                    print(f"   [{severity}] {issue['type']}")
                    print(f"   → {issue['message']}")

                    if issue["type"] == "duplicate_ids":
                        print(
                            f"   → Duplicates found: {list(issue['details'].keys())[:5]}"
                        )
                    elif issue["type"] == "unexpected_values":
                        print(
                            f"   → Column: {issue['column']} (task: {issue['task']}, item: {issue['item']})"
                        )
                        print(
                            f"   → Expected values: {', '.join(issue['expected'][:10])}"
                        )
                        print(
                            f"   → Unexpected values: {', '.join(str(v) for v in issue['unexpected'][:10])}"
                        )
                    elif issue["type"] == "out_of_range":
                        print(
                            f"   → Column: {issue['column']} (task: {issue['task']}, item: {issue['item']})"
                        )
                        print(f"   → Expected range: {issue['range']}")
                        print(
                            f"   → Values out of range: {issue['out_of_range_count']}"
                        )
                    print()

                if len(preview["data_issues"]) > 10:
                    print(f"   ... and {len(preview['data_issues']) - 10} more issues")
            else:
                print("\n✅ NO DATA ISSUES DETECTED")

            # 📝 Participants.tsv Preview (only shown when participants are being created)
            if "participants_tsv" in preview and preview.get("participants_tsv"):
                print("\n📝 PARTICIPANTS.TSV PREVIEW")
                print("   This file will be created with the following structure:\n")

                tsv_preview = preview["participants_tsv"]
                columns = tsv_preview["columns"]
                sample_rows = tsv_preview["sample_rows"]
                total_rows = tsv_preview["total_rows"]

                # Column names
                print(f"   Columns ({len(columns)} total):")
                for col in columns:
                    print(f"     • {col}")

                # Mapping details if present
                if tsv_preview["mappings"]:
                    print("\n   Column Mappings:")
                    for output_col, mapping_info in tsv_preview["mappings"].items():
                        source_col = mapping_info["source_column"]
                        has_mapping = mapping_info.get("has_value_mapping", False)
                        indicator = "🔄" if has_mapping else "✓"
                        print(f"     {indicator} {output_col} ← {source_col}")
                        if has_mapping and mapping_info.get("value_mapping"):
                            print("        (has value transformation mapping)")

                # Sample data
                print(
                    f"\n   Sample Data (showing first {min(5, len(sample_rows))} of {total_rows} participants):"
                )
                print(f"   {'-' * 100}")

                # Header
                header = " | ".join(f"{col:<20}" for col in columns)
                print(f"   {header}")
                print(f"   {'-' * 100}")

                # Rows
                for row_data in sample_rows[:5]:
                    row_str = " | ".join(
                        f"{str(row_data.get(col, 'n/a')):<20}" for col in columns
                    )
                    print(f"   {row_str}")

                if len(sample_rows) > 5:
                    print(
                        f"   ... and {len(sample_rows) - 5} more rows shown above (total {total_rows} participants)"
                    )

                print(f"   {'-' * 100}")

                # Notes
                if tsv_preview["notes"]:
                    print("\n   📌 Notes:")
                    for note in tsv_preview["notes"]:
                        print(f"     • {note}")

                # Unused columns that could be added to participants.tsv
                unused_cols = tsv_preview.get("unused_columns", [])
                if unused_cols:
                    print(
                        f"\n   ⚠️  UNUSED COLUMNS ({len(unused_cols)} available for participants.tsv):"
                    )
                    print(
                        "      These columns are not being imported as survey data and could be included"
                    )
                    print(
                        "      in participants.tsv if you create/update participants_mapping.json:"
                    )

                    displayed = 0
                    for item in unused_cols[:10]:  # Show first 10
                        # Handle both old format (string) and new format (dict with description)
                        if isinstance(item, dict):
                            field_code = item.get("field_code", "")
                            description = item.get("description", "")
                            if description:
                                print(f"      • {field_code}")
                                print(f"        ↳ {description}")
                            else:
                                print(f"      • {field_code}")
                        else:
                            print(f"      • {item}")
                        displayed += 1

                    if len(unused_cols) > 10:
                        print(f"      ... and {len(unused_cols) - 10} more columns")

                print()

            # Participants preview
            print("\n👥 PARTICIPANT SURVEY COMPLETENESS (first 10)")
            for p in preview["participants"][:10]:
                completeness = p["completeness_percent"]
                status = (
                    "✓" if completeness > 80 else ("⚠" if completeness > 50 else "✗")
                )
                print(f"   {status} {p['participant_id']} ({p['session_id']})")
                print(f"      Raw ID: {p['raw_id']}")
                print(
                    f"      Completeness: {completeness}% ({p['total_items'] - p['missing_values']}/{p['total_items']} items)"
                )

            if len(preview["participants"]) > 10:
                print(
                    f"   ... and {len(preview['participants']) - 10} more participants"
                )

            # Column mapping preview
            print("\n📋 COLUMN MAPPING (first 15)")
            shown = 0
            for col, info in list(preview["column_mapping"].items())[:15]:
                run_info = f" (run {info['run']})" if info["run"] else ""
                status = "⚠" if info.get("has_unexpected_values") else "✓"
                print(f"   {status} {col}")
                print(
                    f"      → Task: {info['task']}{run_info}, Item: {info['base_item']}"
                )
                print(
                    f"      → Missing: {info['missing_percent']}% ({info['missing_count']} values)"
                )
                if info.get("has_unexpected_values"):
                    print("      ⚠  Has unexpected values!")
                shown += 1

            if len(preview["column_mapping"]) > 15:
                print(f"   ... and {len(preview['column_mapping']) - 15} more columns")

            # Files to create
            print("\n📁 FILES TO CREATE (showing structure)")
            file_types = {}
            for f in preview["files_to_create"]:
                file_types[f["type"]] = file_types.get(f["type"], 0) + 1

            print(f"   Metadata files: {file_types.get('metadata', 0)}")
            print(f"   Sidecar files: {file_types.get('sidecar', 0)}")
            print(f"   Data files: {file_types.get('data', 0)}")

            print("\n   Sample files:")
            shown_by_type = {"metadata": 0, "sidecar": 0, "data": 0}
            for f in preview["files_to_create"]:
                if shown_by_type[f["type"]] < 3:
                    print(f"   - {f['path']}")
                    print(f"     {f['description']}")
                    shown_by_type[f["type"]] += 1

        print("\n" + "=" * 80)
        print("No files were created. Run without --dry-run to execute the conversion.")
        print("=" * 80)
        return

    print("\n✅ Survey conversion complete.")


def cmd_biometrics_import_excel(args):
    """Imports biometrics templates/library from Excel."""
    print(f"Importing biometrics library from {args.excel} (sheet={args.sheet})...")
    try:
        sheet = (
            int(args.sheet)
            if isinstance(args.sheet, str) and args.sheet.isdigit()
            else args.sheet
        )
        if getattr(args, "library_root", None):
            output_dir = Path(args.library_root) / "biometrics"
        else:
            output_dir = Path(args.output)
            if output_dir.name != "biometrics":
                output_dir = output_dir / "biometrics"

        output_dir_str = str(_ensure_dir(output_dir))
        process_excel_biometrics(
            args.excel,
            output_dir_str,
            sheet_name=sheet,
            equipment=args.equipment,
            supervisor=args.supervisor,
        )

        print("\nValidating imported files...")
        check_uniqueness(output_dir_str)
    except Exception as e:
        print(f"Error importing Excel: {e}")
        sys.exit(1)


def cmd_dataset_build_biometrics_smoketest(args):
    _cmd_dataset_build_biometrics_smoketest(args)


def cmd_survey_validate(args):
    """
    Validates the survey library.
    """
    print(f"Validating survey library at {args.library}...")
    if check_uniqueness(args.library):
        sys.exit(0)
    else:
        sys.exit(1)


def cmd_survey_import_limesurvey(args):
    """
    Imports LimeSurvey structure.
    """
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
            # allow shorthand like t1_ses-1
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
    """Create i18n-capable source files from single-language survey templates.

    This does NOT translate content; it wraps existing strings into the detected language
    and creates empty-string placeholders for other languages.
    """

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

        compiled = compile_survey_template(
            data, lang=lang, fallback_langs=fallback_langs
        )
        out_path = out_dir / p.name
        _write_json(out_path, compiled)
        written += 1

    print(f"✅ Built {written} template(s) for lang='{lang}'")
    print(f"   Output: {out_dir}")


def cmd_library_generate_methods_text(args):
    _cmd_library_generate_methods_text(args)


def cmd_library_sync(args):
    _cmd_library_sync(args)


def cmd_library_catalog(args):
    _cmd_library_catalog(args)


def cmd_library_fill(args):
    _cmd_library_fill(args)


def cmd_anonymize(args):
    """Anonymize a dataset for sharing."""
    from src.anonymizer import create_participant_mapping, anonymize_tsv_file
    import csv

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

    # Step 1: Collect all participant IDs
    participant_ids = set()
    # Check rawdata/ first (PRISM/YODA structure), then root (BIDS)
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
        # Scan for subject folders
        for sub_dir in dataset_path.glob("sub-*"):
            if sub_dir.is_dir():
                participant_ids.add(sub_dir.name)

    if not participant_ids:
        print("Error: No participants found in dataset")
        sys.exit(1)

    print(f"Found {len(participant_ids)} participants")

    # Step 2: Create or load mapping
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
    for i, (orig, anon) in enumerate(list(participant_mapping.items())[:3]):
        print(f"  {orig} → {anon}")
    print()

    # Step 3: Copy dataset structure
    output_path.mkdir(parents=True, exist_ok=True)

    # Copy and anonymize participants.tsv
    if participants_tsv.exists():
        print("Anonymizing participants.tsv...")
        output_participants = output_path / "participants.tsv"
        anonymize_tsv_file(participants_tsv, output_participants, participant_mapping)
        print(f"  ✓ {output_participants}")

    # Step 4: Copy and anonymize survey/biometric data
    print("Anonymizing data files...")
    for tsv_file in dataset_path.rglob("*.tsv"):
        if tsv_file.name == "participants.tsv":
            continue  # Already handled

        # Calculate relative path and update with anonymized IDs
        rel_path = tsv_file.relative_to(dataset_path)
        new_rel_path_str = str(rel_path)

        # Replace participant IDs in path
        for orig_id, anon_id in participant_mapping.items():
            new_rel_path_str = new_rel_path_str.replace(orig_id, anon_id)

        output_file = output_path / new_rel_path_str
        anonymize_tsv_file(tsv_file, output_file, participant_mapping)
        print(f"  ✓ {rel_path} → {new_rel_path_str}")

    # Step 5: Copy JSON sidecars (with optional question masking)
    print("Copying metadata files...")
    for json_file in dataset_path.rglob("*.json"):
        rel_path = json_file.relative_to(dataset_path)

        # Skip the mapping file itself
        if json_file == mapping_file:
            continue

        # Replace participant IDs in path
        new_rel_path_str = str(rel_path)
        for orig_id, anon_id in participant_mapping.items():
            new_rel_path_str = new_rel_path_str.replace(orig_id, anon_id)

        output_file = output_path / new_rel_path_str
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # TODO: If mask_questions flag is set, process survey sidecars to mask question text
        import shutil

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


def main():
    parser = argparse.ArgumentParser(
        description="Prism Tools: Utilities for PRISM/BIDS datasets"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Command: convert
    parser_convert = subparsers.add_parser(
        "convert", help="Convert raw data to BIDS format"
    )
    convert_subparsers = parser_convert.add_subparsers(
        dest="modality", help="Modality to convert"
    )

    # Subcommand: convert physio
    parser_physio = convert_subparsers.add_parser(
        "physio", help="Convert physiological data (Varioport)"
    )
    parser_physio.add_argument(
        "--input", required=True, help="Path to sourcedata directory"
    )
    parser_physio.add_argument(
        "--output", required=True, help="Path to output rawdata directory"
    )
    parser_physio.add_argument(
        "--task", default="rest", help="Task name (default: rest)"
    )
    parser_physio.add_argument(
        "--suffix", default="physio", help="Output suffix (default: physio)"
    )
    parser_physio.add_argument(
        "--sampling-rate", type=float, help="Override sampling rate (e.g. 256)"
    )

    # Command: demo
    parser_demo = subparsers.add_parser("demo", help="Demo dataset operations")
    demo_subparsers = parser_demo.add_subparsers(dest="action", help="Action")

    # Subcommand: demo create
    parser_demo_create = demo_subparsers.add_parser(
        "create", help="Create a demo dataset"
    )
    parser_demo_create.add_argument(
        "--output",
        default="archive/prism_demo_copy",
        help="Output path for the demo dataset",
    )

    # Command: survey
    parser_survey = subparsers.add_parser("survey", help="Survey library operations")
    survey_subparsers = parser_survey.add_subparsers(dest="action", help="Action")

    # Subcommand: survey import-excel
    parser_survey_excel = survey_subparsers.add_parser(
        "import-excel", help="Import survey library from Excel"
    )
    parser_survey_excel.add_argument(
        "--excel", required=True, help="Path to Excel file"
    )
    parser_survey_excel.add_argument(
        "--output", default="survey_library", help="Output directory"
    )
    parser_survey_excel.add_argument(
        "--library-root",
        dest="library_root",
        help="If set, writes to <library-root>/survey instead of --output.",
    )

    # Subcommand: survey convert
    parser_survey_convert = survey_subparsers.add_parser(
        "convert",
        help="Convert a wide survey data file (.xlsx or .lsa) into a PRISM/BIDS survey dataset",
    )
    parser_survey_convert.add_argument(
        "--input",
        required=True,
        help="Path to the survey data file (.xlsx or LimeSurvey .lsa)",
    )
    parser_survey_convert.add_argument(
        "--library",
        default=argparse.SUPPRESS,
        help=(
            "Path to survey template library folder (contains survey-*.json). "
            "If omitted, auto-selects library/survey_<lang>, then library/survey_i18n (compiled), then library/survey."
        ),
    )
    parser_survey_convert.add_argument(
        "--lang",
        default="de",
        help="Language for templates when using i18n libraries (default: de; use 'auto' to infer for .lsa)",
    )
    parser_survey_convert.add_argument(
        "--output",
        required=True,
        help="Output dataset root folder (will be created if missing)",
    )
    parser_survey_convert.add_argument(
        "--survey",
        help="Comma-separated list of surveys to include (e.g., 'ads,psqi'). Default: auto-detect from headers.",
    )
    parser_survey_convert.add_argument(
        "--id-column",
        dest="id_column",
        help="Column name containing participant IDs (default: auto-detect)",
    )
    parser_survey_convert.add_argument(
        "--session-column",
        dest="session_column",
        help="Optional column name for session labels (default: auto-detect; otherwise ses-1)",
    )
    parser_survey_convert.add_argument(
        "--sheet",
        default=0,
        help="Excel sheet name or index (default: 0)",
    )
    parser_survey_convert.add_argument(
        "--unknown",
        choices=["error", "warn", "ignore"],
        default="warn",
        help="How to handle unmapped columns not found in any survey template (default: warn)",
    )
    parser_survey_convert.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print mapping report; do not write files",
    )
    parser_survey_convert.add_argument(
        "--force",
        action="store_true",
        help="Allow writing into a non-empty output dir and overwrite inherited sidecars",
    )
    parser_survey_convert.add_argument(
        "--name",
        help="Dataset name written to dataset_description.json (if created)",
    )
    parser_survey_convert.add_argument(
        "--authors",
        nargs="+",
        default=None,
        help="Authors written to dataset_description.json (if created)",
    )

    parser_survey_convert.add_argument(
        "--alias",
        dest="alias",
        default=None,
        help=(
            "Optional TSV/whitespace alias file: each line is '<canonical_id> <alias1> <alias2> ...'. "
            "Used to map changing item IDs onto stable canonical IDs before template matching."
        ),
    )

    # Command: biometrics
    parser_biometrics = subparsers.add_parser(
        "biometrics", help="Biometrics library operations"
    )
    biometrics_subparsers = parser_biometrics.add_subparsers(
        dest="action", help="Action"
    )

    # Command: recipes
    parser_recipes = subparsers.add_parser(
        "recipes",
        help="Compute scores/recipes from an already-valid PRISM dataset using recipes",
    )
    recipes_subparsers = parser_recipes.add_subparsers(dest="kind", help="Recipe kind")

    parser_deriv_surveys = recipes_subparsers.add_parser(
        "surveys",
        aliases=["survey", "surves"],
        help="Compute survey scores (e.g., reverse coding, subscales) from TSVs",
    )
    parser_deriv_surveys.add_argument(
        "--prism",
        "--dataset",
        required=True,
        help="Path to the PRISM dataset root (input + output target)",
    )
    parser_deriv_surveys.add_argument(
        "--repo",
        default=(
            str(project_root.parent)
            if project_root.name == "app"
            else str(project_root)
        ),
        help=(
            "Path to the PRISM tools repository root (used to locate recipe JSONs under "
            "recipe/survey/*.json). Default: this script's folder."
        ),
    )
    parser_deriv_surveys.add_argument(
        "--recipes",
        help="Optional path to a custom folder containing recipe JSONs. Overrides default repository folder.",
    )
    parser_deriv_surveys.add_argument(
        "--survey",
        "--task",
        help="Optional comma-separated recipe selection (e.g., 'ADS'). Default: run all matching recipes.",
    )
    parser_deriv_surveys.add_argument(
        "--sessions",
        help="Optional comma-separated session list (e.g., 'ses-1,ses-2' or '1,2'). Default: all sessions.",
    )
    parser_deriv_surveys.add_argument(
        "--format",
        default="flat",
        choices=["prism", "flat", "csv", "xlsx", "save", "r"],
        help="Output format: 'flat' (default), 'prism', 'csv', 'xlsx', 'sav' (SPSS), 'r' (feather)",
    )
    parser_deriv_surveys.add_argument(
        "--lang",
        default="en",
        choices=["en", "de"],
        help="Language for metadata labels in export formats (default: en)",
    )
    parser_deriv_surveys.add_argument(
        "--layout",
        default="long",
        choices=["long", "wide"],
        help="Layout for repeated measures: 'long' (one row per session) or 'wide' (one row per participant)",
    )
    parser_deriv_surveys.add_argument(
        "--include-raw",
        action="store_true",
        help="Include original raw data columns in the output",
    )
    parser_deriv_surveys.add_argument(
        "--boilerplate",
        action="store_true",
        help="Generate a scientific methods boilerplate describing the scoring logic",
    )

    parser_deriv_biometrics = recipes_subparsers.add_parser(
        "biometrics",
        aliases=["biometric"],
        help="Compute biometric scores (e.g., best of trials, composite scores) from TSVs",
    )
    parser_deriv_biometrics.add_argument(
        "--prism",
        "--dataset",
        required=True,
        help="Path to the PRISM dataset root (input + output target)",
    )
    parser_deriv_biometrics.add_argument(
        "--repo",
        default=(
            str(project_root.parent)
            if project_root.name == "app"
            else str(project_root)
        ),
        help=(
            "Path to the PRISM tools repository root (used to locate recipe JSONs under "
            "recipe/biometrics/*.json). Default: this script's folder."
        ),
    )
    parser_deriv_biometrics.add_argument(
        "--recipes",
        help="Optional path to a custom folder containing recipe JSONs. Overrides default repository folder.",
    )
    parser_deriv_biometrics.add_argument(
        "--biometric",
        "--task",
        help="Optional comma-separated recipe selection (e.g., 'y_balance'). Default: run all matching recipes.",
    )
    parser_deriv_biometrics.add_argument(
        "--sessions",
        help="Optional comma-separated session list (e.g., 'ses-1,ses-2' or '1,2'). Default: all sessions.",
    )
    parser_deriv_biometrics.add_argument(
        "--format",
        default="flat",
        choices=["prism", "flat", "csv", "xlsx", "save", "r"],
        help="Output format: 'flat' (default), 'prism', 'csv', 'xlsx', 'sav' (SPSS), 'r' (feather)",
    )
    parser_deriv_biometrics.add_argument(
        "--lang",
        default="en",
        choices=["en", "de"],
        help="Language for metadata labels in export formats (default: en)",
    )
    parser_deriv_biometrics.add_argument(
        "--layout",
        default="long",
        choices=["long", "wide"],
        help="Layout for repeated measures: 'long' (one row per session) or 'wide' (one row per participant)",
    )

    # Subcommand: biometrics import-excel
    parser_biometrics_excel = biometrics_subparsers.add_parser(
        "import-excel", help="Import biometrics templates/library from Excel"
    )
    parser_biometrics_excel.add_argument(
        "--excel", required=True, help="Path to Excel file"
    )
    parser_biometrics_excel.add_argument(
        "--output", default="biometrics_library", help="Output directory"
    )
    parser_biometrics_excel.add_argument(
        "--library-root",
        dest="library_root",
        help="If set, writes to <library-root>/biometrics instead of --output.",
    )
    parser_biometrics_excel.add_argument(
        "--sheet",
        default=0,
        help="Sheet name or index containing the data dictionary (e.g., 'Description').",
    )
    parser_biometrics_excel.add_argument(
        "--equipment",
        default="Legacy/Imported",
        help="Default Technical.Equipment value written to biometrics JSON (required by schema).",
    )
    parser_biometrics_excel.add_argument(
        "--supervisor",
        default="investigator",
        choices=["investigator", "physician", "trainer", "self"],
        help="Default Technical.Supervisor value written to biometrics JSON.",
    )

    # Command: dataset
    parser_dataset = subparsers.add_parser("dataset", help="Dataset helper commands")
    dataset_subparsers = parser_dataset.add_subparsers(dest="action", help="Action")

    parser_ds_bio = dataset_subparsers.add_parser(
        "build-biometrics-smoketest",
        help="Build a small PRISM-valid biometrics dataset from a codebook and dummy CSV",
    )
    parser_ds_bio.add_argument(
        "--codebook",
        default="test_dataset/Biometrics_variables.xlsx",
        help="Path to Biometrics codebook Excel (default: test_dataset/Biometrics_variables.xlsx)",
    )
    parser_ds_bio.add_argument(
        "--sheet",
        default="biometrics_codebook",
        help="Sheet name or index for the codebook (default: biometrics_codebook)",
    )
    parser_ds_bio.add_argument(
        "--data",
        default="test_dataset/Biometrics_dummy_data.csv",
        help="Path to dummy biometrics data CSV with participant_id column",
    )
    parser_ds_bio.add_argument(
        "--output",
        default="test_dataset/_tmp_prism_biometrics_dataset",
        help="Output dataset directory (must be empty or non-existent)",
    )
    parser_ds_bio.add_argument(
        "--library-root",
        default="library",
        help="Library root directory to write templates into (creates <library-root>/biometrics)",
    )
    parser_ds_bio.add_argument(
        "--name",
        default="PRISM Biometrics Smoketest",
        help="Dataset name for dataset_description.json",
    )
    parser_ds_bio.add_argument(
        "--authors",
        nargs="+",
        default=None,
        help="Authors for dataset_description.json (default: 'PRISM smoketest')",
    )
    parser_ds_bio.add_argument(
        "--session",
        default="ses-01",
        help="Session folder label to use (default: ses-01)",
    )
    parser_ds_bio.add_argument(
        "--equipment",
        default="Legacy/Imported",
        help="Default Technical.Equipment value for generated biometrics templates",
    )
    parser_ds_bio.add_argument(
        "--supervisor",
        default="investigator",
        choices=["investigator", "physician", "trainer", "self"],
        help="Default Technical.Supervisor value for generated biometrics templates",
    )

    # Command: anonymize
    parser_anonymize = subparsers.add_parser(
        "anonymize",
        help="Anonymize a dataset for sharing (randomize participant IDs, mask copyrighted questions)",
    )
    parser_anonymize.add_argument(
        "--dataset", required=True, help="Path to the PRISM dataset to anonymize"
    )
    parser_anonymize.add_argument(
        "--output",
        help="Path for the anonymized output dataset (default: <dataset>_anonymized)",
    )
    parser_anonymize.add_argument(
        "--mapping",
        help="Path to save/load the ID mapping file (default: <output>/code/anonymization_map.json)",
    )
    parser_anonymize.add_argument(
        "--id-length",
        type=int,
        default=6,
        help="Length of randomized ID codes (default: 6)",
    )
    parser_anonymize.add_argument(
        "--random",
        action="store_true",
        help="Use truly random IDs (default: deterministic based on original IDs)",
    )
    parser_anonymize.add_argument(
        "--force",
        action="store_true",
        help="Force creation of new mapping even if one exists",
    )
    parser_anonymize.add_argument(
        "--mask-questions",
        action="store_true",
        help="Mask copyrighted question text (e.g., 'ADS Question 1' instead of full text)",
    )

    # Subcommand: survey validate
    parser_survey_validate = survey_subparsers.add_parser(
        "validate", help="Validate survey library"
    )
    parser_survey_validate.add_argument(
        "--library", default="survey_library", help="Path to survey library"
    )

    # Subcommand: survey import-limesurvey
    parser_survey_limesurvey = survey_subparsers.add_parser(
        "import-limesurvey", help="Import LimeSurvey structure"
    )
    parser_survey_limesurvey.add_argument(
        "--input", required=True, help="Path to .lsa/.lss file"
    )
    parser_survey_limesurvey.add_argument("--output", help="Path to output .json file")
    parser_survey_limesurvey.add_argument(
        "--task", help="Optional task name override (defaults from file name)"
    )

    parser_survey_limesurvey_batch = survey_subparsers.add_parser(
        "import-limesurvey-batch",
        help="Batch import LimeSurvey files with session mapping",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--input-dir", required=True, help="Root directory containing .lsa/.lss files"
    )
    parser_survey_limesurvey_batch.add_argument(
        "--output-dir", required=True, help="Output root for generated PRISM dataset"
    )
    parser_survey_limesurvey_batch.add_argument(
        "--session-map",
        default="t1:ses-1,t2:ses-2,t3:ses-3",
        help="Comma-separated mapping, e.g. t1:ses-1,t2:ses-2,t3:ses-3",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--task",
        help="Optional task name fallback (otherwise derived from file name)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--library",
        default="survey_library",
        help="Path to survey library (survey-*.json and optional participants.json)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--subject-id-col",
        dest="subject_id_col",
        help="Preferred column name to use for participant ID (e.g., ID, code, token)",
    )
    parser_survey_limesurvey_batch.add_argument(
        "--id-map",
        dest="id_map",
        help="Path to TSV/CSV file mapping LimeSurvey IDs to BIDS participant IDs (cols: limesurvey_id, participant_id)",
    )

    # Subcommand: survey i18n-migrate
    parser_survey_i18n_migrate = survey_subparsers.add_parser(
        "i18n-migrate",
        help="Create i18n-capable source templates from single-language survey-*.json templates (no translation)",
    )
    parser_survey_i18n_migrate.add_argument(
        "--src",
        default="library/survey",
        help="Source folder containing single-language survey-*.json (default: library/survey)",
    )
    parser_survey_i18n_migrate.add_argument(
        "--dst",
        default="library/survey_i18n",
        help="Destination folder for i18n source templates (default: library/survey_i18n)",
    )
    parser_survey_i18n_migrate.add_argument(
        "--languages",
        default="de,en",
        help="Comma-separated language codes to include (default: de,en)",
    )

    # Subcommand: survey i18n-build
    parser_survey_i18n_build = survey_subparsers.add_parser(
        "i18n-build",
        help="Compile i18n survey templates into PRISM schema-compatible survey-*.json for one language",
    )
    parser_survey_i18n_build.add_argument(
        "--src",
        default="library/survey_i18n",
        help="Source folder containing i18n survey-*.json (default: library/survey_i18n)",
    )
    parser_survey_i18n_build.add_argument(
        "--out",
        required=True,
        help="Output folder to write compiled survey-*.json",
    )
    parser_survey_i18n_build.add_argument(
        "--lang",
        required=True,
        help="Target language code to compile (e.g., de, en)",
    )
    parser_survey_i18n_build.add_argument(
        "--fallback",
        default="de",
        help="Fallback language if a translation is missing (default: de)",
    )

    # --- Library Command ---
    parser_library = subparsers.add_parser(
        "library", help="Manage PRISM library templates"
    )
    subparsers_library = parser_library.add_subparsers(
        dest="action", help="Library actions"
    )

    parser_lib_methods = subparsers_library.add_parser(
        "generate-methods-text",
        help="Generate a scientific methods section boilerplate from library templates",
    )
    parser_lib_methods.add_argument(
        "--survey-lib", default="library/survey", help="Path to survey library"
    )
    parser_lib_methods.add_argument(
        "--biometrics-lib",
        default="library/biometrics",
        help="Path to biometrics library",
    )
    parser_lib_methods.add_argument(
        "--output", default="methods_boilerplate.md", help="Output markdown file"
    )
    parser_lib_methods.add_argument(
        "--lang", default="en", choices=["en", "de"], help="Language for the text"
    )

    # library sync
    parser_lib_sync = subparsers_library.add_parser(
        "sync", help="Synchronize keys across library files"
    )
    parser_lib_sync.add_argument(
        "--modality", choices=["survey", "biometrics"], required=True
    )
    parser_lib_sync.add_argument("--path", help="Path to library directory")

    # library catalog
    parser_lib_catalog = subparsers_library.add_parser(
        "catalog", help="Generate a CSV catalog of the survey library"
    )
    parser_lib_catalog.add_argument("--input", required=True, help="Path to library")
    parser_lib_catalog.add_argument("--output", required=True, help="Output CSV path")

    # library fill
    parser_lib_fill = subparsers_library.add_parser(
        "fill", help="Fill missing metadata keys based on schema"
    )
    parser_lib_fill.add_argument(
        "--modality", choices=["survey", "biometrics"], required=True
    )
    parser_lib_fill.add_argument(
        "--path", required=True, help="Path to file or directory"
    )
    parser_lib_fill.add_argument("--version", default="stable", help="Schema version")

    args = parser.parse_args()

    if args.command == "anonymize":
        cmd_anonymize(args)
    elif args.command == "convert" and args.modality == "physio":
        cmd_convert_physio(args)
    elif args.command == "demo" and args.action == "create":
        cmd_demo_create(args)
    elif args.command == "survey":
        if args.action == "import-excel":
            cmd_survey_import_excel(args)
        elif args.action == "convert":
            cmd_survey_convert(args)
        elif args.action == "validate":
            cmd_survey_validate(args)
        elif args.action == "import-limesurvey":
            cmd_survey_import_limesurvey(args)
        elif args.action == "import-limesurvey-batch":
            cmd_survey_import_limesurvey_batch(args)
        elif args.action == "i18n-migrate":
            cmd_survey_i18n_migrate(args)
        elif args.action == "i18n-build":
            cmd_survey_i18n_build(args)
        else:
            parser_survey.print_help()
    elif args.command == "biometrics":
        if args.action == "import-excel":
            cmd_biometrics_import_excel(args)
        else:
            parser_biometrics.print_help()
    elif args.command == "library":
        if args.action == "generate-methods-text":
            cmd_library_generate_methods_text(args)
        elif args.action == "sync":
            cmd_library_sync(args)
        elif args.action == "catalog":
            cmd_library_catalog(args)
        elif args.action == "fill":
            cmd_library_fill(args)
        else:
            parser_library.print_help()
    elif args.command == "dataset":
        if args.action == "build-biometrics-smoketest":
            cmd_dataset_build_biometrics_smoketest(args)
        else:
            parser_dataset.print_help()
    elif args.command == "recipes":
        if args.kind in {"surveys", "survey", "surves"}:
            cmd_recipes_surveys(args)
        elif args.kind in {"biometrics", "biometric"}:
            cmd_recipes_biometrics(args)
        else:
            parser_recipes.print_help()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
