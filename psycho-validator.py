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
    # Import core modules from src
    from schema_manager import load_all_schemas
    from validator import DatasetValidator, MODALITY_PATTERNS
    from stats import DatasetStats
    from reporting import print_dataset_summary, print_validation_results
    # Use refactored runner for the canonical validate_dataset
    from src.runner import validate_dataset
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory")
    sys.exit(1)


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