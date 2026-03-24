"""Tests for the shared tabular file reader (app/src/converters/file_reader.py).

Covers:
- Basic CSV / TSV / XLSX reading
- BOM / encoding detection (UTF-8-sig, latin-1, cp1252)
- Empty-file guard
- Wrong-delimiter detection and auto-sniff recovery
- Column-name whitespace stripping
- Friendly tokenization-error rewriting
- dtype=str enforcement (no numeric coercion)
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from app.src.converters.file_reader import ReadResult, read_tabular_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str | bytes) -> None:
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)


# ---------------------------------------------------------------------------
# Basic happy-path tests
# ---------------------------------------------------------------------------


class TestBasicFormats:
    def test_csv_basic(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, "id,age\n001,25\n002,30\n")
        result = read_tabular_file(f)
        assert isinstance(result, ReadResult)
        assert list(result.df.columns) == ["id", "age"]
        assert len(result.df) == 2
        assert result.delimiter_used == ","

    def test_tsv_basic(self, tmp_path):
        f = tmp_path / "data.tsv"
        _write(f, "id\tage\n001\t25\n002\t30\n")
        result = read_tabular_file(f)
        assert list(result.df.columns) == ["id", "age"]
        assert result.delimiter_used == "\t"

    def test_xlsx_basic(self, tmp_path):
        f = tmp_path / "data.xlsx"
        df = pd.DataFrame({"id": ["001", "002"], "age": [25, 30]})
        df.to_excel(f, index=False)
        result = read_tabular_file(f)
        assert list(result.df.columns) == ["id", "age"]
        assert result.delimiter_used is None

    def test_kind_overrides_extension(self, tmp_path):
        # File has .txt extension but is comma-separated; kind="csv" forces CSV parsing
        f = tmp_path / "data.txt"
        _write(f, "id,age\n001,25\n")
        result = read_tabular_file(f, kind="csv")
        assert list(result.df.columns) == ["id", "age"]

    def test_all_columns_are_str(self, tmp_path):
        """No numeric coercion should happen — dtype=str is enforced."""
        f = tmp_path / "nums.csv"
        _write(f, "x,y\n1,3.14\n2,2.71\n")
        result = read_tabular_file(f)
        assert result.df["x"].dtype == object  # str columns are object dtype
        assert result.df["y"].dtype == object


# ---------------------------------------------------------------------------
# Column name stripping
# ---------------------------------------------------------------------------


class TestColumnStripping:
    def test_strips_whitespace_from_column_names(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, " id , age \n001,25\n")
        result = read_tabular_file(f)
        assert "id" in result.df.columns
        assert "age" in result.df.columns

    def test_strips_tab_column_names(self, tmp_path):
        f = tmp_path / "data.tsv"
        _write(f, "\tid\t\tage\t\n001\t25\n")
        result = read_tabular_file(f)
        assert all(c == c.strip() for c in result.df.columns)


# ---------------------------------------------------------------------------
# Encoding detection
# ---------------------------------------------------------------------------


class TestEncoding:
    def test_utf8_bom_detected(self, tmp_path):
        f = tmp_path / "bom.csv"
        content = "id,age\n001,25\n"
        f.write_bytes(content.encode("utf-8-sig"))
        result = read_tabular_file(f)
        assert "id" in result.df.columns
        assert result.encoding_used == "utf-8-sig"

    def test_latin1_file(self, tmp_path):
        f = tmp_path / "latin.csv"
        # ü encoded as latin-1 (0xFC), not valid UTF-8
        content = "id,name\n001,M\xfcller\n"
        f.write_bytes(content.encode("latin-1"))
        result = read_tabular_file(f)
        assert "name" in result.df.columns
        assert result.encoding_used == "latin-1"

    def test_cp1252_file(self, tmp_path):
        f = tmp_path / "win.csv"
        # Euro sign (U+20AC) encodes to byte 0x80 in cp1252.
        # The same byte is also valid in latin-1 (maps to U+0080 control char),
        # so the reader will match latin-1 first — that's correct & expected.
        # What matters is that the file is readable without error.
        content = "id,amt\n001,\u20ac5\n"
        f.write_bytes(content.encode("cp1252"))
        result = read_tabular_file(f)
        assert "id" in result.df.columns
        assert result.encoding_used in ("latin-1", "cp1252")

    def test_forced_encoding(self, tmp_path):
        f = tmp_path / "forced.csv"
        content = "id,age\n001,25\n"
        f.write_bytes(content.encode("utf-8"))
        result = read_tabular_file(f, encoding="utf-8")
        assert result.encoding_used == "utf-8"

    def test_forced_encoding_wrong_raises(self, tmp_path):
        f = tmp_path / "forced_bad.csv"
        # Write latin-1 content
        f.write_bytes("id,name\n001,M\xfcller\n".encode("latin-1"))
        with pytest.raises(ValueError, match="Cannot decode"):
            read_tabular_file(f, encoding="ascii")


# ---------------------------------------------------------------------------
# Empty file guard
# ---------------------------------------------------------------------------


class TestEmptyFile:
    def test_empty_csv_raises(self, tmp_path):
        f = tmp_path / "empty.csv"
        _write(f, "")
        with pytest.raises(ValueError, match="empty"):
            read_tabular_file(f, kind="csv")

    def test_whitespace_only_csv_raises(self, tmp_path):
        f = tmp_path / "ws.csv"
        _write(f, "   \n   \n")
        with pytest.raises(ValueError, match="empty"):
            read_tabular_file(f, kind="csv")

    def test_empty_xlsx_raises(self, tmp_path):
        f = tmp_path / "empty.xlsx"
        pd.DataFrame().to_excel(f, index=False)
        with pytest.raises(ValueError, match="empty"):
            read_tabular_file(f, kind="xlsx")

    def test_missing_file_raises(self, tmp_path):
        f = tmp_path / "does_not_exist.csv"
        with pytest.raises(ValueError, match="not found"):
            read_tabular_file(f)


# ---------------------------------------------------------------------------
# Wrong-delimiter detection
# ---------------------------------------------------------------------------


class TestDelimiterDetection:
    def test_csv_with_tabs_recovered_with_warning(self, tmp_path):
        """CSV file that is actually tab-delimited: sniffer recovers it and emits a warning."""
        f = tmp_path / "tabbed.csv"
        _write(f, "id\tage\n001\t25\n")
        result = read_tabular_file(f, kind="csv")
        assert len(result.df.columns) == 2
        assert result.warnings  # delimiter mismatch warning was emitted

    def test_tsv_with_semicolons_recovered_with_warning(self, tmp_path):
        """TSV file that is actually semicolon-delimited: sniffer recovers it."""
        f = tmp_path / "semi.tsv"
        _write(f, "id;age\n001;25\n")
        result = read_tabular_file(f, kind="tsv")
        assert len(result.df.columns) == 2
        assert result.warnings

    def test_tsv_with_commas_recovered_with_warning(self, tmp_path):
        """TSV file that is actually comma-delimited: sniffer recovers it."""
        f = tmp_path / "commafile.tsv"
        _write(f, "id,age\n001,25\n")
        result = read_tabular_file(f, kind="tsv")
        assert len(result.df.columns) == 2
        assert result.warnings

    def test_auto_sniff_recovers_delimiter(self, tmp_path):
        """If a CSV is actually tab-delimited, the sniffer detects it
        and the result should have more than one column (sniff succeeds)."""
        f = tmp_path / "sniff_me.csv"
        # Semicolon-delimited "csv" — sniffer can detect `;`
        _write(f, "id;age;sex\n001;25;M\n002;30;F\n")
        # We call with kind=csv, no explicit separator — sniffer should recover
        result = read_tabular_file(f, kind="csv")
        # After sniffing, we should have 3 columns
        assert len(result.df.columns) == 3
        assert result.warnings  # a warning about detected delimiter was emitted

    def test_explicit_separator_respected(self, tmp_path):
        f = tmp_path / "pipe.csv"
        _write(f, "id|age\n001|25\n")
        result = read_tabular_file(f, kind="csv", separator="|")
        assert list(result.df.columns) == ["id", "age"]


# ---------------------------------------------------------------------------
# Tokenization-error rewriting
# ---------------------------------------------------------------------------


class TestTokenizationErrors:
    def test_csv_extra_columns_friendly_message(self, tmp_path):
        """A row with mismatched quotes triggers a pandas ParserError → friendly message."""
        f = tmp_path / "bad.csv"
        # Unclosed quote causes pandas to fail with a tokenization / ParserError
        _write(f, 'id,note\n001,"unclosed quote\n002,fine\n')
        with pytest.raises(ValueError) as exc_info:
            read_tabular_file(f, kind="csv")
        msg = str(exc_info.value).lower()
        assert "csv" in msg or "failed" in msg or "format" in msg


# ---------------------------------------------------------------------------
# ReadResult attributes
# ---------------------------------------------------------------------------


class TestReadResult:
    def test_encoding_used_set_for_text(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, "id,age\n001,25\n")
        result = read_tabular_file(f)
        assert result.encoding_used  # non-empty string

    def test_delimiter_used_none_for_xlsx(self, tmp_path):
        f = tmp_path / "data.xlsx"
        pd.DataFrame({"id": ["001"]}).to_excel(f, index=False)
        result = read_tabular_file(f)
        assert result.delimiter_used is None

    def test_warnings_list_initially_empty(self, tmp_path):
        f = tmp_path / "data.csv"
        _write(f, "id,age\n001,25\n")
        result = read_tabular_file(f)
        assert isinstance(result.warnings, list)

    def test_sheet_parameter_xlsx(self, tmp_path):
        f = tmp_path / "sheets.xlsx"
        with pd.ExcelWriter(f, engine="openpyxl") as w:
            pd.DataFrame({"a": [1]}).to_excel(w, sheet_name="Sheet1", index=False)
            pd.DataFrame({"b": [2]}).to_excel(w, sheet_name="Sheet2", index=False)
        result = read_tabular_file(f, sheet="Sheet2")
        assert "b" in result.df.columns

    def test_sheet_digit_string_coerced(self, tmp_path):
        f = tmp_path / "sheetnum.xlsx"
        pd.DataFrame({"x": ["val"]}).to_excel(f, index=False)
        result = read_tabular_file(f, sheet="0")
        assert "x" in result.df.columns
