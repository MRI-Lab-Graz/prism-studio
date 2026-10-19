"""A minimal PRISM project with a biosample modality validates through the real entry points."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

REPO = Path(__file__).resolve().parent.parent
EXAMPLE = REPO / "official" / "library" / "biosample" / "biosample-inflammation.json"
ROWS = "sample_id\tcollection_time\tfasting\tcrp\til6\ttnfa\nB-0152\t08:40\t0\t0.4\t<LOD\t1.12\n"


def _build(tmp_path: Path, tsv: str = ROWS) -> Path:
    root = tmp_path / "ds"
    folder = root / "sub-02" / "ses-1" / "biosample"
    folder.mkdir(parents=True)
    (root / "dataset_description.json").write_text(
        json.dumps({"Name": "t", "BIDSVersion": "1.10.1", "DatasetType": "raw"}), encoding="utf-8"
    )
    (root / "participants.tsv").write_text("participant_id\nsub-02\n", encoding="utf-8")
    (root / "biosample-inflammation_biosample.json").write_text(EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    (folder / "sub-02_ses-1_biosample-inflammation_biosample.tsv").write_text(tsv, encoding="utf-8")
    return root


def _biosample_errors(issues):
    return [i for i in issues if i[0] == "ERROR" and "biosample" in " ".join(str(x) for x in i).lower()]


def test_validate_dataset_clean_project_has_no_biosample_errors(tmp_path):
    from runner import validate_dataset

    issues, _stats = validate_dataset(str(_build(tmp_path)))
    assert _biosample_errors(issues) == [], _biosample_errors(issues)


def test_validate_dataset_flags_bad_value_in_biosample_file(tmp_path):
    from runner import validate_dataset

    bad = ROWS.replace("0.4", "-2")
    issues, _ = validate_dataset(str(_build(tmp_path, bad)))
    assert any(i[0] == "ERROR" and "less than MinValue" in i[1] for i in issues)


def test_prism_cli_validates_biosample_project(tmp_path):
    root = _build(tmp_path, ROWS.replace("0.4", "-2"))
    result = subprocess.run(
        [sys.executable, str(REPO / "prism.py"), str(root)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert "less than MinValue" in result.stdout + result.stderr


def test_bidsignore_covers_biosample_files():
    from bids_integration import EXTRA_BIDSIGNORE_RULES

    assert "*_biosample.*" in EXTRA_BIDSIGNORE_RULES
