#!/usr/bin/env python3
import sys
import os
import re
import json
import tempfile
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

try:
    from src.biometrics_convert import convert_biometrics_table_to_prism_dataset
    from src.runner import validate_dataset
    from src.web.reporting_utils import format_validation_results
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the project root directory and the venv is activated.")
    sys.exit(1)

def parse_message(message):
    """Extract line number and evidence from error message."""
    line = None
    evidence = None
    
    line_match = re.search(r"line (\d+)", message)
    if line_match:
        line = line_match.group(1)
        
    evidence_match = re.search(r"Value '([^']+)'", message)
    if evidence_match:
        evidence = evidence_match.group(1)
    elif "Value " in message:
        ev_match = re.search(r"Value ([\d\.]+)", message)
        if ev_match:
            evidence = ev_match.group(1)
            
    return line, evidence

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/debug_biometrics_conversion.py <excel_file> [library_path]")
        sys.exit(1)

    excel_file = Path(sys.argv[1]).resolve()
    library_path = Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else project_root / "library"

    if not excel_file.exists():
        print(f"❌ Error: File not found: {excel_file}")
        sys.exit(1)

    print(f"\n🚀 Starting debug conversion for: {excel_file.name}")
    print(f"📚 Using library: {library_path}")

    tmp_dir = Path(tempfile.mkdtemp(prefix="prism_debug_"))
    output_root = tmp_dir / "prism_dataset"

    try:
        # 1. Convert
        print("🔄 Converting Excel to PRISM structure...")
        
        # Determine effective library dir
        biometrics_dir = library_path / "biometrics"
        effective_lib = biometrics_dir if biometrics_dir.is_dir() else library_path
        
        result = convert_biometrics_table_to_prism_dataset(
            input_path=excel_file,
            library_dir=effective_lib,
            output_root=output_root,
            force=True,
            unknown="warn"
        )
        print(f"✅ Conversion complete. Tasks detected: {', '.join(result.tasks_included)}")
        if result.unknown_columns:
            print(f"⚠️  Unknown columns ignored: {', '.join(result.unknown_columns)}")

        # 2. Validate
        print("🔍 Running PRISM validation...")
        issues, stats = validate_dataset(str(output_root), schema_version="stable")
        
        # 3. Report
        formatted = format_validation_results(issues, stats, str(output_root))
        
        error_groups = formatted.get("error_groups", {})
        warning_groups = formatted.get("warning_groups", {})

        print(f"\n📊 Validation Summary: {len(issues)} issues found.")
        
        if error_groups:
            print("\n" + "="*60)
            print("❌ ERRORS")
            print("="*60)
            for code, group in error_groups.items():
                print(f"\n[{code}] {group['description'] or group['message']}")
                # Group by file to avoid repetition
                file_to_issues = {}
                for f in group['files']:
                    fname = f['file']
                    if fname not in file_to_issues:
                        file_to_issues[fname] = []
                    file_to_issues[fname].append(f)
                
                for fname, f_issues in file_to_issues.items():
                    print(f"  📄 {fname}:")
                    for issue in f_issues:
                        line, evidence = parse_message(issue['message'])
                        line_str = f"Line {line}: " if line else ""
                        ev_str = f" [Value: {evidence}]" if evidence else ""
                        # Strip the filename and line from the message for cleaner output
                        clean_msg = issue['message']
                        if ":" in clean_msg:
                            clean_msg = clean_msg.split(":", 1)[-1].strip()
                        
                        print(f"    - {line_str}{clean_msg}{ev_str}")

        if warning_groups:
            print("\n" + "="*60)
            print("⚠️  WARNINGS")
            print("="*60)
            for code, group in warning_groups.items():
                print(f"\n[{code}] {group['description'] or group['message']}")
                for f in group['files']:
                    print(f"  - {f['file']}: {f['message']}")

        if not error_groups and not warning_groups:
            print("\n✅ No issues found! Dataset is valid.")

    except Exception as e:
        print(f"\n❌ Error during process: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if error_groups:
            print(f"\n📂 Debug dataset kept for inspection at: {output_root}")
        else:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            print(f"\n🧹 Temporary files cleaned up.")

if __name__ == "__main__":
    main()
