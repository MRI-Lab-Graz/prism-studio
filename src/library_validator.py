import os
import json
from collections import defaultdict
from pathlib import Path

class LibraryValidator:
    def __init__(self, library_path):
        self.library_path = Path(library_path)
        self.IGNORE_KEYS = {"Technical", "Study", "Metadata", "Questions"}

    def get_all_library_variables(self, exclude_file=None):
        """
        Returns a map of variable -> list of filenames for the entire library,
        optionally excluding a specific filename (useful when checking a draft against others).
        """
        var_map = defaultdict(list)
        
        if not self.library_path.exists():
            return var_map

        files = [
            f for f in self.library_path.glob("*.json")
            if f.name.startswith("survey-") and f.name != exclude_file
        ]

        for file_path in files:
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                
                # Handle both flat structure and nested "Questions" structure
                variables = []
                if "Questions" in data and isinstance(data["Questions"], dict):
                    variables = list(data["Questions"].keys())
                else:
                    variables = [k for k in data.keys() if k not in self.IGNORE_KEYS]

                for var in variables:
                    var_map[var].append(file_path.name)

            except Exception as e:
                print(f"Error reading {file_path.name}: {e}")
        
        return var_map

    def validate_draft(self, draft_content, filename):
        """
        Checks if the draft content introduces any duplicates against the existing library.
        Returns a list of error messages. Empty list means valid.
        """
        errors = []
        
        # 1. Extract variables from draft
        draft_vars = []
        if "Questions" in draft_content and isinstance(draft_content["Questions"], dict):
            draft_vars = list(draft_content["Questions"].keys())
        else:
            draft_vars = [k for k in draft_content.keys() if k not in self.IGNORE_KEYS]

        # 2. Check for internal duplicates (if list? keys are unique in dict, but maybe case sensitivity?)
        # JSON keys are unique by definition in Python dicts, so we are good there.

        # 3. Check against other files
        existing_vars = self.get_all_library_variables(exclude_file=filename)
        
        for var in draft_vars:
            if var in existing_vars:
                conflicting_files = ", ".join(existing_vars[var])
                errors.append(f"Variable '{var}' is already defined in: {conflicting_files}")

        return errors
