"""
Shared tabular file reader for all PRISM converters.

Centralises all file-format edge-case handling that would otherwise be
duplicated across survey, biometrics, and participants converters:

  • Encoding detection & fallback  (UTF-8 → UTF-8-sig/BOM → latin-1 → cp1252)
  • Delimiter auto-sniff for CSV/TSV when the declared separator is wrong
  • Empty-file guard before pandas even opens the file
  • Column-name whitespace stripping
  • Friendly rewriting of pandas tokenization errors
    • Enforce dtype=str across all formats (no silent type inference)

Usage::

    from src.converters.file_reader import read_tabular_file, ReadResult

    result = read_tabular_file(path, kind="csv")
    df = result.df
    # result.encoding_used, result.delimiter_used are available for provenance logging
"""

from __future__ import annotations

import csv
import io
import importlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class ReadResult:
    """Return value from :func:`read_tabular_file`."""

    df: Any  # pandas.DataFrame
    encoding_used: str
    delimiter_used: str | None  # None for Excel
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Encoding candidates (ordered: most common / strict first)
# ---------------------------------------------------------------------------

_ENCODING_CANDIDATES = ["utf-8-sig", "utf-8", "latin-1", "cp1252"]
_SUPPORTED_SUFFIX_TO_KIND = {
    ".csv": "csv",
    ".tsv": "tsv",
    ".xlsx": "xlsx",
    ".xls": "xls",
    ".sav": "sav",
    ".rds": "rds",
    ".rdata": "rdata",
    ".rda": "rdata",
}

