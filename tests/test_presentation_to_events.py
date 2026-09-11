"""Tests for the Presentation .log -> BIDS events.tsv CLI orchestration.

Uses a minimal fake decoder rather than a real task-specific one: task
decoders (e.g. the NEMO/NID study's) bake in one study's own paradigm
quirks and are study-specific code, not a PRISM capability -- per
docs/PROJECT_OVERVIEW.md's src/ vs per-study code/ split, they live only in
that study's own code/ folder, not in this repo. These tests exercise only
convert_log_to_events'/write_task_sidecar's own orchestration logic: file
I/O, the customLog lookup, and threading data through whatever decoder is
injected.
"""

import json
import types
from pathlib import Path

from src.converters.presentation_to_events import (
    convert_log_to_events,
    find_custom_log,
    load_decoder,
    write_task_sidecar,
)

_LOG_TEXT = """Scenario -\t
Logfile written - 05/04/2012 13:58:56

Subject\tTrial\tEvent Type\tCode\tTime\tTTime\tUncertainty\tDuration\tUncertainty\tReqTime\tReqDur\tStim Type\tPair Index

nemo_01\t1\tPulse\t55\t100000\t0\t1
nemo_01\t2\tPicture\tfixation\t100500\t0\t2\t50000\t3\t0\t50000\tother\t0
nemo_01\t3\tPicture\tItem_1_1\t150500\t0\t1\t20000\t2\t0\t600000\tfalse_alarm\t11
nemo_01\t3\tResponse\t44\t155500\t5000\t1
"""


def _fake_decoder():
    """Minimal stand-in exposing the interface convert_log_to_events expects."""

    def enrich_events(df):
        out = df.copy()
        out["trial_type"] = out["raw_code"]
        return out

    def to_bids_events(df):
        out = df.copy()
        out["response_time"] = out["response_time_ms"]
        return out[["onset", "duration", "trial_type", "response_time"]]

    def build_events_sidecar():
        return {"StimulusPresentation": {"SoftwareName": "Presentation"}}

    def parse_item_bank(pcl_text):
        return {"raw_text": pcl_text}

    def parse_custom_log(text):
        return {"raw_text": text}

    def attach_response_correct(df, scores):
        out = df.copy()
        out["response_correct"] = scores.get("raw_text")
        return out

    return types.SimpleNamespace(
        enrich_events=enrich_events,
        to_bids_events=to_bids_events,
        build_events_sidecar=build_events_sidecar,
        parse_item_bank=parse_item_bank,
        parse_custom_log=parse_custom_log,
        attach_response_correct=attach_response_correct,
    )


def test_convert_log_to_events_writes_tsv_from_decoder_output(tmp_path):
    log_path = tmp_path / "sub-01_task-nid_events.log"
    log_path.write_text(_LOG_TEXT)

    tsv_path = convert_log_to_events(log_path, _fake_decoder(), output_dir=tmp_path)

    assert tsv_path == tmp_path / "sub-01_task-nid_events.tsv"
    header = tsv_path.read_text().splitlines()[0]
    assert header.split("\t") == ["onset", "duration", "trial_type", "response_time"]


def test_convert_log_to_events_missing_response_time_rendered_as_na(tmp_path):
    log_path = tmp_path / "sub-01_task-nid_events.log"
    log_path.write_text(_LOG_TEXT)

    tsv_path = convert_log_to_events(log_path, _fake_decoder(), output_dir=tmp_path)

    lines = tsv_path.read_text().splitlines()
    fixation_row = lines[1].split("\t")  # fixation row has no response
    assert fixation_row[0] == "0.05"  # onset, from the generic parser
    assert fixation_row[-1] == "n/a"  # response_time


def test_convert_log_to_events_writes_sidecar_from_decoder_by_default(tmp_path):
    log_path = tmp_path / "sub-01_task-nid_events.log"
    log_path.write_text(_LOG_TEXT)

    convert_log_to_events(log_path, _fake_decoder(), output_dir=tmp_path)

    sidecar = json.loads((tmp_path / "sub-01_task-nid_events.json").read_text())
    assert sidecar["StimulusPresentation"]["SoftwareName"] == "Presentation"


