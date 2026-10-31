"""A first look at a wide data table (.csv/.tsv/.xlsx): columns, the first rows, the likely ID column and the sheets.
One implementation for Studio's wide-to-long file preview and `prism_tools file-management raw-peek`."""

from __future__ import annotations

from pathlib import Path

SUPPORTED_SUFFIXES = {".csv", ".tsv", ".xlsx"}
PEEK_ROWS = 5


def read_wide_table(path: Path, sheet: str | int = 0):
    """The table as a DataFrame. Raises ValueError for any other format."""
    from src.converters.file_reader import read_tabular_file

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Supported formats: .csv, .tsv, .xlsx")
    return read_tabular_file(path, kind="xlsx" if suffix == ".xlsx" else suffix.lstrip("."), sheet=sheet).df


def peek_wide_table(path: Path, *, display_name: str | None = None, sheet: str = "") -> dict:
    """What Studio's preview shows. display_name is the name to report (an upload's own name, or the source
    path's name, not the temporary or annex-object file it was read from). Raises ValueError with a readable
    message for a system file, an unsupported format or an unreadable table."""
    from src.converters.file_reader import list_excel_sheets, resolve_sheet_selection
    from src.participants_id_selection import resolve_participants_id_selection
    from src.system_files import filter_system_files

    filtered = filter_system_files([display_name or path.name])
    if not filtered:
        raise ValueError("System files are not accepted.")
    filename = filtered[0]
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("Supported formats: .csv, .tsv, .xlsx")

    sheet_metadata = list_excel_sheets(path) if suffix == ".xlsx" else None
    resolved_sheet = resolve_sheet_selection(sheet.strip(), sheet_metadata)
    try:
        df = read_wide_table(path, sheet=resolved_sheet)
    except Exception as exc:
        raise ValueError(f"Could not parse file: {exc}") from exc

    id_resolution = resolve_participants_id_selection(
        [str(column) for column in df.columns], suffix, explicit_id_column=None
    )
    return {
        "filename": filename,
        "columns": list(df.columns),
        "rows": df.head(PEEK_ROWS).fillna("").astype(str).to_dict(orient="records"),
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "suggested_id_column": id_resolution.get("suggested_id_column"),
        "participant_id_found": bool(id_resolution.get("participant_id_found")),
        "id_selection_required": bool(id_resolution.get("id_selection_required")),
        "sheet_names": list((sheet_metadata or {}).get("sheet_names") or []),
        "non_empty_sheet_names": list((sheet_metadata or {}).get("non_empty_sheet_names") or []),
        "resolved_sheet": resolved_sheet,
    }
