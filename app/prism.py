#!/usr/bin/env python3
"""
PRISM: Streamlined main entry point

A modular, BIDS-inspired validation tool for psychological research datasets.
"""

import os
import sys
import json
import argparse


def _is_help_mode(argv: list[str]) -> bool:
    """Allow running without venv when only asking for help/version."""
    help_flags = {"-h", "--help", "--version", "-V"}
    return any(arg in help_flags for arg in argv[1:])


# Check if running inside the venv (skip for frozen/packaged apps, CI, or explicit skip)
# Since this script moved to app/, venv is one level up
current_dir = os.path.dirname(os.path.abspath(__file__))
venv_path = os.path.join(os.path.dirname(current_dir), ".venv")
if (
    not getattr(sys, "frozen", False)
    and not os.environ.get("PRISM_SKIP_VENV_CHECK")
    and not os.environ.get("CI")
    and not sys.prefix.startswith(venv_path)
):
    if _is_help_mode(sys.argv):
        print("Warning: prism venv is not active; continuing to show help output.")
    else:
        print("❌ Error: You are not running inside the prism virtual environment!")
        print("   Please activate the venv first:")
        if os.name == "nt":  # Windows
            print(f"     {venv_path}\\Scripts\\activate")
        else:  # Unix/Mac
            print(f"     source {venv_path}/bin/activate")
        print("   Then run this script again.")
        sys.exit(1)

# Add src directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, "src")
sys.path.insert(0, src_path)

