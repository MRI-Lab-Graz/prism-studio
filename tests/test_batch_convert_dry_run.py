"""A dry run writes nothing into the output folder and reports new vs. existing files truthfully."""

from pathlib import Path

from src.batch_convert import batch_convert_folder


def _source(tmp_path: Path) -> Path:
    src = tmp_path / "src"
    src.mkdir()
    (src / "sub-001_ses-1_task-rest.edf").write_bytes(b"0" * 10)
    return src


def _files(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def test_dry_run_leaves_the_output_folder_untouched_and_reports_new_files(tmp_path):
    out = tmp_path / "out"
    out.mkdir()

    result = batch_convert_folder(_source(tmp_path), out, dry_run=True)

    assert _files(out) == []
    assert (result.new_files, result.existing_files) == (2, 0)
    assert all(not f.exists() for c in result.converted for f in c.output_files)
    assert all(out in f.parents for c in result.converted for f in c.output_files)  # paths point into the real folder


def test_dry_run_counts_files_that_are_really_there_as_existing(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    src = _source(tmp_path)
    batch_convert_folder(src, out)  # real run
    before = {name: (out / name).read_bytes() for name in _files(out)}

    result = batch_convert_folder(src, out, dry_run=True)

    assert (result.new_files, result.existing_files) == (0, 2)
    assert {name: (out / name).read_bytes() for name in _files(out)} == before


def test_entity_keys_in_file_names_are_lowercased_but_labels_keep_their_case():
    from src.batch_convert import parse_bids_filename

    parsed = parse_bids_filename("SUB-AbC_SES-Pre_TASK-Rest.edf")
    assert (parsed["sub"], parsed["ses"], parsed["task"]) == ("sub-AbC", "ses-Pre", "task-Rest")
