"""Decide, per response and target file, whether an import would duplicate or clash.

Identity of a LimeSurvey response in the project is the (startdate, seed, token)
fingerprint recorded in the project's code/survey_imports.json ledger (outside
the PRISM-checked BIDS folders).
"""

import json

from src.survey_existing import LEDGER, ImportIndex, record_imports, row_fingerprint


def _tool_file(root, sub, ses, **fields):
    record_imports(root, root, [(sub, ses, row_fingerprint(fields, fields))])


FP = {"startdate": "2026-01-01 10:00:00", "seed": "111", "token": "abc"}


def test_row_fingerprint_uses_present_columns_and_n_a_for_missing():
    row = {"startdate": "2026-01-01 10:00:00", "seed": None, "token": "abc", "x": 1}
    assert row_fingerprint(row, ["startdate", "seed", "token"]) == (
        "2026-01-01 10:00:00", "n/a", "abc",
    )


def test_free_slot_is_imported(tmp_path):
    idx = ImportIndex(tmp_path)
    assert idx.classify("sub-1", "ses-1", row_fingerprint(FP, FP), target_exists=False) == "import"


def test_same_response_already_imported_is_skipped(tmp_path):
    _tool_file(tmp_path, "sub-1", "ses-1", **FP)
    idx = ImportIndex(tmp_path)
    fp = row_fingerprint(FP, FP)
    assert idx.classify("sub-1", "ses-1", fp, target_exists=True) == "skip_imported"


def test_recorded_response_is_skipped_even_when_a_questionnaire_file_is_missing(tmp_path):
    # e.g. a sociodemographic questionnaire the project never had: it must not make the response "new"
    _tool_file(tmp_path, "sub-1", "ses-1", **FP)
    idx = ImportIndex(tmp_path)
    fp = row_fingerprint(FP, FP)
    assert idx.classify("sub-1", "ses-1", fp, target_exists=False) == "skip_imported"


def test_different_response_in_taken_slot_is_a_conflict(tmp_path):
    _tool_file(tmp_path, "sub-1", "ses-1", **FP)
    idx = ImportIndex(tmp_path)
    other = row_fingerprint({**FP, "seed": "999"}, FP)
    assert idx.classify("sub-1", "ses-1", other, target_exists=True) == "conflict"


def test_response_found_under_another_session_is_a_session_mismatch(tmp_path):
    _tool_file(tmp_path, "sub-1", "ses-2", **FP)
    idx = ImportIndex(tmp_path)
    fp = row_fingerprint(FP, FP)
    assert idx.classify("sub-1", "ses-3", fp, target_exists=False) == "moved"
    assert idx.where_imported("sub-1", fp) == "ses-2"


def test_taken_slot_without_ledger_entry_is_skipped_unverified(tmp_path):
    idx = ImportIndex(tmp_path)
    assert idx.classify("sub-1", "ses-1", row_fingerprint(FP, FP), target_exists=True) == "skip_unverified"


def test_record_imports_merges_into_the_project_ledger_written_to_the_output_root(tmp_path):
    project, scratch = tmp_path / "project", tmp_path / "scratch"
    fp1, fp2 = row_fingerprint(FP, FP), row_fingerprint({**FP, "seed": "2"}, FP)
    record_imports(project, project, [("sub-1", "ses-1", fp1)])
    record_imports(project, scratch, [("sub-2", "ses-1", fp2)])
    merged = json.loads((scratch / LEDGER).read_text(encoding="utf-8"))
    assert merged["responses"] == {
        "sub-1": {"ses-1": list(fp1)},
        "sub-2": {"ses-1": list(fp2)},
    }
    assert ImportIndex(scratch).where_imported("sub-2", fp2) == "ses-1"


def test_session_labels_are_kept_exactly(tmp_path):
    fp = row_fingerprint(FP, FP)
    record_imports(tmp_path, tmp_path, [("sub-1", "ses-1", fp), ("sub-1", "ses-01", fp)])
    stored = json.loads((tmp_path / LEDGER).read_text(encoding="utf-8"))["responses"]["sub-1"]
    assert set(stored) == {"ses-1", "ses-01"}


def test_ledger_is_not_inside_a_prism_checked_folder():
    assert LEDGER.parts[0] == "code"


def test_review_table_hides_responses_already_in_the_project_but_keeps_the_numbering(tmp_path):
    import pandas as pd

    from src.participants_sessions import session_assignment_table

    cols = ["startdate", "seed", "token"]
    rows = [
        {"id": "1", "token": "a", "seed": "1", "startdate": "2026-03-01 09:00:00", "submitdate": "x", "lastpage": "6"},
        {"id": "2", "token": "a", "seed": "2", "startdate": "2026-09-01 09:00:00", "submitdate": "x", "lastpage": "6"},
    ]
    record_imports(tmp_path, tmp_path, [("sub-a", "ses-1", row_fingerprint(rows[0], cols))])

    shown, warnings = session_assignment_table(pd.DataFrame(rows), "token", imported_root=tmp_path)

    assert [(r["response_id"], r["session"]) for r in shown] == [("2", "2")]
    assert any("1 response(s) already in the project" in w for w in warnings)
