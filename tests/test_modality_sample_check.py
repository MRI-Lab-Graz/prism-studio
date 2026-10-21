import gzip
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "app", "src"))

from src.modality_contribution import (  # noqa: E402
    check_sample,
    errors_only,
    read_proposal,
    sample_extension,
)

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "modality_proposal"
HEADER = "sample_id\tdraw_time\tfasting\tcrp\tglucose\tcortisol"
ROW = "S001\t08:15\tyes\t1.2\t5.1\t310"


def _proposal(**over) -> dict:
    p = read_proposal(EXAMPLE_DIR / "bloodwork.yml")
    p.update(over)
    return p


def _sample(tmp_path: Path, text: str, name: str = "sample.tsv") -> Path:
    f = tmp_path / name
    f.write_bytes(text.encode("utf-8"))
    return f


def _msgs(problems) -> str:
    return " | ".join(f"{p.where}: {p.message}" for p in errors_only(problems))


def test_example_sample_is_clean() -> None:
    assert check_sample(_proposal(), EXAMPLE_DIR / "bloodwork_sample.tsv") == []


def test_header_mismatch_lists_missing_and_extra_columns(tmp_path: Path) -> None:
    f = _sample(tmp_path, "sample_id\textra\nS1\tx\n")
    msg = _msgs(check_sample(_proposal(), f))
    assert "missing column(s)" in msg and "draw_time" in msg
    assert "unexpected column(s)" in msg and "extra" in msg


def test_value_problems_name_row_and_column(tmp_path: Path) -> None:
    f = _sample(tmp_path, f"{HEADER}\n{ROW}\nS002\t09:00\tmaybe\t-3\tabc\t1\n")
    msg = _msgs(check_sample(_proposal(), f))
    assert "row 2" in msg and "'fasting'" in msg and "maybe" in msg  # not allowed
    assert "row 2" in msg and "'crp'" in msg and "below Min" in msg
    assert "'glucose'" in msg and "not a number" in msg


def test_row_with_wrong_cell_count_is_reported(tmp_path: Path) -> None:
    f = _sample(tmp_path, f"{HEADER}\nS001\t08:15\n")
    assert "2 cells" in _msgs(check_sample(_proposal(), f))


def test_too_many_rows_is_an_error(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + "\n" + "\n".join([ROW] * 51) + "\n")
    assert "more than 50" in _msgs(check_sample(_proposal(), f))


def test_fifty_rows_is_fine(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + "\n" + "\n".join([ROW] * 50) + "\n")
    assert errors_only(check_sample(_proposal(), f)) == []


def test_file_over_one_megabyte_is_an_error(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + "\n" + ROW + "\n" + "#" * 1_000_001)
    assert "too large" in _msgs(check_sample(_proposal(), f))


def test_excel_style_bom_and_crlf_do_not_break_the_header(tmp_path: Path) -> None:
    f = tmp_path / "sample.tsv"
    f.write_bytes(("﻿" + HEADER + "\r\n" + ROW + "\r\n").encode("utf-8"))
    assert check_sample(_proposal(), f) == []


def test_empty_cells_and_na_are_not_type_errors(tmp_path: Path) -> None:
    f = _sample(tmp_path, f"{HEADER}\nS001\tn/a\t\t\tn/a\t310\n")
    assert errors_only(check_sample(_proposal(), f)) == []


def test_gzip_and_uppercase_extension_are_accepted(tmp_path: Path) -> None:
    p = _proposal(extensions=["tsv", "tsv.gz"])
    gz = tmp_path / "SAMPLE.TSV.GZ"
    gz.write_bytes(gzip.compress((HEADER + "\n" + ROW + "\n").encode("utf-8")))
    assert check_sample(p, gz) == []
    upper = _sample(tmp_path, HEADER + "\n" + ROW + "\n", name="SAMPLE.TSV")
    assert check_sample(p, upper) == []
    assert sample_extension(gz, p["extensions"]) == "tsv.gz"


def test_undeclared_extension_and_missing_file_are_errors(tmp_path: Path) -> None:
    assert "extension must be one of" in _msgs(check_sample(_proposal(), _sample(tmp_path, "x", "s.csv")))
    assert "not found" in _msgs(check_sample(_proposal(), tmp_path / "nope.tsv"))


