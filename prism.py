#!/usr/bin/env python3
"""
PRISM: Streamlined main entry point

A modular, BIDS-inspired validation tool for psychological research datasets.
"""

import os
import sys
import json
import argparse

# Check if running inside the venv (skip for frozen/packaged apps)
venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
if not getattr(sys, "frozen", False) and not sys.prefix.startswith(venv_path):
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
    from reporting import print_dataset_summary, print_validation_results
    from runner import validate_dataset
    from issues import tuple_to_issue, issues_to_dict, summarize_issues
    from config import load_config, merge_cli_args, find_config_file
    from fixer import DatasetFixer, get_fixable_issues
    from formatters import format_output
    from plugins import (
        PluginManager,
        create_context,
        generate_plugin_template,
        list_plugins,
    )
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def main():
    """Main CLI entry point"""
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
  %(prog)s --schema-info image
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
        "--version", action="version", version="PRISM 1.7.1"
    )

    args = parser.parse_args()

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
        structured_issues = [
            tuple_to_issue(issue) if isinstance(issue, tuple) else issue
            for issue in issues
        ]

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
            result = {
                "dataset": os.path.abspath(args.dataset),
                "schema_version": schema_version,
                "valid": all(i.severity.value != "ERROR" for i in structured_issues),
                "summary": summarize_issues(structured_issues),
                "issues": issues_to_dict(structured_issues),
                "statistics": {
                    "total_files": stats.total_files,
                    "subjects": list(stats.subjects),
                    "sessions": list(stats.sessions),
                    "tasks": list(stats.tasks),
                    "modalities": dict(stats.modalities),
                },
            }
            indent = 2 if args.json_pretty else None
            write_output(json.dumps(result, indent=indent))
        else:
            # Standard human-readable output
            print_dataset_summary(args.dataset, stats)
            print_validation_results(issues, show_bids_warnings=args.bids_warnings)

        # Exit with appropriate code
        error_count = sum(1 for i in structured_issues if i.severity.value == "ERROR")
        sys.exit(1 if error_count > 0 else 0)

    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
