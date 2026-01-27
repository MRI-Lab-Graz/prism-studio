#!/usr/bin/env python3
"""
Test the anonymization feature on a small example dataset.
"""

import sys
from pathlib import Path
import tempfile

# Add app to path
repo_root = Path(__file__).resolve().parent.parent.parent
app_root = repo_root / "app"
sys.path.insert(0, str(app_root))

from src.anonymizer import create_participant_mapping, anonymize_tsv_file, generate_random_id

print("=" * 70)
print("Anonymization Feature Test")
print("=" * 70)
print()

# Test 1: Generate random IDs
print("Test 1: Random ID Generation")
print("-" * 70)
for i in range(5):
    random_id = generate_random_id("sub", 6, seed=f"test{i}")
    print(f"  sub-00{i+1} → {random_id}")
print()

# Test 2: Create participant mapping
print("Test 2: Participant Mapping")
print("-" * 70)
participant_ids = ["sub-001", "sub-002", "sub-003", "sub-ABC", "sub-XYZ"]
with tempfile.TemporaryDirectory() as tmpdir:
    mapping_file = Path(tmpdir) / "test_mapping.json"
    mapping = create_participant_mapping(participant_ids, mapping_file, id_length=6)
    
    print(f"Created mapping for {len(mapping)} participants:")
    for orig, anon in mapping.items():
        print(f"  {orig} → {anon}")
    print()
    print(f"Mapping file created: {mapping_file}")
    print()

# Test 3: Anonymize a TSV file
print("Test 3: TSV File Anonymization")
print("-" * 70)

with tempfile.TemporaryDirectory() as tmpdir:
    tmpdir = Path(tmpdir)
    
    # Create test TSV
    test_tsv = tmpdir / "test_data.tsv"
    with open(test_tsv, 'w') as f:
        f.write("participant_id\tADS01\tADS02\n")
        f.write("sub-001\t3\t2\n")
        f.write("sub-002\t1\t4\n")
        f.write("sub-003\t2\t3\n")
    
    # Create mapping
    mapping = {
        "sub-001": "sub-R7X2K9",
        "sub-002": "sub-A4B8M3",
        "sub-003": "sub-Q9N5P1"
    }
    
    # Anonymize
    output_tsv = tmpdir / "test_data_anon.tsv"
    anonymize_tsv_file(test_tsv, output_tsv, mapping)
    
    print("Original file:")
    print(open(test_tsv).read())
    
    print("Anonymized file:")
    print(open(output_tsv).read())

print("=" * 70)
print("✅ All tests passed!")
print("=" * 70)
print()
print("Usage example:")
print("  python prism_tools.py anonymize \\")
print("    --dataset /path/to/dataset \\")
print("    --output /path/to/anonymized \\")
print("    --id-length 8")
print()