def test_non_tabular_sample_is_only_checked_for_existence_and_extension(tmp_path: Path) -> None:
    p = _proposal(extensions=["edf"])
    f = tmp_path / "recording.edf"
    f.write_bytes(b"\x00\x01binary")
    assert check_sample(p, f) == []


def test_subject_column_other_than_sub_01_is_an_error(tmp_path: Path) -> None:
    cols = _proposal()["columns"] + [{
        "id": "participant_id", "description": "d", "units": "n/a",
        "datatype": "string", "min": None, "max": None, "allowed_values": None,
    }]
    f = _sample(tmp_path, HEADER + "\tparticipant_id\n" + ROW + "\tsub-17\n")
    msg = _msgs(check_sample(_proposal(columns=cols), f))
    assert "participant_id" in msg and "sub-01" in msg


def test_identifier_like_column_and_email_value_are_warnings(tmp_path: Path) -> None:
    cols = _proposal()["columns"] + [{
        "id": "patient_name", "description": "d", "units": "n/a",
        "datatype": "string", "min": None, "max": None, "allowed_values": None,
    }]
    f = _sample(tmp_path, HEADER + "\tpatient_name\n" + ROW + "\tjane@example.org\n")
    problems = check_sample(_proposal(columns=cols), f)
    assert errors_only(problems) == []
    text = " | ".join(str(p) for p in problems)
    assert "identifier" in text and "e-mail" in text


def test_huge_single_line_is_an_error_not_a_crash(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + "\n" + "x" * 200_000 + "\n")
    assert "cannot read file" in _msgs(check_sample(_proposal(), f))


def test_gzip_bomb_is_an_error_not_a_crash(tmp_path: Path) -> None:
    p = _proposal(extensions=["tsv", "tsv.gz"])
    gz = tmp_path / "bomb.tsv.gz"
    gz.write_bytes(gzip.compress(b"a" * 5_000_000))
    assert "larger than" in _msgs(check_sample(p, gz))


def test_corrupt_gzip_body_is_an_error_not_a_crash(tmp_path: Path) -> None:
    p = _proposal(extensions=["tsv", "tsv.gz"])
    raw = bytearray(gzip.compress((HEADER + "\n" + ROW + "\n").encode("utf-8")))
    for i in range(12, 20):
        raw[i] = 0xFF
    gz = tmp_path / "bad.tsv.gz"
    gz.write_bytes(bytes(raw))
    assert "cannot read file" in _msgs(check_sample(p, gz))


def test_duplicate_header_column_is_an_error(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + "\tcrp\n" + ROW + "\t1.0\n")
    msg = _msgs(check_sample(_proposal(), f))
    assert "duplicate column(s)" in msg and "crp" in msg


def test_blank_lines_are_not_rows(tmp_path: Path) -> None:
    assert check_sample(_proposal(), _sample(tmp_path, HEADER + "\n" + ROW + "\n\n")) == []
    between = _sample(tmp_path, HEADER + "\n" + ROW + "\n\n  \t \n" + ROW + "\n", name="b.tsv")
    assert check_sample(_proposal(), between) == []


def test_row_limit_counts_only_non_blank_rows(tmp_path: Path) -> None:
    text = HEADER + "\n" + "\n\n".join([ROW] * 50) + "\n\n"
    assert errors_only(check_sample(_proposal(), _sample(tmp_path, text))) == []


def test_non_finite_numbers_are_errors(tmp_path: Path) -> None:
    for bad in ("nan", "inf", "-inf"):
        f = _sample(tmp_path, f"{HEADER}\nS001\t08:15\tyes\t1.2\t{bad}\t310\n", name=f"{bad}.tsv")
        assert "not a finite number" in _msgs(check_sample(_proposal(), f)), bad


def test_header_names_are_quoted_with_repr(tmp_path: Path) -> None:
    f = _sample(tmp_path, HEADER + " \n" + ROW + "\n")
    msg = _msgs(check_sample(_proposal(), f))
    assert "'cortisol '" in msg