SUPPORTED_TABULAR_SUFFIXES = frozenset(_SUPPORTED_SUFFIX_TO_KIND)
SUPPORTED_TABULAR_KINDS = frozenset(_SUPPORTED_SUFFIX_TO_KIND.values())

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _try_read_bytes(path: Path) -> bytes:
    """Read raw bytes; raise a friendly ValueError on permission / not-found."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        raise ValueError(f"File not found: {path}")
    except PermissionError:
        raise ValueError(f"Permission denied reading file: {path}")
    except OSError as exc:
        raise ValueError(f"Cannot read file {path.name}: {exc}") from exc


def _decode_bytes(raw: bytes) -> tuple[str, str]:
    """Return (text, encoding) trying candidates in order."""
    for enc in _ENCODING_CANDIDATES:
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    # Final fallback: replace errors
    return raw.decode("utf-8", errors="replace"), "utf-8 (lossy)"


def _rewrite_tokenization_error(msg: str, fmt: str) -> str | None:
    """If *msg* looks like a pandas 'Expected X fields' error, return a nicer version."""
    m = re.search(r"Expected (\d+) fields in line (\d+), saw (\d+)", msg)
    if not m:
        return None
    expected, line_num, got = m.groups()
    sep_label = "tabs" if fmt == "tsv" else "commas"
    extra_tips = (
        "  • Extra tabs or newlines within a cell\n  • Trailing tabs at the end of a line"
        if fmt == "tsv"
        else "  • Extra commas or quotes within a cell\n  • Unescaped quotes or embedded newlines in data"
    )
    return (
        f"{fmt.upper()} format error in row {line_num}: "
        f"Expected {expected} columns but found {got}.\n"
        f"This usually indicates:\n"
        f"{extra_tips}\n"
        f"  • Inconsistent number of columns across rows\n"
        f"Please check the file structure and ensure all rows have the same number of columns."
    )


def _sniff_delimiter(text: str) -> str:
    """Use csv.Sniffer to detect delimiter; fall back to comma."""
    sample = "\n".join(text.splitlines()[:20])
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        return ","


def _strip_columns(df: Any) -> Any:
    """Strip whitespace from all column names in-place and return df."""
    return df.rename(columns={c: str(c).strip() for c in df.columns})


def _coerce_values_to_str(df: Any, pd_module: Any) -> Any:
    """Normalize imported dataframe values to string-like columns."""

    def _coerce(value: Any) -> Any:
        if pd_module.isna(value):
            return pd_module.NA
        return str(value)

    return df.apply(lambda series: series.map(_coerce))


def _import_optional_module(module_name: str, *, feature_label: str):
    """Import an optional dependency and raise a setup-oriented ValueError on failure."""
    try:
        return importlib.import_module(module_name)
    except Exception as exc:
        raise ValueError(
            f"{feature_label} support requires optional dependency '{module_name}'. "
            "Install dependencies via setup.sh."
        ) from exc


def _select_first_r_dataframe(result: Any, *, filename: str) -> tuple[Any, list[str]]:
    """Return the first dataframe-like object from a pyreadr result mapping."""
    dataframes: list[tuple[str, Any]] = []
    for object_name, value in getattr(result, "items", lambda: [])():
        if hasattr(value, "columns") and hasattr(value, "empty"):
            dataframes.append((str(object_name or "").strip(), value))

    if not dataframes:
        raise ValueError(f"No readable data frame found in R data file: {filename}")

    warnings: list[str] = []
    if len(dataframes) > 1:
        labels = ", ".join(name or "<unnamed>" for name, _ in dataframes[:5])
        warnings.append(
            f"R data file contains multiple data frames ({labels}). Using the first object."
        )

    return dataframes[0][1], warnings


def infer_tabular_kind(path: str | Path) -> str | None:
    """Infer a supported tabular kind from a file suffix."""
    return _SUPPORTED_SUFFIX_TO_KIND.get(Path(path).suffix.lower())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_tabular_file(
    path: str | Path,
    kind: str | None = None,
    *,
    sheet: str | int = 0,
    separator: str | None = None,
    encoding: str | None = None,
) -> ReadResult:
    """Read a CSV / TSV / XLSX / XLS / SAV / RData / RDS file into a :class:`ReadResult`.

    Parameters
    ----------
    path:
        Path to the file to read.
    kind:
        Format hint: ``"csv"``, ``"tsv"``, ``"xlsx"``, ``"xls"``, ``"sav"``,
        ``"rds"``, or ``"rdata"``.
        If *None* the extension of *path* is used.
    sheet:
        Sheet name or 0-based index for Excel files (ignored for text formats).
        String digits are coerced to int.
    separator:
        Explicit delimiter for CSV/TSV.  When *None* the default for the format
        is used (``","`` for CSV, ``"\\t"`` for TSV).  If the delimiter appears
        wrong (single-column result) the reader will auto-sniff instead.
    encoding:
        Force a specific encoding instead of auto-detecting.

    Raises
    ------
    ValueError
        For all user-visible problems (empty file, wrong format, bad encoding,
        missing file, …).
    RuntimeError
        When pandas is not installed.
    """
    try:
        import pandas as pd
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "pandas is required. Ensure dependencies are installed via setup.sh."
        ) from exc

    path = Path(path)

    # Resolve kind from extension when not given
    if kind is None:
        kind = infer_tabular_kind(path) or "csv"

    EmptyDataError = getattr(pd.errors, "EmptyDataError", ValueError)

    # ------------------------------------------------------------------
    # SPSS / R binary tables
    # ------------------------------------------------------------------
    if kind == "sav":
        pyreadstat = _import_optional_module(
            "pyreadstat", feature_label="SPSS .sav import"
        )
        try:
            df, _meta = pyreadstat.read_sav(str(path))
        except Exception as exc:
            raise ValueError(f"Failed to read SPSS .sav file {path.name}: {exc}") from exc

        if df is None or df.empty:
            raise ValueError(f"Input SPSS .sav file is empty: {path.name}")

        return ReadResult(
            df=_strip_columns(_coerce_values_to_str(df, pd)),
            encoding_used="binary/sav",
            delimiter_used=None,
        )

    if kind in ("rds", "rdata"):
        pyreadr = _import_optional_module(
            "pyreadr", feature_label="R dataframe import"
        )
        try:
            result = pyreadr.read_r(str(path))
        except Exception as exc:
            raise ValueError(f"Failed to read R data file {path.name}: {exc}") from exc

        df, r_warnings = _select_first_r_dataframe(result, filename=path.name)
        if df is None or df.empty:
            raise ValueError(f"Input R data file is empty: {path.name}")

        return ReadResult(
            df=_strip_columns(_coerce_values_to_str(df, pd)),
            encoding_used=f"binary/{kind}",
            delimiter_used=None,
            warnings=r_warnings,
        )

    # ------------------------------------------------------------------
    # Excel
    # ------------------------------------------------------------------
    if kind in ("xlsx", "xls"):
        resolved_sheet: str | int = sheet
        if isinstance(resolved_sheet, str) and resolved_sheet.isdigit():
            resolved_sheet = int(resolved_sheet)

        try:
            df = pd.read_excel(path, sheet_name=resolved_sheet, dtype=str)
        except EmptyDataError:
            raise ValueError(f"Input Excel file is empty: {path.name}")
        except Exception as exc:
            raise ValueError(f"Failed to read Excel file {path.name}: {exc}") from exc

        if df is None or df.empty:
            raise ValueError(f"Input Excel file is empty: {path.name}")

        return ReadResult(
            df=_strip_columns(df),
            encoding_used="binary/xlsx",
            delimiter_used=None,
        )

    # ------------------------------------------------------------------
    # Text formats (CSV / TSV)
    # ------------------------------------------------------------------
    raw = _try_read_bytes(path)

    if not raw.strip():
        raise ValueError(f"Input file is empty: {path.name}")

    if encoding:
        try:
            text = raw.decode(encoding)
            enc_used = encoding
        except (UnicodeDecodeError, LookupError) as exc:
            raise ValueError(
                f"Cannot decode {path.name} with encoding '{encoding}': {exc}"
            ) from exc
    else:
        text, enc_used = _decode_bytes(raw)

    warnings: list[str] = []

    default_sep = "\t" if kind == "tsv" else ","
    sep = separator if separator is not None else default_sep

    def _do_read(sep_: str) -> Any:
        return pd.read_csv(io.StringIO(text), sep=sep_, dtype=str)

    try:
        df = _do_read(sep)
    except EmptyDataError:
        raise ValueError(f"Input {kind.upper()} file is empty: {path.name}")
    except Exception as exc:
        friendly = _rewrite_tokenization_error(str(exc), kind)
        if friendly:
            raise ValueError(friendly) from exc
        raise ValueError(
            f"Failed to read {kind.upper()} file {path.name}: {exc}"
        ) from exc

    if df is None or df.empty:
        raise ValueError(f"Input {kind.upper()} file is empty: {path.name}")

    # ------------------------------------------------------------------
    # Wrong-delimiter detection: if we ended up with a single column
    # try to auto-sniff and re-read
    # ------------------------------------------------------------------
    if len(df.columns) == 1 and separator is None:
        col0 = str(df.columns[0])
        sniffed = _sniff_delimiter(text)
        if sniffed != sep and sniffed in col0:
            warnings.append(
                f"{kind.upper()} file appears to use '{sniffed}' as delimiter instead "
                f"of the expected '{sep}'. Re-reading with detected delimiter."
            )
            try:
                df2 = _do_read(sniffed)
                if df2 is not None and not df2.empty and len(df2.columns) > 1:
                    df = df2
                    sep = sniffed
            except Exception:
                pass  # stay with the single-column result; caller will get a human error

        # Warn about obvious wrong-delimiter hints even if we couldn't recover
        if len(df.columns) == 1:
            col0 = str(df.columns[0])
            if kind == "csv" and "\t" in col0:
                raise ValueError(
                    f"CSV file '{path.name}' appears to use tabs as delimiter. "
                    "Save as .tsv or select the tab separator."
                )
            if kind == "tsv":
                if ";" in col0:
                    raise ValueError(
                        f"TSV file '{path.name}' appears to use semicolons as delimiter. "
                        "Convert to tab-separated format."
                    )
                if "," in col0:
                    raise ValueError(
                        f"TSV file '{path.name}' appears to use commas as delimiter. "
                        "Save as .csv or convert to tab-separated format."
                    )

    return ReadResult(
        df=_strip_columns(df),
        encoding_used=enc_used,
        delimiter_used=sep,
        warnings=warnings,
    )
