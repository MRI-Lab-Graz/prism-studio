#!/usr/bin/env python3
"""
Psycho-Validator: Streamlined main entry point

A modular, BIDS-inspired validation tool for psychological research datasets.
"""

import os
import sys
import argparse

# Add src directory to path for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(current_dir, 'src')
sys.path.insert(0, src_path)

try:
    from schema_manager import load_all_schemas
    from validator import DatasetValidator, MODALITY_PATTERNS
    from stats import DatasetStats
    from reporting import print_dataset_summary, print_validation_results
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


def validate_dataset(root_dir, verbose=False):
    """Main dataset validation function"""
    issues = []
    stats = DatasetStats()
    
    # Load schemas
    schema_dir = os.path.join(os.path.dirname(__file__), 'schemas')
    schemas = load_all_schemas(schema_dir)
    
    if verbose:
        print(f"📋 Loaded {len(schemas)} schemas")
        print(f"📁 Scanning modalities: {list(MODALITY_PATTERNS.keys())}")
    
    # Initialize validator
    validator = DatasetValidator(schemas)
    
    # Check for dataset description
    dataset_desc_path = os.path.join(root_dir, "dataset_description.json")
    if not os.path.exists(dataset_desc_path):
        issues.append(("ERROR", "Missing dataset_description.json"))
    
    # Walk through subject directories
    for item in os.listdir(root_dir):
        item_path = os.path.join(root_dir, item)
        if os.path.isdir(item_path) and item.startswith("sub-"):
            subject_issues = validate_subject(item_path, item, validator, stats, root_dir)
            issues.extend(subject_issues)
    
    # Check cross-subject consistency
    consistency_warnings = stats.check_consistency()
    issues.extend(consistency_warnings)
    
    return issues, stats


def validate_subject(subject_dir, subject_id, validator, stats, root_dir):
    """Validate a single subject directory"""
    issues = []
    
    for item in os.listdir(subject_dir):
        item_path = os.path.join(subject_dir, item)
        if os.path.isdir(item_path):
            if item.startswith("ses-"):
                # Session directory
                issues.extend(validate_session(item_path, subject_id, item, validator, stats, root_dir))
            elif item in MODALITY_PATTERNS:
                # Direct modality directory
                issues.extend(validate_modality_dir(item_path, subject_id, None, item, validator, stats, root_dir))
    
    return issues


def validate_session(session_dir, subject_id, session_id, validator, stats, root_dir):
    """Validate a single session directory"""
    issues = []
    
    for item in os.listdir(session_dir):
        item_path = os.path.join(session_dir, item)
        if os.path.isdir(item_path) and item in MODALITY_PATTERNS:
            issues.extend(validate_modality_dir(item_path, subject_id, session_id, item, validator, stats, root_dir))
    
    return issues


def validate_modality_dir(modality_dir, subject_id, session_id, modality, validator, stats, root_dir):
    """Validate files in a modality directory"""
    issues = []
    
    for fname in os.listdir(modality_dir):
        file_path = os.path.join(modality_dir, fname)
        if os.path.isfile(file_path):
            # Extract task from filename
            task = None
            if "_task-" in fname:
                import re
                task_match = re.search(r'_task-([A-Za-z0-9]+)(?:_|$)', fname)
                if task_match:
                    task = task_match.group(1)
            
            # Add to stats
            stats.add_file(subject_id, session_id, modality, task, fname)
            
            # Validate filename
            filename_issues = validator.validate_filename(fname, modality)
            issues.extend(filename_issues)
            
            # Validate sidecar if not JSON file itself
            if not fname.endswith('.json'):
                sidecar_issues = validator.validate_sidecar(file_path, modality, root_dir)
                issues.extend(sidecar_issues)
    
    return issues


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Psycho-Validator: BIDS-inspired validation for psychological research data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/dataset
  %(prog)s /path/to/dataset --verbose
  %(prog)s --schema-info image
        """
    )
    
    parser.add_argument("dataset", nargs='?', help="Path to dataset root directory")
    parser.add_argument("-v", "--verbose", action="store_true", 
                       help="Show detailed validation information")
    parser.add_argument("--schema-info", metavar="MODALITY",
                       help="Display schema details for a specific modality")
    parser.add_argument("--version", action="version", version="Psycho-Validator 1.3.0")
    
    args = parser.parse_args()
    
    # Handle schema info request
    if args.schema_info:
        # Import and show schema info (simplified for this streamlined version)
        print(f"Schema information for modality: {args.schema_info}")
        print("(Use the full psycho-validator.py for detailed schema inspection)")
        return
    
    # Validate required arguments
    if not args.dataset:
        parser.error("Dataset path is required")
    
    if not os.path.exists(args.dataset):
        print(f"❌ Dataset directory not found: {args.dataset}")
        sys.exit(1)
    
    # Run validation
    print(f"🔍 Validating dataset: {args.dataset}")
    
    try:
        issues, stats = validate_dataset(args.dataset, verbose=args.verbose)
        
        # Print results
        print_dataset_summary(args.dataset, stats)
        print_validation_results(issues)
        
        # Exit with appropriate code
        error_count = sum(1 for level, _ in issues if level == "ERROR")
        sys.exit(1 if error_count > 0 else 0)
        
    except Exception as e:
        print(f"❌ Validation failed with error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()