def test_convert_log_to_events_write_sidecar_false_skips_per_subject_json(tmp_path):
    # The sidecar is identical for every subject of a given task -- a batch
    # export should write it once at the dataset root (BIDS inheritance
    # principle) via write_task_sidecar(), not duplicate it per subject.
    log_path = tmp_path / "sub-01_task-nid_events.log"
    log_path.write_text(_LOG_TEXT)

    convert_log_to_events(log_path, _fake_decoder(), output_dir=tmp_path, write_sidecar=False)

    assert not (tmp_path / "sub-01_task-nid_events.json").exists()


def test_write_task_sidecar_writes_task_level_json(tmp_path):
    path = write_task_sidecar(tmp_path, task_label="nid", decoder=_fake_decoder())

    assert path == tmp_path / "task-nid_events.json"
    sidecar = json.loads(path.read_text())
    assert sidecar["StimulusPresentation"]["SoftwareName"] == "Presentation"


def test_convert_log_to_events_writes_item_bank_via_decoder(tmp_path):
    log_path = tmp_path / "sub-01_task-nid_events.log"
    log_path.write_text(_LOG_TEXT)
    pcl_path = tmp_path / "NID.pcl"
    pcl_path.write_text("some scenario source")

    convert_log_to_events(log_path, _fake_decoder(), pcl_path=pcl_path, output_dir=tmp_path)

    bank_path = tmp_path / "task-nid_stimuli.json"
    bank = json.loads(bank_path.read_text())
    assert bank["raw_text"] == "some scenario source"


def test_convert_log_to_events_does_not_rewrite_existing_item_bank(tmp_path):
    log_path = tmp_path / "sub-01_task-nid_events.log"
    log_path.write_text(_LOG_TEXT)
    pcl_path = tmp_path / "NID.pcl"
    pcl_path.write_text("some scenario source")
    bank_path = tmp_path / "task-nid_stimuli.json"
    bank_path.write_text('{"sentinel": true}')

    convert_log_to_events(log_path, _fake_decoder(), pcl_path=pcl_path, output_dir=tmp_path)

    assert bank_path.read_text() == '{"sentinel": true}'


def test_find_custom_log_locates_file_by_subject_id_across_dirs(tmp_path):
    dir_a = tmp_path / "log"
    dir_b = tmp_path / "log copy"
    dir_a.mkdir()
    dir_b.mkdir()
    (dir_b / "nemo_01.txt").write_text("run\titem_index\n")

    found = find_custom_log("nemo_01", [dir_a, dir_b])

    assert found == dir_b / "nemo_01.txt"


def test_find_custom_log_returns_none_when_absent(tmp_path):
    assert find_custom_log("nemo_99", [tmp_path]) is None


def test_convert_log_to_events_threads_custom_log_text_through_decoder(tmp_path):
    log_path = tmp_path / "sub-01_task-nid_events.log"
    log_path.write_text(_LOG_TEXT)
    custom_log_dir = tmp_path / "log"
    custom_log_dir.mkdir()
    (custom_log_dir / "nemo_01.txt").write_text("some custom log content")

    tsv_path = convert_log_to_events(
        log_path, _fake_decoder(), output_dir=tmp_path, custom_log_dirs=[custom_log_dir]
    )

    lines = tsv_path.read_text().splitlines()
    header = lines[0].split("\t")
    row = lines[1].split("\t")
    assert row[header.index("response_correct")] == "some custom log content"


def test_convert_log_to_events_missing_custom_log_leaves_decoder_untouched(tmp_path):
    log_path = tmp_path / "sub-01_task-nid_events.log"
    log_path.write_text(_LOG_TEXT)
    empty_dir = tmp_path / "log"
    empty_dir.mkdir()

    tsv_path = convert_log_to_events(
        log_path, _fake_decoder(), output_dir=tmp_path, custom_log_dirs=[empty_dir]
    )

    header = tsv_path.read_text().splitlines()[0].split("\t")
    assert "response_correct" not in header  # attach_response_correct never called


def test_load_decoder_imports_module_from_file_path(tmp_path):
    decoder_path = tmp_path / "fake_decoder.py"
    decoder_path.write_text("SENTINEL = 'loaded'\n")

    module = load_decoder(decoder_path)

    assert module.SENTINEL == "loaded"
