"""Tests for app/src/converters/excel_base.py."""

import warnings

import pandas as pd
import pytest

from app.src.converters.excel_base import read_excel_sheets


def test_read_excel_sheets_suppresses_data_validation_extension_warning(monkeypatch):
    """The known-benign openpyxl 'extension not supported' warning must not surface.

    It fires when a workbook's data validations were upgraded to the x14 extension
    format by Excel/Numbers/LibreOffice on save; it doesn't affect cell values, which
    is all read_excel_sheets reads, so it should be silenced rather than alarming users.
    """
    expected = {"Sheet1": pd.DataFrame([["a", "b"]])}

    def fake_read_excel(path, sheet_name=None, header=None, dtype=str):
        warnings.warn(
            "Data Validation extension is not supported and will be removed",
            UserWarning,
        )
        return expected

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result = read_excel_sheets("dummy.xlsx")

    assert result is expected
    assert not any("Data Validation extension" in str(w.message) for w in caught)


def test_read_excel_sheets_does_not_swallow_unrelated_warnings(monkeypatch):
    """Only the specific known-benign message should be filtered, nothing else."""

    def fake_read_excel(path, sheet_name=None, header=None, dtype=str):
        warnings.warn("some other unrelated warning", UserWarning)
        return {}

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    with pytest.warns(UserWarning, match="some other unrelated warning"):
        read_excel_sheets("dummy.xlsx")
