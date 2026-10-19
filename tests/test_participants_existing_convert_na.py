"""Re-writing an existing participants.tsv must keep BIDS ``n/a`` for missing cells."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "app"))
sys.path.insert(0, str(PROJECT_ROOT))

from src.web.blueprints.conversion_participants_merge import (  # noqa: E402
    _convert_existing_participants_files,
)


def test_excluding_a_column_keeps_na_not_empty_cells(tmp_path):
    (tmp_path / "participants.tsv").write_text(
        "participant_id\tage\tgender\tdrop_me\n"
        "sub-01\t21\t1\tx\n"
        "sub-02\tn/a\tn/a\ty\n",
        encoding="utf-8",
    )

    _convert_existing_participants_files(
        project_root=tmp_path,
        neurobagel_schema={},
        excluded_columns={"drop_me"},
        log_callback=lambda *_: None,
    )

    lines = (tmp_path / "participants.tsv").read_text(encoding="utf-8").splitlines()
    assert lines[2].split("\t") == ["sub-02", "n/a", "n/a"]
