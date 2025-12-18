#!/usr/bin/env python3
"""
Prism-Validator: Streamlined main entry point

A modular, BIDS-inspired validation tool for psychological research datasets.
"""

import os
import sys
import json
import argparse

# Check if running inside the venv (skip for frozen/packaged apps)
venv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv")
if not getattr(sys, "frozen", False) and not sys.prefix.startswith(venv_path):
    print(
        "❌ Error: You are not running inside the prism-validator virtual environment!"
    )
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
    from schema_manager import load_all_schemas
    from validator import DatasetValidator, MODALITY_PATTERNS
    from stats import DatasetStats
    from reporting import print_dataset_summary, print_validation_results
    from bids_integration import check_and_update_bidsignore
    from runner import validate_dataset
    from issues import tuple_to_issue, issues_to_dict, summarize_issues
    from config import load_config, merge_cli_args, find_config_file
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Prism-Validator: BIDS-inspired validation for psychological research data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/dataset
  %(prog)s /path/to/dataset --verbose
  %(prog)s /path/to/dataset --schema-version 0.1
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
        "--json",
        action="store_true",
        help="Output results as JSON (useful for CI/CD pipelines)",
    )
    parser.add_argument(
        "--json-pretty",
        action="store_true",
        help="Output results as formatted JSON",
    )
    parser.add_argument("--version", action="version", version="Prism-Validator 1.3.0")

    args = parser.parse_args()

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
        print("(Use the full prism-validator.py for detailed schema inspection)")
        return

    # Validate required arguments
    if not args.dataset:
        parser.error("Dataset path is required")

    if not os.path.exists(args.dataset):
        print(f"❌ Dataset directory not found: {args.dataset}")
        sys.exit(1)

    # Load config file from dataset (if exists)
    config = load_config(args.dataset)
    config = merge_cli_args(config, args)
    
    # Check if config file was found
    config_path = find_config_file(args.dataset)
    json_output = args.json or args.json_pretty
    
    if config_path and not json_output:
        print(f"📄 Using config: {os.path.basename(config_path)}")

    # Use config values (CLI args already merged and take precedence)
    schema_version = config.schema_version
    run_bids = config.run_bids
    
    if not json_output:
        print(f"🔍 Validating dataset: {args.dataset}")
        if schema_version != "stable":
            print(f"📋 Using schema version: {schema_version}")

    try:
        issues, stats = validate_dataset(
            args.dataset,
            verbose=args.verbose and not json_output,
            schema_version=schema_version,
            run_bids=run_bids,
        )

        # Convert legacy tuples to Issue objects for structured output
        structured_issues = [
            tuple_to_issue(issue) if isinstance(issue, tuple) else issue
            for issue in issues
        ]

        # JSON output mode
        if json_output:
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
            print(json.dumps(result, indent=indent))
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
