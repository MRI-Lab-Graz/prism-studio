"""Import the biosample template into a project: one TSV + sidecar per subject/session/run/panel."""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.biosample_template import _SCHEMA
from src.biosample_template_reader import read_template
from src.participant_ids import normalize_participant_id
from src.session_map import SessionMapError, resolve_import_session
from src.subject_id_matching import load_existing_participant_ids
from src.term_registry import load_registry, resolve_column

_LABEL = re.compile(r"[A-Za-z0-9]+")
_RUN = re.compile(r"[0-9]+")  # kept as written ("01" stays "01")
_BAD = object()  # a session label that could not be resolved
_SAMPLE_COLUMNS = {
    "sample_id": {"Description": "Lab tube ID (pseudonymous)", "Units": "n/a", "DataType": "string"},
    "collection_time": {"Description": "Clock time of the sample, hh:mm only (never a date)",
                        "Units": "hh:mm", "DataType": "string"},
}
_TECHNICAL = ("SpecimenType", "CollectionMethod", "Anticoagulant", "FastingRequired",
              "StorageTemperature", "Laboratory", "AssayMethod", "AssayKit")


@dataclass
class ImportResult:
    written: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _column(analyte: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", analyte.lower()).strip("_")


def _technical(panel: dict, schema_tech: dict) -> dict:
    """The panels-sheet fields as sidecar values; ValueError names the bad field."""
    out: dict = {}
    for key in _TECHNICAL:
        text = panel.get(key) or ""
        if not text:
            continue
        allowed = schema_tech.get(key, {}).get("enum")
        if allowed and text not in allowed:
            raise ValueError(f"{key} {text!r} is not one of {', '.join(v for v in allowed if v)}")
        if key == "FastingRequired":
            if text.lower() not in ("true", "false"):
                raise ValueError(f"FastingRequired {text!r} must be true or false")
            out[key] = text.lower() == "true"
        elif key == "StorageTemperature":
            try:
                num = float(text.replace(",", "."))
            except ValueError:
                raise ValueError(f"StorageTemperature {text!r} is not a number") from None
            out[key] = int(num) if num.is_integer() else num
        else:
            out[key] = text
    return out


def _creation_date(existing: Path) -> str:
    """An overwritten sidecar keeps its CreationDate (re-import is byte-identical on any day)."""
    try:
        date = json.loads(existing.read_text(encoding="utf-8"))["Metadata"]["CreationDate"]
        if isinstance(date, str) and date:
            return date
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return dt.date.today().isoformat()


def _sidecar(name: str, panel: dict, technical: dict, columns: dict, schema_version: str,
             creation_date: str) -> dict:
    study = {"BiosampleName": name}
    if panel.get("Description"):
        study["Description"] = panel["Description"]
    return {"Technical": technical, "Study": study,
            "Metadata": {"SchemaVersion": schema_version, "CreationDate": creation_date},
            **columns}


def _write_all(files: dict[Path, str]) -> None:
    """Write every file to a temp file, then move each into place.

    All checks run before this is called, and a failure while writing the temp files removes
    them and leaves the project unchanged. The final moves are atomic per file, not across files.
    """
    temps: list[tuple[str, Path]] = []
    try:
        for path, text in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
            temps.append((tmp, path))
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(text)
    except BaseException:
        for tmp, _ in temps:
            Path(tmp).unlink(missing_ok=True)
        raise
    for tmp, path in temps:
        os.replace(tmp, path)


def import_biosample(input_path: Path, project: Path, specimen: str | None = None,
                     overwrite: bool = False, dry_run: bool = False) -> ImportResult:
    """Pivot the template's measurements into biosample files of ``project``."""
    project = Path(project)
    res = ImportResult()
    if not project.is_dir():
        res.errors.append(f"{project}: not a directory")
        return res
    rows, panels, problems = read_template(Path(input_path), specimen)
    if problems:
        res.errors = problems
        return res

    schema = json.loads(_SCHEMA.read_text(encoding="utf-8"))
    schema_tech = schema["properties"]["Technical"]["properties"]
    registry = load_registry("biosample")
    known = load_existing_participant_ids(project)
    sessions: dict[str, str | None] = {}

    # (sub, ses, run, panel) -> {(sample_id, time): {analyte: (value, row)}}
    groups: dict[tuple, dict[tuple, dict[str, tuple[str, int]]]] = {}
    for row in rows:
        n = row["row"]
        sub = normalize_participant_id(row["participant_id"])
        if not sub:
            res.errors.append(f"data row {n}: participant_id {row['participant_id']!r} has no letters or digits")
            continue
        label = row["session"]
        if label not in sessions:
            try:
                target, message = resolve_import_session(project, label)
            except SessionMapError as exc:
                res.errors.append(f"data row {n}: session {label!r}: {exc}")
                target, message = _BAD, None
            if message:
                res.warnings.append(message)
            sessions[label] = target if target is not None else label  # not a PRISM project: keep the label
        ses = sessions[label]
        if ses is _BAD:
            continue  # reported once, at its first row
        for what, value, rule, need in (("session", ses, _LABEL, "letters and digits only"),
                                        ("panel", row["panel"], _LABEL, "letters and digits only"),
                                        ("run", row["run"], _RUN, "a number (run index)")):
            if value and not rule.fullmatch(value):
                res.errors.append(f"data row {n}: {what} {value!r} must be {need}")
                break
        else:
            sample = groups.setdefault((sub, ses, row["run"], row["panel"]), {}).setdefault(
                (row["sample_id"], row["collection_time"]), {})
            analyte = row["analyte"]
            if analyte in sample:
                res.errors.append(f"data rows {sample[analyte][1]} and {n}: {analyte} measured twice "
                                  f"for {sub}, sample {row['sample_id'] or '(none)'}")
            else:
                sample[analyte] = (row["value"], n)

    # one sidecar entry per analyte per panel (the reader already refused two units)
    units = {(r["panel"], r["analyte"]): r["unit"] for r in rows if r["unit"]}
    definitions: dict[str, dict[str, dict]] = {}
    technicals: dict[str, dict] = {}
    for name, panel in panels.items():
        try:
            technicals[name] = _technical(panel, schema_tech)
        except ValueError as exc:
            res.errors.append(f"panels: panel {name}: {exc}")
            continue
        spec = technicals[name]["SpecimenType"]
        cols: dict[str, dict] = {}
        for analyte in dict.fromkeys(r["analyte"] for r in rows if r["panel"] == name):
            col = _column(analyte)
            if not col or col in _SAMPLE_COLUMNS or col in cols:
                res.errors.append(f"panel {name}: analyte {analyte!r} gives column name {col!r}, "
                                  "which is empty or already used; rename the analyte")
                continue
            entry: dict = {"Description": analyte}
            hit = resolve_column(registry, col, {"Term": analyte}, spec)
            if hit.kind == "specimen_mismatch":
                res.errors.append(f"panel {name}: {hit.message}")
                continue
            if hit.message:
                res.warnings.append(f"panel {name}: {hit.message}")
            term_unit = (hit.term or {}).get("Units")
            unit = units.get((name, analyte)) or term_unit
            if unit:
                entry["Units"] = unit
            if hit.term:
                entry["Term"] = hit.term["TermID"]
            elif not unit:
                res.errors.append(f"panel {name}: analyte {analyte!r} has no unit and no term "
                                  "in the registry; fill in its unit")
                continue
            if term_unit and unit != term_unit:
                res.warnings.append(f"panel {name}: {analyte} is in {unit}; the term's recommended unit "
                                    f"is {term_unit} (accepted, not converted)")
            limits = panel["limits"].get(analyte)
            if limits:
                entry["LowerLimitOfDetection"] = max(limits)
            cols[col] = entry
        definitions[name] = cols

    for sub in sorted({key[0] for key in groups} - known):
        res.warnings.append(f"{sub} is not in participants.tsv; written anyway, participants.tsv is not changed")

    files: dict[Path, str] = {}
    for (sub, ses, run, name), samples in groups.items():
        if name not in definitions:
            continue
        cols = definitions[name]
        analytes = {_column(a): a for s in samples.values() for a in s}
        analyte_cols = [c for c in cols if c in analytes]
        sample_cols = [c for i, c in enumerate(_SAMPLE_COLUMNS) if any(k[i] for k in samples)]
        lines = ["\t".join(sample_cols + analyte_cols)]
        for key, values in samples.items():
            cells = [key[list(_SAMPLE_COLUMNS).index(c)] or "n/a" for c in sample_cols]
            cells += [values[analytes[c]][0] if analytes[c] in values else "n/a" for c in analyte_cols]
            lines.append("\t".join(cells))
        folder = Path(sub) / (f"ses-{ses}" if ses else "") / "biosample"
        stem = "_".join(p for p in (sub, f"ses-{ses}" if ses else "", f"biosample-{name}",
                                    f"run-{run}" if run else "", "biosample") if p)
        side = _sidecar(name, panels[name], technicals[name],
                        {**{c: _SAMPLE_COLUMNS[c] for c in sample_cols}, **{c: cols[c] for c in analyte_cols}},
                        schema["version"], _creation_date(project / folder / f"{stem}.json"))
        files[folder / f"{stem}.tsv"] = "\n".join(lines) + "\n"
        files[folder / f"{stem}.json"] = json.dumps(side, indent=2, ensure_ascii=False) + "\n"

    if not overwrite:
        res.skipped = [p.as_posix() for p in files if (project / p).exists()]
        if res.skipped:
            res.errors.append(f"{len(res.skipped)} file(s) already exist; nothing was written "
                              "(pass --overwrite to replace them): " + ", ".join(res.skipped))
    if res.errors:
        return res
    if not dry_run:
        _write_all({project / p: text for p, text in files.items()})
    res.written = [p.as_posix() for p in files]
    return res
