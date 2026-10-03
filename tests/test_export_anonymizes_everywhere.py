"""An "anonymised" export must not leave real participant IDs anywhere.

Before: only the participant_id/subject_id/sub columns of .tsv files were
rewritten; scans.tsv `filename` cells and every non-TSV derivative (.csv, .txt,
.R, ...) kept the real ID next to the pseudonym, so the two were linkable
inside the shared ZIP.
"""

import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from src.web.export_project import export_project

REAL = "sub-001"


def _project(tmp_path: Path) -> Path:
    p = tmp_path / "study"
    (p / REAL).mkdir(parents=True)
    (p / "derivatives" / "survey").mkdir(parents=True)
    (p / "participants.tsv").write_text("participant_id\tage\nsub-001\t30\n", encoding="utf-8")
    (p / REAL / f"{REAL}_scans.tsv").write_text(
        f"filename\tacq_time\nsurvey/{REAL}_task-x_survey.tsv\t2020-01-01\n", encoding="utf-8"
    )
    (p / REAL / f"{REAL}_task-x_survey.tsv").write_text("participant_id\tv\nsub-001\t1\n", encoding="utf-8")
    d = p / "derivatives" / "survey"
    (d / "scores.csv").write_text("participant_id,score\nsub-001,5\n", encoding="utf-8")
    (d / "notes.txt").write_text("sub-001 did the task; sub-0010 untouched\n", encoding="utf-8")
    (d / "helper.R").write_text("df <- df[df$id == 'sub-001', ]\n", encoding="utf-8")
    (d / "scores.xlsx").write_bytes(b"PK\x03\x04 binary sub-001")
    (d / "scores.sav").write_bytes(b"$FL2 binary sub-001")
    return p


def _export(project: Path, tmp_path: Path, **kw):
    out = tmp_path / "out.zip"
    stats = export_project(
        project_path=project,
        output_zip=out,
        include_derivatives=True,
        include_code=False,
        include_analysis=False,
        **kw,
    )
    return stats, out


def test_anonymized_export_contains_no_real_id_in_names_or_contents(tmp_path):
    stats, out = _export(_project(tmp_path), tmp_path, anonymize=True, deterministic=True)
    with zipfile.ZipFile(out) as z:
        for info in z.infolist():
            assert REAL not in info.filename, info.filename
            # "sub-0010" is a different participant that merely starts with REAL
            assert REAL.encode() not in z.read(info).replace(b"sub-0010", b""), info.filename


def test_id_replacement_respects_token_boundaries(tmp_path):
    _stats, out = _export(_project(tmp_path), tmp_path, anonymize=True, deterministic=True)
    with zipfile.ZipFile(out) as z:
        notes = z.read("derivatives/survey/notes.txt").decode()
    assert "sub-0010 untouched" in notes


def test_binary_tabular_files_are_left_out_and_reported_when_anonymizing(tmp_path):
    stats, out = _export(_project(tmp_path), tmp_path, anonymize=True, deterministic=True)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
    assert not any(n.endswith((".xlsx", ".sav")) for n in names)
    skipped = stats["unanonymizable_files_skipped"]
    assert sorted(Path(s).name for s in skipped) == ["scores.sav", "scores.xlsx"]


def test_without_anonymize_everything_is_copied_unchanged(tmp_path):
    stats, out = _export(_project(tmp_path), tmp_path, anonymize=False)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "derivatives/survey/scores.xlsx" in names
        assert REAL.encode() in z.read("derivatives/survey/scores.csv")
