"""Tests targeting src/converters/file_reader.py (the canonical src/ version)."""

import sys
import os
import pytest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.converters.file_reader import (
    _try_read_bytes,
    _decode_bytes,
    _rewrite_tokenization_error,
    _sniff_delimiter,
    _strip_columns,
    read_tabular_file,
    ReadResult,
)


# ---------------------------------------------------------------------------
# _try_read_bytes
# ---------------------------------------------------------------------------

class TestTryReadBytes:
    def test_reads_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_bytes(b"hello")
        assert _try_read_bytes(f) == b"hello"

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="File not found"):
            _try_read_bytes(tmp_path / "missing.txt")

    def test_permission_error_raises(self, tmp_path, monkeypatch):
        f = tmp_path / "locked.txt"
        f.write_bytes(b"data")

        def fake_read_bytes(self):
            raise PermissionError("denied")

        monkeypatch.setattr(Path, "read_bytes", fake_read_bytes)
        with pytest.raises(ValueError, match="Permission denied"):
            _try_read_bytes(f)


# ---------------------------------------------------------------------------
# _decode_bytes
# ---------------------------------------------------------------------------

class TestDecodeBytes:
    def test_utf8_plain(self):
        text, enc = _decode_bytes("hello".encode("utf-8"))
        assert text == "hello"
        assert "utf" in enc.lower()

    def test_latin1_bytes(self):
        raw = "café".encode("latin-1")
        text, enc = _decode_bytes(raw)
        assert "caf" in text

    def test_bom_utf8(self):
        raw = "\ufeffhello".encode("utf-8-sig")
        text, enc = _decode_bytes(raw)
        assert "hello" in text


# ---------------------------------------------------------------------------
# _rewrite_tokenization_error
# ---------------------------------------------------------------------------

class TestRewriteTokenizationError:
    def test_rewrites_expected_fields_error(self):
        msg = "Expected 3 fields in line 5, saw 7"
        result = _rewrite_tokenization_error(msg, "csv")
        assert result is not None
        assert "5" in result
        assert "3" in result
        assert "7" in result

    def test_returns_none_for_irrelevant_error(self):
        assert _rewrite_tokenization_error("some other error", "csv") is None

    def test_tsv_format_mentions_tabs(self):
        msg = "Expected 2 fields in line 3, saw 5"
        result = _rewrite_tokenization_error(msg, "tsv")
        assert "tabs" in result.lower()


# ---------------------------------------------------------------------------
# _sniff_delimiter
# ---------------------------------------------------------------------------

class TestSniffDelimiter:
    def test_detects_comma(self):
        assert _sniff_delimiter("a,b,c\n1,2,3") == ","

    def test_detects_tab(self):
        assert _sniff_delimiter("a\tb\tc\n1\t2\t3") == "\t"

    def test_fallback_to_comma(self):
        # Single-token text with no delimiters
        assert _sniff_delimiter("just_text") == ","


# ---------------------------------------------------------------------------
# read_tabular_file — CSV
# ---------------------------------------------------------------------------

class TestReadTabularFileCSV:
    def test_basic_csv(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("col1,col2\na,b\nc,d\n")
        result = read_tabular_file(f)
        assert list(result.df.columns) == ["col1", "col2"]
        assert len(result.df) == 2

    def test_infers_kind_from_extension(self, tmp_path):
        f = tmp_path / "data.tsv"
        f.write_text("col1\tcol2\na\tb\n")
        result = read_tabular_file(f)
        assert list(result.df.columns) == ["col1", "col2"]

    def test_strips_column_whitespace(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text(" col1 , col2 \na,b\n")
        result = read_tabular_file(f)
        assert "col1" in result.df.columns
        assert "col2" in result.df.columns

    def test_empty_csv_raises(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("")
        with pytest.raises(ValueError, match="empty"):
            read_tabular_file(f)

    def test_explicit_separator(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("col1;col2\na;b\n")
        result = read_tabular_file(f, separator=";")
        assert list(result.df.columns) == ["col1", "col2"]

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="not found|File"):
            read_tabular_file(tmp_path / "missing.csv")