try:
    from src import __version__ as prism_validator_version
    from reporting import print_dataset_summary, print_validation_results
    from core.validation import (
        validate_dataset,
        normalize_issues,
        determine_exit_code,
        build_validation_report,
    )
    from config import load_config, merge_cli_args, find_config_file
    from fixer import DatasetFixer, get_fixable_issues
    from formatters import format_output
    from plugins import (
        PluginManager,
        create_context,
        generate_plugin_template,
        list_plugins,
    )
    from template_validator import validate_templates
    from environment.builder import build_environment_tsv
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def _cli_merge_versions(argv: list[str]) -> None:
    """Handle 'prism merge-versions' subcommand for merging survey template versions."""
    import argparse as _ap
    p = _ap.ArgumentParser(
        prog="prism merge-versions",
        description=(
            "Merge a new version of a survey instrument into an existing template.\n\n"
            "Use this when you have two versions of the same questionnaire (e.g., short/long, "
            "Likert/VAS) and want to create a single multi-variant template that PRISM tools "
            "can use for version-aware validation and recipe scoring."
        ),
        formatter_class=_ap.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Merge a long form Excel into an existing short-form template (auto-detects version names)
  prism merge-versions survey-bdi.json bdi_long.xlsx

  # Explicitly name both versions
  prism merge-versions survey-bdi.json bdi_long.json --new-version long --existing-version short

  # Preview without saving
  prism merge-versions survey-bdi.json bdi_long.xlsx --dry-run
        """,
    )
    p.add_argument("template", help="Path to the existing survey template JSON file")
    p.add_argument(
        "new_items",
        help="Path to the new version: either a survey template JSON or an Excel (.xlsx) file",
    )
    p.add_argument(
        "--new-version",
        metavar="NAME",
        help="Version name for the items being merged in (auto-detected if omitted)",
    )
    p.add_argument(
        "--existing-version",
        metavar="NAME",
        help="Version name for the existing template items (auto-detected if omitted)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the merge result without writing changes to disk",
    )
    p.add_argument(
        "--output",
        metavar="PATH",
        help="Write the merged template to this path instead of overwriting the original",
    )

    args = p.parse_args(argv)

    template_path = os.path.abspath(args.template)
    new_items_path = os.path.abspath(args.new_items)

    if not os.path.exists(template_path):
        print(f"❌ Template not found: {template_path}")
        sys.exit(1)
    if not os.path.exists(new_items_path):
        print(f"❌ New items file not found: {new_items_path}")
        sys.exit(1)

    try:
        from src.converters.version_merger import (
            merge_survey_versions,
            save_merged_template,
            detect_version_name_from_import,
        )
    except ImportError as e:
        print(f"❌ Could not import version merger: {e}")
        sys.exit(1)

    # Load new items from JSON or Excel
    ext = os.path.splitext(new_items_path)[1].lower()
    if ext in (".xlsx", ".xls"):
        try:
            from src.converters.excel_to_survey import _extract_items_from_excel
            new_items = _extract_items_from_excel(new_items_path)
        except Exception as e:
            print(f"❌ Failed to read Excel file: {e}")
            sys.exit(1)
    elif ext == ".json":
        try:
            with open(new_items_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            _NON_ITEM_KEYS = {"Technical", "Study", "Metadata", "Normative", "Scoring", "I18n"}
            new_items = {k: v for k, v in raw.items() if k not in _NON_ITEM_KEYS and isinstance(v, dict)}
        except Exception as e:
            print(f"❌ Failed to read JSON file: {e}")
            sys.exit(1)
    else:
        print(f"❌ Unsupported file format: {ext} (expected .json or .xlsx)")
        sys.exit(1)

    if not new_items:
        print("❌ No items found in the new items file.")
        sys.exit(1)

    # Auto-detect version names if not provided
    new_version = args.new_version
    existing_version = args.existing_version
    if not new_version or not existing_version:
        from pathlib import Path as _Path
        suggested_new, suggested_existing = detect_version_name_from_import(
            new_items, _Path(template_path)
        )
        if not new_version:
            new_version = suggested_new
            print(f"  Auto-detected new version name: '{new_version}'")
        if not existing_version:
            existing_version = suggested_existing
            print(f"  Auto-detected existing version name: '{existing_version}'")

    print(f"\n🔀 Merging '{existing_version}' + '{new_version}'")
    print(f"  Template : {template_path}")
    print(f"  New items: {new_items_path} ({len(new_items)} items)")

    from pathlib import Path as _Path
    merged = merge_survey_versions(
        existing_template_path=_Path(template_path),
        new_items=new_items,
        new_version_name=new_version,
        existing_version_name=existing_version,
    )

    if args.dry_run:
        print("\n📋 Dry run — merged template preview (Study section):")
        print(json.dumps(merged.get("Study", {}), indent=2, ensure_ascii=False))
        print("\n(No files were written. Remove --dry-run to apply.)")
        return

    output_path = _Path(args.output) if args.output else _Path(template_path)
    save_merged_template(merged, output_path)
    print(f"\n✅ Merged template saved to: {output_path}")
    versions = merged.get("Study", {}).get("Versions", [])
    print(f"   Versions: {versions}")


def main():  # noqa: C901
    """Main CLI entry point"""
    if len(sys.argv) > 1 and sys.argv[1] == "wide-to-long":
        from src.cli.entrypoint import main as prism_tools_main

        prism_tools_main()
        return

    if len(sys.argv) > 1 and sys.argv[1] == "merge-versions":
        _cli_merge_versions(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(
        description="PRISM: BIDS-inspired validation for psychological research data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/dataset
  %(prog)s /path/to/dataset --verbose
  %(prog)s /path/to/dataset --schema-version 0.1
  %(prog)s /path/to/dataset --fix
  %(prog)s /path/to/dataset --fix --dry-run
    %(prog)s wide-to-long --input survey.xlsx --session-indicators T1_,T2_,T3_ --inspect-only
  %(prog)s --schema-info image
  %(prog)s --validate-templates /path/to/library/survey
    %(prog)s --build-environment --scans-tsv /path/sub-01_scans.tsv --environment-tsv /path/sub-01_environment.tsv --lat 47.07 --lon 15.44
  %(prog)s merge-versions survey-bdi.json bdi_long.xlsx --new-version long --existing-version short
        """,
    )

    parser.add_argument("dataset", nargs="?", help="Path to dataset root directory")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show detailed validation information",
    )
    parser.add_argument(
        "--schema-version",
        metavar="VERSION",
        help="Schema version to use (e.g., 'stable', '0.1'). Default: stable",
    )
    parser.add_argument(
        "--schema-info",
        metavar="MODALITY",
        help="Display schema details for a specific modality",
    )
    parser.add_argument(
        "--list-versions", action="store_true", help="List available schema versions"
    )
    parser.add_argument(
        "--bids",
        action="store_true",
        help="Run the standard BIDS validator in addition to PRISM validation",
    )
    parser.add_argument(
        "--bids-warnings",
        action="store_true",
        help="Show warnings from the BIDS validator (default: hidden)",
    )
    parser.add_argument(
        "--library",
        metavar="PATH",
        help="Path to a template library for sidecar resolution",
    )
    parser.add_argument(
        "--no-prism",
        action="store_true",
        help="Skip PRISM-specific validation (only run BIDS validator if --bids is set)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON (useful for CI/CD pipelines)",
    )
    parser.add_argument(
        "--json-pretty",
        action="store_true",
        help="Output results as formatted JSON",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Automatically fix common issues (missing sidecars, .bidsignore, etc.)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what --fix would do without making changes",
    )
    parser.add_argument(
        "--list-fixes",
        action="store_true",
        help="List all auto-fixable issue types",
    )
    parser.add_argument(
        "--format",
        metavar="FORMAT",
        choices=["json", "sarif", "junit", "markdown", "csv"],
        help="Output format: json, sarif, junit, markdown, csv",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="FILE",
        help="Write output to file instead of stdout",
    )
    parser.add_argument(
        "--init-plugin",
        metavar="NAME",
        help="Generate a plugin template in <dataset>/validators/<NAME>.py",
    )
    parser.add_argument(
        "--list-plugins",
        action="store_true",
        help="List loaded plugins for the dataset",
    )
    parser.add_argument(
        "--no-plugins",
        action="store_true",
        help="Disable plugin loading",
    )
    parser.add_argument(
        "--validate-templates",
        metavar="PATH",
        help="Validate survey/biometrics templates in a library directory",
    )
    parser.add_argument(
        "--build-environment",
        action="store_true",
        help="Build *_environment.tsv from scans.tsv and privacy-safe temporal anchors",
    )
    parser.add_argument(
        "--scans-tsv",
        metavar="PATH",
        help="Input scans TSV containing filename and prism_time_anchor",
    )
    parser.add_argument(
        "--environment-tsv",
        metavar="PATH",
        help="Output *_environment.tsv path",
    )
    parser.add_argument(
        "--lat",
        type=float,
        help="Site latitude for environment enrichment",
    )
    parser.add_argument(
        "--lon",
        type=float,
        help="Site longitude for environment enrichment",
    )
    parser.add_argument(
        "--environment-providers",
        nargs="*",
        default=["weather", "pollen", "air_quality"],
        help="Environment providers to enable: weather pollen air_quality",
    )
    parser.add_argument(
        "--environment-cache",
        metavar="PATH",
        default=".prism/environment_cache.json",
        help="Cache path for environment provider results",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"prism-validator {prism_validator_version}",
    )

    args = parser.parse_args()

    # Handle environment builder mode
    if args.build_environment:
        required_flags = {
            "--scans-tsv": args.scans_tsv,
            "--environment-tsv": args.environment_tsv,
            "--lat": args.lat,
            "--lon": args.lon,
        }
        missing = [flag for flag, value in required_flags.items() if value is None]
        if missing:
            parser.error(
                "Missing required arguments for --build-environment: "
                + ", ".join(missing)
            )

        if not os.path.exists(args.scans_tsv):
            print(f"❌ scans TSV not found: {args.scans_tsv}")
            sys.exit(1)

        try:
            output_path = build_environment_tsv(
                scans_tsv=args.scans_tsv,
                output_tsv=args.environment_tsv,
                lat=args.lat,
                lon=args.lon,
                enabled_providers=args.environment_providers,
                cache_path=args.environment_cache,
            )
            print(f"✅ Environment TSV created: {output_path}")
            sys.exit(0)
        except Exception as e:
            print(f"❌ Environment build failed: {e}")
            if args.verbose:
                import traceback

                traceback.print_exc()
            sys.exit(2)

    # Handle template validation request
    if args.validate_templates:
        library_path = args.validate_templates
        if not os.path.exists(library_path):
            print(f"❌ Library directory not found: {library_path}")
            sys.exit(1)

        errors, summary = validate_templates(library_path, verbose=True)

        # Exit with error code if there are errors (not just warnings)
        error_count = sum(1 for e in errors if e.severity == "error")
        sys.exit(1 if error_count > 0 else 0)

    # Handle list fixes request
    if args.list_fixes:
        print("Auto-fixable issues:")
        print("=" * 50)
        for code, description in get_fixable_issues().items():
            print(f"  {code}: {description}")
        print("\nUse --fix to apply fixes, --dry-run to preview.")
        return

    # Handle list versions request
    if args.list_versions:
        schema_dir = os.path.join(os.path.dirname(__file__), "schemas")
        from schema_manager import get_available_schema_versions

        versions = get_available_schema_versions(schema_dir)
        print("Available schema versions:")
        for v in versions:
            default_marker = " (default)" if v == "stable" else ""
            print(f"  • {v}{default_marker}")
        return

    # Handle schema info request
    if args.schema_info:
        # Import and show schema info (simplified for this streamlined version)
        print(f"Schema information for modality: {args.schema_info}")
        print("(Use the full prism.py for detailed schema inspection)")
        return

    # Validate required arguments for operations that need dataset path
    if not args.dataset and (args.init_plugin or args.list_plugins):
        parser.error("Dataset path is required for this operation")

    # Handle plugin template generation
    if args.init_plugin:
        if not args.dataset:
            parser.error("Dataset path required with --init-plugin")

        plugin_name = args.init_plugin.replace(".py", "")
        plugin_path = os.path.join(args.dataset, "validators", f"{plugin_name}.py")

        if os.path.exists(plugin_path):
            print(f"❌ Plugin already exists: {plugin_path}")
            sys.exit(1)

        generate_plugin_template(
            plugin_path,
            name=plugin_name,
            description=f"Custom validator: {plugin_name}",
        )
        print(f"✅ Created plugin template: {plugin_path}")
        print("   Edit the validate() function to add your checks.")
        return

    # Handle list plugins request
    if args.list_plugins:
        if not args.dataset:
            parser.error("Dataset path required with --list-plugins")

        config = load_config(args.dataset)
        manager = PluginManager(args.dataset)
        manager.load_from_config(config.__dict__)
        manager.discover_local_plugins()
        list_plugins(manager)
        return

    # Validate required arguments
    if not args.dataset:
        parser.error("Dataset path is required")

    if not os.path.exists(args.dataset):
        print(f"❌ Dataset directory not found: {args.dataset}")
        sys.exit(1)

    # Handle --fix mode
    if args.fix or args.dry_run:
        fixer = DatasetFixer(args.dataset, dry_run=args.dry_run)
        fixes = fixer.analyze()

        if not fixes:
            print("✅ No auto-fixable issues found!")
            sys.exit(0)

        print(f"🔧 Found {len(fixes)} fixable issue(s):")
        print("=" * 60)

        for i, fix in enumerate(fixes, 1):
            optional = " (optional)" if fix.details.get("optional") else ""
            print(f"  {i}. [{fix.issue_code}] {fix.description}{optional}")
            print(f"     Action: {fix.action_type} → {os.path.basename(fix.file_path)}")

        print("=" * 60)

        if args.dry_run:
            print("🔍 Dry run - no changes made.")
            print("   Run with --fix to apply these changes.")
        else:
            # Apply fixes (skip optional ones unless they're the only ones)
            non_optional = [f for f in fixes if not f.details.get("optional")]
            to_apply = non_optional if non_optional else fixes

            applied = fixer.apply_fixes([f.issue_code for f in to_apply])
            print(f"\n✅ Applied {len(applied)} fix(es):")
            for fix in applied:
                print(f"   • {fix.description}")

            print("\n💡 Re-run validation to check for remaining issues.")

        sys.exit(0)

    # Load config file from dataset (if exists)
    config = load_config(args.dataset)
    config = merge_cli_args(config, args)

    # Check if config file was found
    config_path = find_config_file(args.dataset)
    json_output = args.json or args.json_pretty
    format_output_mode = args.format is not None
    machine_output = json_output or format_output_mode

    if config_path and not machine_output:
        print(f"📄 Using config: {os.path.basename(config_path)}")

    # Load plugins (unless disabled)
    plugin_manager = None
    if not args.no_plugins:
        plugin_manager = PluginManager(args.dataset)
        plugin_manager.load_from_config(config.__dict__)
        plugin_manager.discover_local_plugins()

        if plugin_manager.plugins and not machine_output:
            print(f"🔌 Loaded {len(plugin_manager.plugins)} plugin(s)")

    # Use config values (CLI args already merged and take precedence)
    schema_version = config.schema_version
    run_bids = config.run_bids

    if not machine_output:
        print(f"🔍 Validating dataset: {args.dataset}")
        if schema_version != "stable":
            print(f"📋 Using schema version: {schema_version}")

    try:
        issues, stats = validate_dataset(
            args.dataset,
            verbose=args.verbose and not machine_output,
            schema_version=schema_version,
            run_bids=run_bids,
            run_prism=not args.no_prism,
            library_path=args.library,
        )

        # Convert legacy tuples to Issue objects for structured output
        structured_issues = normalize_issues(issues)

        # Run plugins
        if plugin_manager and plugin_manager.plugins:
            if not machine_output:
                print(f"🔌 Running {len(plugin_manager.plugins)} plugin(s)...")

            plugin_context = create_context(
                args.dataset,
                stats,
                schema_version=schema_version,
                config=config.__dict__,
                verbose=args.verbose,
            )

            plugin_issues = plugin_manager.run_all(plugin_context)
            structured_issues.extend(plugin_issues)

            if plugin_issues and not machine_output:
                print(f"   Found {len(plugin_issues)} issue(s) from plugins")

        # Helper to write output (to file or stdout)
        def write_output(content: str):
            if args.output:
                with open(args.output, "w") as f:
                    f.write(content)
                if not machine_output:
                    print(f"📄 Output written to: {args.output}")
            else:
                print(content)

        # Format-specific output modes
        if args.format:
            output = format_output(
                issues=structured_issues,
                dataset_path=os.path.abspath(args.dataset),
                format_name=args.format,
                stats=stats,
            )
            write_output(output)
        elif json_output:
            # Legacy JSON output mode
            result = build_validation_report(
                dataset_path=args.dataset,
                schema_version=schema_version,
                structured_issues=structured_issues,
                stats=stats,
            )
            indent = 2 if args.json_pretty else None
            write_output(json.dumps(result, indent=indent))
        else:
            # Standard human-readable output
            print_dataset_summary(args.dataset, stats)
            print_validation_results(issues, show_bids_warnings=args.bids_warnings)

        # Exit with appropriate code
        sys.exit(determine_exit_code(structured_issues))

    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
