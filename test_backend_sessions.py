#!/usr/bin/env python3

from pathlib import Path
from src.converters.survey import convert_survey_xlsx_to_prism_dataset
import tempfile

# Create test paths
test_input = Path("examples/workshop/exercise_2_hunting_errors/bad_examples/mystery_example_06.tsv")
effective_library = Path("survey_library/stable")

# Create temp output
with tempfile.TemporaryDirectory() as tmpdir:
    output_root = Path(tmpdir)
    
    print(f"Input file: {test_input}")
    print(f"Library: {effective_library}")
    print(f"Output root: {output_root}")
    print()
    
    try:
        result = convert_survey_xlsx_to_prism_dataset(
            input_path=test_input,
            library_dir=str(effective_library),
            output_root=output_root,
            dry_run=True,  # Preview mode
            force=True,
            name="preview",
            authors=["test"],
            survey=None,
            id_column=None,  # Let it auto-detect
            session_column=None,  # Let it auto-detect
            session=None,  # No session override
            sheet=0,
            unknown="warn",
            language=None,
            alias_file=None,
            id_map_file=None,
            duplicate_handling="error",
        )
        
        print(f"Result type: {type(result).__name__}")
        print(f"Detected sessions: {result.detected_sessions}")
        print(f"Session column: {result.session_column}")
        print(f"ID column: {result.id_column}")
        print(f"Tasks included: {result.tasks_included}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
