import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    check_proposal,
    check_sample,
    errors_only,
    read_proposal,
)

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "official" / "create_new_modality" / "modality_proposal_template.xlsx"
EXAMPLE_DIR = REPO / "examples" / "modality_proposal"


def test_template_workbook_is_a_valid_proposal_equal_to_the_yaml_example() -> None:
    p = read_proposal(TEMPLATE)
    assert errors_only(check_proposal(p)) == []
    assert errors_only(check_sample(p, EXAMPLE_DIR / "bloodwork_sample.tsv")) == []
    assert p == read_proposal(EXAMPLE_DIR / "bloodwork.yml")
