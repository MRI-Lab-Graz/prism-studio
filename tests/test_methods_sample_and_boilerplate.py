"""Methods draft: sample limited to subjects with data, no license boilerplate, no fake 'n.a.' citation."""

import importlib
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "app"))

helpers = importlib.import_module("src.web.blueprints.projects_metadata_helpers")
generate_full_methods = importlib.import_module("src.reporting").generate_full_methods

PARTICIPANTS = "participant_id\tage\tsex\nsub-01\t20\tM\nsub-02\t30\tF\nsub-03\t40\tM\n"


def _project(tmp_path, folders):
    (tmp_path / "participants.tsv").write_text(PARTICIPANTS, encoding="utf-8")
    for name in folders:
        (tmp_path / "rawdata" / name).mkdir(parents=True)
    return tmp_path


def test_sample_counts_only_subjects_with_a_data_folder(tmp_path):
    stats = helpers._compute_participant_stats(_project(tmp_path, ["sub-01", "sub-02"]))
    assert stats["n"] == 2
    assert stats["age_mean"] == 25.0


def test_sample_is_everyone_listed_while_no_data_is_imported(tmp_path):
    assert helpers._compute_participant_stats(_project(tmp_path, []))["n"] == 3


def _methods(study, **kw):
    return generate_full_methods(
        {"TaskDefinitions": {"ads": {"modality": "survey"}}},
        None,
        {"ads": {"Study": {"TaskName": {"en": "Ads"}, **study}}},
        continuous=True,
        **kw,
    )[0]


def test_converter_license_boilerplate_is_dropped():
    boiler = "Proprietary / Copyright protected. Please ensure you have a valid license for this instrument."
    assert "License" not in _methods({"License": boiler})


def test_real_license_is_kept():
    assert "License: CC-BY-4.0." in _methods({"License": "CC-BY-4.0"})


def test_na_citation_counts_as_missing():
    md = _methods({"Citation": "n.a."})
    assert "(n.a.)" not in md
    assert "[please add: reference for" in md
