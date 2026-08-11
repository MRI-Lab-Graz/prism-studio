from pathlib import Path

from src.converters.survey_core import _load_survey_aliases_and_templates


class _FakeParticipantsConverter:
    def __init__(self, template=None, compare_result=(True, set(), set(), [])):
        self._template = template
        self._compare_result = compare_result

    def load_template(self, library_dir):
        return self._template

    def normalize_template(self, raw_template):
        return raw_template

    def compare_with_global(self, raw_template):
        return self._compare_result


def _fake_load_and_preprocess_templates(library_dir, canonical_aliases, compare_with_global=True):
    return ({"panas": {"json": {}}}, {"panas_1": "panas"}, {}, {})


def test_returns_templates_from_injected_loader(tmp_path):
    result = _load_survey_aliases_and_templates(
        participants_converter=_FakeParticipantsConverter(),
        library_dir=tmp_path,
        alias_file=None,
        load_and_preprocess_templates_fn=_fake_load_and_preprocess_templates,
    )

    assert result.templates == {"panas": {"json": {}}}
    assert result.item_to_task == {"panas_1": "panas"}
    assert result.alias_map is None


def test_participant_template_columns_are_lowercased(tmp_path):
    result = _load_survey_aliases_and_templates(
        participants_converter=_FakeParticipantsConverter(
            template={"Age": {}, "Sex": {}}
        ),
        library_dir=tmp_path,
        alias_file=None,
        load_and_preprocess_templates_fn=_fake_load_and_preprocess_templates,
    )

    assert result.participant_columns_lower == {"age", "sex"}


def test_participant_template_compare_warnings_are_collected(tmp_path):
    result = _load_survey_aliases_and_templates(
        participants_converter=_FakeParticipantsConverter(
            template={"Age": {}},
            compare_result=(False, set(), set(), ["Age column differs from global template"]),
        ),
        library_dir=tmp_path,
        alias_file=None,
        load_and_preprocess_templates_fn=_fake_load_and_preprocess_templates,
    )

    assert "Age column differs from global template" in result.warnings


def test_alias_file_builds_alias_map(tmp_path):
    alias_file = tmp_path / "aliases.csv"
    # _read_alias_rows splits on tab (or whitespace) not comma: canonical id
    # first, followed by whitespace/tab-separated aliases.
    alias_file.write_text("item_1\tq1\n")

    result = _load_survey_aliases_and_templates(
        participants_converter=_FakeParticipantsConverter(),
        library_dir=tmp_path,
        alias_file=alias_file,
        load_and_preprocess_templates_fn=_fake_load_and_preprocess_templates,
    )

    assert result.alias_map is not None


def test_duplicate_item_ids_raise_value_error(tmp_path):
    def _loader_with_duplicates(library_dir, canonical_aliases, compare_with_global=True):
        return ({}, {}, {"item_1": {"panas", "phq9"}}, {})

    import pytest

    with pytest.raises(ValueError, match="Duplicate item IDs"):
        _load_survey_aliases_and_templates(
            participants_converter=_FakeParticipantsConverter(),
            library_dir=tmp_path,
            alias_file=None,
            load_and_preprocess_templates_fn=_loader_with_duplicates,
        )
