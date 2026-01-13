from pathlib import Path
import json
import csv
from typing import Any

def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path

def read_json(path: Path) -> dict[str, Any]:
    """Read JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: Path, obj: dict[str, Any]) -> None:
    """Write JSON file with indentation."""
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def read_tsv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read TSV file into header and list of dicts."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        header = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return header, rows

def write_tsv_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    """Write list of dicts to TSV file."""
    ensure_dir(path.parent)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=header, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "n/a") for k in header})
