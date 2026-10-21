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
    assert any("1 response(s) already handled" in w for w in warnings)


def test_review_table_keeps_imported_responses_with_a_manual_session_override(tmp_path):
    import pandas as pd

    from src.participants_sessions import session_assignment_table

    cols = ["startdate", "seed", "token"]
    rows = [
        {"id": "1", "token": "a", "seed": "1", "startdate": "2026-03-01 09:00:00", "submitdate": "x", "lastpage": "6"},
        {"id": "2", "token": "b", "seed": "2", "startdate": "2026-03-02 09:00:00", "submitdate": "x", "lastpage": "6"},
    ]
    record_imports(tmp_path, tmp_path, [(f"sub-{r['token']}", "ses-1", row_fingerprint(r, cols)) for r in rows])

    shown, warnings = session_assignment_table(
        pd.DataFrame(rows), "token", decisions={"1": {"session": "pre"}}, imported_root=tmp_path
    )

    assert [(r["response_id"], r["session"], r["reason"]) for r in shown] == [("1", "pre", "override")]
    assert any("1 response(s) already handled" in w for w in warnings)


def test_ledger_remembers_every_response_seen_with_its_state(tmp_path):
    record_imports(tmp_path, tmp_path, [], seen={"7": ["", "2"]}, survey_id="999")
    record_imports(tmp_path, tmp_path, [], seen={"8": ["x", "6"]}, survey_id="999")  # merges
    idx = ImportIndex(tmp_path)
    assert idx.is_seen("999", "7", ["", "2"])
    assert idx.is_seen("999", "8", ["x", "6"])
    assert not idx.is_seen("999", "7", ["2026-03-01 10:00:00", "6"])  # finished since: new data
    assert not idx.is_seen("other-survey", "7", ["", "2"])


def test_review_table_shows_only_new_data_but_all_of_it_skipped_or_not(tmp_path):
    import pandas as pd

    from src.participants_sessions import session_assignment_table

    cols = ["startdate", "seed", "token"]
    rows = [
        {"id": "1", "token": "a", "seed": "1", "startdate": "2026-03-01 09:00:00", "submitdate": "", "lastpage": "2"},
        {"id": "2", "token": "a", "seed": "2", "startdate": "2026-03-01 09:05:00", "submitdate": "x", "lastpage": "6"},
        {"id": "3", "token": "b", "seed": "3", "startdate": "2026-03-02 09:00:00", "submitdate": "", "lastpage": "2"},
        {"id": "4", "token": "a", "seed": "4", "startdate": "2026-09-01 09:00:00", "submitdate": "", "lastpage": "1"},
        {"id": "5", "token": "c", "seed": "5", "startdate": "2026-03-03 09:00:00", "submitdate": "x", "lastpage": "6"},
    ]
    record_imports(
        tmp_path, tmp_path, [("sub-a", "ses-1", row_fingerprint(rows[1], cols))],
        seen={"1": ["", "2"], "2": ["x", "6"], "3": ["", "2"], "5": ["", "2"]}, survey_id="999",
    )

    shown, warnings = session_assignment_table(
        pd.DataFrame(rows), "token", imported_root=tmp_path, survey_id="999"
    )

    # 1-3 were reviewed before; 4 is a new unfinished attempt (shown, skipped); 5 was unfinished then, finished now
    assert [(r["response_id"], r["session"]) for r in shown] == [("4", None), ("5", "1")]
    assert any("3 response(s) already handled" in w for w in warnings)
