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


_APP_ROOT = Path(__file__).resolve().parents[3]


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

    if hasattr(args, "library") and args.library:
        candidate = Path(args.library)
        if _library_needs_i18n_compile(candidate):
            lib_dir, library_tmp = _compile_i18n_library(candidate, lang=lang)
            library_label = f"{candidate.resolve()} (i18n compiled to {lang})"
        else:
            lib_dir = candidate
            library_label = str(candidate.resolve())
    else:
        compiled_candidate = _APP_ROOT / f"library/survey_{lang}"
        i18n_candidate = _APP_ROOT / "library/survey_i18n"
        legacy_candidate = _APP_ROOT / "library/survey"

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

            print("\n📊 SUMMARY")
            print(
                f"   Total participants in file: {preview['summary']['total_participants']}"
            )
            print(
                f"   Unique participants: {preview['summary']['unique_participants']}"
            )
            print(f"   Tasks detected: {', '.join(preview['summary']['tasks'])}")
            print(f"   Total files to create: {preview['summary']['total_files']}")

            if preview["data_issues"]:
                print(f"\n⚠️  DATA ISSUES FOUND ({len(preview['data_issues'])})")
                print(
                    "   These issues should be fixed in your input data BEFORE conversion:\n"
                )

                for issue in preview["data_issues"][:10]:
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

            if "participants_tsv" in preview and preview.get("participants_tsv"):
                print("\n📝 PARTICIPANTS.TSV PREVIEW")
                print("   This file will be created with the following structure:\n")

                tsv_preview = preview["participants_tsv"]
                columns = tsv_preview["columns"]
                sample_rows = tsv_preview["sample_rows"]
                total_rows = tsv_preview["total_rows"]

                print(f"   Columns ({len(columns)} total):")
                for col in columns:
                    print(f"     • {col}")

                if tsv_preview["mappings"]:
                    print("\n   Column Mappings:")
                    for output_col, mapping_info in tsv_preview["mappings"].items():
                        source_col = mapping_info["source_column"]
                        has_mapping = mapping_info.get("has_value_mapping", False)
                        indicator = "🔄" if has_mapping else "✓"
                        print(f"     {indicator} {output_col} ← {source_col}")
                        if has_mapping and mapping_info.get("value_mapping"):
                            print("        (has value transformation mapping)")

                print(
                    f"\n   Sample Data (showing first {min(5, len(sample_rows))} of {total_rows} participants):"
                )
                print(f"   {'-' * 100}")

                header = " | ".join(f"{col:<20}" for col in columns)
                print(f"   {header}")
                print(f"   {'-' * 100}")

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

                if tsv_preview["notes"]:
                    print("\n   📌 Notes:")
                    for note in tsv_preview["notes"]:
                        print(f"     • {note}")

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

                    for item in unused_cols[:10]:
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

                    if len(unused_cols) > 10:
                        print(f"      ... and {len(unused_cols) - 10} more columns")

                print()

            print("\n👥 PARTICIPANT SURVEY COMPLETENESS (first 10)")
            for p in preview["participants"][:10]:
                completeness = p["completeness_percent"]
                status = "✓" if completeness > 80 else ("⚠" if completeness > 50 else "✗")
                print(f"   {status} {p['participant_id']} ({p['session_id']})")
                print(f"      Raw ID: {p['raw_id']}")
                print(
                    f"      Completeness: {completeness}% ({p['total_items'] - p['missing_values']}/{p['total_items']} items)"
                )

            if len(preview["participants"]) > 10:
                print(f"   ... and {len(preview['participants']) - 10} more participants")

            print("\n📋 COLUMN MAPPING (first 15)")
            for col, info in list(preview["column_mapping"].items())[:15]:
                run_info = f" (run {info['run']})" if info["run"] else ""
                status = "⚠" if info.get("has_unexpected_values") else "✓"
                print(f"   {status} {col}")
                print(f"      → Task: {info['task']}{run_info}, Item: {info['base_item']}")
                print(
                    f"      → Missing: {info['missing_percent']}% ({info['missing_count']} values)"
                )
                if info.get("has_unexpected_values"):
                    print("      ⚠  Has unexpected values!")

            if len(preview["column_mapping"]) > 15:
                print(f"   ... and {len(preview['column_mapping']) - 15} more columns")

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
