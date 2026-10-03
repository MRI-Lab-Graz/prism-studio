"""Write DataFrames to .xlsx without turning text into live formulas.

openpyxl stores any string starting with '=' as a formula, so a participant's
free-text answer like =HYPERLINK(...) would execute when a colleague opens the
file. Cells are forced back to plain strings (data is kept as-is).

pandas is imported lazily: the validator image has no pandas, and
recipes_surveys.py imports this module at top level.
"""

from __future__ import annotations


def to_excel_safe(df, target, **kwargs) -> None:
    """`df.to_excel(target, **kwargs)` for a path or an openpyxl `ExcelWriter`."""
    import pandas as pd

    if not isinstance(target, pd.ExcelWriter):
        with pd.ExcelWriter(target, engine="openpyxl") as writer:
            to_excel_safe(df, writer, **kwargs)
        return
    df.to_excel(target, **kwargs)
    for row in target.sheets[kwargs.get("sheet_name", "Sheet1")].iter_rows():
        for cell in row:
            if cell.data_type == "f":
                cell.data_type = "s"
