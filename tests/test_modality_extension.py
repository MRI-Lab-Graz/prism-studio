import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    check_proposal,
    errors_only,
    proposal_kind,
    read_proposal,
    write_proposal_workbook,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
NEW = EXAMPLES / "biosample.yml"


def _proposal(**over) -> dict:
    p = read_proposal(NEW)
    p.update(over)
    return p


def _messages(problems) -> str:
    return " | ".join(f"{p.where}: {p.message}" for p in errors_only(problems))


def test_old_files_with_rationale_still_read(tmp_path):
    f = tmp_path / "p.yml"
    f.write_text(
        "modality: biosample\nsuffix: bloodchem\nextensions: [tsv]\ndescription: d\n"
        "rationale: old text\ncolumns:\n  - id: crp\n    description: c\n",
        encoding="utf-8",
    )
    assert "rationale" not in read_proposal(f)


def test_entities_are_read_from_yaml_and_workbook(tmp_path):
    p = read_proposal(NEW)
    assert {"entity": "acq", "value": "fasting"}.items() <= p["entities"][0].items()
    wb = tmp_path / "p.xlsx"
    write_proposal_workbook(p, wb)
    assert read_proposal(wb)["entities"] == p["entities"]


def test_missing_description_is_the_only_text_requirement():
    msg = _messages(check_proposal(_proposal(description="")))
    assert "Modality.Description" in msg
    assert "Rationale" not in msg


@pytest.mark.parametrize(
    "entities,needle",
    [
        ([{"entity": "run", "value": "1", "description": ""}], "task"),  # only task/acq suggestable
        ([{"entity": "acq", "value": "fasting study", "description": ""}], "letters and digits"),
        (
            [{"entity": "acq", "value": "a", "description": ""}, {"entity": "acq", "value": "a", "description": ""}],
            "duplicate",
        ),
    ],
)
def test_entity_suggestions_are_checked(entities, needle):
    assert needle in _messages(check_proposal(_proposal(entities=entities)))


def _ext(**over):
    return _proposal(**{"modality": "biometrics", "suffix": "bloodpanel", "entities": [], **over})


def test_kind_is_new_for_an_unknown_name_and_extension_for_a_prism_modality():
    assert proposal_kind(_proposal()) == "new"
    assert proposal_kind(_ext()) == "extension"


def test_extension_with_a_free_suffix_has_no_errors():
    assert errors_only(check_proposal(_ext())) == []


def test_extension_suffix_that_is_taken_is_still_rejected():
    assert "PRISM suffix 'eyetrack'" in _messages(check_proposal(_ext(suffix="eyetrack")))
    assert "BIDS suffix 'blood'" in _messages(check_proposal(_ext(suffix="blood")))


def test_extension_cannot_carry_entity_suggestions():
    ents = [{"entity": "acq", "value": "fasting", "description": ""}]
    assert "existing modality" in _messages(check_proposal(_ext(entities=ents)))


def test_bids_and_passthrough_names_are_refused_with_advice():
    assert "BIDS" in _messages(check_proposal(_proposal(modality="anat")))
    assert "BIDS datatype 'phenotype'" in _messages(check_proposal(_proposal(modality="phenotype")))
    assert "upstream" in _messages(check_proposal(_proposal(modality="eyetracking")))


def test_alias_points_at_the_real_modality():
    msg = _messages(check_proposal(_proposal(modality="physiological")))
    assert "PRISM alias 'physiological'" in msg and "'physio'" in msg
