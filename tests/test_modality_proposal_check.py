import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import check_proposal, errors_only, read_proposal  # noqa: E402

EXAMPLE_YAML = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal" / "bloodwork.yml"


def _proposal(**over) -> dict:
    p = read_proposal(EXAMPLE_YAML)
    p.update(over)
    return p


def _messages(problems) -> str:
    return " | ".join(f"{p.where}: {p.message}" for p in errors_only(problems))


def test_example_proposal_has_no_errors() -> None:
    assert errors_only(check_proposal(_proposal())) == []


@pytest.mark.parametrize(
    "field,value,needle",
    [
        ("suffix", "blood", "BIDS suffix 'blood'"),
        ("modality", "phenotype", "BIDS datatype 'phenotype'"),
        ("suffix", "physio", "PRISM modality 'physio'"),
    ],
)
def test_names_taken_in_prism_or_bids_are_rejected(field, value, needle) -> None:
    assert needle in _messages(check_proposal(_proposal(**{field: value})))


def test_blood_message_explains_what_the_bids_suffix_means() -> None:
    assert "Blood recording data" in _messages(check_proposal(_proposal(suffix="blood")))


@pytest.mark.parametrize("bad", ["Biosample", "blood sample", "blood-sample", "1blood", ""])
def test_name_and_suffix_must_be_lowercase_letters_and_digits(bad) -> None:
    assert "lowercase" in _messages(check_proposal(_proposal(modality=bad)))
    assert "lowercase" in _messages(check_proposal(_proposal(suffix=bad)))


def test_extensions_and_description_are_required() -> None:
    msg = _messages(check_proposal(_proposal(extensions=[], description="")))
    assert "Modality.Extensions" in msg
    assert "Modality.Description" in msg


def test_bad_extension_is_rejected() -> None:
    assert "Modality.Extensions" in _messages(check_proposal(_proposal(extensions=["t sv"])))


def test_zero_columns_is_an_error() -> None:
    assert "Columns" in _messages(check_proposal(_proposal(columns=[])))


def test_column_problems_are_all_reported() -> None:
    cols = [
        {"id": "a b", "description": "", "units": "n/a", "datatype": "string",
         "min": None, "max": None, "allowed_values": None},
        {"id": "x", "description": "d", "units": "n/a", "datatype": "float",
         "min": 5.0, "max": 1.0, "allowed_values": None},
        {"id": "x", "description": "d", "units": "n/a", "datatype": "blob",
         "min": None, "max": None, "allowed_values": None},
    ]
    msg = _messages(check_proposal(_proposal(columns=cols)))
    assert "letters, digits and underscores" in msg
    assert "Min" in msg and "greater than" in msg
    assert "duplicate" in msg
    assert "datatype" in msg


def _col(**over) -> dict:
    base = {"id": "c", "description": "d", "units": "n/a", "datatype": "string",
            "scale": None, "min": None, "max": None, "allowed_values": None}
    base.update(over)
    return base


def test_empty_column_id_is_reported() -> None:
    assert "ID is empty" in _messages(check_proposal(_proposal(columns=[_col(id="")])))


@pytest.mark.parametrize(
    "col,needle",
    [
        (_col(scale="ordinal"), "scale must be one of"),
        (_col(scale="continuous", datatype="string"), "continuous column"),
        (_col(scale="continuous", datatype="float", allowed_values=[1, 2]), "continuous column"),
        (_col(scale="categorical"), "categorical column needs AllowedValues"),
        (_col(scale="boolean", allowed_values=["a", "b", "c"]), "exactly two"),
    ],
)
def test_scale_must_agree_with_the_column(col, needle) -> None:
    assert needle in _messages(check_proposal(_proposal(columns=[col])))


@pytest.mark.parametrize(
    "col",
    [
        _col(scale="continuous", datatype="float"),
        _col(scale="categorical", allowed_values=["a", "b", "c"]),
        _col(scale="boolean", allowed_values=[0, 1]),
        _col(),  # no scale stated is fine
    ],
)
def test_consistent_scales_and_no_scale_are_accepted(col) -> None:
    assert errors_only(check_proposal(_proposal(columns=[col]))) == []


@pytest.mark.parametrize("cid", ["Technical", "study", "METADATA"])
def test_column_id_equal_to_a_sidecar_block_is_rejected(cid) -> None:
    p = _proposal()
    p["columns"] = p["columns"] + [dict(p["columns"][0], id=cid)]
    assert "sidecar" in _messages(check_proposal(p))
