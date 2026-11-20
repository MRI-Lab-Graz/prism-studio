"""PRISM task labels may contain hyphens (task-gold-dsi, task-pss-10): the dataset stats list them all."""

from src.runner import _extract_task_from_filename
from src.stats import DatasetStats


def test_task_with_hyphen_is_read_whole():
    assert _extract_task_from_filename("sub-1_ses-2_task-gold-dsi_survey.tsv") == "gold-dsi"
    assert _extract_task_from_filename("sub-1_ses-2_task-pss-10_survey.tsv") == "pss-10"
    assert _extract_task_from_filename("sub-1_ses-2_task-ads_survey.tsv") == "ads"
    assert _extract_task_from_filename("sub-1_ses-2_task-ads_acq-short_survey.tsv") == "ads"
    assert _extract_task_from_filename("sub-1_ses-2_task-maia-2") == "maia-2"
    assert _extract_task_from_filename("sub-1_T1w.nii.gz") is None


def test_every_survey_task_reaches_the_stats():
    stats = DatasetStats()
    for name in ("ads", "gold-dsi", "maia-2", "pss-10"):
        fname = f"sub-1_ses-2_task-{name}_survey.tsv"
        stats.add_file("sub-1", "ses-2", "survey", _extract_task_from_filename(fname), fname)
    assert stats.surveys == {"ads", "gold-dsi", "maia-2", "pss-10"}


def test_other_task_readers_keep_the_hyphen(tmp_path):
    from src.conversion_to_project import extract_tasks_from_output

    (tmp_path / "sub-1_ses-2_task-gold-dsi_survey.tsv").write_text("x")
    (tmp_path / "sub-1_ses-2_task-ads_survey.tsv").write_text("x")
    assert extract_tasks_from_output(tmp_path) == ["ads", "gold-dsi"]


def test_license_hint_names_a_hyphenated_survey():
    from src.issues import get_fix_hint

    hint = get_fix_hint("PRISM301", "task-gold-dsi_survey.json: 'LicenseID' is a required property")
    assert "'gold-dsi'" in hint
