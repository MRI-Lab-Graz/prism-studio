"""skip_existing: re-importing a LimeSurvey export only brings in what is new."""

from src.converters.survey import convert_survey_lsa_to_prism_dataset
from tests.lsa_fixtures import REAL_PATTERN, make_library, make_lsa

NEW = ["7", "a", "2026-10-01 10:00:00", "2026-10-01 10:20:00", "5", "1", "2", "3"]


def _convert(tmp_path, rows, **kwargs):
    return convert_survey_lsa_to_prism_dataset(
        input_path=make_lsa(tmp_path, rows),
        library_dir=(tmp_path / "lib") if (tmp_path / "lib").exists() else make_library(tmp_path),
        output_root=tmp_path / "out",
        id_column="token",
        duplicate_handling="sessions",
        **kwargs,
    )


def _survey_files(tmp_path, sub):
    return sorted(p.relative_to(tmp_path / "out") .as_posix() for p in (tmp_path / "out" / sub).glob("ses-*/survey/*_survey.tsv") if "_tool-" not in p.name)


def _mark(tmp_path):
    """Overwrite every survey file with a sentinel so rewrites are detectable."""
    marked = []
    for p in (tmp_path / "out").glob("sub-*/ses-*/survey/*_survey.tsv"):
        if "_tool-" not in p.name:
            p.write_text("SENTINEL")
            marked.append(p)
    return marked


def test_second_import_with_new_response_only_adds_the_new_session(tmp_path):
    _convert(tmp_path, REAL_PATTERN)
    marked = _mark(tmp_path)

    result = _convert(tmp_path, REAL_PATTERN + [NEW], skip_existing=True)

    assert all(p.read_text() == "SENTINEL" for p in marked)  # nothing rewritten
    assert len(_survey_files(tmp_path, "sub-a")) == 3  # ses-3 is new
    assert result.existing_summary["new"] == 1
    assert result.existing_summary["already_imported"] == 3


def test_missing_survey_file_is_restored_while_others_stay(tmp_path):
    _convert(tmp_path, REAL_PATTERN)
    marked = _mark(tmp_path)
    gone = marked[0]
    gone.unlink()

    _convert(tmp_path, REAL_PATTERN, skip_existing=True)

    assert gone.exists() and gone.read_text() != "SENTINEL"
    assert all(p.read_text() == "SENTINEL" for p in marked[1:])


def test_a_different_response_in_a_taken_slot_is_a_conflict_not_an_overwrite(tmp_path):
    _convert(tmp_path, REAL_PATTERN)
    marked = _mark(tmp_path)
    changed = [list(r) for r in REAL_PATTERN]
    changed[1][2] = "2026-03-01 08:00:00"  # sub-a's first completed response now has another startdate

    result = _convert(tmp_path, changed, skip_existing=True)

    assert all(p.read_text() == "SENTINEL" for p in marked)
    assert result.existing_summary["conflict"] >= 1


def test_default_still_overwrites(tmp_path):
    _convert(tmp_path, REAL_PATTERN)
    marked = _mark(tmp_path)

    _convert(tmp_path, REAL_PATTERN, force=True)

    assert all(p.read_text() != "SENTINEL" for p in marked)
