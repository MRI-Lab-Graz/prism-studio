import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))


def test_write_minimal_dataset_creates_expected_files(tmp_path: Path) -> None:
    from src.modality_contribution import write_minimal_dataset

    sidecar = {
        "Study": {"TaskName": "skintemp", "OriginalName": "Skin Temperature"},
        "Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-09-11"},
    }

    data_path = write_minimal_dataset(
        tmp_path,
        suffix="skintemp",
        extension="tsv",
        sidecar=sidecar,
        data_content="temperature_c\n36.5\n",
        task_name="skintemp",
    )

    assert data_path.is_file()
    assert data_path.name == "sub-01_task-skintemp_skintemp.tsv"
    assert (tmp_path / "dataset_description.json").is_file()

    sidecar_path = data_path.with_suffix(".json")
    assert sidecar_path.is_file()
    assert json.loads(sidecar_path.read_text(encoding="utf-8")) == sidecar


def test_write_minimal_dataset_passes_validation(tmp_path: Path) -> None:
    """Uses suffix="survey" deliberately: survey is already a registered
    modality, so this exercises the "new template under an existing
    modality" path, which validates end-to-end today. A brand-new,
    unregistered modality cannot be checked this way -- see Task 8's
    "more significant correction" note."""
    from src.modality_contribution import write_minimal_dataset
    from runner import validate_dataset

    sidecar = {
        "Technical": {
            "StimulusType": "Questionnaire",
            "FileFormat": "tsv",
            "Language": "en",
            "Respondent": "self",
            "SoftwarePlatform": "Other",
            "SoftwareVersion": "1.0",
            "AdministrationMethod": "online",
        },
        "Study": {
            "TaskName": "demo",
            "OriginalName": "Demo Survey",
            "Citation": "Demo fixture survey",
            "LicenseID": "CC0-1.0",
            "Category": "Other / Uncategorized",
        },
        "Metadata": {"SchemaVersion": "2.0.0", "CreationDate": "2026-09-11", "Creator": "tests"},
        "I18n": {"Languages": ["en"]},
    }

    write_minimal_dataset(
        tmp_path,
        suffix="survey",
        extension="tsv",
        sidecar=sidecar,
        data_content="item01\titem02\n1\t2\n",
        task_name="demo",
    )

    issues, stats = validate_dataset(str(tmp_path))

    errors = [i for i in issues if i[0] == "ERROR"]
    assert errors == []
    assert "sub-01" in stats.subjects


def test_write_minimal_dataset_uses_default_task_name(tmp_path: Path) -> None:
    from src.modality_contribution import write_minimal_dataset

    data_path = write_minimal_dataset(
        tmp_path,
        suffix="skintemp",
        extension="tsv",
        sidecar={"Metadata": {"SchemaVersion": "1.0.0", "CreationDate": "2026-09-11"}},
        data_content="x\n1\n",
    )

    assert data_path.name == "sub-01_task-demo_skintemp.tsv"


def test_write_minimal_dataset_modality_folder_and_bytes(tmp_path: Path) -> None:
    from src.modality_contribution import write_minimal_dataset

    data_path = write_minimal_dataset(
        tmp_path,
        modality="bloodwork",
        suffix="bloodchem",
        extension="tsv.gz",
        sidecar={"Study": {}},
        data_content=b"\x1f\x8bbytes",
        task_name="bloodwork",
    )
    assert data_path == tmp_path / "sub-01" / "bloodwork" / "sub-01_task-bloodwork_bloodchem.tsv.gz"
    assert data_path.read_bytes() == b"\x1f\x8bbytes"
    assert (data_path.parent / "sub-01_task-bloodwork_bloodchem.json").is_file()
