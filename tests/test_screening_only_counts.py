"""Screening-only participants are not in the sample; the documents say how many were screened only."""

import importlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

from src.eligibility import screening_only_ids  # noqa: E402

helpers = importlib.import_module("src.web.blueprints.projects_metadata_helpers")
generate_full_methods = importlib.import_module("src.reporting").generate_full_methods
ReadmeGenerator = importlib.import_module("src.readme_generator").ReadmeGenerator

TSV = (
    "participant_id\tage\tsex\tgroup\n"
    "sub-01\t20\tM\tcontrol\n"
    "sub-02\t30\tF\tn/a\n"
    "sub-03\t90\tM\tScreening-Only\n"
    "sub-04\t95\tF\tscreening-only\n"
)


def _project(tmp_path, tsv=TSV):
    (tmp_path / "participants.tsv").write_text(tsv, encoding="utf-8")
    return tmp_path


def test_ids_come_from_the_group_column(tmp_path):
    assert screening_only_ids(_project(tmp_path) / "participants.tsv") == {"sub-03", "sub-04"}


def test_no_group_column_or_no_file_means_nobody(tmp_path):
    assert screening_only_ids(tmp_path / "participants.tsv") == set()
    assert screening_only_ids(_project(tmp_path, "participant_id\tage\nsub-01\t20\n") / "participants.tsv") == set()


def test_sample_statistics_leave_the_screened_out_and_count_them(tmp_path):
    stats = helpers._compute_participant_stats(_project(tmp_path))
    assert stats["n"] == 2 and stats["n_screened"] == 2
    assert stats["age_max"] == 30  # the 90 and 95 year olds are not in the sample


def test_the_methods_text_names_the_screened_only_count(tmp_path):
    stats = helpers._compute_participant_stats(_project(tmp_path))
    text = generate_full_methods({"Eligibility": {}}, None, {}, participant_stats=stats)[0]
    assert "*N* = 2 participants" in text
    assert "2 further participants were screened only" in text


def test_the_methods_text_is_unchanged_without_screening(tmp_path):
    stats = helpers._compute_participant_stats(_project(tmp_path, TSV.replace("creening-only", "ontrol").replace("Screening-Only", "control")))
    text = generate_full_methods({"Eligibility": {}}, None, {}, participant_stats=stats)[0]
    assert "screened only" not in text


def test_readme_counts_the_enrolled_and_lists_the_screened_only(tmp_path):
    content = ReadmeGenerator(_project(tmp_path)).generate()
    assert "Total participants: 2" in content
    assert "Screened only: 2" in content
