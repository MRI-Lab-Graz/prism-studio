"""Convert a Neurobehavioral Systems Presentation .log file to a BIDS-valid,
enriched *_events.tsv (+ sidecar *_events.json), decoding raw event codes
via a task-specific decoder module supplied by the caller.

This module is deliberately task-agnostic: it knows the generic Presentation
.log format (via presentation_log.py) and the BIDS output shape, but not
what any particular study's event codes mean. A task decoder module (see
`load_decoder`'s docstring for the required interface) is study-specific
code -- it belongs in that study's own project, not in this repo.

Usage:
    python src/converters/presentation_to_events.py \\
        sub-NEMO01_ses-1_task-nemo_acq-singleband_run-01_events.log \\
        --decoder /path/to/that/study/code/presentation_tasks/nemo_nid.py \\
        --pcl NID_h/NID.pcl
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import List, Optional

from src.bids_entity_parser import BidsEntityParser
from src.converters.presentation_log import extract_subject_id, parse_presentation_log


def _task_label_from_filename(name: str) -> Optional[str]:
    for part in Path(name).stem.split("_"):
        parsed = BidsEntityParser.parse_entity_token(part)
        if parsed and parsed[0] == "task":
            return parsed[1]
    return None


def find_custom_log(subject_id: str, search_dirs: List[Path]) -> Optional[Path]:
    """Locate a task's customLog file (e.g. NID.pcl's log/<subject_id>.txt).

    Checks search_dirs in order and returns the first match, or None.
    """
    for directory in search_dirs:
        candidate = Path(directory) / f"{subject_id}.txt"
        if candidate.exists():
            return candidate
    return None


def load_decoder(decoder_path: Path) -> ModuleType:
    """Dynamically import a task decoder module from a .py file path.

    A decoder module must expose:
        enrich_events(df) -> df
        to_bids_events(df) -> df
        build_events_sidecar() -> dict
        parse_item_bank(pcl_text) -> dict
        parse_custom_log(text) -> dict
        attach_response_correct(df, scores) -> df

    See e.g. a study's own code/<...>/presentation_tasks/<task>.py.
    """
    decoder_path = Path(decoder_path)
    spec = importlib.util.spec_from_file_location(decoder_path.stem, decoder_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_task_sidecar(output_dir: Path, task_label: str, decoder: ModuleType) -> Path:
    """Write one task-<label>_events.json at output_dir (BIDS root or a
    task subdirectory), covering every subject's events.tsv for that task
    via BIDS's inheritance principle -- the sidecar has no per-subject
    content, so a copy in every subject's folder would just be duplication.
    """
    path = Path(output_dir) / f"task-{task_label}_events.json"
    path.write_text(json.dumps(decoder.build_events_sidecar(), indent=2) + "\n", encoding="utf-8")
    return path


def convert_log_to_events(
    log_path: Path,
    decoder: ModuleType,
    pcl_path: Optional[Path] = None,
    output_dir: Optional[Path] = None,
    custom_log_dirs: Optional[List[Path]] = None,
    write_sidecar: bool = True,
) -> Path:
    """Convert one subject's Presentation .log into events.tsv (+ sidecar).

    decoder is a task-specific decoder module (see load_decoder's
    docstring for the required interface).

    When pcl_path is given, also writes a shared task-<label>_stimuli.json
    item bank (see decoder.parse_item_bank) -- written once per task, not
    once per subject, since its content doesn't vary by subject.

    When custom_log_dirs is given, looks for this subject's companion
    customLog file (see decoder.parse_custom_log) across those directories
    and, if found, attaches response_correct. Silently leaves that column
    absent if no matching file is found.

    write_sidecar controls whether a per-subject *_events.json is also
    written next to the tsv (the default, for a single standalone
    conversion). A batch export covering a whole task should instead pass
    write_sidecar=False and call write_task_sidecar() once at the dataset
    root -- the sidecar is identical for every subject of a given task.

    Returns the path to the written events.tsv.
    """
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    generic_df = parse_presentation_log(log_text)
    events_df = decoder.to_bids_events(decoder.enrich_events(generic_df))

    if custom_log_dirs:
        subject_id = extract_subject_id(log_text)
        custom_log_path = find_custom_log(subject_id, custom_log_dirs) if subject_id else None
        if custom_log_path is not None:
            scores = decoder.parse_custom_log(custom_log_path.read_text(encoding="utf-8", errors="replace"))
            events_df = decoder.attach_response_correct(events_df, scores)

    output_dir = Path(output_dir) if output_dir else log_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = log_path.stem  # e.g. "sub-NEMO01_..._events"

    tsv_path = output_dir / f"{stem}.tsv"
    events_df.to_csv(tsv_path, sep="\t", index=False, na_rep="n/a")

    if write_sidecar:
        json_path = output_dir / f"{stem}.json"
        json_path.write_text(json.dumps(decoder.build_events_sidecar(), indent=2) + "\n", encoding="utf-8")

    if pcl_path is not None:
        task_label = _task_label_from_filename(log_path.name) or "unknown"
        bank_path = output_dir / f"task-{task_label}_stimuli.json"
        if not bank_path.exists():
            bank = decoder.parse_item_bank(pcl_path.read_text(encoding="utf-8", errors="replace"))
            bank_path.write_text(json.dumps(bank, indent=2) + "\n", encoding="utf-8")

    return tsv_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a Presentation .log file to a BIDS events.tsv/json"
    )
    parser.add_argument("log_path", type=Path, help="Path to the subject's *_events.log file")
    parser.add_argument(
        "--decoder",
        type=Path,
        required=True,
        help="Path to the task-specific decoder .py module (see load_decoder's docstring for the required interface)",
    )
    parser.add_argument(
        "--pcl",
        type=Path,
        default=None,
        help="Path to the matching .pcl scenario script, to also write the item-bank companion file",
    )
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output directory (default: alongside the .log)")
    parser.add_argument(
        "--custom-log-dir",
        dest="custom_log_dirs",
        type=Path,
        action="append",
        default=None,
        help="Directory to search for this subject's customLog companion file (repeatable)",
    )
    parser.add_argument(
        "--no-sidecar",
        dest="write_sidecar",
        action="store_false",
        help="Skip writing a per-subject *_events.json (use write_task_sidecar() once instead, for a batch export)",
    )

    args = parser.parse_args()
    if not args.log_path.exists():
        print(f"Error: file not found: {args.log_path}")
        sys.exit(1)

    decoder = load_decoder(args.decoder)
    tsv_path = convert_log_to_events(
        args.log_path,
        decoder,
        pcl_path=args.pcl,
        output_dir=args.output,
        custom_log_dirs=args.custom_log_dirs,
        write_sidecar=args.write_sidecar,
    )
    print(f"Wrote {tsv_path}")


if __name__ == "__main__":
    main()
