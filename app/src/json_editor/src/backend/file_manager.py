"""
File Manager for BIDS JSON operations
Handles loading, saving, and listing BIDS JSON files
"""

import json
from pathlib import Path


class FileManager:
    """Manages BIDS JSON file operations"""

    # Supported BIDS JSON file types
    SUPPORTED_FILES = {
        "dataset_description": "dataset_description.json",
        "participants": "participants.json",
        "samples": "samples.json",
    }

    def __init__(self, bids_folder=None):
        """
        Initialize FileManager
        Args:
            bids_folder: Path to BIDS dataset root folder
        """
        self.bids_folder = Path(bids_folder) if bids_folder else None
        self._validate_bids_folder()

    def _validate_bids_folder(self):
        """Check if bids_folder exists and is a directory"""
        if self.bids_folder:
            if not self.bids_folder.exists():
                raise ValueError(f"BIDS folder does not exist: {self.bids_folder}")
            if not self.bids_folder.is_dir():
                raise ValueError(f"BIDS folder is not a directory: {self.bids_folder}")

    def set_bids_folder(self, folder_path):
        """
        Set BIDS folder path
        Args:
            folder_path: Path to BIDS dataset root
        """
        self.bids_folder = Path(folder_path)
        self._validate_bids_folder()

    def list_available_files(self):
        """
        List BIDS JSON files available in the current folder
        Returns:
            List of dicts with 'type', 'filename', 'exists', 'path'
        """
        if not self.bids_folder:
            return []

        available = []
        for file_type, filename in self.SUPPORTED_FILES.items():
            file_path = self.bids_folder / filename
            available.append(
                {
                    "type": file_type,
                    "filename": filename,
                    "exists": file_path.exists(),
                    "path": str(file_path),
                }
            )

        # Add task files (task-*.json)
        if self.bids_folder.exists():
            for task_file in self.bids_folder.glob("task-*.json"):
                task_name = task_file.stem
                available.append(
                    {
                        "type": task_name,
                        "filename": task_file.name,
                        "exists": True,
                        "path": str(task_file),
                    }
                )

        return available

    def load_file(self, json_type):
        """
        Load a BIDS JSON file
        Args:
            json_type: 'dataset_description', 'participants', 'task-fmri', etc.
        Returns:
            Parsed JSON data
        """
        if not self.bids_folder:
            raise RuntimeError("No BIDS folder set")

        # Get filename
        if json_type in self.SUPPORTED_FILES:
            filename = self.SUPPORTED_FILES[json_type]
            file_path = self.bids_folder / filename
        elif json_type.startswith("task-"):
            file_path = self.bids_folder / f"{json_type}.json"
        else:
            raise ValueError(f"Unknown JSON type: {json_type}")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {file_path}: {str(e)}")

    def save_file(self, json_type, data):
        """
        Save a BIDS JSON file
        Args:
            json_type: 'dataset_description', 'participants', 'task-fmri', etc.
            data: JSON-serializable data to save
        Returns:
            Path to saved file
        """
        if not self.bids_folder:
            raise RuntimeError("No BIDS folder set")

        # Get filename
        if json_type in self.SUPPORTED_FILES:
            filename = self.SUPPORTED_FILES[json_type]
            file_path = self.bids_folder / filename
        elif json_type.startswith("task-"):
            file_path = self.bids_folder / f"{json_type}.json"
        else:
            raise ValueError(f"Unknown JSON type: {json_type}")

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return str(file_path)
        except IOError as e:
            raise RuntimeError(f"Failed to write file {file_path}: {str(e)}")

    def create_new_file(self, json_type, initial_data=None):
        """
        Create a new BIDS JSON file with optional initial data
        Args:
            json_type: 'dataset_description', 'participants', etc.
            initial_data: Initial JSON data (dict)
        Returns:
            Path to created file
        """
        if not self.bids_folder:
            raise RuntimeError("No BIDS folder set")

        data = initial_data or {}
        return self.save_file(json_type, data)
