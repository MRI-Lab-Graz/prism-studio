"""Regression guard for the write-path (filename construction) migration
onto src/entity_rules.py.

Biometrics filename construction already has exact-filename coverage in
tests/test_biometrics_cli.py (e.g. "sub-01_ses-1_task-grip_biometrics.tsv"),
so it isn't duplicated here.
"""

from __future__ import annotations

import pytest

from src.entity_rules import load_entity_rules


def test_primary_suffix_for_known_modalities():
    rules = load_entity_rules()
    assert rules.primary_suffix("survey") == "survey"
    assert rules.primary_suffix("biometrics") == "biometrics"
    assert rules.primary_suffix("physio") == "physio"


def test_primary_suffix_prefers_first_of_multiple_suffixes():
    rules = load_entity_rules()
    # eyetracking has three accepted suffixes for validation; writers should
    # get the primary one.
    assert rules.primary_suffix("eyetracking") == "eyetrack"


def test_primary_suffix_raises_for_unknown_modality():
    rules = load_entity_rules()
    with pytest.raises(KeyError):
        rules.primary_suffix("does-not-exist")


def test_primary_suffix_raises_for_suffixless_modality():
    rules = load_entity_rules()
    with pytest.raises(KeyError):
        rules.primary_suffix("anat")


class TestBuildBidsSurveyFilename:
    def _build(self, **kwargs):
        from app.src.converters.survey_core import _build_bids_survey_filename

        return _build_bids_survey_filename(**kwargs)

    def test_minimal(self):
        assert (
            self._build(sub_id="sub-01", ses_id="ses-1", task="panas")
            == "sub-01_ses-1_task-panas_survey.tsv"
        )

    def test_with_acq_and_run(self):
        assert (
            self._build(
                sub_id="sub-01", ses_id="ses-1", task="panas", acq="a", run=2
            )
            == "sub-01_ses-1_task-panas_acq-a_run-2_survey.tsv"
        )

    def test_json_extension(self):
        assert (
            self._build(
                sub_id="sub-01", ses_id="ses-1", task="panas", extension="json"
            )
            == "sub-01_ses-1_task-panas_survey.json"
        )


class TestNormalizePhysioSuffix:
    def _normalize(self, raw):
        from app.src.cli.commands.convert import _normalize_physio_suffix

        return _normalize_physio_suffix(raw)

    def test_none_defaults_to_ecg(self):
        assert self._normalize(None) == "recording-ecg_physio"

    def test_empty_string_defaults_to_ecg(self):
        assert self._normalize("") == "recording-ecg_physio"

    def test_bare_physio_defaults_to_ecg(self):
        assert self._normalize("physio") == "recording-ecg_physio"

    def test_recording_prefix_without_physio_suffix(self):
        assert self._normalize("recording-eda") == "recording-eda_physio"

    def test_recording_prefix_with_physio_suffix_unchanged(self):
        assert self._normalize("recording-eda_physio") == "recording-eda_physio"

    def test_bare_label_gets_recording_prefix(self):
        assert self._normalize("eda") == "recording-eda_physio"

    def test_bare_label_with_physio_suffix_returned_unchanged(self):
        # Pre-existing quirk, unchanged by this migration: anything already
        # ending in "_physio" short-circuits before the "add recording-
        # prefix" branch, even without a "recording-" prefix of its own.
        assert self._normalize("eda_physio") == "eda_physio"
