"""Regression guard: subject-id sanitization must be deterministic
regardless of which Unicode normalization form the source data used.

Without NFC-normalizing before stripping non-ASCII characters, a visually
identical name like "José" sanitized differently depending on encoding:
NFC's precomposed 'é' (U+00E9) was stripped whole ("sub-Jos"), while NFD's
decomposed 'e' (U+0065) + combining acute accent (U+0301) kept the base
ASCII letter and only stripped the combining mark ("sub-Jose"). Two
collaborators on different platforms (e.g. macOS historically produces
NFD-encoded text, most web forms/Windows produce NFC) typing the "same"
name would silently get different, both-plausible-looking participant
ids — a real identity-integrity bug, not data loss, since neither output
would raise an error or look obviously wrong on its own.
"""

from __future__ import annotations

import unicodedata

import pytest

from src.converters.biometrics import _normalize_sub_id as biometrics_normalize_sub_id
from src.participants_converter import ParticipantsConverter


def _nfc_and_nfd(value: str) -> tuple[str, str]:
    nfc = unicodedata.normalize("NFC", value)
    nfd = unicodedata.normalize("NFD", value)
    assert nfc != nfd, "fixture must actually exercise distinct encodings"
    return nfc, nfd


@pytest.mark.parametrize(
    "raw_name",
    ["sub-José", "sub-François", "sub-Müller", "sub-Renée"],
)
def test_participants_converter_normalizes_consistently_across_unicode_forms(
    raw_name: str,
) -> None:
    nfc, nfd = _nfc_and_nfd(raw_name)
    result_nfc = ParticipantsConverter._normalize_participant_id(nfc)
    result_nfd = ParticipantsConverter._normalize_participant_id(nfd)
    assert result_nfc == result_nfd


@pytest.mark.parametrize(
    "raw_name",
    ["sub-José", "sub-François", "sub-Müller", "sub-Renée"],
)
def test_biometrics_normalize_sub_id_consistent_across_unicode_forms(
    raw_name: str,
) -> None:
    nfc, nfd = _nfc_and_nfd(raw_name)
    assert biometrics_normalize_sub_id(nfc) == biometrics_normalize_sub_id(nfd)


def test_survey_normalize_sub_id_consistent_across_unicode_forms() -> None:
    # The survey converter's _normalize_sub_id is a nested function, not
    # importable directly; exercise it indirectly through a real import
    # call with both encodings and confirm they land on the same subject.
    import tempfile
    from pathlib import Path

    import pandas as pd

    from app.src.hostile_demo_generator import build_random_survey_template
    from src.converters.survey import convert_survey_xlsx_to_prism_dataset
    from src.utils.io import ensure_dir, write_json

    task_name, template, item_codes = build_random_survey_template(seed=1)
    tmp_path = Path(tempfile.mkdtemp())
    library_dir = ensure_dir(tmp_path / "library")
    write_json(library_dir / f"survey-{task_name}.json", template)

    nfc, nfd = _nfc_and_nfd("sub-José")
    for label, name in (("nfc", nfc), ("nfd", nfd)):
        data_csv = tmp_path / f"data_{label}.csv"
        pd.DataFrame([{"participant_id": name, **{c: 1 for c in item_codes}}]).to_csv(
            data_csv, index=False
        )
        convert_survey_xlsx_to_prism_dataset(
            input_path=data_csv,
            library_dir=library_dir,
            output_root=tmp_path / f"out_{label}",
            name="unicode-consistency-test",
        )

    out_nfc_dirs = {p.name for p in (tmp_path / "out_nfc").iterdir() if p.name.startswith("sub-")}
    out_nfd_dirs = {p.name for p in (tmp_path / "out_nfd").iterdir() if p.name.startswith("sub-")}
    assert out_nfc_dirs == out_nfd_dirs
