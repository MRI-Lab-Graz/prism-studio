#!/usr/bin/env python3
"""
Comprehensive demonstration of psycho-validator features
"""

import os
import subprocess
import sys

def run_validator_demo():
    """Demonstrate the validator on different dataset types"""
    
    print("🧪 PSYCHO-VALIDATOR DEMONSTRATION")
    print("=" * 60)
    
    datasets = [
        ("✅ Consistent Dataset", "consistent_test_dataset"),
        ("⚠️  Dataset with Warnings", "valid_test_dataset"), 
        ("❌ Dataset with Errors", "test_dataset"),
    ]
    
    for title, dataset_path in datasets:
        if not os.path.exists(dataset_path):
            print(f"\n{title}: Dataset not found - {dataset_path}")
            continue
            
        print(f"\n{title}")
        print("-" * 40)
        
        try:
            result = subprocess.run([
                sys.executable, "psycho-validator.py", dataset_path
            ], capture_output=True, text=True, cwd=os.path.dirname(os.path.abspath(__file__)))
            
            print(f"Exit Code: {result.returncode}")
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print("STDERR:", result.stderr)
                
        except Exception as e:
            print(f"Error running validator: {e}")
        
        print("\n" + "=" * 60)

def main():
    print("This script demonstrates the psycho-validator on three different datasets:")
    print("1. A perfectly consistent dataset (no issues)")
    print("2. A dataset with consistency warnings")
    print("3. A dataset with validation errors")
    print()
    
    response = input("Continue with demonstration? (y/n): ")
    if response.lower().startswith('y'):
        run_validator_demo()
    else:
        print("Demo cancelled.")

if __name__ == "__main__":
    main()
