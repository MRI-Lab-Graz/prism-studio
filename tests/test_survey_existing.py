"""Decide, per response and target file, whether an import would duplicate or clash.

Identity of a LimeSurvey response in the project is the (startdate, seed, token)
fingerprint stored in its sub-X_ses-N_tool-limesurvey_survey.tsv.
"""

from src.survey_existing import ImportIndex, row_fingerprint


def _tool_file(root, sub, ses, **fields):
    d = root / sub / ses / "survey"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sub}_{ses}_tool-limesurvey_survey.tsv").write_text(
        "\t".join(fields) + "\n" + "\t".join(fields.values()) + "\n", encoding="utf-8"
    )


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


def test_same_response_new_survey_for_that_session_is_imported(tmp_path):
    _tool_file(tmp_path, "sub-1", "ses-1", **FP)
    idx = ImportIndex(tmp_path)
    fp = row_fingerprint(FP, FP)
    assert idx.classify("sub-1", "ses-1", fp, target_exists=False) == "import"


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


def test_taken_slot_without_tool_file_is_skipped_unverified(tmp_path):
    idx = ImportIndex(tmp_path)
    assert idx.classify("sub-1", "ses-1", row_fingerprint(FP, FP), target_exists=True) == "skip_unverified"
