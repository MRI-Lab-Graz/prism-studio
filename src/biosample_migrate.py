"""Reshape a legacy wide blood-sample sheet into the biosample Excel template."""

from __future__ import annotations

from pathlib import Path

from src.converters.file_reader import read_tabular_file


class MigrationError(ValueError):
    """A readable reason why the legacy sheet cannot be migrated."""


def read_legacy_wide(path: Path):
    """Read .csv/.tsv/.xlsx with every cell as text.

    Legacy export quirk: each line is one quoted CSV cell holding tab-separated
    fields, so the reader sees one column whose header contains tabs; split it.
    """
    import pandas as pd

    try:
        try:
            df = read_tabular_file(path).df
        except ValueError as exc:
            if "tabs as delimiter" not in str(exc):
                raise
            # the quirk file: read it as one column (a separator that never occurs)
            df = read_tabular_file(path, separator="\x1f").df
    except (ValueError, OSError) as exc:
        raise MigrationError(f"Cannot read {Path(path).name}: {exc}") from exc
    if len(df.columns) == 1 and "\t" in str(df.columns[0]):
        names = [c.strip() for c in str(df.columns[0]).split("\t")]
        rows = [str(v).split("\t") for v in df.iloc[:, 0].fillna("")]
        rows = [(r + [""] * len(names))[: len(names)] for r in rows]
        df = pd.DataFrame(rows, columns=names, dtype=str)
    return df


def repair_mojibake(text: str) -> str:
    """Undo Mac-Roman-decoded UTF-8 (`¬µU/ml` -> `µU/ml`); else return text unchanged."""
    try:
        return text.encode("mac_roman").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
