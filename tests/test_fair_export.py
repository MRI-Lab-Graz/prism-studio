"""Tests for app/src/fair_export.py — Dublin Core / DataCite metadata export.

Previously zero test coverage existed for this module. Includes a
regression test for a real crash found via hostile testing: PRISM's own
survey/biometrics templates commonly store License/Description as a
multi-language dict (e.g. {"en": "...", "de": "..."}) rather than a plain
string — export_datacite crashed with AttributeError on license_info
.startswith("CC") whenever License was such a dict.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from src.fair_export import export_datacite, export_dublin_core


def _write_metadata(tmp_path: Path, metadata: dict) -> Path:
    path = tmp_path / "dataset_description.json"
    path.write_text(json.dumps(metadata), encoding="utf-8")
    return path


def test_export_dublin_core_with_clean_dataset_description(tmp_path: Path) -> None:
    metadata_file = _write_metadata(
        tmp_path,
        {
            "Name": "Clean Test Dataset",
            "BIDSVersion": "1.8.0",
            "Authors": ["Jane Doe"],
            "License": "CC0",
        },
    )
    output = export_dublin_core(str(metadata_file))
    tree = ET.parse(output)
    title = tree.find("dc:title", {"dc": "http://purl.org/dc/elements/1.1/"})
    assert title is not None
    assert title.text == "Clean Test Dataset"


def test_export_datacite_with_clean_dataset_description(tmp_path: Path) -> None:
    metadata_file = _write_metadata(
        tmp_path,
        {
            "Name": "Clean Test Dataset",
            "BIDSVersion": "1.8.0",
            "Authors": [{"name": "Jane Doe", "orcid": "0000-0000-0000-0000"}],
            "DatasetDOI": "10.1234/test",
        },
    )
    output = export_datacite(str(metadata_file))
    content = Path(output).read_text(encoding="utf-8")
    assert "10.1234/test" in content
    assert "Jane Doe" in content
    assert "orcid.org/0000-0000-0000-0000" in content


def test_export_datacite_handles_dict_shaped_license_without_crashing(
    tmp_path: Path,
) -> None:
    """Regression guard: PRISM's own survey templates store License as
    {"en": "...", "de": "..."} — this used to crash export_datacite with
    AttributeError: 'dict' object has no attribute 'startswith'."""
    metadata_file = _write_metadata(
        tmp_path,
        {
            "Name": "Hostile FAIR test",
            "BIDSVersion": "1.8.0",
            "Authors": ["Test Author"],
            "Metadata": {
                "License": {"en": "Freely available", "de": "Frei verfügbar"},
                "CreationDate": "2026-06-21",
            },
            "Study": {"TaskName": "hostiletest"},
        },
    )
    output = export_datacite(str(metadata_file))
    content = Path(output).read_text(encoding="utf-8")
    assert "Freely available" in content
    assert "<dict" not in content  # never a raw Python repr leaking into XML


def test_export_datacite_handles_dict_shaped_description_without_crashing(
    tmp_path: Path,
) -> None:
    metadata_file = _write_metadata(
        tmp_path,
        {
            "Name": "Hostile FAIR test",
            "BIDSVersion": "1.8.0",
            "Authors": ["Test Author"],
            "Metadata": {
                "Description": {"en": "English description", "de": "Deutsch"},
                "License": "CC0",
            },
        },
    )
    output = export_datacite(str(metadata_file))
    content = Path(output).read_text(encoding="utf-8")
    assert "English description" in content


def test_export_datacite_cc_license_gets_rights_uri(tmp_path: Path) -> None:
    metadata_file = _write_metadata(
        tmp_path,
        {
            "Name": "CC licensed dataset",
            "BIDSVersion": "1.8.0",
            "Authors": ["Test Author"],
            "Metadata": {"License": "CC-BY"},
        },
    )
    output = export_datacite(str(metadata_file))
    tree = ET.parse(output)
    rights = tree.find(".//{http://datacite.org/schema/kernel-4}rights")
    assert rights is not None
    assert "creativecommons.org" in rights.get("rightsURI", "")


def test_export_dublin_core_escapes_xml_special_characters(tmp_path: Path) -> None:
    """Title/description containing XML-significant characters must be
    escaped, not break the XML structure or enable injection."""
    metadata_file = _write_metadata(
        tmp_path,
        {
            "Name": "Dataset <with> & \"special\" 'chars'",
            "BIDSVersion": "1.8.0",
            "Authors": ["Author & Co"],
        },
    )
    output = export_dublin_core(str(metadata_file))
    # Parsing succeeds only if special characters were correctly escaped.
    tree = ET.parse(output)
    title = tree.find("dc:title", {"dc": "http://purl.org/dc/elements/1.1/"})
    assert title.text == "Dataset <with> & \"special\" 'chars'"


def test_export_datacite_missing_optional_fields_uses_defaults(tmp_path: Path) -> None:
    metadata_file = _write_metadata(
        tmp_path,
        {"Name": "Minimal Dataset", "BIDSVersion": "1.8.0"},
    )
    output = export_datacite(str(metadata_file))
    content = Path(output).read_text(encoding="utf-8")
    assert "10.PLACEHOLDER/DATASET" in content


def test_export_dublin_core_missing_metadata_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        export_dublin_core(str(tmp_path / "does_not_exist.json"))
